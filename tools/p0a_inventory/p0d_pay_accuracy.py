#!/usr/bin/env python3
"""P0-D — OEWS/O*NET pay-engine accuracy spike.

Builds the deterministic BLS-OEWS pay estimator the roadmap proposes (title -> SOC
crosswalk -> OEWS national hourly) and scores it against GROUND TRUTH: the disclosed
pay the P0-A harvester already collected on real postings (data/runs/<date>/
all_postings.csv, pay_hourly + pay_source).

Question (roadmap P0-D): is OEWS-alone trustworthy for the RCM title set?
  GO   : median abs error <= $3-5/hr, and it separates $22 commodity from $34 specialist.
  KILL : error > $5/hr or it can't split the tiers -> crowdsourced real-pay must move into V1.

Ground-truth caveat: the harvester stores pay_hourly from the TOP of the posted range
(pay_max), so "actual" is the high end of the disclosed band; OEWS medians are midpoints,
so the estimator's undershoot is if anything *understated* here. Stdlib only.

Usage:  python3 p0d_pay_accuracy.py [--out-dir ./data]
"""
import argparse
import csv
import glob
import json
import math
import os
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
REF = json.load(open(os.path.join(HERE, "p0d_oews_reference.json")))
FLOOR = REF["floor_hourly"]


def map_title(title):
    """First crosswalk rule whose keyword is a substring of the (lowercased) title."""
    t = (title or "").lower()
    for rule in REF["crosswalk"]:
        if any(k in t for k in rule["kw"]):
            return rule
    return None


def estimate(rule):
    w = REF["soc_wages"][rule["soc"]]
    return w["median"], (w["p25"], w["p75"]), w


def _pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (dx * dy) if dx and dy else None


