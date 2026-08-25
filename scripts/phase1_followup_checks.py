"""Two pre-Phase-2 sanity checks requested after the first walking-skeleton run:

1. A higher-yield submarket property (93307) run through the same Phase 1
   simulation, to check whether the Shreveport Ct P(cash flow > 0) = 0%
   result is property-specific or systemic to Bakersfield SFR at current
   financing terms.
2. A leverage sensitivity sweep on the original Shreveport Ct property
   (25/35/50/75/100% down) to find the approximate cash-flow breakeven
   point on leverage.

Run from the project root: python -m scripts.phase1_followup_checks
"""

from __future__ import annotations

import copy

import numpy as np

from src.data_layer.rentcast_client import RentCastClient
from src.simulation.monte_carlo import Assumptions, run_monte_carlo

SHREVEPORT = "6500 Shreveport Ct, Bakersfield, CA 93309"
HIGH_YIELD_CANDIDATE = "3214 Oliver St, Bakersfield, CA 93307"


def print_summary(label: str, snapshot, summary: dict) -> None:
    gross_yield = (snapshot.monthly_rent * 12) / snapshot.purchase_price
    print(f"\n{label}")
    print("-" * len(label))
    print(f"Address:            {snapshot.address}")
    print(f"Purchase price:     ${snapshot.purchase_price:,.0f}")
    print(f"Monthly rent:       ${snapshot.monthly_rent:,.0f}")
    print(f"Gross rent yield:   {gross_yield:.2%}  (annual rent / price, unlevered)")
    print(f"Going-in cap rate:  {summary['going_in_cap_rate']:.2%}")
    print(f"P(cash flow>0, Y1): {summary['p_cash_flow_positive_year1']:.1%}")
    print(f"IRR median:         {summary['irr_median']:.2%}  (5th-95th: {summary['irr_p05']:.2%} to {summary['irr_p95']:.2%})")


def check_high_yield_submarket(client: RentCastClient) -> None:
    print("\n" + "=" * 70)
    print("CHECK 1: higher-yield submarket (93307) vs. Shreveport Ct (93309)")
    print("=" * 70)

    assumptions = Assumptions()

    shreveport_snap = client.get_property_snapshot(SHREVEPORT)
    shreveport_results = run_monte_carlo(shreveport_snap, assumptions, n_iterations=5000, seed=42)
    print_summary("Shreveport Ct, 93309 (original)", shreveport_snap, shreveport_results.summary())

    oliver_snap = client.get_property_snapshot(HIGH_YIELD_CANDIDATE)
    oliver_results = run_monte_carlo(oliver_snap, assumptions, n_iterations=5000, seed=42)
    print_summary("Oliver St, 93307 (higher gross-yield submarket)", oliver_snap, oliver_results.summary())


def check_leverage_sweep(client: RentCastClient) -> None:
    print("\n" + "=" * 70)
    print("CHECK 2: leverage sensitivity sweep, Shreveport Ct")
    print("=" * 70)

    snapshot = client.get_property_snapshot(SHREVEPORT)
    down_payment_pcts = [0.25, 0.35, 0.50, 0.75, 1.00]

    print(f"{'Down %':>8} {'Loan $':>12} {'Ann. debt svc':>14} {'P(CF>0,Y1)':>12} {'IRR median':>12}")
    for pct in down_payment_pcts:
        a = copy.copy(Assumptions())
        a.down_payment_pct = pct
        results = run_monte_carlo(snapshot, a, n_iterations=3000, seed=42)
        summary = results.summary()

        loan_amount = snapshot.purchase_price * (1 - pct)
        from src.simulation.monte_carlo import _monthly_payment
        annual_debt_service = 0.0 if pct >= 1.0 else _monthly_payment(loan_amount, a.interest_rate, a.loan_term_years) * 12

        print(
            f"{pct:>7.0%} ${loan_amount:>10,.0f} ${annual_debt_service:>12,.0f} "
            f"{summary['p_cash_flow_positive_year1']:>11.1%} {summary['irr_median']:>11.2%}"
        )

    print(
        "\nNote: at 100% down there is no loan and no leverage — IRR there reflects "
        "unlevered return only (cap rate + appreciation - costs), included as the "
        "reference endpoint of the curve, not a realistic financing option."
    )


def main() -> None:
    client = RentCastClient()
    check_high_yield_submarket(client)
    check_leverage_sweep(client)


if __name__ == "__main__":
    main()
