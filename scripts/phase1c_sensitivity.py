"""Phase 1c sensitivity analysis — is the systemic non-cash-flow finding a
financing-structure problem (fixed-rate amortizing only) or a rate-environment
problem (today's ~7% rates specifically)?

Re-runs min_down_payment_for_target_cap_rate against the 27 verifiable
properties from phase1c_market_screen.py under:
  1. Interest-only financing at the current 7.0% rate.
  2. A fully-amortizing rate sweep: 7.0% down to 5.0% in 0.5% steps.

Intended as a reusable monitor — re-run whenever rates move materially,
rather than redoing the full market screen.

Requires data/reports/phase1c_market_screen.csv to exist (run
scripts.phase1c_market_screen first).

Run from the project root: python -m scripts.phase1c_sensitivity
"""

from __future__ import annotations

import csv

from src.simulation.leverage_threshold import min_down_payment_for_target_cap_rate

RATE_SWEEP = [0.070, 0.065, 0.060, 0.055, 0.050]
TERM_YEARS = 30


def load_verifiable_properties() -> list[dict]:
    rows = list(csv.DictReader(open("data/reports/phase1c_market_screen.csv")))
    return [r for r in rows if r["rent_unverifiable"] != "True"]


def main() -> None:
    properties = load_verifiable_properties()
    n = len(properties)
    print(f"Loaded {n} verifiable properties from phase1c_market_screen.csv\n")

    out_rows = []

    # --- Check 1: interest-only at current rate ---
    print("=" * 70)
    print("CHECK 1: interest-only financing at 7.0%")
    print("=" * 70)
    io_required = []
    for r in properties:
        cap_rate = float(r["cap_rate"])
        req_down = min_down_payment_for_target_cap_rate(cap_rate, 0.070, TERM_YEARS, interest_only=True)
        io_required.append((r["address"], cap_rate, req_down))
        out_rows.append(
            {
                "address": r["address"],
                "cap_rate": cap_rate,
                "financing": "interest_only",
                "rate": 0.070,
                "required_down_pct": req_down,
            }
        )
    io_required.sort(key=lambda x: x[2])

    jeffrey = next((x for x in io_required if "Jeffrey" in x[0]), None)
    if jeffrey:
        print(f"415 Jeffrey St IO required down: {jeffrey[2]:.1%} (expected ~30%)")

    n_clears_25_io = sum(1 for _, _, d in io_required if d <= 0.25)
    n_clears_35_io = sum(1 for _, _, d in io_required if d <= 0.35)
    print(f"\nInterest-only @ 7.0%: {n_clears_25_io}/{n} clear <=25% down, {n_clears_35_io}/{n} clear <=35% down")
    print(f"{'Address':45s} {'Cap':>7s} {'IO Req.Down':>12s}")
    for addr, cap, req in io_required:
        print(f"{addr[:45]:45s} {cap:>6.2%} {req:>11.1%}")

    # --- Check 2: fully-amortizing rate sweep ---
    print("\n" + "=" * 70)
    print("CHECK 2: fully-amortizing rate sweep")
    print("=" * 70)
    print(f"{'Rate':>6s} {'Clears <=25% down':>18s} {'Clears <=35% down':>18s}")
    for rate in RATE_SWEEP:
        n_25 = 0
        n_35 = 0
        for r in properties:
            cap_rate = float(r["cap_rate"])
            req_down = min_down_payment_for_target_cap_rate(cap_rate, rate, TERM_YEARS, interest_only=False)
            out_rows.append(
                {
                    "address": r["address"],
                    "cap_rate": cap_rate,
                    "financing": "fully_amortizing",
                    "rate": rate,
                    "required_down_pct": req_down,
                }
            )
            if req_down <= 0.25:
                n_25 += 1
            if req_down <= 0.35:
                n_35 += 1
        print(f"{rate:>5.1%} {n_25:>10d}/{n} ({n_25/n:.0%}) {n_35:>10d}/{n} ({n_35/n:.0%})")

    out_path = "data/reports/phase1c_sensitivity.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)
    print(f"\nSaved full sensitivity table to {out_path}")


if __name__ == "__main__":
    main()
