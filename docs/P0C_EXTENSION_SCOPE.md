# P0-C — Extension Parse Spike: Scope

*Scopes the Phase-0 spike from [`BUILD_ROADMAP.md`](BUILD_ROADMAP.md#p0-c--extension-parse-spike-linkedin--indeed--workday). Reprioritized by P0-B evidence. Not yet started — this is the plan to approve.*

## Why this is now the critical path
- **P0-B made the extension load-bearing.** Only ~32% of archetype postings are reachable via free ATS APIs; ~68% live behind Workday / iCIMS / Oracle HCM / Paylocity / Dayforce / custom portals. The owned feed is seed-only. **The extension (or an aggregator-facing capture path) is how the product sees the real market.**
- **Egress is now open on the build host** (it was egress-blocked during the original validation), so the Workday half is cheaply testable — see the Week-0 probe below.

## Reframed objective
Prove we can extract a **reliable, structured `JobPosting` (title, employer, location, real-remote signal, pay-if-present, description)** from the surfaces where the archetype actually lives — **without silent mis-scoring, and without getting the user's account restricted.** Failure mode to design against everywhere: a *wrong* score is worse than an honest "couldn't parse this page."

## Surface priority (revised from the roadmap's flat LinkedIn/Indeed/Workday)
P0-B's ATS distribution (workday 14 · other/Oracle/Paylocity/Dayforce/custom 13 · greenhouse 8 · lever 5 · icims 4 · ashby 3) implies a barbell:

| Rank | Surface | Why | Coverage shape |
|---|---|---|---|
| **1** | **Workday CXS API** | Biggest single enterprise ATS; the beachhead employers (hospitals, BPOs, health plans) are here. JSON, not fragile DOM. | Per-tenant; robust once wired |
| **2** | **Indeed** (aggregator) | Broadest single surface — spans *all* the enterprise ATSes in one adapter. Less litigious than LinkedIn. | Cross-ATS; Cloudflare-gated |
| **3** | **iCIMS / Oracle HCM adapters** | Next-biggest enterprise slices after Workday. | Per-vendor JSON |
| **4 (defer)** | **LinkedIn** | Highest detection + account-restriction + legal risk (a scraper was pulled 2025-04-20; Spectroscopy on every load). | Broad, but a tax |

**Recommendation:** target **Workday + Indeed** for the V1 proof; treat **iCIMS/Oracle** as fast-follow adapters; keep **LinkedIn deferred/optional** and gated behind the detection canary. Aggregator parsers (Indeed) buy cross-ATS breadth in one adapter; ATS-API adapters (Workday/iCIMS) buy robustness on the highest-value slices. Ship both kinds.

## Week-0 probe — DONE (run 2026-07-01, this host)
- **Workday CXS is NOT reachable by naive server-side request.** The careers page bot-filters raw fetches (HTTP 406 without browser headers); the `/wday/cxs/<tenant>/<site>/jobs` endpoint needs the **exact per-tenant `<site>` slug** (blind guesses → 404). **Implication:** the Workday adapter must run **in the browser/content-script context** (page origin passes the bot filter *and* resolves CORS). This *replaces* the roadmap's open question "CXS from content script vs. background worker" with "content-script/page-origin path is the one to build."
- **Endpoints captured live** (headless browser on `devoted.wd1.myworkdayjobs.com`, fixtures saved in `../extension/fixtures/`): list `POST /wday/cxs/<tenant>/<site>/jobs`, detail `GET /wday/cxs/<tenant>/<site>/job/<externalPath>`. **The detail payload carries the full `jobDescription` HTML with posted pay embedded in text** — everything the product needs. Access requires `x-calypso-csrf-token` + same-origin cookies, no CORS. **Workday adapter = GO (viable).**
- **Skeleton built** (`../extension/`): bundler-free MV3 with JSON-LD + Workday adapters, normalizer, on-device scoring (ported from `harvest.py`), side-panel UI, no DOM injection — **9 node tests pass against the real fixtures**. Remaining P0-C work is the LinkedIn/Indeed logged-in-DOM confirmation + detection canary (needs your throwaway accounts) and iCIMS/Oracle fast-follow adapters.

## Per-surface GO / KILL
- **Workday** — GO: content-script/page-origin CXS calls return structured jobs + detail (incl. comp where posted) reliably across ≥3 tenants; `host_permissions` scope is acceptable for CWS. KILL: per-tenant variance or CORS/permission needs make it unreliable → fall back to parsing the rendered Workday job DOM.
- **Indeed** — GO: JSON-LD `JobPosting` extraction succeeds on a high fraction of real logged-in viewjob loads; Cloudflare/Turnstile interstitial rate is low enough that skip-and-retry keeps coverage. KILL: interstitial rate too high / JSON-LD stripped → rely on Workday + owned feed.
- **LinkedIn** — GO: `application/ld+json` present in the **logged-in SPA DOM** (not just the public page) **and** the no-DOM-injection prototype stays undetected over a multi-week canary. KILL LinkedIn (not the product): JSON-LD absent in logged-in DOM (forcing brittle CSS selectors) or detection trips → **drop LinkedIn from V1**, lean on Workday + Indeed + feed.

## Owner split (what unblocks fastest)
**Agent-doable now (no account risk, headless/backend):**
1. Finish the Workday CXS capture via headless browser → exact endpoint + payload/comp confirmation (≥3 tenants).
2. Scaffold the **WXT (Vite, MV3) extension skeleton**: side-panel/popup UI (no DOM injection), a `JobPosting` normalizer, **JSON-LD-first parser + DOM fallback**, a per-site adapter interface, a **remote-config selector/path map** (data, not remote code), and the **score-don't-store** bundling (client-side extraction+scoring, CSP-safe, no page content off-device).
3. **Adapter unit tests against saved page fixtures** (Workday CXS JSON, Indeed/LinkedIn JSON-LD samples) + an extraction-success metric with explicit "couldn't parse" degradation.
4. Public-page JSON-LD presence check on Indeed/LinkedIn viewjob URLs (weak proxy — flags the real logged-in test, doesn't replace it).

**Needs you (real accounts, account-risk, multi-week):**
5. Throwaway **logged-in** LinkedIn + Indeed accounts.
6. Confirm JSON-LD in the **logged-in SPA DOM** (the one unknown a headless public check can't settle).
7. Run the **4–6 week no-injection detection canary** on the throwaway LinkedIn account (watch for account flags / `chrome-extension://` traces); decide LinkedIn go/drop.

## Cross-cutting constraints (bake in from commit #1)
- **CWS review:** single-purpose declaration, **minimal `host_permissions`** (optional-permissions for boards added later), Limited-Use disclosure, score-don't-store. Broad host perms = 1–4 week review per release — budget it.
- **Detection/legal:** no DOM injection (UI in side panel/popup only); explicit opt-in + account-risk warning before any in-page element; accept there is no permanent safe harbor for LinkedIn.
- **Fragility:** versioned per-site adapters + automated canaries + remote-config selectors so breakage is repaired without a CWS round-trip; **explicit "couldn't parse" over a wrong score**, always.
- **Watch item:** Greenhouse is moving to OAuth/v3 and deprecating public v1/v2 by **Aug 2026** — keep feed adapters swappable.

## Timeline & exit
- **Week 0–1 (agent):** Workday CXS capture + WXT skeleton + Workday/Indeed adapters + fixture tests + extraction-success metric.
- **Week 1–2 (you + agent):** logged-in JSON-LD confirmation (LinkedIn/Indeed), start the LinkedIn detection canary.
- **Week 2–6 (you):** canary runs; agent hardens adapters + adds iCIMS/Oracle.
- **Exit / GO:** extension reliably scores real RCM postings on **≥2 surfaces** (target: Workday + Indeed) with a monitored extraction-success rate and honest degradation; LinkedIn decided by the canary; permissions scoped for CWS.

## Immediate next action (pick one)
- **A — Run the Workday CXS capture now** (headless browser → real endpoint + comp payload). Cheapest, highest-info, agent-only.
- **B — Scaffold the WXT extension skeleton** (manifest + side-panel UI + JSON-LD/DOM parser + normalizer + tests) so there's a real artifact to iterate on.
- **C — Both A then B.**
