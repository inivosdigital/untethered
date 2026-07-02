#!/usr/bin/env python3
"""Phase-1.3 Income Staircase - a next-rung recommender for RCM workers.

Given a worker's current role, suggest the adjacent higher-tier RCM roles worth
climbing toward, the concrete gap to close, and - honestly - a pay signal only
when the crowdsourced data can support one.

Everything here is grounded in what the product already trusts, and nothing is
overclaimed:

  * Roles and the gap-to-close terms come from the canonical taxonomy
    (scoring/rules.json title_keywords, via scoring_rules) and the RCM claim
    lexicon (reframe/lexicon.json). Every skill term is validated against that
    combined vocabulary at import, so a fabricated cert/skill cannot ship.
  * Pay per rung reuses the pay-truth engine: pay.crowd_aggregate over the
    density gates (>=5 contributors, >=3 months, no single source >25%). If the
    data is too thin, the rung ABSTAINS on pay - it never asserts a number or a
    lift it cannot support, and it never falls back to OEWS for a hard claim
    (P0-D found OEWS untrustworthy for the floor).
  * Offshore-resistance per rung is a labeled heuristic derived from the same
    onshore/offshore signal lists the harvester uses.

THE RUNG ORDERING BELOW IS AN UNVALIDATED HYPOTHESIS.
It is a defensible starting point for which RCM roles pay more and sit "higher",
not a proven career map. It exists to be tested against real callback and pay
data, and should be revised as that evidence arrives.
"""
import argparse
import json
import os

import pay
import store
from scoring_rules import OFFSHORE_SIGNALS, ONSHORE_SIGNALS, TITLE_KEYWORDS

_LEXICON_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "reframe", "lexicon.json")
with open(_LEXICON_PATH) as _f:
    _LEX = json.load(_f)

# Combined vocabulary a gap-to-close / skill term MUST belong to (no fabrication).
_VOCAB = set(TITLE_KEYWORDS) | {s.lower() for s in ONSHORE_SIGNALS} | {
    s.lower() for s in OFFSHORE_SIGNALS
} | {
    t.lower()
    for key in ("certs", "systems", "clearinghouses", "insurers", "codesets")
    for t in _LEX.get(key, [])
}

# --------------------------------------------------------------------------- #
# The hypothesized ladder (UNVALIDATED - see module docstring). Each rung's
# keywords are taxonomy title_keywords; skills are validated against _VOCAB.
# --------------------------------------------------------------------------- #
RUNGS = [
    {"canonical": "patient_access", "role": "Patient Access / Registration", "tier": 1,
     "keywords": ["patient access", "insurance verification", "eligibility"],
     "skills": ["insurance verification", "eligibility", "prior authorization"]},
    {"canonical": "billing_charge", "role": "Medical Billing / Charge Capture", "tier": 1,
     "keywords": ["medical billing", "charge capture"],
     "skills": ["medical billing", "charge capture", "claims"]},
    {"canonical": "claims_ar", "role": "Claims / Accounts Receivable", "tier": 2,
     "keywords": ["claims", "accounts receivable", "ar analyst", "collections", "patient financial"],
     "skills": ["accounts receivable", "claims", "collections"]},
    {"canonical": "coding", "role": "Medical Coding", "tier": 2,
     "keywords": ["medical coding"],
     "skills": ["medical coding", "CPC", "CPT", "ICD-10", "HCPCS"]},
    {"canonical": "denials_appeals", "role": "Denials & Appeals", "tier": 3,
     "keywords": ["denial", "denials", "appeal", "appeals"],
     "skills": ["denials", "appeals", "payer policy", "root cause"]},
    {"canonical": "prior_auth_reimbursement", "role": "Prior Authorization / Reimbursement", "tier": 3,
     "keywords": ["prior authorization", "reimbursement"],
     "skills": ["prior authorization", "reimbursement", "payer policy"]},
    {"canonical": "credentialing_enrollment", "role": "Credentialing / Payer Enrollment", "tier": 4,
     "keywords": ["credentialing", "payer enrollment"],
     "skills": ["credentialing", "payer enrollment"]},
    {"canonical": "revenue_integrity_cycle", "role": "Revenue Integrity / Revenue Cycle", "tier": 4,
     "keywords": ["revenue integrity", "revenue cycle"],
     "skills": ["revenue integrity", "revenue cycle", "charge capture"]},
]

HYPOTHESIS_NOTE = ("Rung ordering is an UNVALIDATED hypothesis - a starting point to test "
                   "with real callback and pay data, not a proven career map.")


def _validate():
    """Fail fast at import if the ladder drifts from the trusted vocabulary."""
    kw_set = set(TITLE_KEYWORDS)
    for r in RUNGS:
        for kw in r["keywords"]:
            if kw not in kw_set:
                raise ValueError(f"rung {r['canonical']} keyword {kw!r} not in title_keywords")
        for sk in r["skills"]:
            if sk.lower() not in _VOCAB:
                raise ValueError(f"rung {r['canonical']} skill {sk!r} not in the trusted vocabulary")


