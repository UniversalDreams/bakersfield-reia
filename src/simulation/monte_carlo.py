"""Phase 1 walking-skeleton Monte Carlo simulation.

Six inputs are "fixed point estimates" per PROJECT_PLAN.md Phase 1 — i.e.
single global scalars, not per-ZIP Bayesian priors (that's Phase 3) and not
scenario-based insurance (that's Phase 4): rent, vacancy, cap rate,
appreciation, interest rate, flat insurance cost.

Those scalars are the *parameters* of simple stochastic draws (annual rent
growth, annual appreciation, annual vacancy) — that's what makes this a
Monte Carlo simulation rather than a single deterministic DCF. Cap rate is
reported as an informational going-in metric, not simulated.

Purchase financing assumes a DSCR/conventional investment loan (20-25% down)
per PROJECT_PLAN.md's explicit exclusion of FHA/owner-occupant assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import brentq

from src.data_layer.rentcast_client import PropertySnapshot


@dataclass
class Assumptions:
    hold_years: int = 10

    down_payment_pct: float = 0.25
    closing_costs_pct: float = 0.03  # of purchase price, paid at acquisition
    interest_rate: float = 0.070  # fixed-rate loan, locked at purchase — not simulated
    loan_term_years: int = 30

    property_tax_rate: float = 0.011  # CA Prop 13-ish effective rate, of assessed (purchase) value

    insurance_annual: float = 1800.0  # flat, constant every year (Phase 4 replaces this)

    maintenance_pct_of_rent: float = 0.06
    capex_pct_of_rent: float = 0.05
    property_mgmt_pct_of_rent: float = 0.0  # assume self-managed by default

    rent_growth_mean: float = 0.03
    rent_growth_std: float = 0.015

    appreciation_mean: float = 0.03
    appreciation_std: float = 0.03

    vacancy_mean: float = 0.06
    vacancy_std: float = 0.02

    selling_costs_pct: float = 0.07  # commission + closing at exit


@dataclass
class SimulationResults:
    irr_samples: np.ndarray
    year1_cash_flow_samples: np.ndarray
    going_in_cap_rate: float
    n_iterations: int

    def summary(self) -> dict:
        irr_valid = self.irr_samples[~np.isnan(self.irr_samples)]
        return {
            "n_iterations": self.n_iterations,
            "n_irr_converged": int(irr_valid.size),
            "p_cash_flow_positive_year1": float(
                np.mean(self.year1_cash_flow_samples > 0)
            ),
            "irr_mean": float(np.mean(irr_valid)) if irr_valid.size else float("nan"),
            "irr_p05": float(np.percentile(irr_valid, 5)) if irr_valid.size else float("nan"),
            "irr_p25": float(np.percentile(irr_valid, 25)) if irr_valid.size else float("nan"),
            "irr_median": float(np.percentile(irr_valid, 50)) if irr_valid.size else float("nan"),
            "irr_p75": float(np.percentile(irr_valid, 75)) if irr_valid.size else float("nan"),
            "irr_p95": float(np.percentile(irr_valid, 95)) if irr_valid.size else float("nan"),
            "going_in_cap_rate": self.going_in_cap_rate,
        }


def _monthly_payment(loan_amount: float, annual_rate: float, term_years: int) -> float:
    monthly_rate = annual_rate / 12
    n_payments = term_years * 12
    if monthly_rate == 0:
        return loan_amount / n_payments
    return (
        loan_amount
        * monthly_rate
        * (1 + monthly_rate) ** n_payments
        / ((1 + monthly_rate) ** n_payments - 1)
    )


def _remaining_balance(
    loan_amount: float, annual_rate: float, term_years: int, years_elapsed: int
) -> float:
    monthly_rate = annual_rate / 12
    n_payments = term_years * 12
    payment = _monthly_payment(loan_amount, annual_rate, term_years)
    months_elapsed = years_elapsed * 12
    if monthly_rate == 0:
        return max(loan_amount - payment * months_elapsed, 0.0)
    balance = loan_amount * (1 + monthly_rate) ** months_elapsed - payment * (
        ((1 + monthly_rate) ** months_elapsed - 1) / monthly_rate
    )
    return max(balance, 0.0)


def _irr(cash_flows: list[float]) -> float:
    """Annual IRR via bisection on NPV(r) = 0. NaN if no sign change (no root)."""

    def npv(rate: float) -> float:
        return sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))

    if cash_flows[0] >= 0:
        return float("nan")
    if all(cf <= 0 for cf in cash_flows[1:]):
        return float("nan")

    try:
        return brentq(npv, -0.99, 5.0)
    except ValueError:
        return float("nan")


def simulate_single_path(
    snapshot: PropertySnapshot, assumptions: Assumptions, rng: np.random.Generator
) -> tuple[list[float], float]:
    a = assumptions
    purchase_price = snapshot.purchase_price
    annual_rent0 = snapshot.monthly_rent * 12

    down_payment = purchase_price * a.down_payment_pct
    closing_costs = purchase_price * a.closing_costs_pct
    loan_amount = purchase_price - down_payment
    annual_debt_service = _monthly_payment(loan_amount, a.interest_rate, a.loan_term_years) * 12

    rent_growth_draws = rng.normal(a.rent_growth_mean, a.rent_growth_std, a.hold_years)
    appreciation_draws = rng.normal(a.appreciation_mean, a.appreciation_std, a.hold_years)
    vacancy_draws = np.clip(
        rng.normal(a.vacancy_mean, a.vacancy_std, a.hold_years), 0.0, 1.0
    )

    cash_flows = [-(down_payment + closing_costs)]
    year1_cash_flow = None
    cumulative_rent_growth = 1.0
    cumulative_appreciation = 1.0

    for t in range(a.hold_years):
        cumulative_rent_growth *= 1 + rent_growth_draws[t]
        cumulative_appreciation *= 1 + appreciation_draws[t]

        gross_scheduled_rent = annual_rent0 * cumulative_rent_growth
        effective_rent = gross_scheduled_rent * (1 - vacancy_draws[t])
        property_value = purchase_price * cumulative_appreciation

        operating_expenses = (
            property_value * a.property_tax_rate
            + a.insurance_annual
            + effective_rent * a.maintenance_pct_of_rent
            + effective_rent * a.capex_pct_of_rent
            + effective_rent * a.property_mgmt_pct_of_rent
        )
        noi = effective_rent - operating_expenses
        cash_flow = noi - annual_debt_service

        if t == a.hold_years - 1:
            remaining_balance = _remaining_balance(
                loan_amount, a.interest_rate, a.loan_term_years, a.hold_years
            )
            selling_costs = property_value * a.selling_costs_pct
            net_sale_proceeds = property_value - selling_costs - remaining_balance
            cash_flow += net_sale_proceeds

        if t == 0:
            year1_cash_flow = cash_flow

        cash_flows.append(cash_flow)

    irr = _irr(cash_flows)
    return cash_flows, irr, year1_cash_flow


def run_monte_carlo(
    snapshot: PropertySnapshot,
    assumptions: Assumptions | None = None,
    n_iterations: int = 5000,
    seed: int | None = 42,
) -> SimulationResults:
    a = assumptions or Assumptions()
    rng = np.random.default_rng(seed)

    irr_samples = np.empty(n_iterations)
    year1_cf_samples = np.empty(n_iterations)

    for i in range(n_iterations):
        _, irr, year1_cf = simulate_single_path(snapshot, a, rng)
        irr_samples[i] = irr
        year1_cf_samples[i] = year1_cf

    return SimulationResults(
        irr_samples=irr_samples,
        year1_cash_flow_samples=year1_cf_samples,
        going_in_cap_rate=going_in_cap_rate(snapshot, a),
        n_iterations=n_iterations,
    )


def going_in_cap_rate(snapshot: PropertySnapshot, assumptions: Assumptions | None = None) -> float:
    """Year-1 NOI / purchase price, at mean assumptions (no simulation)."""
    a = assumptions or Assumptions()
    annual_rent0 = snapshot.monthly_rent * 12
    effective_rent = annual_rent0 * (1 - a.vacancy_mean)
    operating_expenses = (
        snapshot.purchase_price * a.property_tax_rate
        + a.insurance_annual
        + effective_rent * (a.maintenance_pct_of_rent + a.capex_pct_of_rent + a.property_mgmt_pct_of_rent)
    )
    year1_noi = effective_rent - operating_expenses
    return year1_noi / snapshot.purchase_price
