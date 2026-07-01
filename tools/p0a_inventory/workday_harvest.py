#!/usr/bin/env python3
"""Session-context Workday CXS list harvester (Phase-1.1).

Lifts P0-A past the ~32% free-API ceiling (P0-B) by counting the REMOTE ARCHETYPE-IC RCM
roles behind Workday — the single largest enterprise-ATS slice (HCA/R1/Ensemble/Conifer/
Optum/Centene/Elevance/Molina all live there).

What the session probes established (and this module relies on):
  * The CXS jobs LIST works server-side with plain stdlib: GET `.../approot` to bootstrap
    the Cloudflare + Workday session cookies (it 406s but sets the cookies), then
    POST `.../jobs` with a `searchText`. No headless browser, no CSRF needed for the list.
  * The job DETAIL endpoint is browser-only (422 server-side without the CALYPSO session),
    so description + posted PAY are NOT available here — Workday roles come out with pay
    UNKNOWN (they lift coverage + the upper bound; the EXTENSION supplies pay-truth in the
    page context, exactly the "extension is load-bearing" design from P0-B).
  * CRITICAL header: `Accept-Language` must be a BARE locale ("en-US"), not "en-US,en;q=0.9"
    — Workday parses the header as the locale and 422s on the q-weights.

Pure network layer: returns raw job dicts; harvest.py normalizes them. Never raises out.
Stdlib only.
"""
import gzip
import http.cookiejar
import json
import re
import sys
import urllib.request

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36")
HDRS = {"User-Agent": UA, "Accept-Language": "en-US", "Accept": "application/json, text/plain, */*"}


def _session():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def _req(op, url, data=None, method=None, extra=None, timeout=30):
    req = urllib.request.Request(url, data=data, headers={**HDRS, **(extra or {})}, method=method)
    with op.open(req, timeout=timeout) as r:
        body = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
        return r.getcode(), body


def list_jobs(tenant, pod, site, search_terms, page_limit=20, max_pages=8):
    """All jobs matching any search term for one Workday tenant, deduped by externalPath.

    Returns a list of {source_id, title, location, url, posted_at}. Never raises; on any
    per-term error it logs to stderr and moves on.
    """
    origin = f"https://{tenant}.{pod}.myworkdayjobs.com"
    base = f"{origin}/wday/cxs/{tenant}/{site}"
    op = _session()
    try:
        _req(op, base + "/approot")   # bootstrap cookies (may 406 — cookies still get set)
    except Exception:
        pass
    post_hdr = {"Content-Type": "application/json", "Origin": origin, "Referer": f"{origin}/en-US/{site}"}
    seen, out = set(), []
    for term in search_terms:
        offset = 0
        for _ in range(max_pages):
            payload = json.dumps({"appliedFacets": {}, "limit": page_limit,
                                  "offset": offset, "searchText": term}).encode()
            try:
                code, raw = _req(op, base + "/jobs", data=payload, method="POST", extra=post_hdr)
            except Exception as e:
                print(f"  [workday:{tenant}] {term!r} skip ({e})", file=sys.stderr)
                break
            if code != 200:
                print(f"  [workday:{tenant}] {term!r} http {code}", file=sys.stderr)
                break
            try:
                d = json.loads(raw)
            except ValueError:
                break
            jps = d.get("jobPostings") or []
            for j in jps:
                ep = j.get("externalPath") or ""
                key = ep or (j.get("bulletFields") or [""])[0]
                if key in seen:
                    continue
                seen.add(key)
                out.append({
                    "source_id": key,
                    "title": j.get("title") or "",
                    "location": j.get("locationsText") or "",
                    "url": f"{origin}/en-US/{site}{ep}" if ep else origin,
                    "posted_at": j.get("postedOn") or "",
                })
            offset += page_limit
            if not jps or offset >= (d.get("total") or 0):
                break
    return out


def probe_site(tenant, pod, candidates):
    """Verify which candidate `site` slug actually serves this tenant's CXS jobs endpoint.
    Returns the first slug that returns HTTP 200 with jobs, or None. Used to seed the
    registry semi-automatically."""
    origin = f"https://{tenant}.{pod}.myworkdayjobs.com"
    op = _session()
    try:
        _req(op, f"{origin}/wday/cxs/{tenant}/{candidates[0]}/approot")
    except Exception:
        pass
    for site in candidates:
        try:
            code, raw = _req(
                op, f"{origin}/wday/cxs/{tenant}/{site}/jobs",
                data=json.dumps({"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""}).encode(),
                method="POST", extra={"Content-Type": "application/json", "Origin": origin})
            if code == 200 and (json.loads(raw).get("jobPostings") is not None):
                return site
        except Exception:
            continue
    return None


if __name__ == "__main__":  # quick probe: python3 workday_harvest.py devoted wd1 Devoted
    t, p, s = sys.argv[1], sys.argv[2], sys.argv[3]
    jobs = list_jobs(t, p, s, ["revenue cycle", "denials", "medical billing", "credentialing"])
    print(f"{t}/{s}: {len(jobs)} jobs")
    for j in jobs[:10]:
        print("  -", j["title"], "|", j["location"])
