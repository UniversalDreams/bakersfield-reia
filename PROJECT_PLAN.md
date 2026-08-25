# Bakersfield Rental Investment Decision Model — Build Plan

## Purpose (read this first)

This is a personal quantitative decision-support tool for buy-and-hold rental investing in Bakersfield/Kern County, CA. It is not a trading bot and not a general proptech product — it exists to answer three questions for one operator making a small number of real, capital-at-risk decisions over the coming years:

1. **Which property, and is it a buy** (given a blended cash-flow + appreciation goal)?
2. **When to buy** (now vs. wait — the option value of waiting under uncertainty)?
3. **When to hold, sell, or refinance**, revisited annually, not decided once?

Everything below follows from that framing. Favor auditable, explainable math over sophisticated-but-opaque methods. Build incrementally — a working simple version beats a stalled complex one.

---

## STOP — First actions before any simulation code is written

Claude Code should do these two things first, in order, before writing any modeling code:

### 1. Ask the user for their RentCast API key

Do not proceed to Phase 1 until this is done. Prompt the user directly:

> "Before I build anything, please paste your RentCast API key. I'll store it in a local `.env` file that's excluded from git — it will never be committed or hardcoded into source files."

Store it as `RENTCAST_API_KEY` in a `.env` file at the project root. Add `.env` to `.gitignore` immediately, before the `.env` file itself is created, so there's no window where it could be accidentally committed. Use `python-dotenv` to load it at runtime. Never print the key to logs or commit history.

### 2. Set up git and a private GitHub repository under the UniversalDreams account

- Initialize a git repo locally.
- Create a **private** repository under the user's GitHub account/org `UniversalDreams`. Confirm the GitHub CLI (`gh`) is authenticated first (`gh auth status`); if not, prompt the user to run `gh auth login` before proceeding.
- Suggested repo name: `bakersfield-reia` (Real Estate Investment Analyzer) — adjust if the user prefers something else.
- Add a `.gitignore` covering `.env`, `__pycache__/`, `*.pyc`, `.venv/`, and any local data cache directories before the first commit.
- First commit: repo scaffold + this plan file (`PROJECT_PLAN.md`) + `.gitignore` + empty `.env.example` (a template showing `RENTCAST_API_KEY=` with no real value, safe to commit).
- Push to the private remote.

Only after both of these are done should Phase 1 begin.

---

## Tech stack

- **Python 3.11+**
- `numpy`, `scipy` — simulation and stats
- `pandas` — data handling
- `requests` — RentCast API calls
- `python-dotenv` — secrets management
- `matplotlib` or `plotly` — output distributions/visualization
- `pytest` — testing, especially for the ablation harness (below)
- No ML framework needed yet — nothing in this project currently requires PyTorch/TensorFlow. Don't add one preemptively.

## Repository structure

```
bakersfield-reia/
├── .env                    # RENTCAST_API_KEY (gitignored)
├── .env.example            # template, safe to commit
├── .gitignore
├── PROJECT_PLAN.md         # this file
├── README.md
├── requirements.txt
├── data/
│   ├── cache/               # RentCast pulls, gitignored, refreshed periodically
│   └── priors/              # calibrated prior distributions per Bakersfield ZIP
├── src/
│   ├── data_layer/
│   │   └── rentcast_client.py
│   ├── priors/
│   │   └── bayesian_update.py
│   ├── simulation/
│   │   ├── monte_carlo.py
│   │   ├── insurance_models.py     # flat / linear / jump-scenario variants
│   │   └── convergence.py          # adaptive iteration + variance reduction
│   ├── decision/
│   │   └── lsm_backward_induction.py
│   ├── validation/
│   │   └── challenger_models.py    # simple lattice / flat-DCF benchmark
│   └── reporting/
│       └── output.py               # probability-based output, not point estimates
├── ablation/
│   └── run_ablation.py             # the harness described in Phase 4 and 6
└── tests/
```

---

## Build order (walking skeleton first — do not build sophisticated pieces before the plumbing works end to end)

### Phase 1 — Walking skeleton

Goal: prove the full pipeline runs end to end in its dumbest possible form.

