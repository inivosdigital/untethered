# V1 Data Architecture Brief — Extension-Led Remote Healthcare/RCM Job App with Floor-Truth Pay

## Recommended V1 Stack

The architecture has **two legally distinct halves**: (A) a server-side inventory you own/cache from clean direct-from-source feeds, and (B) an in-browser scoring overlay that reads boards the user already loaded. Keep them separate in your head and in your contracts — they answer different legal questions.

**CORE — server-side inventory (cache, normalize, own):**

| Source | Why it's core | RCM fit |
|---|---|---|
| **Greenhouse Job Board API** (`boards-api.greenhouse.io`) | Free, no-auth GET, explicitly public, designed for third-party job sites. `updated_at` enables cheap diffing. | Health-tech RCM-adjacent: Natera (Revenue Cycle Analyst – Prior Auth), Spring Health (Revenue Ops). Top end of ICP. |
| **Lever Postings API** (`api.lever.co/v0/postings`) | Strongest pro-aggregation language anywhere — Lever's own docs say postings "may be scraped by third parties." `workplaceType` gives a clean remote flag. | Venture-backed digital-health revenue-ops/CSM/analyst. |
| **Ashby Public Posting API** | Free, unauthenticated, `includeCompensation=true` often returns real pay — directly feeds your $30/hr floor filter. | Clipboard Health + modern health-ops startups. |
| **USAJOBS API** (OPM) | The only source that *openly invites* commercial redistribution. Public-domain federal data. Zero legal risk. | Underrated beachhead: VA, IHS, military health, CMS — patient access, HIM/medical records (series 0669), medical billing, revenue/finance (0503/0510). |

**SUPPLEMENTAL — server-side, free, attribution-gated:**
- **SmartRecruiters Posting API** — opportunistic hospital/staffing-firm RCM roles.
- **Remotive + Jobicy + Himalayas + RemoteOK** — free JSON, attribution + deep-link, no re-syndication to other aggregators. Jobicy has a real Healthcare category; all four carry health-tech CSM volume.
- **We Work Remotely** — use the **public RSS** (`/remote-medical-and-health-jobs`, `/categories/remote-customer-support-jobs`), **not** the partner API (anti-compete clause). Attribution only.

**THE OVERLAY (your real moat) — not an ingestion pipeline:**
- The **browser extension** scores **LinkedIn / Indeed / WWR / Workday CXS** pages the user already opened, client-side, in their own session. This is where the bulk of true RCM volume lives (high-frequency patient-access, eligibility, denials, billing/AR seats are concentrated at **Workday** shops: R1 RCM, Waystar, Ensemble, Humana, CVS/Aetna).

**Enrichment layer (low-risk, both halves):**
- Parse **JobPosting JSON-LD (schema.org)** from employer career pages — machine-readable data the employer *published to be read*. Clean way to enrich detail in-place.

**Explicitly DO NOT architect around:**
- **Indeed Publisher/Search API** — dead (deprecated, employer-side only).
- **JSearch** — prototype/coverage-fill *only*; it resells scraped LinkedIn/Indeed/Glassdoor data, so it imports the highest downstream redistribution risk. Never a production backbone.
- **Adzuna** — its free key is *not a license to ship*; production requires a written commercial agreement (14-day trial + no-aggregation clause). Park it until you've emailed for commercial consent; do **not** make it core for V1 despite broad coverage.
- **Remote.co / DailyRemote / Arbeitnow** — non-commercial ToS or no feed.

> **Honest gap up front:** the clean free ATS channel (Greenhouse/Lever/Ashby/SmartRecruiters) covers the *health-tech analyst/CSM/revenue-ops top end* well but covers **zero** of the marquee legacy RCM employers. Those are all on Workday, reachable only via the unofficial CXS endpoint — which is exactly why the extension model is load-bearing, not optional.

## Is the Browser-Extension Overlay Legal & Free?

**Verdict: Viable — free, and legally defensible — *only if* you hold to a strict client-side, score-don't-store discipline.** The overlay is materially safer than a hosted scraped board, but it is **not** immune to breach-of-contract or account bans. Treat the following as hard constraints, not nice-to-haves.

