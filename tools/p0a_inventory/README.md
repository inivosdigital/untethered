# P0-A — Filtered Live-Inventory + Freshness Harvester

Implements spike **P0-A** from [`../../docs/BUILD_ROADMAP.md`](../../docs/BUILD_ROADMAP.md) — the #1
make-or-break test: **is there enough _flow_ (net-new per week), not just stock, of roles that survive
all five kill-filters?** If the answer is "single digits/week nationally," the job-board framing is
dead and the product pivots to staircase-first.

## What it does

Pulls postings from **free, no-auth ATS APIs** (Greenhouse, Lever, Ashby) + **USAJOBS** (free key),
normalizes them, and runs each through a survival funnel:

| Stage | Filter |
|---|---|
| 1 | **RCM-title-relevant** (keyword match) |
| 2 | **+ accessible IC role-type** (rejects leadership VP/Director/Manager, and wrong-function eng/product/sales/marketing/legal/HR/clinical titles that merely mention revenue-cycle work; title-only) |
| 3 | **+ genuinely fully-remote** (rejects hybrid / "must reside in" / "X days in office") |
| 4 | **+ posted pay ≥ $30/hr** (structured fields or `$NN/hr` in text; annual ÷ 2080) |
| 5 | **+ offshore-resistant** (onshore RCM taxonomy: denials/appeals/payer-policy/patient-financial beats charge-entry/posting/coding) |
| 6 | **= QUALIFYING** (credential-accessible — no hard RN / bachelor's gate) |

It dedups by posting id and persists a `state/seen.json`, so running it daily measures **net-new
qualifying roles per run** — the freshness/flow signal that actually matters.

## ⚠ Honest scope & limitations

- **This is a FREE-FEED LOWER BOUND.** The archetype-fit IC volume lives on LinkedIn / Indeed /
  ZipRecruiter, which **cannot be legally server-side harvested** (roadmap P0-B). Those are **not
  counted here.** Complement this with **manual aggregator sampling** to get the true picture.
- **Pay is often unpublished** on free feeds. The funnel's strict path requires posted pay ≥ $30; the
  report also prints an **upper bound** that includes pay-unknown postings, and a **pay-coverage**
  line so you know how much is missing. Don't read the strict number as the whole truth.
- **The pay / offshore-resistance / credential classifiers are transparent HEURISTICS** (keyword
  lists at the top of `harvest.py`). **Spot-check `qualifying.csv` and tune the lists** before
  trusting the funnel. They are a starting point, not ground truth.

## Run it

```bash
cp config.example.json config.json      # then edit: add real ATS board tokens
python3 harvest.py --config config.json --out-dir ./data
```

No dependencies — Python 3.9+ standard library only.

**Finding board tokens:** take them from a company's careers URL —
`boards.greenhouse.io/<TOKEN>`, `jobs.lever.co/<COMPANY>`, `jobs.ashbyhq.com/<BOARD>`. Seed
`config.json` with health-tech / revenue-cycle-vendor / digital-health / payer employers. Unknown
tokens are skipped gracefully and reported on stderr.

**USAJOBS (optional):** set `"usajobs": {"enabled": true}` in the config and export a free key
(request one at <https://developer.usajobs.gov/>):

```bash
export USAJOBS_API_KEY=...    export USAJOBS_EMAIL=you@example.com
```

**Measure flow (the point of P0-A):** run it daily for ~4 weeks, e.g. cron —

```
0 9 * * *  cd /path/to/tools/p0a_inventory && python3 harvest.py --config config.json --out-dir ./data
```

Each run prints `net-new qualifying this run` and appends to `state/seen.json`; weekly net-new is your
flow number.

## Outputs (per run, under `data/runs/<date>/`)

- `summary.json` — the funnel counts, upper bound, net-new, pay coverage, caveat.
- `qualifying.csv` — the roles that survived all five filters (spot-check these!).
- `all_postings.csv` — every fetched posting with its per-filter flags (audit the classifier here).

## Go / Kill criteria (from the roadmap)

- **GO:** net-new qualifying roles refill fast enough to sustain recurring engagement (enough fresh
  ≥$30 archetype-accessible roles per week to keep a user returning), even if stock is in the low tens.
- **KILL / PIVOT:** net-new is **single digits/week nationally** across all sources, or raw filter
  survival is **<5–10%** → the feed framing is dead; pivot to **coaching-staircase-first**, feed as
  destination.

## Validation status

- **Logic:** the filter funnel is unit-validated offline — each filter (IC-role-type vs
  leadership/wrong-function/clinical, remote/hybrid, pay floor, offshore-resistance, RN/degree gate)
  makes the correct call on synthetic postings.
- **Live fetch:** requires open network egress. (It will not run against the live APIs from a sandbox
  with a restricted egress policy — run it where Greenhouse/Lever/Ashby/USAJOBS are reachable.)

## P0 command center & the other Phase-0 spikes

The harvester is the free-feed half of P0-A. The rest of Phase 0 is instrumented alongside it, and a
dashboard ties it together (all zero-dependency, stdlib only):

- **`dashboard.py`** — P0 command center. Reads `data/runs/*/summary.json` + latest `qualifying.csv`
  live and renders the funnel, net-new **flow vs the KILL line**, qualifying roles, and a Phase-0
  tracker. Runs under pm2 as `p0a-dashboard`: `python3 dashboard.py --out-dir ./data --port 8770`.
- **`p0d_pay_accuracy.py`** (+ committed `p0d_oews_reference.json`) — **P0-D**: builds the OEWS/O*NET
  title→SOC pay estimator and scores it against the harvested disclosed-pay corpus. Result on current
  data: **KILL** (median abs err ~$12/hr, can't separate tiers → posted-range + crowdsourced pay must
  be V1). `python3 p0d_pay_accuracy.py --out-dir ./data`.
- **`p0e_callback_ab.py`** — **P0-E**: within-user randomized reframe-vs-control instrumentation
  (`assign` / `record` / `report`; balanced 3-arm assignment, chi-square readout). Awaiting real
  applications. `python3 p0e_callback_ab.py report`.
- **P0-B** (ATS-feed coverage) result lives in `data/spikes/p0b.json`: **32%** free-API reachability
  on a market-weighted archetype sample → owned feed is **seed-only**, the extension is load-bearing.

Each spike writes `data/spikes/<id>.json` (keyed by an `"id"` field like `"P0-D"`); the dashboard
tracker shows whatever is present. Tests: `python3 -m unittest test_harvest test_p0e`.
