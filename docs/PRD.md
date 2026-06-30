# Untethered — Product Requirements Document (V1)

**Status:** Draft for founder review · **Date:** 2026-06-30 · **Owner:** Product

> Working product name: **Untethered**. This PRD is the capstone of three research workflows
> (competitive landscape, career level-up, data architecture) plus a live worked example on a
> real candidate. Source briefs live in [`docs/research/`](./research/). Every claim here traces
> to that research; every feature here survived an independent adversarial pre-mortem.

---

## 1. Vision

**Untethered is the honest income coach for people who are already qualified for better-paid remote
work and don't know it.** It's a browser extension + companion app that scores any remote job for
*real fit*, *real pay*, and *real-remote / not-a-scam* as you browse — then walks you up an honest,
month-by-month staircase to $30/hr and beyond. We start with one beachhead: **healthcare
revenue-cycle (RCM) and patient-access roles.**

**The one sentence no incumbent can answer for our user:**
> *"Show me only fully-remote roles in my field that pay at least $30/hr, confirmed by the employer,
> are genuinely open, and aren't scams."*

That sentence is unbuildable today on Upwork, Indeed, ZipRecruiter, LinkedIn, Wellfound, FlexJobs,
RemoteOK, Jobright, or Toptal. It is our wedge.

---

## 2. The Problem

The remote-job market is large but **trust-broken**, and it fails one specific worker the same three
ways:

1. **Pay is unfilterable, hidden, or fictional.** No major destination offers a clean, employer-
   *confirmed* hourly filter. Upwork/Wellfound/Jobright/RemoteOK have no $/hr filter; ZipRecruiter/
   Indeed inject *estimated* (fabricated) pay; FlexJobs paywalls discovery and still hides pay.
2. **Listings can't be trusted to be real, remote, or safe.** ~1 in 3 US postings are ghost jobs
   (~50% in **health services** — our exact field); "remote" routinely means hybrid/region-locked;
   and FTC job-scam losses hit **~$501M (+95% in two years)**, concentrated in **data-entry / VA /
   healthcare-admin** — our user's exact niche.
3. **Fit scores are opaque, inflated, or recruiter-facing.** The one precise score on the market
   (Jobright's 0–100%) is the *least* trusted — under-explained, inconsistent, and its companion
   auto-tailoring *fabricates credentials* the user never had.

And underneath all of it: the people most hurt are **already qualified but mislabeled** — their
résumés describe them in the wrong vocabulary, so an ATS files a $30 candidate into a $20 bucket.

---

## 3. Target User (V1)

**Primary persona — "the mislabeled 80%."** A US-based remote worker with real, transferable
experience whose résumé undersells them into a lower pay band. Concretely, the validation persona:

- 8+ yrs customer-service / healthcare-operations experience: eligibility & benefits verification,
  claims, denials/AR, medical billing, EHR, scheduling, Salesforce.
- **No bachelor's degree.** Budget-sensitive. Bilingual (EN/ES) is common and monetizable.
- Hard goal: **fully-remote work at $30/hr minimum.**
- Reads to an ATS as "Customer Service / Admin" (~$16–24/hr) but is latently a "Revenue Cycle /
  Patient Access Specialist" (~$25–34/hr).

**Why this wedge:** highest hit-rate (they really are qualified, so honest claims are *easy*),
cheapest to serve, and the place every incumbent is structurally weakest.

**Beachhead vertical:** **Healthcare revenue-cycle / patient-access.** Reasons: huge and genuinely
remote-friendly; a clear, cheap credential ladder (CHAA, CRCR); ATS-keyword-driven hiring (so the
résumé reframe bites hardest); and it's where ghost jobs and scams cluster (so trust features matter
most). We expand to adjacent remote ops/admin/CS verticals only after proving outcomes here.

**Explicit non-goals for V1:** cold career-changers starting from zero; tech/engineering roles
(well-served by incumbents); general "all remote jobs" breadth (dilutes the wedge).

---

## 4. Positioning & Principles