**Why it's defensible (precedent):**
- **hiQ v. LinkedIn** (9th Cir. 2022): accessing *public* data is not CFAA "unauthorized access." (But note: LinkedIn still won a permanent injunction on **ToS-breach** grounds in Dec 2022 — CFAA is not the whole story.)
- **Meta v. Bright Data** (N.D. Cal. 2024): ToS do **not** bind a non-logged-in non-"user," and do not bar logged-off scraping/sale of public data.

**Hard constraints (the difference between defensible and not):**
1. **Client-side only.** All reads happen in the user's own browser, on a page they already navigated to. **No server-side fetching of gated/logged-in pages** — that re-creates the hiQ/JSearch problem and forfeits the Bright Data posture.
2. **Score, don't re-host.** Do **not** centrally cache full verbatim job descriptions from LinkedIn/Indeed/Workday. Score in-page; store at most factual fields + your score + a deep link. (Verbatim long descriptions are employer copyright; central re-hosting is the copyright/misappropriation exposure — recall hiQ paid a $500k stipulated judgment on *state-law tort* theories even after winning on CFAA.)
3. **No salary-field ingestion.** Indeed/Glassdoor salary numbers may be shown as **ephemeral on-page context** only; never store/redistribute them as your dataset.
4. **Account-ban mitigation.** The user, not your servers, bears any ToS exposure — so (a) never automate navigation/clicks or paginate on the user's behalf; the extension reads what's *already on screen*. (b) Disclose clearly in onboarding. (c) Throttle nothing because you initiate nothing.
5. **Store-policy mitigation (Manifest V3).** Single-purpose, minimal host permissions (only the boards you score), no remote code, transparent privacy disclosure. The risk here is store review, not litigation — keep the manifest narrow and the data flow auditable.

**Residual risk you should name to the founder:** California trespass-to-chattels / misappropriation survives hiQ, and a board can still ban a user account or send a C&D. The overlay lowers exposure by an order of magnitude vs. central scraping; it does not zero it.

## Pay-Truth Data Plan

**Free estimate layer (ship now) — the U.S. government stack is the only legally clean, commercial-OK, percentile-grade option:**

- **BLS OEWS (core engine)** — public domain (17 U.S.C. §105), commercial use/caching/derivation all permitted. Gives **title (SOC) × geography × 5 wage percentiles (10/25/50/75/90), hourly + annual.** BLS itself labels the 10th/25th/75th as *entry / upper-entry / experienced* — exactly the "realistic-entry floor, not incumbent average" framing you want. Top-coding only hits high-wage occupations, so RCM floors come through clean.
  - **Ingestion:** download the **annual flat files** (no auth, no rate limit) into your own DB; use the **BLS API v2** (free key, 500 q/day) only for refresh. The bulk files also expose **NAICS industry cuts** (622 hospitals, 524114 health insurers) — use these to isolate *healthcare-sector* RCM wages rather than the all-industry blend. Materially better floor truth.
- **O*NET (CC BY 4.0)** — **taxonomy/crosswalk layer, not a pay source.** This is the linchpin: rich alternate-title lists map noisy scraped titles ("denials & appeals specialist," "eligibility coordinator," "patient access rep") onto a canonical SOC for the OEWS lookup. Without this, the whole scoring pipeline is guesswork.
- **CareerOneStop Salary API (supplemental)** — a free, pre-joined OEWS wrapper (free-text title → percentiles). Accelerator, not foundation: its license says data "will not be modified or altered," expires 36 months, and DOL can terminate at will. Use it for quick metro-vs-national comparisons; always keep raw OEWS as the fallback so you're free to reframe percentiles as a "floor."
- **DOL OFLC H-1B/LCA disclosure (differentiated supplemental)** — public-domain, individual-record employer + title + offered wage + **DOL Wage Level I = literal "entry-level"** marker, cross-checkable against OEWS 10th/25th. Great independent floor signal for the *higher-skill* end (RCM analyst, health-tech CSM); thin for hourly patient-access/billing roles that are rarely sponsored.

