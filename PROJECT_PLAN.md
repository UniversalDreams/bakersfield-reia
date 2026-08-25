# Bakersfield Rental Investment Decision Model — Build Plan (v2)

## Purpose (read this first)

This is a personal quantitative decision-support tool for buy-and-hold rental investing in Bakersfield/Kern County, CA. It is not a trading bot and not a general proptech product — it exists to answer three questions for one operator making a small number of real, capital-at-risk decisions over the coming years:

1. **Which property, and is it a buy** (given a blended cash-flow + appreciation goal)?
2. **When to buy** (now vs. wait — the option value of waiting under uncertainty)?
3. **When to hold, sell, or refinance**, revisited annually, not decided once?

Everything below follows from that framing. Favor auditable, explainable math over sophisticated-but-opaque methods. Build incrementally — a working simple version beats a stalled complex one.

**Financing constraint (fixed):** non-owner-occupied only. All financing logic assumes DSCR or conventional investment loans (20-25%+ down), never FHA/owner-occupant.

---

## STATUS SUMMARY (read before doing anything)

**Completed and validated:** Phase 0 (repo/env setup), Phase 1 (walking skeleton), Phase 1c (leverage threshold function + market screen + rate/IO sensitivity), and a sourcing-landscape research pass. Headline finding, confirmed across 27 verifiable properties in 8 Kern County ZIPs:

> **At current ~7.0% investment financing, Bakersfield SFR and small multifamily systemically fail to cash-flow on standard 25-35% down leverage.** Cap rates (~4-5%) sit well below the mortgage constant (~8% fully amortizing). Interest-only structuring helps but only gets 2/27 properties to clear ≤35% down. The gap doesn't meaningfully close until financing rates fall ~150-200bps, and even at 5.0% only ~15% of listed inventory clears 35% down.

This is a **rate-environment / negative-leverage problem**, not a property-selection or search-radius problem, and it changes near-term priorities: standard listed-inventory screening is now a low-value workflow to build more infrastructure around. Effort is redirected toward (a) forced value creation and (b) genuinely software-accessible off-market sourcing, while (c) generic data-layer hardening on standard listings is paused pending a rate move.

---

## Completed phases

### Phase 0 — Environment & repo setup ✅
- RentCast API key collected, stored in `.env` (gitignored), loaded via `python-dotenv`.
- Private GitHub repo under `UniversalDreams`, `bakersfield-reia`.

### Phase 1 — Walking skeleton ✅
- Plain Monte Carlo, fixed point-estimate inputs, one property (6500 Shreveport Ct, Bakersfield): $397,000 price, $2,190/mo rent, 3.98% cap rate.
- Result: `P(cash flow > 0, Year 1) = 0.0%` at 25% down / 7.0% financing. Median IRR 4.68%, 5th-95th pctile 0.90%-8.00%.
- Confirmed this is a leverage/negative-spread issue, not simulation noise: cap rate is deterministically below the debt constant, so variance across paths barely matters.

### Phase 1c — Breakeven cap rate function + market screen ✅
- `src/simulation/leverage_threshold.py`: `mortgage_constant()`, `min_cap_rate_for_breakeven()`, `min_down_payment_for_target_cap_rate()`, both fully-amortizing and `interest_only` variants. Validated exactly against the Shreveport Ct sweep.
- Market screen: 27 verifiable properties (16 SFR + 11 MF) across 93305/307/308/309/313/311/312/314. **0/27 clear ≤25% down; 0/27 clear ≤35% down** (fully amortizing, 7.0%). Best case: 415 Jeffrey St, 4.90% cap rate, needs 38.6% down. Multifamily did not outperform SFR (best MF cap rate 4.06%).
- Interest-only @ 7.0%: 2/27 clear ≤35% down (415 Jeffrey St at 30.0%, 911 N Chester Ave at 32.0%); 0/27 clear ≤25% down.
- Rate sensitivity sweep (fully amortizing, reusable monitor — `scripts/phase1c_sensitivity.py`, rerun monthly): 7.0%→0/27 at both thresholds; 6.5%→0/27; 6.0%→2/27 at ≤35%; 5.5%→3/27; 5.0%→1/27 at ≤25%, 4/27 at ≤35%.
- Data-quality note: RentCast rent-AVM/value-AVM unit-count mismatches on some multifamily records were detected (bedroom-count cross-check) and excluded (5/16 MF records) rather than papered over with a fabricated heuristic.