**Positioning:** *"The only job feed where every remote role shows a real, employer-confirmed hourly
wage — and only ones that clear your floor, are genuinely open, and aren't scams — built for the
non-degreed healthcare-ops worker that FlexJobs paywalls, Toptal rejects, and Wellfound ignores. And
when you're not there yet, it coaches you up the ladder instead of leaving you to guess."*

**Product principles (these are also our legal and trust guardrails):**

1. **Honesty is the moat.** We say the true thing even when it's a worse sales pitch — including
   "this path stalled," "this job pays below your floor," and "don't buy that cert yet."
2. **No absolute claims on probabilistic systems.** Every badge is a *confidence signal* with visible
   evidence and a timestamp — never "verified remote," "confirmed open," or "guaranteed $30."
3. **We never bet against the user's paycheck.** Subscription / employer-side only. No ISAs, no
   outcome-financing, no escrow stakes. This is what *lets* us give honest advice.
4. **Income now + ladder, never a red light.** We never tell a budget-constrained user to decline
   winnable income; sub-floor roles appear only when framed as an on-path rung.
5. **Never fabricate.** The résumé tool reframes only what the user actually did; the fit tool never
   invents skills. Every reframed line has a "defense sheet" the user could survive a screen on.
6. **Realistic-entry, not incumbent-average.** Pay estimates anchor to entry/upper-entry percentiles
   and show the full distribution, including the share of users who *don't* reach $30.

---

## 5. Product Model — Two Layers, Two Modes

### 5.1 Two layers (kept legally distinct)

| Layer | Job | Why |
|---|---|---|
| **The extension (overlay)** | Scores jobs **in-page**, client-side, on boards the user already opened (LinkedIn, Indeed, WWR, **Workday**). | Kills cold-start (works on any board day one) **and** is the *only* viable way to reach the heart of the beachhead: legacy RCM employers (R1, Waystar, Ensemble, Humana, CVS/Aetna) live on Workday, which has no clean free server-side path. The extension is **load-bearing, not optional.** |
| **The owned feed** | A curated, cached spine from clean **free** direct-from-source feeds. | Greenhouse / Lever / Ashby ATS APIs (health-tech RCM, some employer-confirmed pay) + **USAJOBS** (federal health ops, commercial-OK) + remote-niche feeds (supplemental). |

**Hard discipline (non-negotiable):** the extension is **client-side, score-don't-store**. No
server-side fetching of gated pages; no central re-hosting of verbatim job descriptions; salary
numbers on third-party pages are ephemeral on-page context only, never ingested as our dataset. This
keeps us on the defensible side of *hiQ v. LinkedIn* and *Meta v. Bright Data* and out of copyright/
misappropriation exposure. (See §9.)

### 5.2 Two modes (resolves the core design tension)

The wedge promise ("every job clears $30") and the coaching promise ("we walk you up to $30") need
different views, because the user's **best first move often pays below the floor**:

- **Floor Mode** — only employer-*confirmed* ≥$30/hr, fully-remote, scam-screened roles. The pure
  wedge. The floor is never silently violated.
- **Staircase Mode** — also surfaces on-path **bridge** roles *below* the floor, explicitly tagged
  *"Step 1 — below your floor, but builds the title + keywords that get you there in ~6–12 months."*

Sub-floor jobs appear **only** when framed as a rung. Both promises stay honest simultaneously.

---

## 6. V1 Feature Scope

Each feature is shaped by its adversarial pre-mortem. "Honesty constraints" are acceptance criteria,
not nice-to-haves.

### 6.1 Mislabel Diagnosis + Résumé Re-Frame Studio  *(the free wedge)*
- **What:** Detects the user's current vs. latent title bucket and rewrites real experience into the
  keyword bucket that clears the ATS for $30 roles. Outputs a reframed résumé + a "defense sheet."
- **Why:** Cheapest, fastest, most defensible income lever — the user genuinely *is* mislabeled.
- **Honesty constraints:** Zero invented skills; every reframed line backed by real experience.
  **Instrument callback rate** (before/after) so the tool can see — and admit — its own failure.
