# Untethered extension — WXT / Vite / TypeScript (MV3)

The V1 wedge surface. P0-B showed the free ATS feed only reaches ~32% of the archetype
market; **this extension is how the product sees the rest** (Workday / iCIMS / aggregators).
Migrated to WXT (Vite/MV3) + TypeScript (Foundation F6) so every context — content script,
side panel, service worker — is **bundled from the same shared modules**, with one typed
scoring + pay engine that stays in lockstep with the Python backend via parity tests.

## ⚠ Build on LOCAL disk, not the repo mount
The repo lives on a **CIFS/SMB mount** (`/mnt/nas`) where the Node toolchain fails —
`npm install` stalls on the many-small-file writes and SQLite/symlink locking hangs (the
same CIFS limitation that forces the F3 database onto local disk). **Check the repo out to a
local filesystem to build**, e.g.:

```bash
cp -r extension ~/build/ext && cp -r scoring ~/build/    # keep the ../scoring sibling
cd ~/build/ext && npm install
```
(On a normal local checkout, just `npm install` in `extension/`.)

## Commands
```bash
npm install         # WXT + Vite + vitest + TypeScript
npm run compile     # tsc --noEmit  (typecheck)
npm test            # vitest — parsers, scoring parity, pay parity, telemetry
npm run build       # wxt build -> .output/chrome-mv3/  (loadable MV3 extension)
npm run dev         # wxt dev (HMR) for iterating on the side panel
```
Verified end-to-end: `tsc` clean, **14 vitest tests pass**, `wxt build` produces a ~44 kB
`chrome-mv3` bundle.

## Architecture (score-don't-store)
Extraction + scoring happen **on-device**; no page content leaves the browser. No DOM
injection (side-panel-only UI — the LinkedIn-detection mitigation).

```
entrypoints/
  content.ts     page context — gathers raw material only (JSON-LD blocks, or Workday CXS
                 detail JSON). Imports workdayContext()+csrfToken() from the SHARED parser
                 (src/parsers/workday.ts) — no re-implementation (the point of F6).
  background.ts  ephemeral service worker (opens the side panel)
  sidepanel/     index.html + main.ts — parse → score → estimate pay → render verdicts,
                 and record extraction telemetry (canary)
src/
  types.ts       JobPosting, PayEstimate, ScoreResult, PayReport
  score.ts       on-device scoring (rules from scoring/rules.json; parity-tested vs Python)
  pay.ts         pay-truth engine (floor=lower bound, "straddles $30", OEWS-abstain, crowd)
  normalizer.ts / units.ts   canonical JobPosting + toHourly
  parsers/       jsonld.ts (schema.org), workday.ts (CXS list/detail + shared context/CSRF)
  config.ts      remote-config site/adapter map (chrome.storage override + bundled default)
  telemetry.ts   per-adapter extraction-success canaries + "couldn't parse" recording
  scoring/rules.json   COPY of the canonical scoring/rules.json (identity-tested)
```

Verdicts surfaced: **accessible-IC role · fully-remote · pay (floor–ceiling / straddles $30)
· offshore-resistant · credential-accessible → QUALIFIES**. Unparseable page ⇒ an honest
"couldn't parse", never a wrong score.

## Cross-language parity (can't drift)
`src/score.ts` and `src/pay.ts` load the canonical `scoring/rules.json` and are asserted, via
`scoring/parity_fixtures.json` + `scoring/pay_parity_fixtures.json`, to reproduce the exact
verdicts the Python engine produces (`tools/p0a_inventory/test_scoring_parity.py`,
`test_pay_parity.py`). An identity test guards the bundled `rules.json` copy.

## Load it (manual)
`chrome://extensions` → Developer mode → **Load unpacked** → `.output/chrome-mv3/`.
Open a Workday/Greenhouse/Lever/Ashby/Indeed job page → toolbar icon → **Score this page**.

## Status & next
- **Done:** WXT/TS migration, shared bundled engine, remote-config adapter map, extraction
  canaries, typed parsers/pay/score, vitest suite.
- **Deferred (P0-C):** LinkedIn (behind the detection canary); iCIMS / Oracle adapters.
- **Needs you:** throwaway logged-in accounts for the logged-in-DOM JSON-LD confirmation +
  the 4–6 week detection canary.