- Pull data for **one** Bakersfield property (or one ZIP's comps) via the RentCast client.
- Plain Monte Carlo simulation with **fixed point-estimate inputs** (no Bayesian updating yet, no jump-scenario insurance yet): rent, vacancy, cap rate, appreciation, interest rate, flat insurance cost.
- Output: distribution of IRR and cash flow across simulated paths, reported as `P(cash flow > 0)` and a rough IRR histogram — probability-based output from day one, not a single number.
- No LSM yet. No buy/hold/sell timing logic yet. Just: does the simulation run, on real pulled data, and produce a sane-looking distribution?

**Do not proceed to Phase 2 until Phase 1 runs cleanly on real RentCast data.**

### Phase 2 — Data layer hardening

- `rentcast_client.py`: wrapper with caching (respect RentCast's free-tier call limits), a documented refresh cadence (monthly or quarterly — not real-time), and clear separation between raw API response and the cleaned fields the simulation consumes.
- Cache pulled data to `data/cache/` so repeated runs don't burn API calls.

### Phase 3 — Bayesian updating layer

- Replace fixed point estimates with priors calibrated from RentCast/published Bakersfield submarket data (per ZIP).
- Add a posterior-update mechanism: as the user's own property performance data accumulates (starts empty), update the relevant distributions.
- Expected behavior to verify: as synthetic "owned property" data points are added (even test fixtures at first, since the user has zero properties today), posterior variance should visibly narrow. Write a test that checks this narrowing behavior directly — it's the mechanism the user is relying on to demonstrate the model is learning, not just running static assumptions with extra steps.

### Phase 4 — Insurance module + first ablation

Build **three** variants, not one:
- `flat`: constant insurance cost, year over year. This is a deliberate null baseline, not a real candidate — its only purpose is to test whether insurance modeling matters *at all* for a given deal.
- `linear_trend`: smooth upward drift with noise.
- `jump_scenario`: discretized compound-Poisson-style approach — 3-4 named annual states (normal / elevated / crisis year) with probabilities and cost multipliers calibrated from the 2017-2025 CA insurance/regulatory event history (reinsurance repricing, FAIR Plan assessment years). This is the realistic model — the other two exist to be compared against it, not to compete with it.

Build `ablation/run_ablation.py` to run all three on the same property and report whether the buy/sell decision output changes materially between them. Two separate comparisons, not one:
1. `flat` vs. either realistic model → does insurance modeling matter at all for this property?
2. `linear_trend` vs. `jump_scenario` → does getting the *shape* right (smooth vs. event-driven) change the decision enough to justify the added complexity?

### Phase 5 — Convergence and tail-risk handling

- Implement adaptive iteration counts: cheap convergence monitoring (running mean/standard error) for point estimates like expected IRR.
- Separately, handle tail metrics (5th-percentile IRR, `P(DSCR < 1)`) with either a much larger iteration budget or basic importance/conditional-tail sampling — these converge far slower than the mean and are the numbers the buy/no-buy decision actually depends on. Don't apply the same iteration count to both without checking.
- Add a convergence-study test: run the same simulation at increasing N and confirm decision-relevant tail outputs (not just the mean) have actually stabilized before trusting them.

### Phase 6 — LSM / backward induction decision layer

- Build on top of the Monte Carlo paths from Phase 1-5 (do not build this as a separate model — it consumes the simulated paths as its input, per Longstaff-Schwartz).
- Solves: buy-now-vs-wait at the front end, then each simulated year, hold-vs-sell-vs-refinance, via least-squares regression backward induction.
- Output: an optimal stopping rule, not just a static score.

### Phase 7 — Validation / challenger model

- Build a deliberately simple benchmark (a 2-variable binomial lattice, or a plain deterministic DCF) that is NOT part of production but is run periodically — before any real purchase decision, or quarterly — to sanity-check the full pipeline's output.
- If the challenger and the full pipeline disagree sharply, investigate before trusting the full model. This is a validation step, not a permanent parallel system.

### Phase 8 — Reporting

- Output probability signals: `P(IRR ≥ target)`, `P(cash flow > 0)`, `P(DSCR < 1)`, 5th-percentile downside IRR. Never collapse this to a single point estimate in the final report.
- Optional, later: a thin LLM layer for (a) parsing unstructured listings/disclosures into structured inputs at the front of the pipeline, and (b) drafting a readable deal-memo summary of the simulation output at the back. Keep the LLM out of the actual decision math in the middle.

---

## Explicitly excluded (do not build these)

- **Reinforcement learning** — the decision frequency here (roughly 5-10 lifetime decisions) is far too sparse for RL to learn anything; it needs many episodes this problem will never generate.
- **Monte Carlo Tree Search** — this problem has a small branching factor and an analytically tractable value function (discounted cash flow); MCTS is built for huge-branching-factor problems with no closed-form value function (games, high-frequency trading). It would also risk pruning promising branches prematurely given how few simulated rollouts per decision node this problem allows.
- **FHA / owner-occupant financing assumptions** — the user will not live in the property; all financing logic should assume DSCR or conventional investment loans (20-25% down) only.
- **Full continuous-time jump-diffusion for insurance** — that's cat-bond-issuer-grade precision for a portfolio of one to a few houses; the discretized compound-Poisson-style scenario model in Phase 4 is the right resolution.

---

## Definition of done for v1

A single Bakersfield property, given a RentCast-pulled data snapshot, produces: a Monte Carlo-simulated distribution of outcomes with Bayesian-calibrated inputs, an insurance-scenario-aware cost model validated by ablation against simpler baselines, a buy-now-vs-wait and hold-vs-sell recommendation from the LSM decision layer, convergence-checked tail-risk metrics, and a probability-based report — cross-checked against a simple challenger model before being trusted for a real decision.
