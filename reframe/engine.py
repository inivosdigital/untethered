#!/usr/bin/env python3
"""Orchestration: propose -> guard -> mode-gate -> grounded result.

The proposer is injectable so the whole pipeline is testable with no SDK, no
network, and no API key - tests pass a canned :class:`ReframeProposal`; the CLI
passes the live :func:`reframe.llm.propose`. ``control`` never calls a proposer
at all (it is the untouched-resume A/B baseline, so there is nothing to spend).

Modes match the P0-E callback A/B arms exactly (see tools/p0a_inventory):
  * control      - resume unchanged.
  * title_only   - only a headline relabel (isolates the title lever).
  * full_reframe - headline relabel + summary/bullet/skills reemphasis.
"""
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from reframe import taxonomy
from reframe.guardrails import check_edit
from reframe.schema import Edit, ReframeProposal

# Which accepted edits each mode keeps. Enforced deterministically here even
# though the proposer is also told the mode - defense in depth.
MODE_KEEP = {
    "control": lambda e: False,
    "title_only": lambda e: e.field == "headline" and e.change_type == "relabel",
    "full_reframe": lambda e: True,
}
MODES = tuple(MODE_KEEP)


@dataclass
class ReframeResult:
    mode: str
    resume: str
    applied_resume: str
    accepted: List[Edit]
    abstained: List[Tuple[Edit, List[str]]]
    mode_filtered: List[Edit]

    @property
    def new_search_hits(self):
        """Target-title terms present after reframing that were absent before -
        the product's real success metric (found in recruiter Boolean search)."""
        before = {t for t in taxonomy.TARGET_TITLES if t in taxonomy.norm(self.resume)}
        after = {t for t in taxonomy.TARGET_TITLES if t in taxonomy.norm(self.applied_resume)}
        return sorted(after - before)

    def to_dict(self):
        return {
            "mode": self.mode,
            "accepted": [e.model_dump() for e in self.accepted],
            "abstained": [
                {"edit": e.model_dump(), "reasons": r} for e, r in self.abstained
            ],
            "mode_filtered": [e.model_dump() for e in self.mode_filtered],
            "new_search_hits": self.new_search_hits,
            "applied_resume": self.applied_resume,
        }


def apply_edits(resume, edits):
    """Apply accepted edits by replacing the first verbatim occurrence of each
    ``before`` with its ``after``. Grounding guarantees ``before`` exists; if an
    exact match is unavailable (whitespace drift) the edit is skipped rather than
    risk a wrong splice."""
    out = resume
    for e in edits:
        if e.before and e.before in out:
            out = out.replace(e.before, e.after, 1)
    return out


def reframe(
    resume: str,
    mode: str = "full_reframe",
    proposer: Optional[Callable[..., ReframeProposal]] = None,
    **proposer_kwargs,
) -> ReframeResult:
    if mode not in MODE_KEEP:
        raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")

    if mode == "control":
        proposal = ReframeProposal(edits=[])
    else:
        if proposer is None:
            from reframe.llm import propose as proposer  # lazy: avoids SDK import
        proposal = proposer(resume, mode, **proposer_kwargs)

    keep = MODE_KEEP[mode]
    accepted, abstained, mode_filtered = [], [], []
    for e in proposal.edits:
        reasons = check_edit(e, resume)
        if reasons:
            abstained.append((e, reasons))
        elif keep(e):
            accepted.append(e)
        else:
            mode_filtered.append(e)

    return ReframeResult(
        mode=mode,
        resume=resume,
        applied_resume=apply_edits(resume, accepted),
        accepted=accepted,
        abstained=abstained,
        mode_filtered=mode_filtered,
    )
