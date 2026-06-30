# Untethered V1 — Build Roadmap

## How to read this

This roadmap is built on **partially-validated** evidence. Every adversarial check returned `holds-partly` and `de-risk-first`. That verdict is the spine of the plan: **validate the riskiest assumptions before writing product code**, because two of the load-bearing premises are unproven and one is contested.

**What validated (build on these):**
- **The segmentation thesis is real.** There is a documented, durable onshore-vs-offshore RCM taxonomy: complex denials/appeals, payer-policy interpretation, and US patient-financial conversations stay onshore; charge entry, posting, simple AR, eligibility, credentialing, and coding race offshore. This is a usable signal for the scorer, not a guess.
- **The pay engine is cheap, deterministic, and explainable** as *infrastructure*: BLS OEWS public-domain flat files + O*NET CC-BY crosswalk is a SOC-join, not ML. The stack (WXT/MV3, free no-auth ATS feeds, Haiku/Sonnet at ~$0.014–$0.04/resume, ZDR for PII) is settled and low-cost.
- **The "title is the highest-leverage lever" mechanism is real.** Recruiter Boolean/title search is brittle to variants; a "Customer Service Rep" title genuinely won't surface in a "Revenue Cycle Analyst" search. The *mechanism* (search-invisibility) is defensible.
- **Workday CXS / Greenhouse / Lever / Ashby / USAJOBS APIs exist and are integrable** (~1 day each). Ashby exposes real comp.

**Caution flags (build, but instrument and hedge):**
- **The free ATS feed under-represents the archetype.** Archetype-fit IC/analyst roles concentrate on LinkedIn/Indeed/ZipRecruiter, not Greenhouse/Lever. The owned feed is *not* the primary volume source — the extension is. Build the feed for reliability/seed, not for volume.
- **Pay-engine accuracy on these specific bimodal titles is the quiet risk.** "Denials specialist" spans $22 → $86k inside catch-all SOC codes. SOC averages mislead exactly here. Crowdsourced real-pay may need to ship sooner than "later."
- **Bilingual EN/ES is a 5–20% tie-breaker boost, not a path to $30/hr.** Treat it as a scoring nudge, never a headline.
- **CWS distribution risk and LinkedIn detection are live, recurring taxes** (a LinkedIn jobs scraper was pulled 2025-04-20). Single-purpose framing + Limited-Use disclosure + no-DOM-injection are mandatory, not optional.