def _score(rows):
    """rows: list of (actual_pay, est_median, band, bimodal). Returns metrics dict."""
    if not rows:
        return None
    errs = [abs(est - act) for act, est, _, _ in rows]
    signed = [est - act for act, est, _, _ in rows]
    within3 = sum(1 for e in errs if e <= 3) / len(errs)
    within5 = sum(1 for e in errs if e <= 5) / len(errs)
    band_cov = sum(1 for act, _, (lo, hi), _ in rows if lo <= act <= hi) / len(rows)
    # $30 floor confusion (OEWS median as the predictor, disclosed pay as truth)
    tp = fp = tn = fn = 0
    for act, est, _, _ in rows:
        pe, pa = est >= FLOOR, act >= FLOOR
        tp += pe and pa
        fp += pe and not pa
        tn += (not pe) and (not pa)
        fn += (not pe) and pa
    n = len(rows)
    # tier separation: mean OEWS estimate for commodity(<28) vs specialist(>=34) actuals
    commodity = [est for act, est, _, _ in rows if act < 28]
    specialist = [est for act, est, _, _ in rows if act >= 34]
    r = _pearson([est for _, est, _, _ in rows], [act for act, _, _, _ in rows])
    return {
        "n": n,
        "median_abs_error": round(st.median(errs), 2),
        "mean_abs_error": round(sum(errs) / n, 2),
        "median_signed_error": round(st.median(signed), 2),
        "pct_within_3": round(100 * within3, 1),
        "pct_within_5": round(100 * within5, 1),
        "iqr_band_coverage_pct": round(100 * band_cov, 1),
        "floor30": {
            "accuracy_pct": round(100 * (tp + tn) / n, 1),
            "false_positive_says_ge30_wrongly": fp,
            "false_negative_hides_real_ge30": fn,
            "fn_rate_pct": round(100 * fn / (fn + tp), 1) if (fn + tp) else None,
        },
        "tier_separation": {
            "pearson_r_est_vs_actual": round(r, 3) if r is not None else None,
            "mean_est_for_commodity_lt28": round(sum(commodity) / len(commodity), 2) if commodity else None,
            "mean_est_for_specialist_ge34": round(sum(specialist) / len(specialist), 2) if specialist else None,
            "n_commodity": len(commodity), "n_specialist": len(specialist),
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="./data")
    args = ap.parse_args()

    paths = sorted(glob.glob(os.path.join(args.out_dir, "runs", "*", "all_postings.csv")))
    if not paths:
        print("no all_postings.csv found — run the harvester first")
        return
    src = paths[-1]
    rows = list(csv.DictReader(open(src)))

    all_mapped, arch_mapped, unmapped_with_pay = [], [], 0
    per_soc = {}
    examples = []
    for r in rows:
        pay = r.get("pay_hourly")
        if not pay:
            continue
        try:
            act = float(pay)
        except ValueError:
            continue
        rule = map_title(r.get("title", ""))
        if not rule:
            unmapped_with_pay += 1
            continue
        est, band, _ = estimate(rule)
        rec = (act, est, band, rule["bimodal"])
        all_mapped.append(rec)
        per_soc.setdefault(rule["soc"], []).append(abs(est - act))
        if (r.get("_role_archetype", "") == "True"):
            arch_mapped.append(rec)
            if len(examples) < 14:
                examples.append({"title": r.get("title", "")[:52], "employer": r.get("employer", ""),
                                 "actual": round(act, 2), "oews_median": est, "soc": rule["soc"],
                                 "bimodal": rule["bimodal"]})

    primary = _score(arch_mapped)      # the product's real use case
    secondary = _score(all_mapped)     # raw engine behavior incl. seniority confusion
    bimodal = _score([x for x in arch_mapped if x[3]])
    clean = _score([x for x in arch_mapped if not x[3]])

    # verdict
    go = bool(primary and primary["median_abs_error"] <= 5
              and primary["tier_separation"]["pearson_r_est_vs_actual"] is not None
              and primary["tier_separation"]["pearson_r_est_vs_actual"] >= 0.5)
    status = "go" if go else "kill"
    if not primary:
        headline = "P0-D: no archetype postings with disclosed pay to test"
    elif go:
        headline = f"OEWS OK — ${primary['median_abs_error']}/hr median err"
    else:
        headline = (f"OEWS UNTRUSTWORTHY — ${primary['median_abs_error']}/hr median err, "
                    f"r={primary['tier_separation']['pearson_r_est_vs_actual']}, "
                    f"hides {primary['floor30']['false_negative_hides_real_ge30']} real $30+ roles")

    spike = {
        "id": "P0-D", "status": status, "headline": headline,
        "release": REF["release"], "ground_truth_source": os.path.relpath(src, HERE),
        "test_sets": {
            "primary_archetype_IC": primary,
            "all_mapped_incl_senior": secondary,
            "archetype_bimodal_titles": bimodal,
            "archetype_clean_titles": clean,
        },
        "unmapped_with_pay": unmapped_with_pay,
        "per_soc_median_abs_error": {k: round(st.median(v), 2) for k, v in sorted(per_soc.items())},
        "examples": examples,
        "go_criteria": "median abs err <= $3-5/hr AND separates $22 commodity from $34 specialist (r>=0.5)",
        "interpretation": (
            "OEWS national medians map the RCM analyst/specialist titles into broad clerk SOCs "
            "(43-3021 median $23.32) or the huge-IQR Compliance-Officer SOC (13-1041 $29-$52), so a "
            "single median can neither hit real pay within $5/hr nor separate commodity from specialist. "
            "Confirms the roadmap: posted-range extraction + crowdsourced real-pay must be V1, not V3; "
            "the pay engine must show a confidence band / abstain, never a false floor."),
    }

    os.makedirs(os.path.join(args.out_dir, "spikes"), exist_ok=True)
    with open(os.path.join(args.out_dir, "spikes", "p0d.json"), "w") as f:
        json.dump(spike, f, indent=2)

    # report
    print(f"== P0-D pay-engine accuracy ({REF['release']}) ==")
    print(f"ground truth: {src}\n")
    def show(name, m):
        if not m:
            print(f"  {name}: (no rows)"); return
        ts = m["tier_separation"]; fl = m["floor30"]
        print(f"  {name} (n={m['n']}):")
        print(f"    median abs error ..... ${m['median_abs_error']}/hr   (within ±$5: {m['pct_within_5']}%, ±$3: {m['pct_within_3']}%)")
        print(f"    median signed error .. ${m['median_signed_error']}/hr   (negative = OEWS undershoots)")
        print(f"    $30 floor accuracy ... {fl['accuracy_pct']}%   hides {fl['false_negative_hides_real_ge30']} real $30+ roles (FN rate {fl['fn_rate_pct']}%), {fl['false_positive_says_ge30_wrongly']} false $30+")
        print(f"    tier separation ...... r={ts['pearson_r_est_vs_actual']}   commodity<$28 est=${ts['mean_est_for_commodity_lt28']}  specialist≥$34 est=${ts['mean_est_for_specialist_ge34']}")
        print(f"    IQR band coverage .... {m['iqr_band_coverage_pct']}%")
    show("PRIMARY (archetype IC + disclosed pay)", primary)
    show("bimodal-risk titles", bimodal)
    show("clean titles", clean)
    show("all mapped (incl. senior)", secondary)
    print(f"\n  unmapped postings with pay (out of RCM scope): {unmapped_with_pay}")
    print(f"\n  VERDICT: {status.upper()} — {headline}")
    print(f"  -> wrote {os.path.join(args.out_dir,'spikes','p0d.json')} (dashboard tracker will show it)")


if __name__ == "__main__":
    main()
