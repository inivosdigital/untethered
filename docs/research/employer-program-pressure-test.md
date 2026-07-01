# Employer-Side Program — Pressure-Test

*Decision brief · 2026-06-30 · Tests the "pay-transparent-employer program" proposed as the moat in PRD §10.*
*Grounded by five research sub-agents (staffing-fee economics, comparable hiring-marketplaces, RCM hiring reality, pay-transparency law, and the Glassdoor/Indeed/Yelp employer-pays precedent). Figures flagged `(verify)` are directional.*

---

## The program under test

> Employers post verified, pay-transparent, truly-remote RCM roles. In exchange they get a "verified
> employer" badge and access to Untethered's pool of pre-screened, fit-checked, remote-committed
> candidates. They pay (subscription and/or per-hire). This funds the demand side and supplies
> confirmed-pay provenance.

## The central risk: we're charging the party we police

Every other feature builds trust by **policing employers** (exposing hidden pay, mislabeled
"remote," sub-$30 roles, scams). The program proposes to **take money from those same employers** —
the defining conflict, with a well-documented graveyard:

- **Glassdoor** — paid "Enhanced Profiles" let an employer **feature a chosen review at the top**;
  the review-dispute process removes a review if the author doesn't re-confirm; the 2024 Fishbowl
  acquisition **de-anonymized users without consent**. Stated "algorithm + guidelines" independence
  was undercut the moment money could reorder/dispute/unmask the content that judges the payer.
  *(slashdot.org 2024-03; SHRM; help.glassdoor.com Enhanced Profile FAQ)*
- **Indeed** — the 2024 "Healthy Marketplace" change **deprioritized organic listings**; from Oct
  2024 ATS-fed jobs **must be sponsored to get visibility** ("the more you invest in Indeed, the more
  you get out"). Note the tell: ghost jobs were **deprioritized, not removed** — "reducing clutter"
  became cover for selling the front page. *(ere.net; jobboarddoctor.com 2025-11)*
- **Yelp** — *Levitt v. Yelp* (9th Cir. 2014) held arranging reviews is protected editorial
  discretion, not extortion; the FTC closed its probe (2015) with no action. **But a decade of
  "extortion" perception still shadows it** — winning in court ≠ being trusted. *(law.justia.com;
  techcrunch.com 2015-01)*

**The evidence-backed lesson (this is the design constraint):** *a stated policy of independence is
worthless; the only durable protection is **structural separation of revenue from ranking/moderation**,
an **auditable advertiser-blind algorithm**, and **removal — not mere deprioritization — of bad-faith
content**, because the perception of conflict survives even legal vindication.*

## Grounded pressure points

**1. Value ceiling is real but per-unit modest** *(staffing-fee research)*. Direct-hire fees run
**15–30% of first-year salary (~20% common)** *(hirecruiting.com, RecruitBPM)*; RCM back-office lands
~15–22%. So a placement is worth ~**$7–11K** for a biller/patient-access/AR role (~$40–55K salary)
and ~**$15–28K** for a Revenue Cycle Analyst (~$85K+) — the ceiling. Contract/temp runs ~**1.5×
markup (~$20K+/yr per seat)**. **Implication:** volume business, not high-ACV enterprise sales.

**1a. The ACV-vs-volume split inside RCM.** High-volume back-office roles give *candidate density*
(the data moat) but ~$8K placement value; the *analyst tier* holds the ~$25–30K value. → **back-office
for density/data, analyst tier for dollars** — which maps onto the Income Staircase (back-office =
Step-1 bridge, analyst = Step-2 $30+ destination), so *the destination is also where we monetize.*

**2. Employment-agency licensing — moderate and manageable, not zero** *(licensing research)*. ~30+
states regulate employment/placement agencies (no federal license; state-by-state, model-driven);
**NY, IL, MA, NJ, MN** require license/registration + bond ($5–25K+), while **CA, FL, CO do not**
require a state-level license for general placement. You must comply where the **worker is placed**,
so a remote marketplace has multi-state exposure. The decisive lever: **charging only the employer
(never the worker)** drops you into the lightest tier and explicit exemptions — NY's **"employer fee
paid"** carve-out (GBS §191, no license for commercial/clerical/professional placements, just a filed
fee-paid letter) and MA's lighter **"placement agency"** tier (which expressly covers a business that
"consists solely of providing employers, by electronic means, biographical information… of
applicants"). Two risk amplifiers: **(a) a per-hire success fee** is the classic "procures employment
for a fee" agency hallmark — *highest-risk monetization*; subscription/listing fees are lowest-risk;
**(b) active matching** (screening/curating specific candidates to specific openings) looks more like
an agency than passive listing — and *Mobley v. Workday* (N.D. Cal., 2023–25, allowed to proceed)
shows courts will entertain "your screening tool functions as an employment agency/agent" theories
(also a bias-audit flag, see PRD §9). → **Subscription/access pricing, never charge the worker
(documented), lean listing/advertising framing over curated placement, and a per-state check keyed to
worker location (NY/IL/NJ/MA the priority registration states) with counsel before launch.**

