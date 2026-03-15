"""
High-level analysis orchestrator.

Ties together catalog simulation, portfolio optimization, bundle analysis,
and decision evaluation into a single `analyze()` call.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

import numpy as np

from .catalog import CATALOG, CatalogEntry, get_catalog, simulate_catalog
from .combination import find_optimal_portfolio_with_costs
from .bundles import recommend_bundles
from .confounding import ConfoundingPrior, publication_bias_correct
from .intervention import Distribution, Intervention, MortalityEffect
from .profile import Profile
from .simulate import simulate_qaly_profile_vectorized


@dataclass
class AnalysisConfig:
    """Configuration for a complete supplement analysis."""

    profile: Profile
    wtp: float = 200_000  # Willingness-to-pay per QALY
    horizon_years: float = 40
    pub_bias_shrinkage: float = 0.30
    n_simulations: int = 50_000
    random_state: int = 42
    complexity_free_slots: int = 3
    complexity_cost_per_item: float = 0.0005  # QALYs/yr per extra item
    categories: Optional[List[str]] = None  # Filter catalog; None = all


@dataclass
class Decision:
    """A specific stack change to evaluate."""

    type: Literal["add", "drop", "adjust"]
    item_id: str
    label: str  # Human-readable description, e.g. "ADD: Glycine 2g ($40/yr)"
    # For DROP: the item's effect is negated and cost becomes savings
    # For ADJUST: override any of these to model the changed version
    override_hr: Optional[float] = None
    override_cost: Optional[float] = None
    override_qol: Optional[float] = None


@dataclass
class AnalysisResult:
    """Complete analysis output."""

    config: AnalysisConfig
    item_results: List[dict]  # Per-item simulation results
    item_results_by_id: Dict[str, dict]  # Same, keyed by ID
    portfolio: List[dict]  # Greedy portfolio steps
    bundle_recommendations: List[dict]  # Bundle analysis
    decisions: Optional[List[dict]] = None  # Decision evaluations

    @property
    def selected_ids(self) -> List[str]:
        """IDs selected by portfolio optimizer."""
        if not self.portfolio:
            return []
        return self.portfolio[-1]["selected_interventions"]

    @property
    def total_annual_cost(self) -> float:
        if not self.portfolio:
            return 0
        return self.portfolio[-1]["total_annual_cost"]

    @property
    def total_qaly(self) -> float:
        if not self.portfolio:
            return 0
        return self.portfolio[-1]["total_qaly"]

    @property
    def total_days(self) -> float:
        return self.total_qaly * 365.25


def _simulate_one(
    name: str,
    hr: float,
    log_sd: float,
    conf_a: float,
    conf_b: float,
    annual_cost: float,
    qol_annual: float,
    config: AnalysisConfig,
) -> dict:
    """Simulate a single intervention (used for decisions with overrides)."""
    intervention = Intervention(
        id=name, name=name, category="diet",
        mortality=MortalityEffect(
            hazard_ratio=Distribution(
                type="lognormal",
                params={"log_mean": np.log(hr), "log_sd": log_sd},
            ),
        ),
        confounding_prior=ConfoundingPrior(alpha=conf_a, beta=conf_b),
    )
    r = simulate_qaly_profile_vectorized(
        intervention, config.profile,
        n_simulations=config.n_simulations,
        random_state=config.random_state,
    )
    mort_qaly = r.mean
    qol_qaly = qol_annual * config.horizon_years
    total_qaly = mort_qaly + qol_qaly
    total_cost = annual_cost * config.horizon_years
    net_value = total_qaly * config.wtp - total_cost

    return {
        "name": name,
        "mort_qaly": mort_qaly,
        "qol_qaly": qol_qaly,
        "total_qaly": total_qaly,
        "days": total_qaly * 365.25,
        "annual_cost": annual_cost,
        "total_cost": total_cost,
        "net_value": net_value,
        "p_benefit": r.prob_positive,
        "ci_low": r.ci95[0] * 365.25 if r.ci95 else 0,
        "ci_high": r.ci95[1] * 365.25 if r.ci95 else 0,
    }


def evaluate_decisions(
    decisions: List[Decision],
    config: AnalysisConfig,
) -> List[dict]:
    """
    Evaluate specific add/drop/adjust decisions.

    ADD: Simulate the item and compute net value.
    DROP: Negate the item's effect; cost becomes savings.
    ADJUST: Simulate with overridden parameters.

    Returns list of dicts sorted by net_value descending.
    """
    results = []

    for d in decisions:
        entry = CATALOG.get(d.item_id)

        if d.type == "add":
            if entry is None:
                raise ValueError(f"Unknown catalog item: {d.item_id}")
            hr = publication_bias_correct(
                d.override_hr or entry.hr_observed,
                config.pub_bias_shrinkage,
            )
            cost = d.override_cost if d.override_cost is not None else entry.annual_cost
            qol = d.override_qol if d.override_qol is not None else entry.qol_annual
            r = _simulate_one(
                d.label, hr, entry.log_sd,
                entry.conf_alpha, entry.conf_beta,
                cost, qol, config,
            )

        elif d.type == "drop":
            if entry is None:
                raise ValueError(f"Unknown catalog item: {d.item_id}")
            # Dropping = you LOSE the item's benefit and GAIN cost savings
            hr = publication_bias_correct(
                entry.hr_observed, config.pub_bias_shrinkage,
            )
            r = _simulate_one(
                d.label, hr, entry.log_sd,
                entry.conf_alpha, entry.conf_beta,
                -entry.annual_cost,  # Savings
                -entry.qol_annual,   # Lose QoL benefit
                config,
            )

        elif d.type == "adjust":
            # User provides override params for the adjusted version
            if entry is None:
                raise ValueError(f"Unknown catalog item: {d.item_id}")
            hr_raw = d.override_hr if d.override_hr is not None else entry.hr_observed
            hr = publication_bias_correct(hr_raw, config.pub_bias_shrinkage)
            cost = d.override_cost if d.override_cost is not None else 0
            qol = d.override_qol if d.override_qol is not None else 0
            r = _simulate_one(
                d.label, hr, entry.log_sd,
                entry.conf_alpha, entry.conf_beta,
                cost, qol, config,
            )

        r["decision_type"] = d.type
        r["item_id"] = d.item_id
        r["label"] = d.label

        if r["net_value"] > 0:
            r["verdict"] = "DO IT"
        elif r["net_value"] > -2000:
            r["verdict"] = "MARGINAL"
        else:
            r["verdict"] = "SKIP"

        results.append(r)

    results.sort(key=lambda x: x["net_value"], reverse=True)
    return results


def analyze(
    config: AnalysisConfig,
    current_stack: Optional[List[str]] = None,
    decisions: Optional[List[Decision]] = None,
    catalog_entries: Optional[Dict[str, CatalogEntry]] = None,
) -> AnalysisResult:
    """
    Run complete supplement analysis pipeline.

    1. Simulate all catalog entries
    2. Build optimal greedy portfolio with costs
    3. Analyze bundle recommendations
    4. Optionally evaluate specific decisions

    Args:
        config: Analysis parameters (profile, WTP, horizon, etc.)
        current_stack: Optional list of catalog IDs currently being taken.
            Used for context in decision analysis.
        decisions: Optional specific add/drop/adjust decisions to evaluate.
        catalog_entries: Optional custom catalog (default: full CATALOG).

    Returns:
        AnalysisResult with all outputs.
    """
    # 1. Simulate all catalog items
    item_results = simulate_catalog(
        profile=config.profile,
        n_simulations=config.n_simulations,
        random_state=config.random_state,
        pub_bias_shrinkage=config.pub_bias_shrinkage,
        horizon_years=config.horizon_years,
        categories=config.categories,
    )

    # Key by ID for lookups
    item_results_by_id = {r["id"]: r for r in item_results}

    # 2. Build greedy portfolio
    single_qalys = {r["id"]: r["total_qaly"] for r in item_results}
    annual_costs = {r["id"]: r["annual_cost"] for r in item_results}

    portfolio = find_optimal_portfolio_with_costs(
        single_qalys=single_qalys,
        annual_costs=annual_costs,
        wtp=config.wtp,
        horizon_years=config.horizon_years,
        complexity_free_slots=config.complexity_free_slots,
        complexity_cost_per_item=config.complexity_cost_per_item,
    )

    # 3. Bundle recommendations
    selected_ids = portfolio[-1]["selected_interventions"] if portfolio else []
    bundle_recs = recommend_bundles(
        selected_ids=selected_ids,
        item_results=item_results_by_id,
        horizon_years=config.horizon_years,
    )

    # 4. Decision analysis
    decision_results = None
    if decisions:
        decision_results = evaluate_decisions(decisions, config)

    return AnalysisResult(
        config=config,
        item_results=item_results,
        item_results_by_id=item_results_by_id,
        portfolio=portfolio,
        bundle_recommendations=bundle_recs,
        decisions=decision_results,
    )