**Must be empirically tested FIRST (do not build product around these until measured):**
1. **The filtered live-inventory + freshness numbers.** Best estimate of the genuinely-qualifying pool (≥$30/hr AND fully-remote-confirmed AND offshore-resistant AND no-bachelor's/no-RN) is **low tens at any moment nationally** — thin, not thick. Hundreds-at-any-time is *not* supported. A feed that thin can feel broken. **The make-or-break number is net-new flow/week, not stock.**
2. **The reframe → callback lift.** This is the core monetizable claim and it is **unproven**. Every favorable number (10.6x, 11.7% vs 4.2%) is vendor-conflicted, observational, confounded. Independent reviewers document 80%+ match scores with zero callbacks. No peer-reviewed study isolates the causal link. **Your own RCT is the only honest basis for the product.**
3. **Pay-estimate error on real postings.** If OEWS median absolute error >$5/hr, or it can't separate $22 commodity from $34 specialist, the "real pay" score isn't trustworthy.
4. **Extension parse reliability in the logged-in SPA DOM** (JSON-LD confirmed on *public* LinkedIn pages; UNVERIFIED in the logged-in DOM the extension actually reads) and **Workday CXS CORS from a real content script** (untested — host was egress-blocked during validation).

---

## Phase 0 — Validate Before Code (riskiest-assumption-first)

Run these *before* committing to the product build. Each is a spike with a go and a kill criterion. Sequence them roughly in parallel where possible; **P0-A and P0-E are the two that can kill the whole concept.**

### P0-A — Filtered Live-Inventory + Freshness Harvest (THE make-or-break)
**Effort: 2–4 week harvest, then ongoing 8–12 week flow tracking.**
> **Harvester implemented:** [`tools/p0a_inventory/`](../tools/p0a_inventory/) runs the free-feed half
> (Greenhouse/Lever/Ashby/USAJOBS) with the four-filter survival funnel and net-new flow tracking. The
> funnel logic is unit-validated; populate `config.json` with real ATS board tokens and run it daily.
> The LinkedIn/Indeed/ZipRecruiter half still needs **manual sampling** (can't be legally harvested).

Harvest core titles across LinkedIn / Indeed / ZipRecruiter / WeWorkRemotely + Greenhouse / Lever / Ashby / USAJOBS. Core titles = **revenue cycle analyst, denials analyst, AR analyst (analyst-titled), complex denials/appeals (non-clinical)**. Hand-label a random sample for survival through each filter: (a) ≥$30/hr posted-or-inferred, (b) genuinely fully-remote (not hybrid/state-restricted), (c) offshore-resistant per the taxonomy, (d) accessible without bachelor's/RN. Report **survival rate per filter** and **resulting daily/weekly net-new count**. Then track the same searches daily for a month to measure **flow, not just stock**.
- **GO:** Net-new qualifying roles refill at a rate that can sustain recurring engagement (enough fresh ≥$30 archetype-accessible roles per week to keep a user returning), even if stock is in the low tens.
- **KILL / PIVOT:** Net-new is **single digits/week nationally** across all sources combined, or filter survival on raw inventory is **<5–10%**. If so, the job-board framing is dead — **pivot the product to coaching-staircase-first with the feed as a destination, not the entry point** (the evidence already leans this way).

### P0-B — ATS-Feed Coverage Test
**Effort: spike (days).**
Take 50 known archetype-fit IC/analyst postings found on Indeed/LinkedIn; check how many are reachable via Greenhouse/Lever/Ashby/USAJOBS APIs.
- **GO:** Coverage informs how much seed the owned feed can carry.
- **KILL the "owned feed is primary inventory" assumption:** If coverage is **<20–30%** (likely — healthcare runs iCIMS/Taleo/Workday), the owned legal feed is *not* a viable primary inventory source. This doesn't kill the product; it **confirms the extension is load-bearing** and the feed is seed/reliability only.

### P0-C — Extension Parse Spike (LinkedIn / Indeed / Workday)
**Effort: 1–2 week proof, then a 4–6 week canary.**
Build throwaway JSON-LD-first + DOM-fallback adapters. Three separate tests:
- **LinkedIn:** On a throwaway *logged-in* account, confirm `application/ld+json` JobPosting is present in the SPA DOM the extension actually reads (not just the public page). Build a **no-DOM-injection prototype** (UI in side panel/popup only) and verify over a multi-week window that no `chrome-extension://` trace appears and the account isn't flagged.
- **Workday:** From a real MV3 content script AND a background service worker, POST to several live tenants' `/wday/cxs/.../jobs` and GET `/job/{externalPath}`. Record status, `Access-Control-Allow-Origin`, and whether `host_permissions` are required. (This was untested in validation — egress-blocked.)
- **Indeed:** Across many real logged-in viewjob loads, measure Cloudflare/Turnstile interstitial rate and JSON-LD extraction success; validate skip-and-retry.
- **GO:** Field-extraction success rate is high enough per adapter to promise coverage, and LinkedIn no-injection design stays undetected.
- **KILL LinkedIn (not the product):** If JSON-LD is absent/stripped in the logged-in DOM (forcing brittle CSS selectors), or the no-injection design still trips detection, **drop LinkedIn from V1 scope** and lean on Workday (the beachhead employers live there anyway) + Indeed + owned feed.

### P0-D — OEWS/O*NET Pay-Engine Accuracy Spike
**Effort: spike (days–1 week).**
Take 50–100 (ideally 200) real postings *with disclosed pay* across the core titles. Run the BLS OEWS + O*NET estimator. Measure: how often within ±$3/hr; how often it wrongly says "$30+"; median absolute error. Separately, evaluate the title→SOC mapper against a human-coded gold set of ~300 RCM titles.
- **GO:** Median absolute error ≤$3–5/hr, 6-digit SOC mapping accuracy ≥85%, and the engine separates $22 commodity from $34 specialist.
- **KILL the "crowdsourced pay is V2/later" plan:** If median error >$5/hr or it can't separate the two tiers, OEWS-alone is untrustworthy → **crowdsourced real-pay and/or posted-range extraction must move into V1**, and the UI must show confidence/abstain rather than a false floor.

### P0-E — Manual Resume-Reframe Callback Test (the existential one)
**Effort: spike to set up, weeks to read out (callback signal is sparse).**
Run a **within-user randomized A/B**: reframed vs control framing, alternated across comparable RCM applications, pooled into cohorts, chi-square on callback conversion. Also test the **title-correction lever in isolation** (same body, only target title/headline changed) vs full keyword reframe vs control, to learn which component drives any lift. If possible, validate the mechanism directly: does a reframed profile surface in recruiter Boolean searches it previously missed?
- **GO:** A statistically meaningful callback lift attributable to reframe (especially the title lever), with reframed resumes that also survive a 6-second human skim (recruiter-panel rating) without reading as keyword-stuffed.
- **KILL / REDESIGN:** If the lift is null or marginal — **entirely plausible given zero independent causal evidence and the referral-dominated RCM channel** — do *not* bet the product on the wedge. **Redesign around the two well-grounded legs: segmentation (offshore-resistance) + pay-truth.** Never put a vendor multiplier (10.6x, 11.7%) in your own marketing; it's borrowed and refutable.

**A note on framing, regardless of P0-E outcome:** correct the narrative *now*. The "ATS auto-rejects you for keywords" claim is a debunked myth (92% of recruiter systems don't content-auto-reject). Sell the true mechanism — **"get found in recruiter searches and ranked above the pile."** Optimize for title/keyword alignment to the recruiter's likely Boolean search and human-skim readability, **not a Jobscan-style match-percentage** (a vanity metric that hits 80%+ with zero callbacks).

---

## Phase 1 — The Wedge MVP

**Goal: the thinnest shippable product, gated on P0 passing.** Build risk-first, not feature-first. Sequence by *stability*, not user glamour.

**Tie to evidence:** Phase 1 leans on what validated — the deterministic pay engine, the free feeds, and the title-lever mechanism — and defers the contested callback claim to measurement, not marketing.

**Build items, in dependency order:**

1. **Owned feed ingestion (weekend-to-week).** Greenhouse / Lever / Ashby (`includeCompensation=true`) / USAJOBS, ~1 day each, into a shared `JobPosting` normalizer. This is the **lowest-risk, highest-reliability surface** and powers a working product with zero scraping risk. Treat as **seed + reliability backbone, not primary volume** (per P0-B).

2. **Pay engine (days, not weeks).** Deterministic OEWS/O*NET SOC-crosswalk join over downloaded flat files. Ship with an **LLM-assisted + human-curated crosswalk for the RCM title set** and **show confidence in-UI**. If P0-D failed, include posted-range extraction as the primary path with OEWS as fallback.

3. **Scoring rubric built directly on the published onshore-vs-offshore RCM taxonomy.** Onshore signals (complex denials/appeals, payer-policy interpretation, US patient-financial) = offshore-resistant; offshore signals (charge entry/posting/eligibility/credentialing/coding) = at-risk. **Add a hard credential-gate axis** (RN required / bachelor's required / associate's-or-experience OK) — without it the scorer surfaces RN-gated $66k+ roles to a no-bachelor's user as "fit" and destroys trust. **Add a real-remote verifier axis** (remote→hybrid bait, in-office-X-days clauses, state restrictions) — given healthcare's ~9% fully-remote base rate, this is a genuine differentiator.

4. **Grounded resume reframe with visible diff + hard abstain (week-to-month).** Re-label/re-emphasize-only, user-confirmable diff, abstain-if-unsupported. Map "Customer Service / Patient Account Rep / Admin" → offshore-resistant target titles **only where the user's real experience supports it.** Haiku 4.5 default; Sonnet for the reframe step if P0 quality testing requires it. ZDR on, redact/consent pre-send. **Market "never fabricates" only after the guardrails are built and tested** — a single fabrication scandal kills the brand with this vulnerable user base.

5. **Fit checklist + Floor-Truth estimate as an extension overlay on a couple of boards.** Start with the **most stable surfaces that passed P0-C** — likely Workday (CXS API, beachhead employers) + one of Indeed/LinkedIn. LinkedIn UI renders in side panel/popup, injecting nothing into LinkedIn's DOM. Per-site adapters with a shared normalizer and **extraction-success metrics + alerting from day one.**

6. **Next.js companion app** for the resume flow, account, and saved/scored jobs.

7. **CWS submission (early, narrow).** Single-purpose declaration, minimal `host_permissions`, Limited-Use disclosure, "score-don't-store" architecture (extraction + scoring fully client-side, no page content off-device by default). Budget 1–4 week in-depth review into the cadence.

**Phase 1 exit criteria:**
- Extension reliably scores real RCM postings on ≥2 boards with monitored extraction-success rate and **honest "couldn't parse this page" degradation** (never a silent wrong score).
- Pay floor is within validated error bounds with confidence shown.
- Reframe ships with diff + abstain and a measured fabrication rate at/near zero on an adversarial set.
- CWS-approved with intended permissions.
- **Callback instrumentation is live as a day-1 controlled experiment** (randomized reframed-vs-control across cohorts) — because your own measurement *is* the moat and the only honest basis for later claims.

---

## Phase 2 — Trust + Staircase

**Tie to evidence:** The thin ≥$30 archetype-accessible pool means **most target users start below $30 and need a path up.** The validation is explicit: **the real value is the coaching/staircase, the feed is the destination.** If P0-A killed the feed framing, this phase becomes the product's center of gravity, not an add-on.

**Build items:**

1. **Income Staircase as core.** Use the sub-$30 commodity tier (prior auth $20.89, payer enrollment ~$23, credentialing ~$24, medical AR specialist $20.94, bilingual patient access $17–22) as **rung/aspiration-comparison content** — explicitly *not* the headline feed. The top rung is the reliably-$30+ lane: revenue cycle analyst (avg $35.13, entry ~$29), denials/AR analyst. **Be honest that the top step is narrow** (degree-preferred bias, 500+ applicants/posting) and that the staircase is the path to it.

2. **Input-based accountability.** Because per-user callback signal is sparse (~2–3% interview conversion, ~42 apps/interview), an individual will *never* see a statistically meaningful personal lift. Coach and measure on **inputs** (applications to well-fit, offshore-resistant, real-remote, credential-matched roles) and report efficacy only **in aggregate/cohort** — never an unverifiable "we improved YOUR callbacks."

3. **Trust signals as first-class scoring output:** surfaced credential-gate verdict, real-remote verdict, offshore-resistance verdict, and pay-confidence. These are the differentiators competitors don't ship.

4. **Begin crowdsourced real-pay capture** (build the store now; expect it empty for months — value is gated on volume). If P0-D forced it earlier, mature it here.

5. **Cohorted callback instrumentation matures** into the basis for any honest, data-backed claim. Only after sufficient cohort N do you make *any* quantified statement, **backed by your own data.**

**Phase 2 exit criteria:** Users below $30 retain and progress on the staircase even when same-day $30+ matches are scarce (this was an explicit Phase-0 retention test); trust verdicts measurably reduce wasted applications; crowdsourced pay store is accumulating.

---

## Phase 3 — The Moat

**Tie to evidence:** The moat is *earned*, not designed-in. It only exists at **data density.**

**Build items:**

1. **Confirmed-pay Floor Mode at density.** Once crowdsourced reports reach the modeled threshold (likely **30–50+ reports/title/geo** for a stable per-title estimate), Floor Mode shifts from OEWS prior to confirmed real pay — directly fixing the bimodal-SOC weakness. The OEWS prior is a *stopgap*; if crowdsourced never reaches density, it becomes permanent — so density is the explicit gate here.

2. **Crowdsourced-pay maturity** as the primary pay signal where dense; OEWS fallback where sparse.

3. **Gated employer / staffing-firm program.** Lean into employers whose offshore-resistant RCM postings come through the clean owned-feed/Workday-API path (hospital systems, large employers on Workday/Greenhouse). Gate it behind the antitrust/privacy thresholds that crowdsourced pay-sharing requires.

4. **Earned, calibrated fit score** — calibrated against accumulated callback/outcome cohorts, so the score finally reflects *measured* conversion, not a heuristic. This is the asset the public literature lacks and competitors can't borrow.

**Phase 3 exit criteria:** Floor Mode runs on confirmed pay in the densest title/geo cells; fit score is calibrated against real outcomes; employer program live behind privacy gates.

---

## Recommended stack & the 3–4 biggest technical risks

**Stack (settled, low-cost):**
- **Extension:** WXT (Vite, cross-browser MV3; MV2 is dead). Ephemeral service worker → persist state in `chrome.storage`. CSP bans remote code → **bundle the scoring engine**, no remote model calls from the content script. **Score-don't-store** as a load-bearing architecture decision: client-side extraction + scoring, no page content off-device by default. Remote-config-driven selector/path map (allowed as *data*, not remote code) so you repair breakage without a CWS round-trip.
- **Feeds:** Greenhouse / Lever / Ashby (real comp) / USAJOBS (free key, no approval, commercial-OK, PII-free), behind a shared `JobPosting` normalizer.
- **Pay engine:** OEWS public-domain flat files + free API v2 (500 q/day) + O*NET CC-BY crosswalk. Deterministic join — cheap, explainable.
- **LLM:** Haiku 4.5 default (~$0.014/resume), Sonnet 4.6 for the reframe where quality matters (~$0.04). ZDR on the first-party API for resume PII (PII, not PHI — no BAA needed for the resume flow). Prompt caching + batch reduce cost further.
- **Companion app:** Next.js.

**Biggest technical risks + mitigations:**

1. **Extension DOM/JSON-LD fragility (#1).** JSON-LD confirmed on LinkedIn's *public* page but **unverified in the logged-in SPA DOM**; Indeed (Cloudflare) and Workday (per-tenant variance) are worse. Failure mode is *silent mis-scoring*. **Mitigate:** JSON-LD-first with DOM fallback, versioned per-site adapters, automated canaries, and **explicit "couldn't parse" over a wrong score.** Prototype on live pages before any coverage promise (P0-C).

2. **LinkedIn detection / account-restriction risk to YOUR users.** LinkedIn runs Spectroscopy on every page load and restricts accounts for ToS-violating extensions; the AED target list grows ~12/day and explicitly hunts job-search tools. The harm lands on job seekers who can least afford a lockout. **Mitigate:** no-DOM-injection design (UI in side panel/popup), explicit opt-in with a clear ToS/account-risk warning if an in-page badge is ever offered, low-profile niche footprint. Accept there is **no permanent safe harbor** — be ready to drop LinkedIn (Workday is the beachhead surface anyway).

3. **CWS distribution / policy risk.** Broad host permissions guarantee 1–4 week in-depth review on every release; a LinkedIn scraper was pulled 2025-04-20. **Mitigate:** airtight single-purpose framing, minimal `host_permissions`, optional-permissions for boards added later, Limited-Use disclosure, "score-don't-store" — from day one. Budget review latency into every release.

4. **SOC-crosswalk / pay-estimate accuracy on bimodal RCM titles.** Title-only SOC coding misclassifies mislabeled roles; catch-all SOC averages can't separate $22 from $86k; local-MSA OEWS doesn't reflect national-remote pay. A wrong floor inverts the trust wedge. **Mitigate:** curated + LLM-assisted crosswalk for the RCM title set, human-reviewed, **confidence shown in-UI**, and crowdsourced real-pay prioritized to density (move earlier if P0-D fails).

*(Watch item, not yet a hard risk: Greenhouse is moving Harvest to OAuth/v3 and deprecating v1/v2 by Aug 2026 — the public-board trend is toward gating. Keep the feed adapters swappable.)*

---

## Sequencing logic & dependencies — what gates what

**The dependency chain:**

- **P0-E (reframe callback test) and P0-A (filtered inventory + freshness) gate the entire product thesis.** Both can return "redesign" or "pivot." Run them first and in parallel. Until they read out, do not build product around either the wedge or the feed.
- **P0-C (extension parse) gates which boards ship in Phase 1** and whether LinkedIn is in scope at all. **P0-B (ATS coverage) gates whether the owned feed is primary or seed** (almost certainly seed).
- **P0-D (pay accuracy) gates the pay-engine roadmap** — specifically whether crowdsourced pay is V1 or V3.
- **Phase 1 gates Phase 2:** the staircase needs the scorer (with credential-gate + real-remote axes) and the day-1 callback instrumentation already running.
- **Phase 2 gates Phase 3:** the moat (confirmed-pay Floor Mode, calibrated fit score, employer program) only exists once crowdsourced pay reaches **density** and callback cohorts reach **N**. No density → no moat → OEWS prior becomes permanent.

**Where the red-team said de-risk-first / redesign, this plan reflects it:** every claim is gated behind a Phase-0 spike with a kill criterion; the contested wedge is measured (P0-E) before it's marketed; the feed is treated as thin (seed, not volume) until P0-A proves flow; and the staircase is positioned as the product center precisely because the ≥$30 pool is thin.

**The single thing most likely to kill the build:**

**Freshness/refill rate of the filtered lane (P0-A).** A static snapshot of "low tens to low hundreds" is meaningless if the lane doesn't *refill* faster than AI + nearshore drain it. If **net-new postings surviving all four filters (≥$30 AND fully-remote-confirmed AND offshore-resistant AND no-degree/no-RN) are in the single digits per week nationally,** the feed cannot sustain a recurring-engagement product — no scoring polish, extension reliability, or reframe quality fixes a feed with no flow. This is the number to measure before anything else, and the one that forces the staircase-first pivot if it comes back thin.

*(Close seconds, both already de-risked above: the reframe lift proving null (P0-E), and LinkedIn restricting users' accounts.)*
---

*Validation provenance: this roadmap is grounded in a 6-claim validation + adversarial-verification
pass. Five claims returned (live-inventory, extension-feasibility, pay-engine, reframe-wedge,
tech-stack) — all `partially-validated / de-risk-first`. The sixth (ATS-feed RCM coverage) failed to
return structured output; its substance is covered by the live-inventory finding (free ATS feeds
under-represent archetype-fit IC roles; in-scope volume lives on Indeed/LinkedIn) and is explicitly
re-tested as Phase-0 spike **P0-B**.*
