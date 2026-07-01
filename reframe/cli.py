#!/usr/bin/env python3
"""Command-line entry for the resume re-frame engine.

    python -m reframe.cli --resume resume.txt --mode full_reframe
    python -m reframe.cli --resume resume.txt --proposals edits.json   # offline

``--proposals`` injects a canned ReframeProposal (the same shape the model
returns) so the full guard -> diff pipeline runs with no API key - used by the
worked example and for demos. Without it, the live Claude proposer is called and
credentials are resolved from the environment (ANTHROPIC_API_KEY or an
``ant auth login`` profile).
"""
import argparse
import json
import sys

from reframe import diff, ingest
from reframe.engine import MODES, reframe
from reframe.schema import ReframeProposal


def _read(path):
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as f:
        return f.read()


def _canned_proposer(path):
    proposal = ReframeProposal.model_validate(json.loads(_read(path)))
    return lambda resume, mode, **_: proposal


def main(argv=None):
    ap = argparse.ArgumentParser(description="Ground-guarded resume re-frame.")
    ap.add_argument("--resume", required=True, help="Resume file (.txt/.pdf/.docx) or '-' for stdin.")
    ap.add_argument("--mode", default="full_reframe", choices=MODES)
    ap.add_argument("--target-title", default=None, help="Candidate's target title (hint).")
    ap.add_argument("--proposals", default=None, help="Canned proposals JSON (offline).")
    ap.add_argument("--model", default=None, help="Override the Claude model id.")
    ap.add_argument("--json", action="store_true", help="Emit the result as JSON.")
    args = ap.parse_args(argv)

    try:
        resume = ingest.load_resume(args.resume)  # cleans text; handles pdf/docx/stdin
    except ingest.IngestError as exc:
        print(f"reframe failed: {exc}", file=sys.stderr)
        return 1
    proposer = _canned_proposer(args.proposals) if args.proposals else None

    try:
        result = reframe(
            resume,
            mode=args.mode,
            proposer=proposer,
            target_title=args.target_title,
            model=args.model,
        )
    except Exception as exc:  # surface a clean message, no traceback of PII
        print(f"reframe failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(diff.render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
