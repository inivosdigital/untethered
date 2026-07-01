# Untethered — Phase-1 (MVP) Build Plan v2

Supersedes the Phase-1 section of [`BUILD_ROADMAP.md`](BUILD_ROADMAP.md) with what Phase-0 actually
learned. **Ordered by product value and dependency — development time/effort is given zero weight**
(per standing direction). A 5-lens codebase relook (2026-07-01) grounds every item below.

## What changed the plan (validated deltas)
- **P0-B** — free ATS feed reaches only ~32% of the archetype; the extension is load-bearing, the owned feed is seed-only.
- **P0-C** — Workday CXS (list + detail) is reachable **in a same-origin session context** → we can harvest Workday both in the extension *and* a backend session-harvester, not just the one page a user views.
- **P0-D** — OEWS-alone pay is untrustworthy (≈$12/hr median error, can't separate tiers) → pay-truth = **posted-range + crowdsourced**, OEWS demoted to an abstaining prior.
- **Relook** — the scoring rubric is implemented **3× and already drifted** (harvest.py 16 kw / score.js 22 kw / config.json overrides); the **$30 floor is taken from `pay_max` (top of range)** → false qualifications; persistence is flat files that can't answer flow/cohort/density; plus concrete correctness + security defects (below).

---

## Phase 1.0 — Foundation (precedes all feature work)
Not polish — these remove trust-breaking defects and are the substrate everything else builds on.

**F1 · One source of truth for scoring.** Collapse the triplicated rubric to a single **data-defined rules spec + one engine** consumed by backend *and* extension, guarded by cross-runtime **parity tests**. Today a user's on-page verdict (`score.js`) and the feed/dashboard verdict (`harvest.py`) can silently disagree on the same posting — fatal for a trust product. *(4 findings converge here.)*

**F2 · Pay-truth core (P0-D + false-floor fix).**
- Extract **min + max + currency + period** as first-class fields (not just the top figure).
- Decide the floor on the **lower bound**, with an explicit **"straddles $30"** state — kills the `pay_max`/`max(nums)`/`maxValue`-first false floor in `harvest.py`, `parse_pay_from_text`, and `jsonld.js`.
- Demote OEWS to a **low-confidence percentile-band prior that abstains** when it's the only signal (surface p25–p75, never a bare median).
- Add a **`PayReport` crowdsource store** aggregated at *(canonical-role × geo/remote × mode)*; display a figure only past the moat gates (**≥5 contributors, ≥3 months, no single source >25%**), anchored to OEWS while sparse.

**F3 · Persistence → SQLite** (harvest history, P0-E log, pay reports), with a clean Postgres path for the companion app / multi-writer crowdsource. Flat `seen.json` is already 721 KB / 7k records rewritten every run and structurally can't answer the three make-or-break queries: **net-new flow over time**, **callback cohorts**, **crowdsourced-pay density**.

**F4 · Correctness fixes** (make once in the canonical engine, mirror to both runtimes):
- `f_remote` drops genuinely-remote US-nationwide roles via the "located in / must reside in" hybrid trap → deflates the target archetype (risks a false KILL).
- JSON-LD adapter has **no currency guard** → non-USD "$40/hour" falsely clears $30 (the exact P0-D false floor).
- Legit base salary nuked when a bonus/stipend sits within the fixed 28-char window.
- `strip_html` entity handling diverges (Python full-unescape vs JS 6 entities); JSON-LD salary/location edge cases (missing `unitText`→annual mis-scale, value-array→NaN, array `jobLocationType` misses remote).

**F5 · Security.** Untrusted feed/page strings are written to `innerHTML` unescaped in **both** the dashboard and the side panel → stored-XSS + broken-markup. Escape at every render boundary.

**F6 · Extension → WXT/Vite/TypeScript MV3.** All contexts (content script, side panel, service worker) share the same bundled modules — kills the in-extension duplication (`content.js` re-implements `workdayContext()` + CSRF inline). Add the **remote-config selector/adapter map** (data, not code) and **per-adapter extraction-success canaries + "couldn't parse" telemetry** the roadmap mandates "from commit #1" but that don't exist yet.

---

## Phase 1.1 — Coverage (see the real market, not just startups)
**C1 · Session-context Workday-tenant LIST harvester** over a curated tenant registry — the single largest coverage unlock (Workday is where HCA/Parallon, R1, Ensemble, Conifer, Optum, Centene, Elevance, Molina live). Walks the CXS `jobs` endpoint per tenant; turns the biggest unreachable slice into countable, monitorable **flow**.
**C2 · Health-employer ATS-tenant registry** — the shared substrate every adapter draws from (employer → ATS → tenant/slug → careers URL).
**C3 · iCIMS / Oracle-HCM / Paylocity / Dayforce list adapters** in the same session-context harness.
**C4 · Indeed / aggregator JSON-LD capture** — cross-ATS breadth in one adapter (covers the custom-portal slice too).
> The extension's detail-only, single-page path **cannot measure flow** — coverage lift must live in the bulk harvester, and every new adapter must score through the F1 single engine or it will double-score.

---

## Phase 1.2 — The Wedge + Trust surface (monetizable core + differentiators)
**W1 · Grounded Résumé Re-Frame Studio** — the highest-leverage income lever, and it does not exist yet. Re-label/re-emphasize only, **visible diff, hard abstain when unsupported, title-lever isolation**, never fabricate. Its lift is *measured* by P0-E, not marketed.
**W2 · First-class trust verdicts** — real-remote / credential-gate / offshore-resistance / pay-confidence as **evidence-bearing, timestamped confidence reads**, not the current evidenceless colored pills (a PRD non-negotiable the UI currently violates).
**W3 · Fit Checklist** — private **requirement-coverage** read; **never a 0–100 match %** (a vanity metric that hits 80% with zero callbacks).
**W4 · Pay-confidence in the UI** — posted-range primary, OEWS as abstaining context, the "straddles $30" state surfaced honestly.

---

## Phase 1.3 — Staircase (the product's center of gravity if the ≥$30 pool stays thin)
**S1 · Income Staircase + Staircase Mode** — surface winnable sub-$30 *bridge* rungs honestly instead of red-lighting them with the strict single `QUALIFIES` boolean; map the path up to the reliably-$30 lane.
**S2 · Input-based accountability + cohort callback readout** — coach on inputs (well-fit applications), report efficacy **aggregate/cohort only** (per-user callback signal is too sparse to be honest), fed by the P0-E framework.

---

## Phase 1.4 — Companion app + ship
**A1 · Next.js companion** (resume flow, account, saved/scored jobs, staircase). **A2 · CWS submission** (single-purpose, minimal `host_permissions`, Limited-Use, score-don't-store). **A3 · Day-1 callback instrumentation live** (P0-E) — the exit gate.

---

## Sequencing, gates, and honesty
- **1.0 Foundation gates everything** — the single scoring engine, pay-truth, persistence, and WXT/TS base are what 1.1–1.4 build on.
- **Two Phase-0 gates remain open and decide the shape:** P0-A **flow** (measuring) and P0-E **callback lift** (needs your real applications). If either comes back thin/null, **1.3 Staircase becomes the center of gravity, not an add-on** — which is why it's a first-class phase, not a footnote.
- **Exit criteria (unchanged):** ≥2 boards reliably scored with monitored success + honest "couldn't parse" degradation; pay within validated bounds with confidence shown; reframe with diff + abstain and ~0 fabrication on an adversarial set; CWS-approved; callback instrumentation live.
- **On ordering:** by product value and dependency only. We take the full WXT/TS migration, SQLite, the single scoring engine, and all four coverage adapters as the correct end-state — none deferred for being larger.

## Appendix — relook findings (28: 15 high / 13 medium)
Full structured list in the review output; the load-bearing ones are folded into F1–F6, C1–C4, W1–W4, S1–S2 above. The three that most directly break the product's core promise today: **(1)** floor from top-of-range, **(2)** scoring drift across Python/JS/config, **(3)** non-USD salaries clearing the $30 floor in the JSON-LD path.
