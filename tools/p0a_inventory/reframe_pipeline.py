#!/usr/bin/env python3
"""Close the loop between the reframe wedge and the P0-E callback A/B.

P0-E (p0e_callback_ab.py) assigns a balanced within-user arm but does not touch
resumes - it prints instructions. This module makes the assignment PRODUCE the
artifact: the assigned arm drives ``reframe(resume, mode=arm)``, and the
application is recorded, so the callback measured later is attributable to the
exact reframe the user submitted. That is the only honest basis for the lift
claim the whole product rests on.

PII: the applications table stores only user/employer/role/arm (never resume
text); the reframed resume is returned in memory for the user to submit and is
never persisted or logged - the same score-don't-store discipline as the engine.
"""
import argparse
import os
import random
import sys
from datetime import datetime

# reframe/ is a top-level package; put the repo root on the path so this p0a tool
# can import it alongside the flat store / p0e modules in this directory.
_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import store  # noqa: E402  (F3 SQLite persistence, same directory)
from p0e_callback_ab import ARMS, assign_arm  # noqa: E402
from reframe import diff, ingest  # noqa: E402
from reframe.engine import reframe  # noqa: E402


def apply_and_record(conn, user, employer, role, resume_text, *,
                     seed=None, target_title=None, proposer=None, ts=None):
    """Assign this user's next balanced arm, reframe the resume in that arm's
    mode, record the application, and return ``(app_id, arm, ReframeResult)``.

    ``proposer`` is injectable (offline/testing); when omitted the live Claude
    proposer runs for non-control arms. ``control`` never calls a proposer.
    """
    apps = store.list_applications(conn)
    if seed is not None:
        random.seed(seed)
    arm = assign_arm(apps, user)
    result = reframe(resume_text, mode=arm, proposer=proposer, target_title=target_title)
    app_id = store.add_application(conn, {
        "ts": ts or datetime.now().isoformat(timespec="seconds"),
        "user": user, "employer": employer, "role": role, "arm": arm,
    })
    return app_id, arm, result


def _arm_hint(arm):
    return {
        "control": "submit the resume unchanged (A/B baseline)",
        "title_only": "only the target title/headline was relabeled",
        "full_reframe": "full grounded relabel + reemphasis applied",
    }[arm]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Assign a P0-E arm and produce its reframed resume.")
    ap.add_argument("--user", required=True)
    ap.add_argument("--employer", required=True)
    ap.add_argument("--role", required=True)
    ap.add_argument("--resume", required=True, help="Resume file (.txt/.pdf/.docx) or '-'.")
    ap.add_argument("--proposals", default=None, help="Canned proposals JSON (offline).")
    ap.add_argument("--target-title", default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--out", default=None, help="Write the reframed resume here (default: stdout).")
    args = ap.parse_args(argv)

    try:
        resume = ingest.load_resume(args.resume)
    except ingest.IngestError as exc:
        print(f"reframe pipeline failed: {exc}", file=sys.stderr)
        return 1

    proposer = None
    if args.proposals:
        import json
        from reframe.schema import ReframeProposal
        with open(args.proposals, encoding="utf-8") as f:
            proposal = ReframeProposal.model_validate(json.load(f))
        proposer = lambda r, m, **_: proposal  # noqa: E731

    conn = store.connect(store.default_db_path())
    app_id, arm, result = apply_and_record(
        conn, args.user, args.employer, args.role, resume,
        seed=args.seed, target_title=args.target_title, proposer=proposer)

    print(f"application #{app_id}  user={args.user}  ARM = {arm}")
    print(f"  ({_arm_hint(arm)})\n")
    print(diff.render(result))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(result.applied_resume)
        print(f"\n  -> wrote reframed resume to {args.out}")
    else:
        print("\n----- REFRAMED RESUME (submit this) -----")
        print(result.applied_resume)
    print(f"\n  Record the outcome later: python3 p0e_callback_ab.py record --id {app_id} --callback yes|no")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
