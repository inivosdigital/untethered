#!/usr/bin/env python3
"""P0-E — Resume-reframe callback A/B (the existential spike).

The reframe->callback lift is the core monetizable claim and is UNPROVEN; every
favorable vendor number is confounded. This is the instrumentation for your OWN
within-user randomized experiment — the only honest basis for the product.

Design (from docs/BUILD_ROADMAP.md):
  * Three arms, randomized & balanced WITHIN each user across comparable RCM apps:
      - control      : the user's real resume/title, unchanged
      - title_only   : ONLY the target title/headline changed (isolate the title lever)
      - full_reframe  : full grounded keyword/title reframe
  * Pool across users into cohorts; chi-square on callback conversion.
  * Because per-user callback signal is sparse (~2-3% interview conv, ~42 apps/interview),
    NO individual will see a personal lift — only aggregate/cohort readouts are honest.

This tool does NOT touch resumes. It (a) assigns the arm for each new application so
you stay balanced and blind-ish, (b) records callback outcomes, (c) runs the readout
(per-arm rates, omnibus + pairwise chi-square with Yates, and an N-needed power note).

Stdlib only.  Usage:
  python3 p0e_callback_ab.py assign  --user U --employer E --role "Denials Analyst"
  python3 p0e_callback_ab.py record  --id 7 --callback yes
  python3 p0e_callback_ab.py report  [--out-dir ./data]
"""
import argparse
import json
import math
import os
import random
from datetime import date, datetime

import store  # F3 SQLite persistence

ARMS = ["control", "title_only", "full_reframe"]


# ---------------------------------------------------------------------------
# Stats — stdlib chi-square (regularized upper incomplete gamma; no scipy).
# ---------------------------------------------------------------------------
def _gammap(a, x):
    """Regularized lower incomplete gamma P(a, x)."""
    if x <= 0:
        return 0.0
    if x < a + 1:  # series expansion
        ap, term, s = a, 1.0 / a, 1.0 / a
        for _ in range(500):
            ap += 1
            term *= x / ap
            s += term
            if abs(term) < abs(s) * 1e-14:
                break
        return s * math.exp(-x + a * math.log(x) - math.lgamma(a))
    # continued fraction for Q = 1 - P
    tiny = 1e-300
    b, c, d = x + 1 - a, 1 / tiny, 1 / (x + 1 - a)
    h = d
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-14:
            break
    q = math.exp(-x + a * math.log(x) - math.lgamma(a)) * h
    return 1 - q


def chi2_sf(x, df):
    """P(chi-square_df > x)."""
    if x <= 0:
        return 1.0
    return 1.0 - _gammap(df / 2.0, x / 2.0)


def chi2_2x2_yates(a, b, c, d):
    """Yates-corrected 2x2 chi-square. a/b = arm1 callbacks/non, c/d = arm2."""
    n = a + b + c + d
    r1, r2, c1, c2 = a + b, c + d, a + c, b + d
    if min(r1, r2, c1, c2) == 0:
        return None, None
    chi = n * max(0.0, abs(a * d - b * c) - n / 2.0) ** 2 / (r1 * r2 * c1 * c2)
    return chi, chi2_sf(chi, 1)


def chi2_rxk(table):
    """Omnibus chi-square for an r x k contingency table (list of rows)."""
    rows = len(table)
    cols = len(table[0])
    n = sum(sum(r) for r in table)
    if n == 0:
        return None, None, None
    rt = [sum(r) for r in table]
    ct = [sum(table[i][j] for i in range(rows)) for j in range(cols)]
    chi = 0.0
    for i in range(rows):
        for j in range(cols):
            e = rt[i] * ct[j] / n
            if e > 0:
                chi += (table[i][j] - e) ** 2 / e
    df = (rows - 1) * (cols - 1)
    return chi, df, chi2_sf(chi, df)


