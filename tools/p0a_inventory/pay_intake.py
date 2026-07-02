#!/usr/bin/env python3
"""Crowdsourced pay-report intake - the honest remediation for the P0-D OEWS kill.

OEWS proved untrustworthy for the $30 floor, so the pay-truth engine and the
income staircase both depend on CROWDSOURCED reports instead - but only past the
moat-safe density gates (>=5 distinct contributors, >=3 months span, no single
source > 25%). Below the gates the aggregate abstains rather than assert a thin,
gameable number. This module is the record intake: it validates a report against
scoring/pay_report.schema.json, normalizes it to $/hr, dedups by contributor per
cell (so one person cannot inflate the distinct-contributor gate), stores it via
the F3 store, and reports how close a cell is to lighting up.

Validation is data-driven from the schema (required fields + enums) so it can
never drift from the contract. Stdlib only. contributorId is pseudonymous, not
PII; consent is explicit and revocable (a report can be deleted, aggregates
recompute).
"""
import argparse
import datetime
import json
import os

import pay
import store
from scoring_rules import to_hourly

_SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "scoring", "pay_report.schema.json")
with open(_SCHEMA_PATH) as _f:
    SCHEMA = json.load(_f)

_PROPS = SCHEMA["properties"]
_REQUIRED = SCHEMA["required"]
_REMOTE_MODES = _PROPS["remoteMode"]["enum"]
_SOURCE_TYPES = _PROPS["sourceType"]["enum"]
GATES = SCHEMA["_gates"]


def normalize(rec):
    """Return a copy normalized to the schema: fill currency, and derive `hourly`
    from an `amount` + `interval` intake convenience (removed after conversion)."""
    r = dict(rec)
    r.setdefault("currency", "USD")
    if "hourly" not in r and "amount" in r:
        r["hourly"] = to_hourly(r.get("amount"), r.get("interval", ""))
    r.pop("amount", None)
    r.pop("interval", None)
    return r


def validate(rec):
    """Return a list of error strings for a (normalized) report; empty == valid.
    Enforces the schema's required fields, enums, types, and additionalProperties."""
    errors = []
    for key in rec:
        if key not in _PROPS:
            errors.append(f"unknown field: {key}")
    for key in _REQUIRED:
        if rec.get(key) is None:
            errors.append(f"missing required field: {key}")

    def _isstr(k):
        if k in rec and not isinstance(rec[k], str):
            errors.append(f"{k} must be a string")

    for k in ("canonicalRole", "geo", "currency", "contributorId", "reportedAt", "note", "id"):
        _isstr(k)
    if isinstance(rec.get("hourly"), bool) or not isinstance(rec.get("hourly"), (int, float)):
        errors.append("hourly must be a number")
    elif rec["hourly"] < 1:
        errors.append("hourly must be >= 1 (normalized USD/hr)")
    if rec.get("remoteMode") not in _REMOTE_MODES:
        errors.append(f"remoteMode must be one of {_REMOTE_MODES}")
    if rec.get("sourceType") not in _SOURCE_TYPES:
        errors.append(f"sourceType must be one of {_SOURCE_TYPES}")
    if not isinstance(rec.get("consent"), bool):
        errors.append("consent must be a boolean")
    ra = rec.get("reportedAt")
    if isinstance(ra, str):
        try:
            datetime.date.fromisoformat(ra)
        except ValueError:
            errors.append("reportedAt must be an ISO date (YYYY-MM-DD)")
    return errors


def _already_reported(conn, rec):
    """One report per contributor per (role x geo x mode) - protects the distinct-
    contributor gate from a single person padding a cell."""
    existing = store.pay_reports_for(conn, rec["canonicalRole"], rec["geo"], rec["remoteMode"])
    return any(r.get("contributorId") == rec["contributorId"] for r in existing)


def submit(conn, rec):
    """Normalize, validate, dedup, and store one report.
    Returns {ok: bool, errors: [...]}."""
    r = normalize(rec)
    errors = validate(r)
    if errors:
        return {"ok": False, "errors": errors}
    if not r.get("consent"):
        return {"ok": False, "errors": ["consent is required to aggregate a report"]}
    if _already_reported(conn, r):
        return {"ok": False, "errors": ["duplicate: this contributor already reported this cell"]}
    store.add_pay_report(conn, r)
    return {"ok": True, "errors": []}


