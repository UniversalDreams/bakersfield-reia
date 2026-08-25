"""Breakeven cap rate as a function of leverage and financing rate.

Derivation: Year-1 cash flow >= 0  <=>  NOI >= annual debt service
<=> (NOI / price) >= (annual debt service / loan) * (loan / price)
<=> cap_rate >= mortgage_constant * LTV

This ignores opex variance (it's a point-estimate screening threshold, not
a substitute for the Monte Carlo simulation) — use it to rank/filter
candidates cheaply, then run the full simulation on survivors.
"""

from __future__ import annotations


def mortgage_constant(annual_rate: float, term_years: int, interest_only: bool = False) -> float:
    """Annual debt constant: annual debt service per $1 of loan.

    interest_only=True: no principal paydown, so the constant is just the
    rate itself (payment = principal x rate).
    """
    if interest_only:
        return annual_rate
    i = annual_rate / 12
    n = term_years * 12
    if i == 0:
        return 12 / n
    monthly_payment_factor = (i * (1 + i) ** n) / ((1 + i) ** n - 1)
    return monthly_payment_factor * 12


def min_cap_rate_for_breakeven(
    down_payment_pct: float, annual_rate: float, term_years: int = 30, interest_only: bool = False
) -> float:
    """Going-in cap rate needed for Year-1 cash flow >= 0, ignoring opex variance."""
    ltv = 1 - down_payment_pct
    return mortgage_constant(annual_rate, term_years, interest_only) * ltv


def min_down_payment_for_target_cap_rate(
    cap_rate: float, annual_rate: float, term_years: int = 30, interest_only: bool = False
) -> float:
    """Inverse: down payment needed for a given property to breakeven."""
    mc = mortgage_constant(annual_rate, term_years, interest_only)
    return max(0.0, 1 - (cap_rate / mc))