**3. Pay-transparency law is a structural tailwind** *(pay-transparency research)*. **12 states**
require a pay range *in the posting* (CA, CO, HI, IL, ME, MD, MA, MN, NJ, NY, VT, WA) + NYC/Jersey
City/Ithaca, covering **~50% of the US workforce / 60M+ workers by 2026**, expanding, enforcement
hardening (penalties to $250K). **Critically: a remote role that *could* be filled in a covered state
must post the range, and "except CA/NY" carve-outs fail** — so remote-first employers default to
posting ranges nationwide. *(NWLC; Jackson Lewis "Navigating 2026"; GovDocs)* → The data brief's
"no posted range is the base case" assumption is **structurally eroding for remote roles**, so
Floor-Truth's confirmed-pay coverage improves on its own, and "confirm your pay" becomes a near-zero
ask (it's just compliance).

**4. Comparable marketplaces — copy the gated model, avoid the pay-to-rank model** *(marketplace
research)*. Two archetypes: **success-fee** (Paraform ~20–25%, Hired ~15%) vs. **subscription/access**
(RippleMatch $30–250K/yr pure sub; Wellfound $499/mo; Handshake $0–250K). **RippleMatch is the
cleanest analog** (subscription, free to candidates, algorithm-gated, *no* promoted-listing product).
**Wellfound and Handshake are the cautionary ones** — both sell paid placement that **literally
pushes a job higher in candidate search, with weak disclosure** (Handshake also has billing-opacity
complaints). **The standout: Hired's `1% of salary × 24 months`** model — revenue accrues only if the
candidate *stays ~2 years*: the employer-side analog of our no-ISA ethos. *(flexiple.com; getapp.com;
help.wellfound.com; pin.com)*

**5. RCM hiring reality reshapes the ICP and adds the offshore insight** *(RCM-hiring research)*.
**97% of healthcare orgs outsource ≥1 RCM function; offshore Asia is ~60% of healthcare BPO at 50–70%
labor savings**, and the giants (R1, Optum, Conifer, Ensemble) *are* the outsourcers with captive
offshore + internal TA — **poor early customers.** Turnover is brutal: patient access ~40%, AR/
call-center **47–61%** (69–73% first-year). **Early ICP:** mid-market health-tech / managed-billing,
physician & specialty groups, FQHCs, smaller hospitals, **and RCM staffing firms** (a $45B→$82B
market that already buys external sourcing). *(Becker's/Savista 2025; Experian; Currance; Precedence
Research)*

## The unifying insight: target offshore-resistant roles

The commoditized US-remote back-office is **racing offshore**. The roles that resist offshoring are
the *same* roles that are higher-ACV, the $30+ Staircase destination, and where the target user's
bilingual + payer-knowledge edge matters:

| | Commoditized back-office | **Offshore-resistant** |
|---|---|---|
| Examples | Basic billing, data entry, posting | **Bilingual patient-facing, complex denials/appeals (US payer knowledge), compliance-sensitive, RC analyst** |
| Offshore pressure | High | **Low** |
| Employer ACV | ~$8K, competes w/ 50–70%-cheaper BPO | **~$25–30K, no offshore substitute** |
| Staircase rung | Step-1 bridge | **Step-2 $30+ destination** |

→ **Steer both sides toward offshore-resistant role types**, away from work that's leaving the country.

## Pre-mortem (12 months in, the program failed)

| # | Failure mode | Likelihood | Why it kills us |
|---|---|---|---|
| 1 | **Corruption spiral** — money buys softer flags/ranking | Med | Consumer trust (the moat) collapses |
| 2 | **Adverse selection** — only churn-and-burn employers pay in | **High** (RCM is high-churn) | "Exclusive" inventory worse than open market |
| 3 | **Thin density** — too few quality employers | High | Reverts to "just an extension," no moat/revenue |
| 4 | **Agency re-classification** — placement fees trigger licensing | Med | Legal/bonding burden; forces mid-flight model change |
| 5 | **Giants never engage** — stuck with mid-market scraps | Med-High | Paying-employer TAM too small alone |
| 6 | **Offshore undercut** — employers default to 50–70%-cheaper BPO for back-office | High (commodity roles) | Unwinnable on price → must avoid that segment |

## The resolved design

**Make the program's entry requirements identical to the consumer trust criteria.** An employer can
only buy access if they *already pass the honesty bar* (confirmed ≥$30/hr, true remote, no scam
patterns, acceptable churn signals). Then money can't buy a softer flag — *passing the flag is the
price of admission* — and adverse selection flips to positive selection. Plus the evidence-backed
structural rules:

1. **Structural separation of revenue from ranking/moderation** — not a policy promise; the fit
   score, pay-truth read, and search rank are computed in a path money cannot touch, and it's
   **auditable** (the Yelp/Glassdoor lesson).
2. **Remove — never merely deprioritize — bad-faith listings** (the Indeed lesson). Scams/ghosts come
   off, regardless of who pays.
3. **Money buys access + a behavior-earned, revocable, public-criteria badge — never rank.** Any paid
   surface is plainly labeled.
4. **Subscription-led pricing** to stay a platform, not an agency; **never charge the worker.**
5. **Retention-aligned** (Hired's 1%×24mo): we get paid as placements prove durable, so our revenue
   model itself screens out churn-and-burn employers. *(Tension: a retention-linked fee leans toward
   "agency" — likely a subscription core + optional retention component, counsel-vetted.)*
6. **Never sell employer-side comp benchmarking** (antitrust + it weaponizes worker data).
7. **Focus on offshore-resistant, higher-ACV roles.**

**And reframe the payer to de-risk the conflict entirely:**
- **Primary, zero-conflict:** consumer subscription (coaching tier).
- **Aligned B2B:** **RCM staffing firms** + **workforce-development funders** (colleges, WIOA, Year-Up-
  style nonprofits whose *funders* pay to place graduates) + employer **L&D budgets** — wallets
  aligned with the worker, not the policed job-ad budget.
- **Policed-employer program:** layered on last, gated by the honesty bar.

## Verdict

**The employer-pays program is a Phase-3 monetization layer — not the launch moat.** The PRD over-
promises it; revise. The actual moat is **(a) the pre-screened pool of *US-remote-defensible*
candidates in a tight niche, and (b) the crowdsourced confirmed-pay dataset** — the employer program
*monetizes* those. That distinction is the leverage that keeps the program honest: because we don't
*need* employer revenue to have a defensible business, we can walk away from any employer who wants us
to soften the policing.

**Recommendation:**
1. Don't make launch economics depend on the policed-employer program.
2. Re-label the moat (pool + pay-data); employer program = a gated, retention-aligned, offshore-
   resistant-focused monetization layer.
3. Lead monetization with **consumer subscription + the $45B staffing-firm / workforce-funder B2B.**
4. Pilot the policed-employer program after candidate density, **subscription-led**, **entry-gated by
   the honesty bar**, with **structural (auditable) separation of revenue from ranking** and
   **removal of bad-faith listings**.
5. The one-question pilot: *will a qualifying (≥$30, true-remote, low-churn) RCM employer pay for
   access to our pool without asking us to soften anything?*

## Sources (key)

Staffing fees: hirecruiting.com, RecruitBPM, Second Talent, BLS OOH, ZipRecruiter, Glassdoor.
Marketplaces: flexiple.com (Hired), dover.com/paraform, getapp.com (Wellfound/RippleMatch), pin.com
(Handshake), help.wellfound.com. RCM hiring: Becker's/Savista 2025, Experian, Currance, qualify.health,
Precedence Research, insightglobal.com. Pay transparency: NWLC, Jackson Lewis, GovDocs, MorganHR.
Precedent: slashdot.org/SHRM (Glassdoor 2024), ere.net (Indeed), law.justia.com / techcrunch.com (Yelp).
