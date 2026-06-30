# P0-A — Filtered Live-Inventory + Freshness Harvester

Implements spike **P0-A** from [`../../docs/BUILD_ROADMAP.md`](../../docs/BUILD_ROADMAP.md) — the #1
make-or-break test: **is there enough _flow_ (net-new per week), not just stock, of roles that survive
all four kill-filters?** If the answer is "single digits/week nationally," the job-board framing is
dead and the product pivots to staircase-first.

## What it does

Pulls postings from **free, no-auth ATS APIs** (Greenhouse, Lever, Ashby) + **USAJOBS** (free key),
normalizes them, and runs each through a survival funnel:

| Stage | Filter |
|---|---|
| 1 | **RCM-title-relevant** (keyword match) |
| 2 | **+ genuinely fully-remote** (rejects hybrid / "must reside in" / "X days in office") |
| 3 | **+ posted pay ≥ $30/hr** (structured fields or `$NN/hr` in text; annual ÷ 2080) |
| 4 | **+ offshore-resistant** (onshore RCM taxonomy: denials/appeals/payer-policy/patient-financial beats charge-entry/posting/coding) |
| 5 | **= QUALIFYING** (credential-accessible — no hard RN / bachelor's gate) |

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

- **Logic:** the filter funnel is unit-validated offline — each filter (remote/hybrid, pay floor,
  offshore-resistance, RN/degree gate) makes the correct call on synthetic postings.
- **Live fetch:** requires open network egress. (It will not run against the live APIs from a sandbox
  with a restricted egress policy — run it where Greenhouse/Lever/Ashby/USAJOBS are reachable.)