**Granularity you can honestly promise in V1:** SOC-title × worksite-geography × percentile band, healthcare-industry-cut where available.

**The honesty caveat you must surface in the UI:** OEWS reflects **worksite geography, not remote pay**, and lags ~12 months. Label the estimate as **geo-anchored, not remote-specific** (derive a remote-equivalent floor from national or a high-cost blend, or the user's home metro). Do not imply real-time remote precision you don't have.

**Crowdsourced moat (the asset gov data can't give you):**
- **Give-to-get:** users unlock peer pay by reporting their own — exact title, employer (optional), remote/onsite/hybrid, metro, hourly rate, shift, years, certs (CPC, CRCR). This fills OEWS's two real gaps: **remote-specificity** and **sub-SOC RCM granularity** ("remote denials analyst, 3 yrs, $28/hr").
- **Anchor early sparse data** against OEWS percentiles + LCA wage levels so the cold-start isn't noisy.
- **Two non-obvious legal duties — design for them now:**
  1. **Privacy (GDPR/CCPA/CPRA):** explicit consent, frame around roles/market not identifiable individuals, honor access/deletion, truly anonymize before display.
  2. **Antitrust:** DOJ (Feb 2023) and FTC (Jul 2023) **withdrew the comp-data-exchange safe harbors** — the old "safety zone" is gone. Mitigation: keep it **worker-facing**, **never sell employer-side benchmarking**, and still honor the old safe-harbor mechanics defensively (**≥5 contributors per stat, no single source >25%, data ≥3 months old, aggregated so no individual is identifiable**).

## RCM Employer Coverage

Honest, segmented read:

| ICP segment | Coverage | Source path |
|---|---|---|
| **Health-tech analyst / revenue-ops / CSM** (top of ICP) | **Good** | Greenhouse, Lever, Ashby (free, clean, cached server-side) |
| **Federal health ops** (VA, IHS, CMS, military health) | **Good & zero-risk** | USAJOBS (commercial-OK) |
| **Legacy RCM enterprise** — patient access, eligibility, denials/appeals, billing/AR at R1, Waystar, Ensemble, Humana, CVS/Aetna | **Only via the extension overlay** | Workday CXS, read in-page in the user's browser. **No clean free server-side path exists.** |
| **Remote-native niche boards** | **Thin for true RCM**, usable for health-tech CSM | Remotive/Jobicy/Himalayas/WWR-RSS |

**The structural truth:** the marquee, high-*volume* hourly RCM seats (the core of the beachhead) are almost entirely on **Workday**, which has no public API and sits behind Akamai bot management. You **cannot** cover them with cached free feeds — server-side scraping gets blocked in minutes *and* carries the higher legal risk. The **extension is the only viable coverage mechanism** for the heart of the beachhead. This is the single most important architectural fact in this brief: your free server-side inventory is a *supplement*; the overlay is where the beachhead actually lives.

## Cost & Effort

**Free at V1 and well into scale:**
- All core ATS feeds (Greenhouse/Lever/Ashby/SmartRecruiters) — free, no-auth, ~1 day integration each.
- USAJOBS, BLS OEWS (files + API), O*NET, CareerOneStop, LCA data — all free, public-domain/CC-BY.
- Remote-niche feeds — free with attribution.
- The extension overlay — free (cost is engineering + DOM-maintenance, not data licensing).
- Crowdsourced pay — cost is **product/eng + compliance**, not licensing.

**Becomes paid only when you choose to scale specific things:**
- **Adzuna** — needs a negotiated commercial agreement (sales conversation) before production use.
- **JSearch** — cheap to prototype (200 free req/mo), expensive and legally risky at production scale → don't.
- **ZipRecruiter Publisher** — Phase-2 *monetization* channel (revenue-share on clicks), not a V1 data source.
- **Google Cloud Talent Solution** — pay-as-you-go *ranking* engine over jobs you already own; a later relevance-layer upgrade, never a listings source.

**Net:** V1 data + pay layer is **$0 in licensing.** Your real spend is engineering: extension DOM adapters, OEWS/O*NET ingestion + SOC crosswalk, and the crowdsource product. The first paid line item is whatever *you* decide to scale (Adzuna agreement or ZR monetization), not a V1 requirement.

## Pre-mortem

| # | Failure mode | Mitigation |
|---|---|---|
| 1 | **Legal takedown / C&D from a board** (LinkedIn-style ToS-breach, even post-hiQ) | Keep overlay strictly client-side + score-don't-store; never re-host verbatim descriptions; no server-side fetch of gated pages; written commercial agreements before relying on Adzuna; lean on the genuinely-permissive sources (USAJOBS, Greenhouse/Lever, OEWS) as the irremovable spine. |
| 2 | **Feed shut-off** (the Indeed-Publisher precedent — a free source closes the door) | Don't single-source. Multi-ATS + government spine means no one shutoff is fatal. Treat any *undocumented* endpoint (Workday CXS, Working Nomads) as ephemeral-by-design and route it through the extension so a server-side block can't take you down. |
| 3 | **DOM fragility** (LinkedIn/Indeed/Workday change markup; overlay silently mis-scores) | Per-board adapter modules with versioned selectors; prefer **JobPosting JSON-LD** over raw DOM where present (far more stable); automated canary checks that alert on selector breakage; graceful degradation (show "couldn't parse this page" rather than a wrong score). |
| 4 | **Thin RCM coverage from free sources** (server-side inventory misses the legacy giants) | Acknowledge it: the extension *is* the coverage strategy for legacy RCM. Lean USAJOBS hard for federal health ops; mine O*NET alternate titles so you catch RCM roles hiding under nonstandard titles on the boards the user browses. |
| 5 | **Stale / mislabeled pay estimates** (OEWS lags 12mo, is worksite- not remote-pay, users feel misled) | Label estimates as *geo-anchored, entry-percentile, ~12mo lag* explicitly in-UI; use healthcare NAICS cuts for tighter floors; cross-check with LCA Wage Level I; **prioritize the crowdsource moat** so real remote RCM pay replaces estimates fastest exactly in your densest beachhead. |
| 6 | **Crowdsource cold-start + compliance blowup** (sparse early data is noisy; or a privacy/antitrust misstep) | Anchor sparse data to OEWS/LCA; enforce ≥5-contributors / no-source->25% / ≥3mo-old / aggregated thresholds from day one; worker-facing only, never sell employer benchmarking; explicit consent + deletion rights. |

## Open Decisions for the Founder

1. **Adzuna: pursue the commercial agreement, or skip?** It would broaden coverage meaningfully, but it's a sales conversation + no-aggregation clause. Decision: is the coverage worth the negotiation and the dependency, given the free spine already exists?
2. **Workday CXS via extension — how aggressively?** This is the heart of beachhead coverage *and* the highest-friction, "no" commercial-use ToS source. How much legal appetite do we have for reading it in-page, and do we want counsel to bless the client-side posture before we ship it as a headline feature?
3. **How prominent is the score-don't-store line?** Are we comfortable *never* caching full descriptions from gated boards (the safe posture), accepting that some product features — e.g. server-side search across LinkedIn jobs — are simply off the table in V1?
4. **Pay-estimate honesty vs. polish.** How explicitly do we surface the "geo-anchored, not remote, 12-month lag" caveat? More honesty = more trust but less magic. Where's the line?
5. **Crowdsource incentive design.** Give-to-get gating is the obvious lever — but how hard do we gate (and risk friction / Remotive-style "don't gate listings behind signup" concerns for *displayed feed* listings vs. *peer pay*)?
6. **Counsel sign-off timing.** Do we want a one-time legal review of (a) the extension posture and (b) the crowdsource antitrust/privacy design *before* launch, given the safe harbors were withdrawn in 2023?
7. **When do we layer in paid ranking (Google CTS) and ZipRecruiter monetization** — and does adding ZR's revenue-share feed change our "score-don't-store" purity?

---

**Files:** none — this brief is the deliverable, returned inline above. No source files were read or written.