def _resistant(rung):
    """Labeled heuristic: offshore-resistant if a rung's terms hit an onshore
    signal and no offshore signal (reuses the harvester's signal lists)."""
    blob = " ".join(rung["keywords"] + rung["skills"]).lower()
    onshore = any(sig in blob for sig in ONSHORE_SIGNALS)
    offshore = any(sig in blob for sig in OFFSHORE_SIGNALS)
    return onshore and not offshore


_validate()
for _r in RUNGS:
    _r["resistant"] = _resistant(_r)


# --------------------------------------------------------------------------- #
# Core
# --------------------------------------------------------------------------- #
def _norm(s):
    return " ".join((s or "").lower().split())


def map_title(title):
    """Map an arbitrary title onto the nearest ladder rung by its longest keyword
    match (ties broken toward the lower tier). Returns the rung or None."""
    t = _norm(title)
    if not t:
        return None
    best, best_len = None, -1
    for r in RUNGS:
        for kw in r["keywords"]:
            if kw in t and (len(kw) > best_len or (len(kw) == best_len and best and r["tier"] < best["tier"])):
                best, best_len = r, len(kw)
    return best


def next_rungs(rung, n=3):
    """The next reachable rungs: strictly higher tiers, ordered by tier then role."""
    higher = [r for r in RUNGS if r["tier"] > rung["tier"]]
    higher.sort(key=lambda r: (r["tier"], r["role"]))
    return higher[:n]


def gap_to_close(current, target):
    """Terms the target rung needs that the current rung does not already have."""
    have = set(s.lower() for s in current["skills"])
    return [s for s in target["skills"] if s.lower() not in have]


def pay_signal(conn, canonical, geo="US", remote_mode="remote"):
    """Density-gated pay for a rung, or an explicit abstain. Never asserts a
    number the crowdsourced data cannot support (P0-D: no OEWS hard claim)."""
    if conn is None:
        return {"status": "abstain", "note": "pay unknown - needs crowdsourced data (no db)"}
    reports = store.pay_reports_for(conn, canonical, geo, remote_mode)
    est = pay.crowd_aggregate(reports)
    if est is None:
        return {"status": "abstain", "n": len(reports),
                "note": "pay unknown - not enough crowdsourced reports to be honest yet"}
    return {"status": "data", "floorHourly": est["floorHourly"], "ceilingHourly": est["ceilingHourly"],
            "clearsFloor": est["clearsFloor"], "confidence": est["confidence"],
            "n": len(reports), "note": est["note"]}


def build_staircase(title, conn=None, geo="US", remote_mode="remote", n=3):
    """Assemble the staircase for a current title: the mapped current rung plus
    the next reachable rungs, each with pay (or abstain), the gap to close, and a
    labeled offshore-resistance heuristic."""
    current = map_title(title)
    out = {"input_title": title, "matched": bool(current),
           "hypothesis": HYPOTHESIS_NOTE,
           "current": _public(current) if current else None, "next": []}
    if not current:
        return out
    for tgt in next_rungs(current, n):
        out["next"].append({
            "role": tgt["role"], "tier": tgt["tier"], "canonical": tgt["canonical"],
            "offshore_resistant": tgt["resistant"],
            "why_reachable": (f"Tier {current['tier']} -> {tgt['tier']} step; "
                              f"{'offshore-resistant judgment work' if tgt['resistant'] else 'operational role (may be offshore-prone)'}."),
            "gap_to_close": gap_to_close(current, tgt),
            "pay": pay_signal(conn, tgt["canonical"], geo, remote_mode),
        })
    return out


def _public(rung):
    return {"role": rung["role"], "tier": rung["tier"], "canonical": rung["canonical"],
            "offshore_resistant": rung["resistant"]}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _fmt_pay(p):
    if p["status"] != "data":
        return p["note"]
    rng = f"${round(p['floorHourly'])}-${round(p['ceilingHourly'])}/hr" if p.get("ceilingHourly") else f"${round(p['floorHourly'])}/hr"
    return f"{rng} ({p['clearsFloor']}, {p['confidence']}, n={p['n']})"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Income staircase: next reachable RCM rungs (hypothesis).")
    ap.add_argument("--title", required=True, help="Your current role/title.")
    ap.add_argument("--geo", default="US")
    ap.add_argument("--remote-mode", default="remote")
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--no-pay", action="store_true", help="Skip the pay lookup (no DB).")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    conn = None if args.no_pay else store.connect(store.default_db_path())
    result = build_staircase(args.title, conn=conn, geo=args.geo,
                             remote_mode=args.remote_mode, n=args.n)

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    print(f"Income staircase for: {args.title}")
    print(f"  ({HYPOTHESIS_NOTE})\n")
    if not result["matched"]:
        print("  Could not map that title to an RCM rung. Try an RCM role (billing, AR, denials, coding, credentialing).")
        return 0
    c = result["current"]
    print(f"  Current rung: {c['role']} (tier {c['tier']})\n")
    if not result["next"]:
        print("  You are already at the top of the hypothesized ladder.")
        return 0
    print("  Next reachable rungs:")
    for r in result["next"]:
        print(f"\n  -> {r['role']} (tier {r['tier']})")
        print(f"     {r['why_reachable']}")
        print(f"     gap to close: {', '.join(r['gap_to_close']) or '(none identified)'}")
        print(f"     pay: {_fmt_pay(r['pay'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