### Sourcing landscape research ✅ (research report, not yet built)
Evaluated distressed/pre-foreclosure, seller-financing, subject-to, and assumable-mortgage paths for software feasibility. Verdict:
- **Software-native, worth building:** Kern County Recorder class-search (free, real-time NOD/NOS filings — but legacy CGI, metadata-only, no APN search since AB 1785/Dec 2024) + Kern GEODAT ArcGIS parcel data (free API) to resolve owner names to APN/address.
- **Software-native, paid, pending a subscription decision (not yet authorized to build):** PropStream (~$99/mo, has API) or ATTOM (enterprise, best API, opaque pricing) for broader pre-foreclosure/probate/absentee/high-equity lead lists.
- **Software-searchable but deprioritized:** Assumable.io / Roam / AssumeList — real assumable-mortgage marketplaces covering CA, but the economics (equity-gap cash requirement) and typical use case (owner-occupant/house-hack) fit poorly given this project's non-owner-occupied constraint.
- **Not software-buildable — manual/relationship legwork only, keep out of the codebase:** seller financing (no residential inventory feed exists; it's a negotiation you propose to motivated/free-and-clear owners) and subject-to deals (local wholesaler networks, REIA meetups).

---

## Revised build order (current priorities, supersedes the original Phase 2+ sequence)

### Phase 1d — Kern Recorder NOD/NOS scraper (next)
- `src/sourcing/kern_recorder_scraper.py`: scrape recorderonline.co.kern.ca.us class-search for document classes "Default Notice" and "Notice of Trustee's Sale," paged over a rolling date range (start: trailing 90 days). Output: grantor/grantee name, doc type, recording date, doc number. No APN search (disabled under AB 1785) — query by class + date only.

### Phase 1e — Owner-to-parcel enrichment
- `src/sourcing/geodat_enrichment.py`: pull Kern GEODAT ArcGIS parcel layer (free REST/GeoJSON), join scraper output to APN/address/assessed value by owner name.
- Feed resolved addresses into the existing `leverage_threshold.py` screen (Phase 1c logic) using RentCast for rent/value estimates, instead of only screening standard listed inventory.

### Phase 1f — BRRRR / forced-value module
- `src/simulation/brrr_analysis.py`: accepts `rehab_cost`, `post_rehab_arv`, `post_rehab_rent`, cash-out refinance at target LTV (75%) on ARV. Outputs capital recycled, cash left in deal, post-refi `P(cash flow > 0)` and IRR (probabilistic, not point estimate).
- Test against properties closest to clearing from the Phase 1c screen (415 Jeffrey St, 911 N Chester Ave): what rehab budget + rent/ARV uplift flips each from fail to clear.

### Phase 2 — Data-layer hardening (PAUSED, conditional)
Original scope (RentCast caching, refresh cadence for standard listings) is deprioritized — building infrastructure around standard-listing screening is low-value while the systemic negative-leverage finding holds. Resume only when the rate-sensitivity monitor (Phase 1c) shows meaningful inventory starting to clear, or if Stage 2 sourcing (below) proves distressed/off-market volume is thin and standard-listing screening becomes the primary workflow again.

**Not authorized to build yet (pending explicit go-ahead):**
- PropStream or ATTOM API integration — hold until a subscription is chosen and an API key is provided, same pattern as RentCast.
- Assumable.io/Roam/AssumeList integration — deprioritized; revisit only if the owner-occupied constraint changes.
- Any "seller financing search" feature — there is no real inventory to query against; do not build a placeholder for this.

### Phase 3 — Bayesian updating layer
- As originally scoped: priors from RentCast/published Bakersfield submarket data, posterior updates as owned-property performance data accumulates. Now also a natural input point for distressed-lead conversion data once Phase 1d/1e are producing leads.

### Phase 4 — Insurance module + ablation
- As originally scoped: `flat` (null baseline) / `linear_trend` / `jump_scenario` (discretized compound-Poisson-style, calibrated on 2017-2025 CA insurance/regulatory event history) variants, with the ablation harness comparing decision-relevant outputs across all three.

### Phase 5 — Convergence and tail-risk handling
- As originally scoped: adaptive iteration counts for point estimates (fast-converging); larger budget or importance/conditional-tail sampling for tail metrics (5th-percentile IRR, `P(DSCR<1)`) which converge far slower and are what the buy/no-buy decision actually depends on.

### Phase 6 — LSM / backward induction decision layer
- As originally scoped: built on top of Monte Carlo paths (not a separate model), solving buy-now-vs-wait then annual hold-vs-sell-vs-refinance via least-squares regression backward induction.

### Phase 7 — Validation / challenger model
- As originally scoped: a deliberately simple benchmark (2-variable lattice or flat DCF) run periodically, not in production, to sanity-check the full pipeline before any real purchase decision.

### Phase 8 — Reporting
- As originally scoped: probability-based output only (`P(IRR≥target)`, `P(cash flow>0)`, `P(DSCR<1)`, 5th-percentile downside IRR) — never collapse to a single point estimate.
- Optional LLM layer at both ends: front (parsing unstructured listings/disclosures/distressed-lead records into structured inputs) and back (deal-memo drafting). Never in the decision math itself.

---

## Explicitly excluded (do not build these)

- **Reinforcement learning** — decision frequency (~5-10 lifetime decisions) is far too sparse for RL to learn anything.
- **Monte Carlo Tree Search** — small branching factor, analytically tractable value function (discounted cash flow); MCTS is built for huge-branching-factor, no-closed-form-value problems (games, HFT), and risks premature pruning given how few rollouts per node this problem allows.
- **FHA / owner-occupant financing assumptions** — fixed constraint, non-owner-occupied only.
- **Full continuous-time jump-diffusion for insurance** — cat-bond-issuer-grade precision for a portfolio of one to a few houses; discretized scenario model is the right resolution.
- **PropStream/ATTOM/BatchData integration** — until a subscription is explicitly authorized.
- **Assumable.io/Roam/AssumeList integration** — deprioritized given the non-owner-occupied constraint.
- **Any seller-financing "search" feature** — no structured inventory exists; this is a manual outreach workflow (Bakersfield REIA/wholesaler networks), not code.

---

## Standing monitors (rerun periodically, not one-off)

- `scripts/phase1c_sensitivity.py` — rate-sweep + IO-vs-amortizing breakeven check across the 27-property screen. Rerun monthly, or on any meaningful rate move, to catch when Bakersfield inventory starts clearing leverage thresholds again.

---

## Definition of done for v1

A single Bakersfield property or distressed lead, given RentCast/GEODAT-sourced data, produces: a Monte Carlo-simulated distribution of outcomes with Bayesian-calibrated inputs, an insurance-scenario-aware cost model validated by ablation against simpler baselines, a buy-now-vs-wait and hold-vs-sell recommendation from the LSM decision layer (or a BRRRR-specific recommendation where forced value applies), convergence-checked tail-risk metrics, and a probability-based report — cross-checked against a simple challenger model before being trusted for a real decision.