- **Pre-mortem fix applied:** Don't position as "the only lever"; it's Step 0 of a sequenced plan.

### 6.2 Floor-Truth Pay  *(the differentiator)*
- **What:** For any job, an honest hourly read: **employer-confirmed** (from ATS comp fields) vs.
  **estimated** (from BLS OEWS). Sort-first, with Floor/Staircase modes.
- **Why:** No competitor offers confirmed, sortable $/hr; the rest fabricate it.
- **Honesty constraints:** Never assert a wage we didn't get from the employer/ATS. Estimates are
  labeled *geo-anchored, entry-percentile, ~12-mo lag*. **"No posted range" is the base case** (most
  remote postings hide pay), shown as third-party market context, never an individualized claim.
- **Pre-mortem fix applied:** Ship **sort-first, not default-on filter**, to avoid the empty-feed
  churn event; "confirmed" must be real-data-backed or it inverts the trust wedge.

### 6.3 Fit Checklist  *(not a score)*
- **What:** A private **requirement-coverage checklist** per job: ✅ matched / ⚠️ partial /
  ❌ missing, tuned for RCM. Missing items feed the Staircase.
- **Why:** Every rival's fit signal is opaque, inflated, or recruiter-facing.
- **Honesty constraints:** **No public 0–100 score in V1** — we have no score→callback calibration
  data yet, so a number would be unbackable "false confidence." Earn the number later with outcomes.

### 6.4 Trust Signals  *(real / really-remote / not-scam)*
- **What:** Per-listing confidence reads: freshness ("still listed 6h ago"), remote-reality (surfaces
  buried "must reside in X" clauses), and scam screen (off-platform contact, pay-realism mismatch,
  unverifiable employer).
- **Why:** Our user's niche is the scam + ghost-job epicenter; nobody screens at the listing level.
- **Honesty constraints:** Confidence signals with evidence + timestamp, **never absolute badges.**
  Keep the scam screen and the pay filter *orthogonal* — a high wage is a flag input, not proof of
  fraud, and never silently hides a legit high-paying job.

### 6.5 Income Staircase  *(the retention engine)*
- **What:** A personalized 12/24/36-month plan from the user's résumé + target rung, with bridge
  roles, branch points, and an **"is this path still alive?"** honesty check.
- **Why:** Turns a one-shot job search into a multi-year relationship; the near-term paid win funds
  the climb (directly attacks the ~21% AI-coach retention problem).
- **Honesty constraints:** **Substantiated probability ranges, not fabricated dates.** Always show
  the realistic month-12 outcome (titled bridge, $26–29) vs. the sustained-$30 milestone (~mo 18–24).
  Point users to **free public funding (WIOA/CareerOneStop) before any paid cert.**

### 6.6 Input-Based Accountability
- **What:** Streaks/check-ins on **apps sent and reframes done** — never offers landed — with an
  optional community/human touch at demoralizing moments.
- **Honesty constraints:** **No money at stake, ever.** We never financially penalize a user for a
  slow market. (The escrow-stake variant is deferred until counsel clears it — see §11.)

---

## 7. The Income Staircase Model (reference)

The honest promise is a staircase, **not** "$30 in 12 months" (that headline is the exact FTC /
false-hope claim that got the accelerator cluster — e.g. BloomTech — banned).

| Step | When | Move | Outcome (real research figures) |
|---|---|---|---|
| **0 — Reframe & target** | Wk 1–4 | Résumé reframe + apply only to in-bucket, real, ≥$25 roles | More callbacks · **$0** |
| **1 — The bridge** | Mo 0–3 | Land a *titled* Patient Access / Eligibility / Denials role | **~$25–29/hr** (a real raise; right title) |
| **2 — The $30 rung** | Mo 6–24 | **CHAA** ($179) + **CRCR** (~$400) + on-the-job **Epic** exposure | **RC Analyst → $30–34/hr** ✅ |
| **3 — The ceiling** | Mo 24–36 | Senior RC Analyst, or add Salesforce **Health Cloud** | **$35–45/hr** |

