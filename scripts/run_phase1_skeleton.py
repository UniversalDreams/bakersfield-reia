"""Phase 1 walking skeleton: pull one Bakersfield property, run a fixed-input
Monte Carlo, print probability-based output. Run from the project root:

    python -m scripts.run_phase1_skeleton
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.data_layer.rentcast_client import RentCastClient
from src.simulation.monte_carlo import Assumptions, run_monte_carlo

TEST_ADDRESS = "6500 Shreveport Ct, Bakersfield, CA 93309"


def main() -> None:
    client = RentCastClient()
    snapshot = client.get_property_snapshot(TEST_ADDRESS)

    print("Property snapshot")
    print("-----------------")
    print(f"Address:        {snapshot.address}")
    print(f"Type:           {snapshot.property_type}, built {snapshot.year_built}")
    print(f"Beds/baths:     {snapshot.bedrooms}bd / {snapshot.bathrooms}ba, {snapshot.square_footage} sqft")
    print(f"Purchase price: ${snapshot.purchase_price:,.0f}  (range ${snapshot.price_range_low:,.0f}-${snapshot.price_range_high:,.0f})")
    print(f"Monthly rent:   ${snapshot.monthly_rent:,.0f}  (range ${snapshot.rent_range_low:,.0f}-${snapshot.rent_range_high:,.0f})")
    print()

    assumptions = Assumptions()
    results = run_monte_carlo(snapshot, assumptions, n_iterations=5000, seed=42)
    summary = results.summary()

    print("Simulation summary (fixed point-estimate inputs, Phase 1)")
    print("-----------------------------------------------------------")
    print(f"Iterations:                {summary['n_iterations']} ({summary['n_irr_converged']} produced a real IRR root)")
    print(f"Going-in cap rate (Yr 1):  {summary['going_in_cap_rate']:.2%}")
    print(f"P(cash flow > 0, Yr 1):    {summary['p_cash_flow_positive_year1']:.1%}")
    print(f"IRR mean:                  {summary['irr_mean']:.2%}")
    print(f"IRR 5th / 25th pctile:     {summary['irr_p05']:.2%} / {summary['irr_p25']:.2%}")
    print(f"IRR median:                {summary['irr_median']:.2%}")
    print(f"IRR 75th / 95th pctile:    {summary['irr_p75']:.2%} / {summary['irr_p95']:.2%}")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

    axes[0].hist(results.irr_samples[~__import__("numpy").isnan(results.irr_samples)], bins=60, color="#3b6ea5")
    axes[0].set_title(f"{snapshot.address}\nSimulated {assumptions.hold_years}-yr IRR ({summary['n_iterations']} paths)")
    axes[0].set_xlabel("IRR")
    axes[0].set_ylabel("Count")

    axes[1].hist(results.year1_cash_flow_samples, bins=60, color="#a53b3b")
    axes[1].axvline(0, color="black", linestyle="--", linewidth=1)
    axes[1].set_title("Simulated Year-1 cash flow")
    axes[1].set_xlabel("Year 1 cash flow ($)")

    fig.tight_layout()
    out_path = "data/reports/phase1_walking_skeleton.png"
    fig.savefig(out_path, dpi=130)
    print(f"\nSaved histogram to {out_path}")


if __name__ == "__main__":
    main()
