#!/usr/bin/env python3
"""Pay-truth engine (Foundation F2) — Python mirror of extension/src/pay.js.

Same rules (scoring/rules.json via scoring_rules); parity guarded by
scoring/pay_parity_fixtures.json + test_pay_parity.py. A PayEstimate is a plain dict:
  floorHourly, ceilingHourly, currency, period, source, confidence, clearsFloor,
  straddlesFloor, note  (see pay.js for the field contract).

Fixes P0-D + the relook: the floor is the LOWER bound (a range straddling $30 gets an
explicit "straddles" verdict, not a false "yes"), and the OEWS prior ABSTAINS — it
surfaces a p25-p75 band as context but never asserts a floor it cannot support.
"""
from datetime import datetime

from scoring_rules import (
    FLOOR_HOURLY, PAY_DISQUALIFIERS, PAY_HOURLY, PAY_RANGE, MONEY, to_hourly,
)


def _num(s):
    return float(str(s).replace(",", ""))


def _r2(x):
    return None if x is None else round(x, 2)


def _near_disq(low, start, end):
    ctx = low[max(0, start - 28): end + 28]
    return any(b in ctx for b in PAY_DISQUALIFIERS)


def clears_floor(floor, ceiling):
    """The funnel verdict: distinguish a reliable 'yes' from a 'straddles $30' range."""
    if floor is None:
        return "unknown"
    if floor >= FLOOR_HOURLY:
        return "yes"
    if ceiling is not None and ceiling >= FLOOR_HOURLY:
        return "straddles"
    return "no"


_NONE = {"floorHourly": None, "ceilingHourly": None, "currency": "USD", "period": "",
         "source": "none", "confidence": "abstain", "clearsFloor": "unknown",
         "straddlesFloor": False, "note": "no pay signal"}


def range_from_structured(min=None, max=None, currency=None, interval=None):
    if (currency or "USD").upper() != "USD":
        return None  # no false floor from FX

    def conv(v):  # tolerate non-numeric structured pay ("competitive"/"DOE") -> None
        try:
            return to_hourly(float(str(v).replace(",", "")), interval)
        except (TypeError, ValueError):
            return None

    lo = conv(min) if min is not None else None
    hi = conv(max) if max is not None else None
    if lo is None and hi is None:
        return None
    return {"minHourly": lo if lo is not None else hi,
            "maxHourly": hi if hi is not None else lo,
            "currency": "USD", "period": interval or "", "basis": "structured"}


def range_from_text(text):
    if not text:
        return None
    h = PAY_HOURLY.search(text)
    if h:
        lo = float(h.group(1))
        hi = float(h.group(2)) if h.group(2) else lo
        return {"minHourly": min(lo, hi), "maxHourly": max(lo, hi),
                "currency": "USD", "period": "hour", "basis": "text"}
    low = text.lower()
    r = PAY_RANGE.search(text)
    if r and not _near_disq(low, r.start(), r.end()):
        a = _num(r.group(1)); b = _num(r.group(2))
        lo, hi = min(a, b), max(a, b)
        if lo >= 10 and hi / lo <= 25:  # ratio guard: reject typo artifacts
            period = "year" if lo > 1500 else "hour"
            return {"minHourly": to_hourly(lo, period), "maxHourly": to_hourly(hi, period),
                    "currency": "USD", "period": period, "basis": "text"}
    nums = []
    for m in MONEY.finditer(text):
        if _near_disq(low, m.start(), m.end()):
            continue
        v = _num(m.group(1))
        if v >= 10:
            nums.append(v)
    if not nums:
        return None
    top = max(nums)
    period = "year" if top > 1500 else "hour"
    hourly = to_hourly(top, period)
    return {"minHourly": hourly, "maxHourly": hourly, "currency": "USD",
            "period": period, "basis": "text-single"}


def _from_range(rng, source):
    if not rng:
        return dict(_NONE)
    floor = _r2(rng["minHourly"]); ceiling = _r2(rng["maxHourly"])
    cf = clears_floor(floor, ceiling)
    conf = {"structured": "high", "text": "medium"}.get(rng["basis"], "low")
    return {"floorHourly": floor, "ceilingHourly": ceiling, "currency": rng.get("currency", "USD"),
            "period": rng.get("period", ""), "source": source, "confidence": conf,
            "clearsFloor": cf, "straddlesFloor": cf == "straddles",
            "note": "posted range straddles $30 — floor below, ceiling above" if cf == "straddles" else ""}


def posted_estimate(structured=None, text=None):
    rng = (range_from_structured(**structured) if structured else None) or range_from_text(text or "")
    return _from_range(rng, "posted")


def oews_prior(p25=None, p75=None):
    """An ABSTAINING estimate: surfaces the p25-p75 band as context, never a floor verdict."""
    if p25 is None and p75 is None:
        return dict(_NONE)
    return {"floorHourly": _r2(p25), "ceilingHourly": _r2(p75), "currency": "USD",
            "period": "hour", "source": "oews-prior", "confidence": "abstain",
            "clearsFloor": "unknown", "straddlesFloor": False,
            "note": "OEWS p25-p75 band (context only; abstains from a floor verdict)"}


def crowd_aggregate(reports, min_contributors=5, min_months=3, max_source_share=0.25):
    """Density-gated crowdsourced estimate, else None. reports:
    [{hourly, contributorId, sourceType, reportedAt}]."""
    if not isinstance(reports, list):
        return None
    valid = [r for r in reports
             if r and isinstance(r.get("hourly"), (int, float)) and r.get("contributorId")]
    if len({r["contributorId"] for r in valid}) < min_contributors:
        return None
    times = []
    for r in valid:
        try:
            times.append(datetime.fromisoformat(str(r["reportedAt"]).replace("Z", "+00:00")).timestamp())
        except (KeyError, ValueError, AttributeError):
            pass
    if times:
        span_months = (max(times) - min(times)) / (60 * 60 * 24 * 30.44)
        if span_months < min_months:
            return None
    elif min_months > 0:
        return None
    by_source = {}
    for r in valid:
        s = r.get("sourceType", "unknown")
        by_source[s] = by_source.get(s, 0) + 1
    if max(by_source.values()) / len(valid) > max_source_share:
        return None
    sorted_h = sorted(r["hourly"] for r in valid)

    def q(p):
        return sorted_h[min(len(sorted_h) - 1, int(p * (len(sorted_h) - 1)))]

    floor = _r2(q(0.25)); ceiling = _r2(q(0.75))
    cf = clears_floor(floor, ceiling)
    return {"floorHourly": floor, "ceilingHourly": ceiling, "currency": "USD", "period": "hour",
            "source": "crowdsourced", "confidence": "high" if len(sorted_h) >= 30 else "medium",
            "clearsFloor": cf, "straddlesFloor": cf == "straddles",
            "note": f"crowdsourced p25-p75 from {len(sorted_h)} reports"}


def combine(posted=None, crowd=None, oews=None):
    """Trust priority: posted > crowdsourced > OEWS prior > none."""
    for e in (posted, crowd, oews):
        if e and e.get("source") != "none":
            return e
    return dict(_NONE)
