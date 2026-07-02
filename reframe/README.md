# Resume Re-Frame engine (Phase 1.2 - the wedge)

Reframe a healthcare revenue-cycle resume so the candidate is **found in recruiter Boolean and job-title search**, without inventing anything.
The engine optimizes for being *searchable*, not for maximizing an ATS match percentage.

## The design: creative proposer, deterministic guard

The engine is two layers, kept deliberately separate.

1. **Creative layer** ([`llm.py`](llm.py)) asks Claude to *propose* edits as strict structured JSON.
Two kinds only: `relabel` (change a job-title/skill label to a canonical, searchable target term) and `reemphasis` (surface existing content more prominently).
Nothing it returns is trusted.

2. **Deterministic guard** ([`guardrails.py`](guardrails.py)) re-validates every proposed edit against the source resume and hard-abstains anything it cannot prove:
   - **span** - the edit must be anchored to text that is verbatim in the resume;
   - **numeric** - every number in the new text must already appear in the resume (invented metrics are the top resume-integrity risk);
   - **entity** - no cert, system, clearinghouse, insurer, code set, or named employer that the resume does not support (canonical target-title relabels are allowed);
   - **relabel discipline** - a relabel must surface a keyword from the approved recruiter-search taxonomy.

The guard never rewrites text.
It only accepts or rejects, with a stable reason for every rejection, so the user can see exactly what was dropped and why.
Because the guard, taxonomy, schema, engine, and diff import with no SDK dependency, the trust core is fully unit-tested with no API key and no network.

## Ingestion and field-scoped application

[`ingest.py`](ingest.py) loads a resume from `.txt`/`.pdf`/`.docx`/stdin into one clean canonical string (newlines normalized, BOM/zero-width/non-breaking spaces folded) that every offset and the grounding guard index identically.
PDF/DOCX libraries are imported lazily, so the package and all tests run with no extra dependencies.

[`segment.py`](segment.py) turns that string into a `ResumeDoc`: a byte-exact, gap-free partition into typed segments (headline, summary, experience, bullet, skills, ...), each carrying exact raw character offsets and a `splice_safe` flag.
It is heading-anchored when it finds section headers, falls back to a layout heuristic otherwise, and abstains to a single whole-doc region rather than ever mis-assigning text; the partition invariants are hard-asserted at construction.
With a `ResumeDoc`, [`engine.py`](engine.py) `apply_edits` writes each accepted edit into its field's exact window (splices applied back-to-front so multi-edit offsets stay valid), and falls back to the whole-resume replace for anything that does not resolve to a splice-safe window.
This fixes two latent bugs (a global replace splicing the wrong region when the `before` text recurs, and forward-splice offset drift) while leaving the grounding guard untouched: it still validates every edit against the whole resume, and segmentation only chooses *where* an already-accepted edit lands.

## Modes (aligned to the P0-E callback A/B arms)

- `control` - resume unchanged (the A/B baseline; never calls the model, so it costs nothing).
- `title_only` - only a headline relabel, to isolate the title lever.
- `full_reframe` - headline relabel plus summary/bullet/skills reemphasis.

The mode is passed to the model and re-enforced deterministically in the engine.

## PII / ZDR

A resume is PII.
Zero Data Retention is an **account-level** Anthropic setting, not a request parameter - enable it on the API key/organization so prompts and completions are not retained past serving the response.
A ZDR organization cannot use Claude Fable 5 (it requires 30-day retention and returns 400 under ZDR), which is one reason the default model is `claude-sonnet-5`.
The engine is stateless and never persists resume text; [`llm.py`](llm.py) never logs resume text or model output (telemetry records only counts, model id, and token usage).
Optionally pin inference region with `REFRAME_INFERENCE_GEO=us`.

## Try it offline (no API key)

```bash
python -m reframe.cli \
  --resume reframe/examples/laritza_resume.txt \
  --proposals reframe/examples/laritza_edits.json \
  --mode full_reframe
```

The example proposals include three grounded edits (accepted) and three deliberately ungrounded ones - an invented metric, an invented system, and invented experience - which the guard rejects.

## Live run

```bash
export ANTHROPIC_API_KEY=...        # or `ant auth login`
python -m reframe.cli --resume path/to/resume.txt --mode full_reframe
```

Override the model with `--model` or `REFRAME_MODEL`.

## Backend proposer proxy (for the extension)

The browser extension must never ship an Anthropic key, so its side panel calls a small proxy that holds the ZDR-enabled key and returns raw proposals; the extension's on-device guard then validates every one.

```bash
export ANTHROPIC_API_KEY=...                              # ZDR-enabled
export REFRAME_ALLOWED_ORIGINS=chrome-extension://<id>    # CORS allowlist
python -m reframe.server --host 127.0.0.1 --port 8781
```

`POST /reframe/propose` with `{resume, mode, target_title?}` returns `{edits: [...]}`; `GET /health` returns `{status: "ok"}`.
The proxy never logs or echoes the resume, locks CORS to the allowlist (an unlisted origin is browser-blocked), rejects bodies over 512 KB, and returns a generic error on a proposer failure.
It does no auth of its own - put it behind your own gate (Cloudflare Access, an API key, a private network) before exposing it publicly.
Point the extension at it by setting the `reframe_proxy` key in the extension's storage to the proxy URL.

## Tests

```bash
python -m unittest discover -s reframe -p 'test_*.py'
```