def cell_status(conn, canonical_role, geo="US", remote_mode="remote"):
    """How close a (role x geo x mode) cell is to displaying an aggregate: the
    density metrics, which gates are unmet, and the aggregate iff it clears."""
    reports = store.pay_reports_for(conn, canonical_role, geo, remote_mode)
    contributors = {r["contributorId"] for r in reports}
    months = _month_span(reports)
    shares = _source_shares(reports)
    max_share = max(shares.values()) if shares else 0.0
    est = pay.crowd_aggregate(reports)

    needs = []
    if len(contributors) < GATES["min_contributors"]:
        needs.append(f"{GATES['min_contributors'] - len(contributors)} more distinct contributor(s)")
    if months < GATES["min_months_span"]:
        needs.append(f"a wider time span (>= {GATES['min_months_span']} months; have {months:.1f})")
    if max_share > GATES["max_single_source_share"]:
        needs.append(f"more source diversity (a single source is {max_share:.0%} > {GATES['max_single_source_share']:.0%})")

    return {
        "cell": {"canonicalRole": canonical_role, "geo": geo, "remoteMode": remote_mode},
        "n": len(reports), "contributors": len(contributors),
        "months_span": round(months, 1), "source_shares": shares,
        "clears_gates": est is not None, "estimate": est, "needs": needs,
    }


def _month_span(reports):
    ts = []
    for r in reports:
        try:
            ts.append(datetime.date.fromisoformat(str(r["reportedAt"])))
        except (KeyError, ValueError, TypeError):
            pass
    if len(ts) < 2:
        return 0.0
    return (max(ts) - min(ts)).days / 30.44


def _source_shares(reports):
    counts = {}
    for r in reports:
        s = r.get("sourceType", "other")
        counts[s] = counts.get(s, 0) + 1
    n = len(reports)
    return {s: c / n for s, c in counts.items()} if n else {}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv=None):
    ap = argparse.ArgumentParser(description="Crowdsourced pay-report intake.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("submit", help="submit one pay report")
    s.add_argument("--role", required=True, dest="canonicalRole")
    s.add_argument("--geo", default="US")
    s.add_argument("--mode", default="remote", dest="remoteMode", choices=_REMOTE_MODES)
    s.add_argument("--hourly", type=float)
    s.add_argument("--amount", type=float, help="raw amount (with --interval) to normalize to $/hr")
    s.add_argument("--interval", default="", help="e.g. year, hour, month (with --amount)")
    s.add_argument("--source", required=True, dest="sourceType", choices=_SOURCE_TYPES)
    s.add_argument("--contributor", required=True, dest="contributorId")
    s.add_argument("--date", required=True, dest="reportedAt", help="YYYY-MM-DD")
    s.add_argument("--consent", action="store_true", help="explicit consent to aggregate")
    s.add_argument("--note", default=None)

    st = sub.add_parser("status", help="show a cell's density-gate status")
    st.add_argument("--role", required=True)
    st.add_argument("--geo", default="US")
    st.add_argument("--mode", default="remote")

    im = sub.add_parser("import", help="bulk-import a JSON array of reports")
    im.add_argument("--file", required=True)

    args = ap.parse_args(argv)
    conn = store.connect(store.default_db_path())

    if args.cmd == "submit":
        rec = {k: v for k, v in {
            "canonicalRole": args.canonicalRole, "geo": args.geo, "remoteMode": args.remoteMode,
            "hourly": args.hourly, "amount": args.amount, "interval": args.interval,
            "sourceType": args.sourceType, "contributorId": args.contributorId,
            "reportedAt": args.reportedAt, "consent": args.consent, "note": args.note,
        }.items() if v is not None and v != ""}
        res = submit(conn, rec)
        print("stored" if res["ok"] else "rejected: " + "; ".join(res["errors"]))
        return 0 if res["ok"] else 1

    if args.cmd == "import":
        with open(args.file, encoding="utf-8") as f:
            recs = json.load(f)
        ok = sum(1 for r in recs if submit(conn, r)["ok"])
        print(f"imported {ok}/{len(recs)} reports")
        return 0

    if args.cmd == "status":
        rep = cell_status(conn, args.role, args.geo, args.mode)
        c = rep["cell"]
        print(f"cell: {c['canonicalRole']} x {c['geo']} x {c['remoteMode']}")
        print(f"  reports={rep['n']}  contributors={rep['contributors']}  span={rep['months_span']}mo")
        print(f"  source shares: {', '.join(f'{k} {v:.0%}' for k, v in rep['source_shares'].items()) or '-'}")
        if rep["clears_gates"]:
            e = rep["estimate"]
            print(f"  CLEARS GATES -> ${round(e['floorHourly'])}-${round(e['ceilingHourly'])}/hr "
                  f"({e['clearsFloor']}, {e['confidence']})")
        else:
            print(f"  abstains - needs: {'; '.join(rep['needs']) or 'more data'}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