**Backup track (parallel, free):** reframe toward **health-tech CSM / Implementation** ($30–34/hr).

---

## 8. Data & Pay Architecture

**Net cost of the V1 data + pay layer: $0 in licensing.** Spend is engineering, not data.

**Listings — core (free, cached server-side):** Greenhouse Job Board API, Lever Postings API (its
docs explicitly invite third-party aggregation), Ashby (`includeCompensation=true` → real pay),
**USAJOBS** (the only source that *invites* commercial redistribution). **Supplemental:** Remotive /
Jobicy / Himalayas / RemoteOK / We Work Remotely **RSS** (attribution, no re-syndication). **The
overlay** covers the high-volume legacy RCM seats on Workday (read in-page only).

**Do NOT architect around:** Indeed Publisher/Search API (dead), **JSearch** (resells scraped data —
prototype only), **Adzuna** as core (free key is *not* a license to ship — needs a written commercial
agreement first).

**Pay-Truth (free estimate layer, ship now):**
- **BLS OEWS** = the engine. Public domain; gives title (SOC) × geography × wage percentiles
  (10/25/50/75/90); BLS itself labels 10th/25th as *entry/upper-entry* — exactly our "realistic floor"
  framing. Ingest the annual flat files; use the API only for refresh; use NAICS healthcare cuts for
  tighter floors.
- **O\*NET** = the crosswalk linchpin: maps noisy job titles → canonical SOC for the OEWS lookup.
- **CareerOneStop** + **DOL LCA** = supplemental floor signals.
- **UI honesty caveat:** OEWS is worksite-geo (not remote-specific) and lags ~12 mo — label it so.

**Pay-Truth (crowdsourced moat, the asset gov data can't give):** give-to-get peer pay (title,
employer-optional, remote/onsite, metro, hourly, certs). Fills OEWS's two gaps — remote-specificity
and sub-SOC RCM granularity. **Compliance built in from day one:** worker-facing only; never sell
employer-side benchmarking; honor the (withdrawn-but-defensive) safe-harbor mechanics — **≥5
contributors per stat, no single source >25%, data ≥3 months old, fully anonymized**; explicit
consent + deletion (GDPR/CCPA).

---

## 9. Claims, Legal & Trust Guardrails

This section is the product's spine, not boilerplate. The accelerator cluster got rich and then
radioactive on exactly these mistakes.

1. **No outcome guarantees, no individualized earnings predictions.** Third-party-sourced ranges +
   standing no-guarantee disclaimer only. (FTC 2024–25 enforcement: BloomTech, Operation AI Comply,
   the proposed earnings-claim rule.)
2. **Per-claim substantiation file** — every number we show carries source + date + confidence; legal
   review of any multi-user claim before launch.
3. **Extension discipline** (§5.1): client-side only, score-don't-store, no verbatim re-hosting, no
   server-side fetch of gated pages, narrow Manifest V3 permissions, clear onboarding disclosure.
4. **No ISA / no escrow stakes without consumer-finance counsel.** "This is not a loan" is *legally
   false* for outcome-tied wrappers (CFPB has ruled ISAs are loans).
5. **Bias / fair-lending review** of any steering logic (incl. "monetize your Spanish") before a
   second user; adverse-impact awareness (NYC LL144 / EU AI Act / AEDT) for any scoring.
6. **PII/PHI handling:** résumé redaction, explicit consent, deletion rights.

---

## 10. Monetization & Moat

> Revised per the employer-program pressure-test ([`docs/research/employer-program-pressure-test.md`](./research/employer-program-pressure-test.md)).

- **The moat is NOT the employer program.** It is **(a) the pre-screened pool of *US-remote-defensible*
  candidates** in a tight niche, and **(b) the crowdsourced confirmed-pay dataset.** The employer
  program *monetizes* those — but the pool + data is the durable, defensible asset. This distinction
  is the leverage that keeps us honest: because we don't *need* employer revenue to have a business,
  we can walk away from any employer who wants us to soften the policing.
