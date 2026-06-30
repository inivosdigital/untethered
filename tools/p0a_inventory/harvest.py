#!/usr/bin/env python3
"""
P0-A — Filtered Live-Inventory + Freshness Harvester (Untethered build roadmap).

Answers the #1 make-or-break question from docs/BUILD_ROADMAP.md: is there enough
FLOW (net-new per week), not just stock, of roles that survive ALL of these filters?

  Stage 1  RCM-title-relevant
  Stage 2  genuinely fully-remote (not hybrid / state-restricted)
  Stage 3  posted pay >= $30/hr
  Stage 4  offshore-resistant (onshore RCM taxonomy)
  Stage 5  credential-accessible (no hard RN / bachelor's gate)   -> QUALIFYING

Sources: FREE, no-auth ATS job-board APIs (Greenhouse, Lever, Ashby) + USAJOBS
(free key, optional).

HONEST SCOPE: this is a LEGAL LOWER BOUND. The archetype-fit IC volume that lives
on LinkedIn / Indeed / ZipRecruiter is NOT counted here (those can't be legally
server-side harvested — see roadmap P0-B). Treat these numbers as a floor and
complement with manual aggregator sampling. The pay, offshore-resistance, and
credential classifiers are transparent HEURISTICS — tune the keyword lists below
and spot-check the CSV before trusting the funnel.

Stdlib only. Python 3.9+.  Usage:  python3 harvest.py --config config.json --out-dir ./data
Run it daily (cron) to measure flow; it dedups by posting id across runs.
"""

import argparse
import csv
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import date
from html.parser import HTMLParser

UA = "untethered-p0a-inventory/0.1 (research spike; contact: admin@inivosdigital.com)"
HOURS_PER_YEAR = 2080
HOURS_PER_DAY = 8
FLOOR_HOURLY = 30.0

# ----------------------------------------------------------------------------
# Heuristic keyword lists — TUNE THESE. They are the whole ballgame; spot-check.
# ----------------------------------------------------------------------------
DEFAULT_TITLE_KEYWORDS = [
    "revenue cycle analyst", "revenue cycle", "denials analyst", "denial analyst",
    "denials", "appeals analyst", "appeals", "accounts receivable analyst",
    "ar analyst", "prior authorization", "patient access", "medical billing",
    "payer enrollment", "credentialing", "reimbursement", "claims",
]
# Onshore = offshore-RESISTANT signals (complex, judgment, US-context, patient-facing)
ONSHORE_SIGNALS = [
    "denial", "denials", "appeal", "appeals", "underpayment",
    "payer policy", "payer-policy", "dispute", "negotiat", "escalat",
    "patient financial", "financial counsel", "patient-facing",
    "clinical documentation", "cdi", "variance", "root cause", "grievance",
]
# Offshore-prone = commodity / transactional signals (racing offshore)
OFFSHORE_SIGNALS = [
    "charge entry", "payment posting", "post payments", "data entry",
    "eligibility verification", "credentialing", "coding", "claim submission",
    "indexing", "scanning", "keying", "transcription",
]
RN_GATE = re.compile(
    r"\b(rn|registered nurse|bsn|nursing license|nurse licensure|"
    r"active.{0,25}nurs|compact (rn|nurs|license))\b", re.I)
DEGREE_GATE = re.compile(
    r"(bachelor[’'s]*\s*(?:degree)?\s*(?:is\s*)?(?:required|require|mandatory)|"
    r"requires?\s+a\s+bachelor|ba/bs\s+required|"
    r"(?:must|need)\s+(?:have|possess)\s+a?\s*bachelor)", re.I)
HYBRID_FLAGS = re.compile(
    r"\b(hybrid|on-?site|in-?office|in person|days?\s+(?:per week\s+)?in (?:the )?office|"
    r"must reside in|must live in|located in|relocat|commut)\b", re.I)
REMOTE_FLAGS = re.compile(r"\b(fully remote|100% remote|remote|work from home|telework|wfh)\b", re.I)
# Clear NON-remote phrasing: 'remote not available', 'non-remote', 'no/not remote'.
NEG_REMOTE_FLAGS = re.compile(
    r"\b(no|not) remote\b"
    r"|\bnon-?remote\b"
    r"|\bremote\b[^.]{0,25}\b(not (?:available|offered|eligible|permitted|an option)|unavailable)\b"
    r"|\bnot eligible for remote\b", re.I)
