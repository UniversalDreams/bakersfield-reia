"""Phase 1c — market-wide breakeven cap rate screen.

Pulls SFR + Multi-Family candidates across Kern County submarkets, computes
each one's going-in cap rate, and runs it through
min_down_payment_for_target_cap_rate to see whether anything clears a
realistic 25-35% down-payment threshold at current financing terms.

This is a cheap point-estimate screen (ignores opex variance), not a
replacement for the full Monte Carlo — its job is to narrow 10-15 candidates
down to whichever ones are worth the full simulation.

Run from the project root: python -m scripts.phase1c_market_screen
"""

from __future__ import annotations

import csv
import statistics

from src.data_layer.rentcast_client import RentCastClient
from src.simulation.leverage_threshold import min_down_payment_for_target_cap_rate
from src.simulation.monte_carlo import Assumptions, going_in_cap_rate

# RentCast's rent AVM sometimes estimates a single unit's market rent while
# the value AVM prices the whole multi-unit building (seen directly on
# 1207 Monterey St: value comps were 8bd/4ba ~$600k buildings, rent comps
# were 2bd/1ba ~$1,400/mo units). There's no reliable unit-count field to
# correct for this, so instead of guessing a multiplier we detect the
# mismatch and mark the cap rate unverifiable rather than reporting a
# fabricated number.
RENT_COMP_BEDROOM_MISMATCH_RATIO = 0.65

ZIPS = ["93305", "93307", "93308", "93309", "93313", "93311", "93312", "93314"]
SUBMARKET_TIER = {
    "93305": "cash-flow",
    "93307": "cash-flow",
    "93308": "cash-flow",
    "93309": "middle",
    "93313": "middle",
    "93311": "appreciation",
    "93312": "appreciation",
    "93314": "appreciation",
}


def main() -> None:
    client = RentCastClient()
    rows = []

    for z in ZIPS:
        sfr_results = client._get(
            "/properties", {"zipCode": z, "propertyType": "Single Family", "limit": 2}
        )
        mf_results = client._get(
            "/properties", {"zipCode": z, "propertyType": "Multi-Family", "limit": 2}
        )
        candidates = [(p["formattedAddress"], "Single Family") for p in sfr_results] + [
            (p["formattedAddress"], "Multi-Family") for p in mf_results
        ]

        for address, ptype_hint in candidates:
            try:
                snapshot = client.get_property_snapshot(address)
                rent_avm = client.get_avm_rent(address)
            except Exception as exc:
                print(f"  SKIP {address}: {exc}")
                continue

            subject_bd = rent_avm["subjectProperty"].get("bedrooms")
            comp_bds = [
                c.get("bedrooms") for c in rent_avm.get("comparables", []) if c.get("bedrooms") is not None
            ]
            med_comp_bd = statistics.median(comp_bds) if comp_bds else None
            rent_unverifiable = (
                med_comp_bd is not None
                and subject_bd is not None
                and subject_bd > 0
                and (med_comp_bd / subject_bd) <= RENT_COMP_BEDROOM_MISMATCH_RATIO
            )

            a = Assumptions()
            cap_rate = going_in_cap_rate(snapshot, a)
            required_down = min_down_payment_for_target_cap_rate(
                cap_rate, a.interest_rate, a.loan_term_years
            )

            rows.append(
                {
                    "address": snapshot.address,
                    "zip": z,
                    "tier": SUBMARKET_TIER[z],
                    "property_type": snapshot.property_type or ptype_hint,
                    "bedrooms": snapshot.bedrooms,
                    "price": snapshot.purchase_price,
                    "monthly_rent": snapshot.monthly_rent,
                    "cap_rate": cap_rate,
                    "required_down_pct": required_down,
                    "gap_vs_25pct_down": required_down - 0.25,
                    "gap_vs_35pct_down": required_down - 0.35,
                    "rent_unverifiable": rent_unverifiable,
                }
            )
            flag = " [UNVERIFIABLE: rent AVM likely priced 1 unit, not whole building]" if rent_unverifiable else ""
            print(
                f"  {snapshot.address[:45]:45s} ({snapshot.property_type or ptype_hint:12s}) "
                f"cap={cap_rate:6.2%}  req.down={required_down:6.1%}{flag}"
            )

    rows.sort(key=lambda r: r["required_down_pct"])

    out_path = "data/reports/phase1c_market_screen.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    verifiable = [r for r in rows if not r["rent_unverifiable"]]
    unverifiable = [r for r in rows if r["rent_unverifiable"]]
    n_total = len(verifiable)
    n_clears_25 = sum(1 for r in verifiable if r["required_down_pct"] <= 0.25)
    n_clears_35 = sum(1 for r in verifiable if r["required_down_pct"] <= 0.35)

    print("\n" + "=" * 70)
    print("RANKED RESULTS (lowest required down payment first, verifiable only)")
    print("=" * 70)
    print(f"{'Address':45s} {'Type':12s} {'Zip':5s} {'Cap':>7s} {'Req.Down':>9s}")
    for r in verifiable:
        print(
            f"{r['address'][:45]:45s} {r['property_type'][:12]:12s} {r['zip']:5s} "
            f"{r['cap_rate']:>6.2%} {r['required_down_pct']:>8.1%}"
        )

    if unverifiable:
        print(f"\n{len(unverifiable)} excluded as UNVERIFIABLE (rent AVM likely priced 1 unit of a multi-unit building, not the whole property):")
        for r in unverifiable:
            print(f"  {r['address']}")

    print(f"\nSaved full table (incl. unverifiable, flagged) to {out_path}")
    print(f"\nn={n_total} verifiable candidates screened")
    print(f"  Clears <=25% down: {n_clears_25} ({n_clears_25/n_total:.0%})")
    print(f"  Clears <=35% down: {n_clears_35} ({n_clears_35/n_total:.0%})")


if __name__ == "__main__":
    main()