- **"US-remote-defensible" is a hard targeting rule, not a flavor.** 97% of healthcare orgs outsource
  RCM and offshore Asia is ~60% of healthcare BPO at 50–70% labor savings — the commoditized
  back-office is racing offshore. Steer both sides toward **offshore-resistant, higher-ACV roles**
  (bilingual patient-facing, complex denials/appeals needing US payer knowledge, compliance-sensitive,
  RC analyst) and away from commodity data-entry billing. These are also the $30+ Staircase
  destinations and where the target user's edge matters.
- **V1 monetization — lead with the conflict-free wallets:**
  - **Consumer subscription** (coaching tier: Staircase, human-in-the-loop résumé/appeal review,
    accountability). Zero conflict.
  - **Aligned B2B:** RCM **staffing firms** and **workforce-development funders** (colleges, WIOA,
    Year-Up-style nonprofits whose *funders* pay to place graduates) + employer **L&D budgets** — a
    $45B→$82B staffing market that already buys external sourcing, with interests aligned to the worker.
- **The pay-transparent-employer program = a Phase-3, gated monetization *layer*** (not the launch
  moat). Hard structural rules, each evidence-backed by the Glassdoor/Indeed/Yelp precedent:
  1. **Entry is gated by the same trust criteria we police** (confirmed ≥$30, true-remote, no scam
     patterns, acceptable churn). Passing the bar *is* the price of admission → adverse selection
     flips to positive selection, and money can't buy a softer flag.
  2. **Structural (auditable) separation of revenue from ranking/moderation** — not a policy promise.
  3. **Remove — never merely deprioritize — bad-faith listings** (the Indeed lesson).
  4. **Money buys access + a behavior-earned, revocable, public-criteria badge — never rank.** Paid
     surfaces are plainly labeled.
  5. **Subscription/access pricing, never per-placement agency fees; never charge the worker** (the
     licensing-safe posture — NY §191 "employer fee paid" / MA "placement agency" tiers; register
     where workers are placed: NY/IL/NJ/MA).
  6. **Retention-aligned** where a success component is used (Hired's 1%×24mo analog) — our revenue
     screens out churn-and-burn employers. *(Counsel-vetted; subscription core to stay a platform.)*
  7. **Never sell employer-side comp benchmarking** (antitrust + it weaponizes worker data).
- **Later channels:** ZipRecruiter publisher revenue-share (Phase 2); Google Cloud Talent Solution as
  a paid *ranking* upgrade over jobs we already own.
- **Hard rule:** revenue never comes from betting against the user's paycheck.

---

## 11. Out of Scope / Deferred (V1)

- **"One cert away" unlock as a confident recommender** — *unanimous* red-team cut. The labor math is
  backwards for a switcher (fresh cert + zero experience ≈ $17–20/hr, often onsite-first, *below* her
  current pay), and a paid "spend $X → earn $Y" claim is BloomTech-grade FTC exposure on N=1 data.
  Reframe later as a hedged, freshness-dated *information* tool with a free-funding off-ramp and
  profile-match abstention. Ship only after an instrumented cohort proves real pay-lift.
- **Public 0–100 fit score** — deferred until score→callback calibration data exists (§6.3).
- **Financial-stake accountability / escrow** — deferred until counsel clears a structure surviving
  CFPB precedent (§6.6).
- **Medical-coding (CPC) path** as the 12-month lever — research shows sustained remote $30 is an
  18–30-month reality; not a V1 promise.
- **Verticals beyond healthcare RCM**, and **non-mislabeled cold career-changers.**

---

## 12. Success Metrics

**North Star:** *# of users who reach a confirmed pay raise on-platform* (the honest outcome no
incumbent measures).