def n_needed_per_arm(p_control, rel_lift, alpha=0.05, power=0.80):
    """Approx per-arm N for two-proportion test (z-approx). rel_lift e.g. 0.5 = +50%."""
    p1 = p_control
    p2 = min(0.999, p_control * (1 + rel_lift))
    if p1 <= 0 or p1 >= 1:
        return None
    pbar = (p1 + p2) / 2
    za, zb = 1.959964, 0.841621  # alpha=.05 two-sided, power=.80
    num = (za * math.sqrt(2 * pbar * (1 - pbar)) + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2
    return math.ceil(num / (p2 - p1) ** 2)


# ---------------------------------------------------------------------------
# Store — applications live in the shared SQLite DB (F3); see store.py. The legacy
# data/p0e/applications.json is migrated once on first use.
# ---------------------------------------------------------------------------
def assign_arm(apps, user):
    """Balanced within-user: pick the arm this user has used least (ties broken randomly)."""
    counts = {a: 0 for a in ARMS}
    for r in apps:
        if r.get("user") == user and r.get("arm") in counts:
            counts[r["arm"]] += 1
    lo = min(counts.values())
    return random.choice([a for a in ARMS if counts[a] == lo])


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def build_report(apps):
    scored = [r for r in apps if r.get("callback") in (True, False)]
    per = {a: {"n": 0, "cb": 0} for a in ARMS}
    for r in scored:
        arm = r.get("arm")
        if arm in per:
            per[arm]["n"] += 1
            per[arm]["cb"] += 1 if r["callback"] else 0
    for a in ARMS:
        n = per[a]["n"]
        per[a]["rate"] = (per[a]["cb"] / n) if n else None

    # omnibus 3-arm (callback vs not)
    table = [[per[a]["cb"] for a in ARMS], [per[a]["n"] - per[a]["cb"] for a in ARMS]]
    omni_chi, omni_df, omni_p = chi2_rxk(table)

    # pairwise vs control (+ full vs title to isolate the title lever)
    def pair(x, y):
        chi, p = chi2_2x2_yates(per[x]["cb"], per[x]["n"] - per[x]["cb"],
                                per[y]["cb"], per[y]["n"] - per[y]["cb"])
        return {"chi2": round(chi, 3) if chi is not None else None,
                "p": round(p, 4) if p is not None else None,
                "rate_x": per[x]["rate"], "rate_y": per[y]["rate"]}
    pairwise = {
        "full_reframe_vs_control": pair("full_reframe", "control"),
        "title_only_vs_control": pair("title_only", "control"),
        "full_reframe_vs_title_only": pair("full_reframe", "title_only"),
    }

    pc = per["control"]["rate"]
    power = None
    if pc:
        power = {f"+{int(l*100)}%_lift": n_needed_per_arm(pc, l) for l in (0.5, 1.0, 2.0)}

    total = len(apps)
    n_scored = len(scored)
    if n_scored == 0:
        status, headline = "pending", f"Framework ready · {total} apps logged, 0 outcomes recorded"
    elif omni_p is None or min(per[a]["n"] for a in ARMS) < 20:
        status, headline = "pending", (f"Accruing · {n_scored} outcomes "
                                       f"(need ~{power['+100%_lift'] if power else '?'}/arm for +100% lift)")
    elif omni_p < 0.05:
        lifts_up = (per["full_reframe"]["rate"] or 0) > (pc or 0)
        status = "go" if lifts_up else "kill"
        headline = f"{'LIFT' if lifts_up else 'NO LIFT'} · omnibus p={omni_p:.3f}, control {pc:.1%} vs full {per['full_reframe']['rate']:.1%}"
    else:
        status, headline = "kill", f"Null · omnibus p={omni_p:.3f} at n={n_scored} (no callback lift)"

    return {
        "id": "P0-E", "status": status, "headline": headline,
        "arms": ARMS, "total_applications": total, "outcomes_recorded": n_scored,
        "per_arm": per,
        "omnibus_chi2": round(omni_chi, 3) if omni_chi is not None else None,
        "omnibus_df": omni_df, "omnibus_p": round(omni_p, 4) if omni_p is not None else None,
        "pairwise": pairwise,
        "power_n_per_arm": power,
        "go_criteria": "Statistically meaningful callback lift attributable to the reframe / title lever.",
        "note": ("Per-user signal is sparse; only cohort/aggregate readouts are honest. "
                 "For small expected counts, Yates-corrected chi-square is conservative; "
                 "prefer Fisher's exact once cells are tiny. Title-lever isolation = "
                 "full_reframe_vs_title_only + title_only_vs_control."),
    }


def write_spike(out_dir, rep):
    os.makedirs(os.path.join(out_dir, "spikes"), exist_ok=True)
    with open(os.path.join(out_dir, "spikes", "p0e.json"), "w") as f:
        json.dump(rep, f, indent=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="P0-E resume-reframe callback A/B")
    ap.add_argument("--out-dir", default="./data")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("assign", help="assign the arm for a new application")
    a.add_argument("--user", required=True)
    a.add_argument("--employer", required=True)
    a.add_argument("--role", required=True)
    a.add_argument("--seed", type=int, default=None)

    r = sub.add_parser("record", help="record a callback outcome for an application id")
    r.add_argument("--id", type=int, required=True)
    r.add_argument("--callback", required=True, choices=["yes", "no"])
    r.add_argument("--date", default=None)

    sub.add_parser("report", help="print the readout and write data/spikes/p0e.json")
    sub.add_parser("list", help="list logged applications")

    args = ap.parse_args()
    conn = store.connect(store.default_db_path())   # local disk (out_dir is CIFS)
    store.migrate_apps_json(conn, os.path.join(args.out_dir, "p0e", "applications.json"))
    apps = store.list_applications(conn)

    if args.cmd == "assign":
        if args.seed is not None:
            random.seed(args.seed)
        arm = assign_arm(apps, args.user)
        nid = store.add_application(conn, {
            "ts": datetime.now().isoformat(timespec="seconds"), "user": args.user,
            "employer": args.employer, "role": args.role, "arm": arm})
        print(f"application #{nid} -> ARM = {arm}")
        print(f"  ({'use the real resume unchanged' if arm=='control' else 'change ONLY the target title/headline' if arm=='title_only' else 'apply the full grounded reframe'})")
        return

    if args.cmd == "record":
        if store.set_callback(conn, args.id, args.callback == "yes",
                              args.date or date.today().isoformat()):
            print(f"application #{args.id}: callback={args.callback == 'yes'}")
        else:
            print(f"no application with id {args.id}")
        return

    if args.cmd == "list":
        for rec in apps:
            cb = {True: "CALLBACK", False: "none", None: "pending"}[rec.get("callback")]
            print(f"  #{rec['id']:>3}  {rec['arm']:<12}  {cb:<9}  {rec.get('employer','')} — {rec.get('role','')}")
        print(f"  ({len(apps)} applications)")
        return

    if args.cmd == "report":
        rep = build_report(apps)
        write_spike(args.out_dir, rep)
        print("== P0-E resume-reframe callback A/B ==")
        print(f"  applications logged: {rep['total_applications']} | outcomes recorded: {rep['outcomes_recorded']}\n")
        for arm in ARMS:
            p = rep["per_arm"][arm]
            rate = f"{p['rate']:.1%}" if p["rate"] is not None else "—"
            print(f"  {arm:<12} n={p['n']:>3}  callbacks={p['cb']:>3}  rate={rate}")
        print(f"\n  omnibus chi2={rep['omnibus_chi2']} df={rep['omnibus_df']} p={rep['omnibus_p']}")
        for k, v in rep["pairwise"].items():
            print(f"  {k:<32} chi2={v['chi2']} p={v['p']}")
        if rep["power_n_per_arm"]:
            print(f"\n  N needed per arm (power .80, alpha .05): {rep['power_n_per_arm']}")
        print(f"\n  STATUS: {rep['status'].upper()} — {rep['headline']}")
        print(f"  -> wrote {os.path.join(args.out_dir,'spikes','p0e.json')}")
        return


if __name__ == "__main__":
    main()
