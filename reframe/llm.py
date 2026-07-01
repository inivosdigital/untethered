#!/usr/bin/env python3
"""Creative layer: ask Claude to PROPOSE grounded re-label / re-emphasis edits.

Nothing here is trusted. The model returns a structured :class:`ReframeProposal`
and every edit is then re-validated by :mod:`reframe.guardrails`. Keeping the
creative step and the validation step in separate modules is the whole design:
the model can be swapped, retried, or mocked without touching the guarantees.

PII / ZDR
---------
A resume is PII. Two things follow:

  * Zero Data Retention is an ACCOUNT-level setting, not a request parameter -
    enable it on the API key/organization via an Anthropic ZDR agreement so
    prompts and completions are not retained past serving the response. This
    module cannot turn it on; it is the operator's responsibility.
  * A ZDR organization cannot use Claude Fable 5 (it requires 30-day retention
    and returns 400 under ZDR). That is one reason the default model is Sonnet 5,
    which is fully usable under ZDR and near-Opus quality on this task.

This module never logs resume text or model output. Telemetry records only
counts, the model id, and token usage - see :func:`_telemetry`. Optionally pin
inference to a region for data residency via ``REFRAME_INFERENCE_GEO``.
"""
import hashlib
import logging
import os

from reframe.schema import ReframeProposal
from reframe.taxonomy import TARGET_TITLES

# Configurable, but the deterministic guard re-validates whatever model is used.
# Sonnet 5 is the default: ZDR-compatible and near-Opus quality here.
MODEL = os.environ.get("REFRAME_MODEL", "claude-sonnet-5")
MAX_TOKENS = 8000
INFERENCE_GEO = os.environ.get("REFRAME_INFERENCE_GEO")  # e.g. "us"; None = default

_LOG = logging.getLogger("reframe.llm")


class ReframeError(RuntimeError):
    """Raised when the model declines or returns no usable structured output."""


def redact(text, keep=12):
    """PII-safe fingerprint for logs: length + a short salt-free hash. Never the
    text itself. (No secrets involved, so a plain digest is sufficient here.)"""
    text = text or ""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:keep]
    return f"<{len(text)} chars sha256:{digest}>"


def _telemetry(mode, model, proposal, usage):
    _LOG.info(
        "reframe.propose mode=%s model=%s edits=%d in_tok=%s out_tok=%s",
        mode,
        model,
        len(proposal.edits),
        getattr(usage, "input_tokens", "?"),
        getattr(usage, "output_tokens", "?"),
    )


_SYSTEM = """\
You reframe healthcare revenue-cycle resumes so the candidate is FOUND in \
recruiter Boolean and job-title search. You optimize for being searchable, not \
for maximizing an ATS match percentage.

You may do exactly two things, and nothing else:
  - relabel:    change a job-title or skill LABEL to a canonical, \
recruiter-searchable term the candidate's real experience supports.
  - reemphasis: rewrite existing content to surface real skills more prominently.

Hard rules (an edit that breaks any of these will be discarded by a downstream \
validator, so do not attempt them):
  - Never invent an employer, a job title the candidate did not hold, a tool, a \
system, a certification, a date, or a metric/number.
  - Every number in your rewritten text must already appear in the resume.
  - Anchor every edit to a verbatim substring of the resume (source_span) and \
quote your evidence in the rationale.
  - Relabels must target the approved recruiter search vocabulary below and list \
the surfaced term(s) in surfaced_keywords.

Approved recruiter-search target titles:
{titles}

Mode:
  - title_only:   propose ONLY a single headline relabel to the strongest \
supported target title. No other edits.
  - full_reframe: propose the headline relabel PLUS reemphasis edits across the \
summary, bullets, and skills to surface supported target terms.
"""

_USER = """\
Mode: {mode}
{target}
Resume:
<resume>
{resume}
</resume>

Propose grounded edits per the rules. Return an empty edit list rather than \
inventing anything unsupported."""


def _system_prompt():
    return _SYSTEM.format(titles="\n".join(f"  - {t}" for t in TARGET_TITLES))


def _user_prompt(resume, mode, target_title):
    target = f"Candidate's target title: {target_title}\n" if target_title else ""
    return _USER.format(mode=mode, target=target, resume=resume)


def propose(resume, mode, target_title=None, model=None, client=None):
    """Call Claude and return a validated-shape :class:`ReframeProposal`.

    Raises :class:`ReframeError` on a safety refusal or empty structured output.
    The returned edits are still UNTRUSTED - the engine runs the guard on them.
    """
    import anthropic  # lazy: the deterministic core imports without the SDK

    model = model or MODEL
    client = client or anthropic.Anthropic()

    kwargs = dict(
        model=model,
        max_tokens=MAX_TOKENS,
        thinking={"type": "adaptive"},
        system=_system_prompt(),
        messages=[{"role": "user", "content": _user_prompt(resume, mode, target_title)}],
        output_format=ReframeProposal,
    )
    if INFERENCE_GEO:
        kwargs["inference_geo"] = INFERENCE_GEO

    response = client.messages.parse(**kwargs)

    if response.stop_reason == "refusal":
        raise ReframeError(f"model declined the request (stop_reason=refusal): {redact(resume)}")
    proposal = response.parsed_output
    if proposal is None:
        raise ReframeError(f"no structured output (stop_reason={response.stop_reason})")

    _telemetry(mode, model, proposal, response.usage)
    return proposal