| Layer | Metric |
|---|---|
| Wedge works | Callback-rate lift post-reframe (the instrumented honesty metric) |
| Trust works | % of scam/ghost listings correctly flagged; user-reported "saved me from" events |
| Pay-truth works | Coverage: % of viewed jobs with a confirmed-or-estimated pay read; estimate error vs. crowdsourced actuals |
| Retention works | Week-2+ retention vs. the ~21% AI-coach benchmark; staircase milestone completion |
| Moat builds | # pay-transparent employers; # crowdsourced pay datapoints meeting the ≥5/≥3-mo thresholds |
| Honesty holds | Zero substantiated-claim violations; complaint/refund rate vs. accelerator benchmarks |

---

## 13. Key Risks (cross-cutting pre-mortem themes)

1. **Absolute claims on probabilistic systems** → reframe every badge as a confidence signal (§4, §9).
2. **No validated/legal data source** → free ATS + government spine; extension discipline (§8, §9).
3. **Cold-start empty feed** for the exact target persona → sort-first, Staircase Mode, extension
   works on any board day one (§5).
4. **Calibration void** → checklist before score; don't market accuracy we can't back (§6.3).
5. **No demand side** → the pay-transparent-employer program is funded as the product (§10).
6. **Harm to a vulnerable user** → income-now-not-red-light; no financial stakes; bias/PII rails (§4, §9).
7. **False hope / FTC** → staircase not sprint; realistic percentiles; free-funding-first (§7, §9).

---

## 14. Open Decisions for the Founder

1. **Counsel timing:** one-time legal review *before* launch of (a) the extension/Workday-CXS
   posture, (b) the crowdsource antitrust/privacy design, and (c) **employment-agency exposure** —
   confirm the subscription/never-charge-the-worker posture and which states need registration (NY/
   IL/NJ/MA keyed to where workers are placed), plus the *Mobley v. Workday* "matching = agency/agent"
   risk on the fit-score.
2. **Adzuna:** pursue the commercial agreement for breadth, or stay on the free spine?
3. **Score-don't-store line:** confirm we're OK *never* caching gated-board descriptions in V1 (rules
   out server-side search across LinkedIn jobs).
4. **Monetization sequencing:** the pressure-test says lead with consumer subscription + staffing-firm/
   workforce-funder B2B, and treat the policed-employer program as a gated Phase-3 layer (not the
   launch moat). Confirm we're aligned — and who owns the eventual employer-side go-to-market?
5. **Retention-fee vs. pure subscription:** do we want a retention-linked employer success component
   (best alignment) accepting the added agency-licensing scrutiny, or stay pure-subscription (cleanest
   legally, less outcome-aligned)?
6. **Pay-estimate honesty vs. polish:** how prominently do we surface the "geo-anchored, ~12-mo lag"
   caveat? (Note: the pay-transparency-law tailwind means confirmed ranges on remote postings will
   grow on their own.)
7. **Persona scope discipline:** stay all-in on healthcare RCM (offshore-resistant roles first) until
   outcomes are proven, or widen sooner?

---

## 15. Phased Roadmap (indicative)

- **Phase 0 — Validate (pre-build):** confirm live inventory count of fresh, in-band, fully-remote
  RCM roles; counsel sign-off on extension posture; stand up the OEWS + O\*NET pay engine.
- **Phase 1 — The wedge:** Résumé Re-Frame Studio + Fit Checklist + Floor-Truth (estimate layer) as
  the extension overlay on LinkedIn/Indeed/Workday; owned feed from Greenhouse/Lever/Ashby + USAJOBS.
- **Phase 2 — Trust + Staircase:** trust signals, Income Staircase, input-based accountability;
  begin crowdsourced pay collection.
- **Phase 3 — The moat:** pay-transparent-employer program; confirmed-pay Floor Mode at density;
  earn the calibrated fit score from accumulated outcomes.

---

*Appendix — research basis:* [`docs/research/competitive-landscape.md`](./research/competitive-landscape.md),
[`docs/research/level-up-coach.md`](./research/level-up-coach.md),
[`docs/research/data-architecture.md`](./research/data-architecture.md),
[`docs/research/worked-example-laritza.md`](./research/worked-example-laritza.md),
[`docs/research/employer-program-pressure-test.md`](./research/employer-program-pressure-test.md).