# Remote-AFFIRMING geo phrasing that should NOT trip the hybrid/geo flags.
REMOTE_ANYWHERE_FLAGS = re.compile(
    r"\b(fully remote|100% remote|work from anywhere|remote from anywhere|"
    r"located in any|any (?:us )?state|anywhere in the (?:us|united states))\b", re.I)


# ----------------------------------------------------------------------------
# HTTP + HTML helpers
# ----------------------------------------------------------------------------
def http_get(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers={**{"User-Agent": UA}, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


class _Stripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def strip_html(raw):
    if not raw:
        return ""
    # Greenhouse returns ENTITY-ENCODED html (&lt;p&gt;...); decode entities first
    # so the tags become real tags the parser can strip. For already-plain html
    # this only unescapes text entities (e.g. &amp;) and leaves tags intact.
    text = html.unescape(raw)
    p = _Stripper()
    try:
        p.feed(text)
    except Exception:
        return re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", " ".join(p.parts)).strip()


# ----------------------------------------------------------------------------
# Pay parsing -> hourly
# ----------------------------------------------------------------------------
# Bare interval CODES that carry no English word (USAJOBS RateIntervalCode,
# etc.) mapped to a word the substring logic below understands.
_INTERVAL_CODES = {
    "ph": "hour", "pa": "year", "py": "year", "pm": "month",
    "pw": "week", "pd": "day", "bw": "biweek",
}


def to_hourly(amount, interval_hint=""):
    """Normalize a numeric amount to an hourly figure using an interval hint or magnitude.

    Recognizes hourly/annual/monthly/weekly/biweekly/daily intervals, expressed
    either as English words (Lever 'per-month-salary') or as bare codes
    (USAJOBS 'PM'/'PW'/'PD'/'BW'). Falls back to a magnitude guess only for
    genuinely unknown hints.
    """
    if amount is None:
        return None
    hint = (interval_hint or "").lower().strip()
    hint = _INTERVAL_CODES.get(hint, hint)
    if any(k in hint for k in ("hour", "hr", "/h")):
        return amount
    if any(k in hint for k in ("year", "annual", "annum", "yr", "/y")):
        return amount / HOURS_PER_YEAR
    if "biweek" in hint or "bi-week" in hint or "bi week" in hint:
        return amount * 26 / HOURS_PER_YEAR
    if "month" in hint or "/mo" in hint or "mth" in hint:
        return amount * 12 / HOURS_PER_YEAR
    if "week" in hint or "wk" in hint:
        return amount * 52 / HOURS_PER_YEAR
    if "day" in hint or "daily" in hint or "diem" in hint:
        return amount / HOURS_PER_DAY
    # genuinely unknown interval: fall back to magnitude
    return amount if amount < 1000 else amount / HOURS_PER_YEAR


_MONEY = re.compile(r"\$\s*([0-9]{2,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)")
# Context words that mark a nearby $ figure as NOT salary. A bonus, tuition
# benefit, or "we saved clients $X" claim is not pay — counting it as such
# inflates the funnel (a $500k savings figure would clear the $30/hr floor).
_PAY_DISQUALIFIERS = (
    "bonus", "sign-on", "sign on", "signing", "reimburs", "tuition",
    "relocat", "saved", "saving", "revenue", "portfolio", "aum",
    "401", "stipend", "budget", "raised", "funding", "valuation",
    "valued", "scholarship", "award", "prize", "grant", "equity",
    "stock", "discount", "deductible", "premium", "penalty",
)


def parse_pay_from_text(text):
    """Best-effort: pull a posted pay figure from free text. Returns (hourly, raw) or (None, None)."""
    if not text:
        return None, None
    window = text
    # prefer an explicit hourly mention
    m = re.search(r"\$\s*([0-9]{2,3}(?:\.[0-9]+)?)\s*(?:-|to|–)?\s*\$?\s*([0-9]{2,3}(?:\.[0-9]+)?)?\s*(?:/|per\s+)?\s*(hour|hr|hourly)", window, re.I)
    if m:
        lo = float(m.group(1))
        hi = float(m.group(2)) if m.group(2) else lo
        return max(lo, hi), m.group(0)
    # fall back to the largest plausible salary figure, skipping any $ amount
    # whose nearby context marks it as non-salary (bonus/savings/tuition/...).
    low = window.lower()
    nums = []
    for mm in _MONEY.finditer(window):
        ctx = low[max(0, mm.start() - 28): mm.end() + 28]
        if any(bad in ctx for bad in _PAY_DISQUALIFIERS):
            continue
        val = float(mm.group(1).replace(",", ""))
        if val >= 10:  # drop noise
            nums.append(val)
    if not nums:
        return None, None
    top = max(nums)
    interval = "year" if top > 1500 else "hour"
    return to_hourly(top, interval), f"${top:,.0f} ({interval})"


# ----------------------------------------------------------------------------
# Normalized posting
# ----------------------------------------------------------------------------
def posting(source, source_id, employer, title, location, workplace, description,
            pay_min=None, pay_max=None, pay_interval="", url="", posted_at=""):
    desc = strip_html(description)
    pay_hourly, pay_src = None, ""
    if pay_max is not None or pay_min is not None:
        amt = _to_float(pay_max if pay_max is not None else pay_min)
        if amt is not None:
            pay_hourly = to_hourly(amt, pay_interval)
            pay_src = "structured"
    if pay_hourly is None:
        pay_hourly, raw = parse_pay_from_text(f"{title} {desc}")
        if pay_hourly is not None:
            pay_src = "text:" + (raw or "")
    return {
        "source": source, "source_id": str(source_id), "employer": employer,
        "title": title or "", "location": location or "", "workplace": workplace or "",
        "description": desc, "pay_hourly": round(pay_hourly, 2) if pay_hourly else None,
        "pay_source": pay_src, "url": url, "posted_at": posted_at,
    }


# ----------------------------------------------------------------------------
# Source fetchers (each returns a list of normalized postings; never raises)
# ----------------------------------------------------------------------------
def fetch_greenhouse(token):
    out = []
    try:
        data = json.loads(http_get(
            f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"))
    except Exception as e:
        print(f"  [greenhouse:{token}] skip ({e})", file=sys.stderr)
        return out
    jobs = data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(jobs, list):
        print(f"  [greenhouse:{token}] skip (unexpected payload)", file=sys.stderr)
        return out
    for j in jobs:
        try:
            meta = {m.get("name", "").lower(): m.get("value") for m in (j.get("metadata") or [])}
            pmin = pmax = None
            for k in ("salary", "pay range", "compensation"):
                if k in meta and meta[k]:
                    hourly, _ = parse_pay_from_text(str(meta[k]))
                    if hourly:
                        pmax = hourly
                        break
            out.append(posting(
                "greenhouse", j.get("id"), token, j.get("title"),
                (j.get("location") or {}).get("name"), "", j.get("content", ""),
                pay_max=pmax, pay_interval="hour" if pmax else "",
                url=j.get("absolute_url", ""), posted_at=j.get("updated_at", "")))
        except Exception as e:
            print(f"  [greenhouse:{token}] bad record skipped ({e})", file=sys.stderr)
    return out


def fetch_lever(company):
    out = []
    try:
        data = json.loads(http_get(f"https://api.lever.co/v0/postings/{company}?mode=json"))
    except Exception as e:
        print(f"  [lever:{company}] skip ({e})", file=sys.stderr)
        return out
    if not isinstance(data, list):
        print(f"  [lever:{company}] skip (unexpected payload)", file=sys.stderr)
        return out
    for j in data:
        try:
            cats = j.get("categories") or {}
            sr = j.get("salaryRange") or {}
            # only trust structured pay when it's USD (or unspecified); a non-USD
            # amount must not be normalized as USD and clear the $30/hr floor.
            usd = (sr.get("currency") or "USD").upper() == "USD"
            out.append(posting(
                "lever", j.get("id"), company, j.get("text"),
                cats.get("location"), j.get("workplaceType") or cats.get("workplaceType") or "",
                j.get("descriptionPlain") or j.get("description") or "",
                pay_min=sr.get("min") if usd else None,
                pay_max=sr.get("max") if usd else None,
                pay_interval=sr.get("interval", "") if usd else "",
                url=j.get("hostedUrl", ""),
                posted_at=str(j.get("createdAt", ""))))
        except Exception as e:
            print(f"  [lever:{company}] bad record skipped ({e})", file=sys.stderr)
    return out


def fetch_ashby(board):
    out = []
    try:
        data = json.loads(http_get(
            f"https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true"))
    except Exception as e:
        print(f"  [ashby:{board}] skip ({e})", file=sys.stderr)
        return out
    jobs = data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(jobs, list):
        print(f"  [ashby:{board}] skip (unexpected payload)", file=sys.stderr)
        return out
    for j in jobs:
        try:
            comp = j.get("compensation") or {}
            summary = comp.get("compensationTierSummary") or ""
            pmax, _ = parse_pay_from_text(summary) if summary else (None, None)
            loc = j.get("location") or ""
            workplace = "remote" if j.get("isRemote") else ""
            out.append(posting(
                "ashby", j.get("id"), board, j.get("title"), loc, workplace,
                j.get("descriptionHtml") or j.get("descriptionPlain") or "",
                pay_max=pmax, pay_interval="hour" if pmax else "",
                url=j.get("jobUrl") or j.get("applyUrl") or "", posted_at=j.get("publishedAt", "")))
        except Exception as e:
            print(f"  [ashby:{board}] bad record skipped ({e})", file=sys.stderr)
    return out


def fetch_usajobs(keywords, api_key, email, remote_only=True):
    out = []
    if not api_key or not email:
        print("  [usajobs] skip (set USAJOBS_API_KEY and USAJOBS_EMAIL to enable)", file=sys.stderr)
        return out
    headers = {"Host": "data.usajobs.gov", "User-Agent": email, "Authorization-Key": api_key}
    for kw in keywords:
        try:
            q = urllib.parse.quote(kw)
            url = f"https://data.usajobs.gov/api/search?Keyword={q}&ResultsPerPage=250"
            if remote_only:
                url += "&RemoteIndicator=True"
            data = json.loads(http_get(url, headers=headers))
        except Exception as e:
            print(f"  [usajobs:{kw}] skip ({e})", file=sys.stderr)
            continue
        sr = data.get("SearchResult") if isinstance(data, dict) else None
        items = sr.get("SearchResultItems") if isinstance(sr, dict) else None
        if not isinstance(items, list):
            print(f"  [usajobs:{kw}] skip (unexpected payload)", file=sys.stderr)
            continue
        for item in items:
            try:
                d = item.get("MatchedObjectDescriptor", {}) or {}
                rem_list = d.get("PositionRemuneration")
                rem = rem_list[0] if isinstance(rem_list, list) and rem_list else {}
                pmin = _to_float(rem.get("MinimumRange"))
                pmax = _to_float(rem.get("MaximumRange"))
                out.append(posting(
                    "usajobs", d.get("PositionID"), d.get("OrganizationName", "Federal"),
                    d.get("PositionTitle"), d.get("PositionLocationDisplay"),
                    "remote", (d.get("UserArea", {}).get("Details", {}) or {}).get("JobSummary", ""),
                    pay_min=pmin, pay_max=pmax, pay_interval=rem.get("RateIntervalCode", ""),
                    url=d.get("PositionURI", ""), posted_at=d.get("PublicationStartDate", "")))
            except Exception as e:
                print(f"  [usajobs:{kw}] bad record skipped ({e})", file=sys.stderr)
    return out


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ----------------------------------------------------------------------------
# Filters
# ----------------------------------------------------------------------------
def f_rcm(p, title_keywords):
    hay = f"{p['title']} {p['description'][:400]}".lower()
    return any(k in hay for k in title_keywords)


def f_remote(p):
    blob = f"{p['workplace']} {p['location']} {p['description']}"
    wp = p["workplace"].lower()
    # explicit negation first: 'remote not available', 'non-remote', etc.
    if NEG_REMOTE_FLAGS.search(blob):
        return "hybrid_or_onsite"
    if wp in ("on-site", "onsite", "hybrid"):
        return "hybrid_or_onsite"
    # geo language ('located in ...') only means hybrid when it isn't the benign
    # 'located in any US state' / 'work from anywhere' remote-affirming phrasing.
    remote_affirmed = bool(REMOTE_ANYWHERE_FLAGS.search(blob))
    if HYBRID_FLAGS.search(blob) and not remote_affirmed:
        return "hybrid_or_onsite"
    if wp == "remote" or REMOTE_FLAGS.search(blob):
        return "remote"
    return "unclear"


def f_pay(p):
    h = p["pay_hourly"]
    if h is None:
        return "unknown"
    return "ge30" if h >= FLOOR_HOURLY else "lt30"


def _signal_hits(text, signals):
    # Leading word-boundary match: counts 'coding' but not 'encoding', 'denial(s)'
    # but not arbitrary substrings; stems like 'negotiat' still match 'negotiate'.
    return sum(1 for s in signals if re.search(r"\b" + re.escape(s), text))


def f_offshore_resistant(p):
    text = f"{p['title']} {p['description']}".lower()
    on = _signal_hits(text, ONSHORE_SIGNALS)
    off = _signal_hits(text, OFFSHORE_SIGNALS)
    resistant = on >= 1 and on >= off
    return resistant, on, off


def f_credential(p):
    text = f"{p['title']} {p['description']}"
    if RN_GATE.search(text):
        return "rn_gated"
    if DEGREE_GATE.search(text):
        return "degree_gated"
    return "accessible"


def classify(p, title_keywords):
    p["_rcm"] = f_rcm(p, title_keywords)
    p["_remote"] = f_remote(p)
    p["_pay"] = f_pay(p)
    resistant, on, off = f_offshore_resistant(p)
    p["_offshore_resistant"], p["_onshore_score"], p["_offshore_score"] = resistant, on, off
    p["_credential"] = f_credential(p)
    p["_qualifies_strict"] = bool(
        p["_rcm"] and p["_remote"] == "remote" and p["_pay"] == "ge30"
        and p["_offshore_resistant"] and p["_credential"] == "accessible")
    p["_qualifies_if_pay_unknown"] = bool(
        p["_rcm"] and p["_remote"] == "remote" and p["_pay"] in ("ge30", "unknown")
        and p["_offshore_resistant"] and p["_credential"] == "accessible")
    return p


# ----------------------------------------------------------------------------
# State (freshness / net-new flow)
# ----------------------------------------------------------------------------
def load_state(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except (ValueError, OSError) as e:
        # a truncated/corrupt state file (e.g. a run killed mid-write) must not
        # crash every subsequent run — start fresh rather than abort the experiment
        print(f"  [state] ignoring unreadable state file ({e}); starting fresh",
              file=sys.stderr)
        return {}


def save_state(path, state):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, path)  # atomic rename — never leaves a half-written seen.json


def update_flow_state(deduped, qualifying, state, today):
    """Record first-seen and first-qualified per posting; return net-new-qualifying.

    A posting counts as net-new the first run it QUALIFIES, even if it was seen
    earlier while non-qualifying (e.g. pay was unpublished then). Legacy flat
    {key: date} state values are migrated to the structured record on contact.
    """
    qual_keys = {f"{p['source']}:{p['source_id']}" for p in qualifying}
    new_qual = []
    for p in deduped:
        k = f"{p['source']}:{p['source_id']}"
        rec = state.get(k)
        if not isinstance(rec, dict):
            rec = {"first_seen": rec if isinstance(rec, str) else today,
                   "first_qualified": None}
            state[k] = rec
        if k in qual_keys and not rec.get("first_qualified"):
            rec["first_qualified"] = today
            new_qual.append(p)
    return new_qual


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="P0-A filtered live-inventory + freshness harvester")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--out-dir", default="./data")
    args = ap.parse_args()

    with open(args.config) as f:
        cfg = json.load(f)
    title_keywords = [k.lower() for k in cfg.get("title_keywords", DEFAULT_TITLE_KEYWORDS)]

    today = date.today().isoformat()
    run_dir = os.path.join(args.out_dir, "runs", today)
    os.makedirs(run_dir, exist_ok=True)
    state_path = os.path.join(args.out_dir, "state", "seen.json")
    state = load_state(state_path)

    print(f"== P0-A harvest {today} ==")
    postings = []
    for tok in cfg.get("greenhouse_boards", []):
        postings += fetch_greenhouse(tok)
    for c in cfg.get("lever_companies", []):
        postings += fetch_lever(c)
    for b in cfg.get("ashby_boards", []):
        postings += fetch_ashby(b)
    uj = cfg.get("usajobs", {})
    if uj.get("enabled"):
        postings += fetch_usajobs(uj.get("keywords", []), os.environ.get("USAJOBS_API_KEY"),
                                  os.environ.get("USAJOBS_EMAIL"), uj.get("remote_only", True))

    # dedup within this run
    seen_keys, deduped = set(), []
    for p in postings:
        k = f"{p['source']}:{p['source_id']}"
        if k in seen_keys:
            continue
        seen_keys.add(k)
        deduped.append(classify(p, title_keywords))

    # funnel (strict path)
    n_total = len(deduped)
    s_rcm = [p for p in deduped if p["_rcm"]]
    s_remote = [p for p in s_rcm if p["_remote"] == "remote"]
    s_pay = [p for p in s_remote if p["_pay"] == "ge30"]
    s_offshore = [p for p in s_pay if p["_offshore_resistant"]]
    s_qual = [p for p in s_offshore if p["_credential"] == "accessible"]
    upper = [p for p in deduped if p["_qualifies_if_pay_unknown"]]

    # net-new flow vs prior runs (counts the first run a posting QUALIFIES, even
    # if it was seen earlier while non-qualifying); records first-seen for all.
    new_qual = update_flow_state(deduped, s_qual, state, today)
    save_state(state_path, state)

    def pct(n):
        return f"{(100.0*n/n_total):.1f}%" if n_total else "n/a"

    summary = {
        "date": today,
        "sources": {
            "greenhouse": cfg.get("greenhouse_boards", []),
            "lever": cfg.get("lever_companies", []),
            "ashby": cfg.get("ashby_boards", []),
            "usajobs_enabled": bool(uj.get("enabled")),
        },
        "funnel": {
            "0_total_fetched": n_total,
            "1_rcm_relevant": len(s_rcm),
            "2_fully_remote": len(s_remote),
            "3_pay_ge_30": len(s_pay),
            "4_offshore_resistant": len(s_offshore),
            "5_qualifying_strict": len(s_qual),
        },
        "pay_unknown_upper_bound_qualifying": len(upper),
        "net_new_qualifying_this_run": len(new_qual),
        "pay_coverage": {
            "postings_with_posted_pay": sum(1 for p in deduped if p["_pay"] != "unknown"),
            "postings_pay_unknown": sum(1 for p in deduped if p["_pay"] == "unknown"),
        },
        "caveat": "FREE-FEED LOWER BOUND. LinkedIn/Indeed/ZipRecruiter IC volume NOT counted. "
                  "Pay/offshore/credential filters are heuristics — spot-check qualifying.csv.",
    }

    # write outputs
    _write_csv(os.path.join(run_dir, "all_postings.csv"), deduped)
    _write_csv(os.path.join(run_dir, "qualifying.csv"), s_qual)
    with open(os.path.join(run_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    # print
    print(f"\nSURVIVAL FUNNEL (strict, free-feed lower bound):")
    print(f"  0. fetched ................. {n_total}")
    print(f"  1. RCM-relevant ............ {len(s_rcm):>5}  ({pct(len(s_rcm))})")
    print(f"  2. + fully-remote .......... {len(s_remote):>5}  ({pct(len(s_remote))})")
    print(f"  3. + pay >= $30/hr ......... {len(s_pay):>5}  ({pct(len(s_pay))})")
    print(f"  4. + offshore-resistant .... {len(s_offshore):>5}  ({pct(len(s_offshore))})")
    print(f"  5. = QUALIFYING ............ {len(s_qual):>5}  ({pct(len(s_qual))})")
    print(f"\n  upper bound (incl. pay-unknown): {len(upper)}")
    print(f"  net-new qualifying this run ...: {len(new_qual)}")
    print(f"  pay coverage ..................: "
          f"{summary['pay_coverage']['postings_with_posted_pay']}/{n_total} have posted pay")
    print(f"\n  -> outputs in {run_dir}/  (summary.json, qualifying.csv, all_postings.csv)")
    print(f"  -> {summary['caveat']}")
    if n_total == 0:
        print("\n  NOTE: 0 fetched — populate config.json with real ATS board tokens "
              "(see README) and/or enable USAJOBS.")


def _write_csv(path, rows):
    cols = ["source", "employer", "title", "location", "workplace", "pay_hourly",
            "pay_source", "_remote", "_pay", "_offshore_resistant", "_onshore_score",
            "_offshore_score", "_credential", "_qualifies_strict", "url", "posted_at"]
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for p in rows:
            w.writerow([p.get(c, "") for c in cols])


if __name__ == "__main__":
    main()
