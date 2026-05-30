"""
High-level analysis orchestrator.

Ties together catalog simulation, portfolio optimization, bundle analysis,
and decision evaluation into a single `analyze()` call.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Literal, Optional

import numpy as np

from .catalog import CATALOG, CatalogEntry, get_catalog, simulate_catalog
from .combination import find_optimal_portfolio_with_costs
from .bundles import recommend_bundles
from .confounding import ConfoundingPrior, hr_to_lognormal_params, publication_bias_correct
from .defaults import (
    DEFAULT_COST_DISCOUNT_RATE,
    DEFAULT_QALY_DISCOUNT_RATE,
    validate_qaly_discount_rate,
)
from .intervention import Distribution, Intervention, MortalityEffect
from .profile import Profile
from .simulate import (
    effective_hr_for_mortality_qaly,
    effective_qol_factor_for_years,
    mortality_qaly_for_combined_hr,
    simulate_qaly_profile_vectorized,
)
from .sleep import (
    SleepBurdenEstimate,
    SleepMetrics,
    estimate_sleep_burden,
    sleep_baseline_mortality_multiplier,
    sleep_component_overlap_multipliers,
)
from .stack_interactions import build_stack_interaction_penalty_fn


@dataclass
class AnalysisConfig:
    """Configuration for a complete supplement analysis."""

    profile: Profile
    wtp: float = 200_000  # Willingness-to-pay per QALY
    horizon_years: float = 40  # Used for QoL QALY calc; mortality uses survival curves
    qaly_discount_rate: float = DEFAULT_QALY_DISCOUNT_RATE
    cost_discount_rate: float = DEFAULT_COST_DISCOUNT_RATE
    pub_bias_shrinkage: float = 0.30
    # Soft cap on total portfolio QALY gain. Absent a ceiling, greedy
    # additive models can claim multi-QALY gains from supplement stacks that
    # exceed what primary-prevention CEA literature supports. A concave
    # saturation caps the total at ~``portfolio_qaly_ceiling`` while
    # preserving ranking. Default ~3 QALY over 40 yrs for healthy adults.
    portfolio_qaly_ceiling: Optional[float] = 3.0
    n_simulations: int = 50_000
    random_state: int = 42
    categories: Optional[List[str]] = None  # Filter catalog; None = all
    active_interaction_tags: Optional[List[str]] = None
    sleep_metrics: Optional[SleepMetrics] = None
    sleep_estimate: Optional[SleepBurdenEstimate] = None

    def __post_init__(self) -> None:
        self.qaly_discount_rate = validate_qaly_discount_rate(self.qaly_discount_rate)
        if self.sleep_estimate is None and self.sleep_metrics is not None:
            self.sleep_estimate = estimate_sleep_burden(self.sleep_metrics)

    @property
    def sleep_overlap_multipliers(self) -> Optional[Dict[str, float]]:
        if self.sleep_estimate is None:
            return None
        return sleep_component_overlap_multipliers(self.sleep_estimate)

    @property
    def sleep_baseline_hazard_multiplier(self) -> float:
        return sleep_baseline_mortality_multiplier(self.sleep_estimate)


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
    qol_years: float,
    sleep_qol_annual: float,
    sleep_mortality_hr_multiplier: float,
    config: AnalysisConfig,
) -> dict:
    """Simulate a single intervention (used for decisions with overrides)."""
    intervention = Intervention(
        id=name, name=name, category="diet",
        mortality=MortalityEffect(
            hazard_ratio=Distribution(
                type="lognormal",
                params={"hr": hr, "log_sd": log_sd},
            ),
        ),
        confounding_prior=ConfoundingPrior(alpha=conf_a, beta=conf_b),
    )
    r = simulate_qaly_profile_vectorized(
        intervention, config.profile,
        n_simulations=config.n_simulations,
        discount_rate=config.qaly_discount_rate,
        cost_discount_rate=config.cost_discount_rate,
        active_interaction_tags=config.active_interaction_tags,
        baseline_hazard_multiplier=config.sleep_baseline_hazard_multiplier,
        global_intervention_hr_multiplier=sleep_mortality_hr_multiplier,
        random_state=config.random_state,
    )
    harm_qaly = r.expected_harm_qalys + r.expected_interaction_harm_qalys
    mort_qaly = r.mean - harm_qaly
    effective_years = min(float(qol_years), float(config.horizon_years))
    qol_factor = effective_qol_factor_for_years(
        r.expected_qol_weights,
        effective_years,
        r.expected_qol_factor,
    )
    qol_qaly = qol_annual * qol_factor
    sleep_qol_qaly = sleep_qol_annual * qol_factor
    total_qaly = mort_qaly + harm_qaly + qol_qaly + sleep_qol_qaly
    # Survival-weighted discounted cost
    total_cost = annual_cost * r.expected_discounted_cost_factor
    net_value = total_qaly * config.wtp - total_cost
    cost_per_qaly = total_cost / total_qaly if total_qaly > 0 and annual_cost > 0 else None

    return {
        "name": name,
        "mort_qaly": mort_qaly,
        "posterior_hr": float(r.posterior_hr_mean) if r.posterior_hr_mean is not None else 1.0,
        "harm_qaly": harm_qaly,
        "direct_harm_qaly": r.expected_harm_qalys,
        "interaction_harm_qaly": r.expected_interaction_harm_qalys,
        "qol_qaly": qol_qaly,
        "qol_years": effective_years,
        "sleep_qol_annual": sleep_qol_annual,
        "sleep_qol_qaly": sleep_qol_qaly,
        "total_qaly": total_qaly,
        "days": total_qaly * 365.25,
        "annual_cost": annual_cost,
        "total_cost": total_cost,
        "cost_per_qaly": cost_per_qaly,
        "net_value": net_value,
        "p_benefit": r.prob_positive,
        "p_harm": r.prob_negative,
        "expected_upside_days": r.expected_upside * 365.25,
        "expected_downside_days": r.expected_downside * 365.25,
        "ci_low": r.ci95[0] * 365.25 if r.ci95 else 0,
        "ci_high": r.ci95[1] * 365.25 if r.ci95 else 0,
        # 80% interval on TOTAL QALYs: shift the draw-based interval by the
        # deterministic non-mortality (QoL) component (total_qaly - r.mean).
        "net_qaly_ci": [
            r.ci80[0] + (total_qaly - r.mean),
            r.ci80[1] + (total_qaly - r.mean),
        ],
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
            if d.override_hr is None:
                hr = entry.corrected_hr_observed(config.pub_bias_shrinkage, config.profile)
            else:
                hr = publication_bias_correct(d.override_hr, config.pub_bias_shrinkage)
            cost = d.override_cost if d.override_cost is not None else entry.annual_cost
            qol = d.override_qol if d.override_qol is not None else entry.effective_qol_annual()
            sleep_qol = entry.sleep_qol_annual(config.sleep_estimate)
            sleep_mortality_hr_multiplier = entry.sleep_mortality_hr_multiplier(config.sleep_estimate)
            r = _simulate_one(
                d.label, hr, entry.log_sd,
                entry.conf_alpha, entry.conf_beta,
                cost, qol, entry.qol_years, sleep_qol, sleep_mortality_hr_multiplier, config,
            )

        elif d.type == "drop":
            if entry is None:
                raise ValueError(f"Unknown catalog item: {d.item_id}")
            # Dropping = you LOSE the item's benefit and GAIN cost savings
            hr = entry.corrected_hr_observed(config.pub_bias_shrinkage, config.profile)
            sleep_qol = entry.sleep_qol_annual(config.sleep_estimate)
            sleep_mortality_hr_multiplier = entry.sleep_mortality_hr_multiplier(config.sleep_estimate)
            r = _simulate_one(
                d.label, hr, entry.log_sd,
                entry.conf_alpha, entry.conf_beta,
                -entry.annual_cost,  # Savings
                -entry.effective_qol_annual(),   # Lose QoL benefit
                entry.qol_years,
                -sleep_qol,          # Lose sleep-related QoL benefit
                sleep_mortality_hr_multiplier,
                config,
            )

        elif d.type == "adjust":
            # User provides override params for the adjusted version
            if entry is None:
                raise ValueError(f"Unknown catalog item: {d.item_id}")
            hr_raw = d.override_hr if d.override_hr is not None else entry.hr_observed
            if d.override_hr is None:
                hr = entry.corrected_hr_observed(config.pub_bias_shrinkage, config.profile)
            else:
                hr = publication_bias_correct(hr_raw, config.pub_bias_shrinkage)
            cost = d.override_cost if d.override_cost is not None else 0
            qol = d.override_qol if d.override_qol is not None else 0
            sleep_qol = entry.sleep_qol_annual(config.sleep_estimate)
            sleep_mortality_hr_multiplier = entry.sleep_mortality_hr_multiplier(config.sleep_estimate)
            r = _simulate_one(
                d.label, hr, entry.log_sd,
                entry.conf_alpha, entry.conf_beta,
                cost, qol, entry.qol_years, sleep_qol, sleep_mortality_hr_multiplier, config,
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
    stack_interaction_penalty_fn: Optional[Callable[[List[str]], float]] = None,
    marginal_cost_value_fn: Optional[Callable[[List[str], str], float]] = None,
    total_annual_cost_fn: Optional[Callable[[List[str]], float]] = None,
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
    if catalog_entries is not None:
        entries = catalog_entries
        if config.categories is not None:
            entries = {k: v for k, v in entries.items() if v.category in config.categories}
    else:
        entries = get_catalog(config.categories)

    # 1. Simulate all catalog items
    item_results = simulate_catalog(
        profile=config.profile,
        n_simulations=config.n_simulations,
        random_state=config.random_state,
        pub_bias_shrinkage=config.pub_bias_shrinkage,
        horizon_years=config.horizon_years,
        qaly_discount_rate=config.qaly_discount_rate,
        cost_discount_rate=config.cost_discount_rate,
        wtp=config.wtp,
        categories=None,
        catalog_entries=entries,
        active_interaction_tags=config.active_interaction_tags,
        sleep_estimate=config.sleep_estimate,
    )

    # Key by ID for lookups
    item_results_by_id = {r["id"]: r for r in item_results}

    # 2. Build greedy portfolio
    single_qalys = {r["id"]: r["total_qaly"] for r in item_results}
    annual_costs = {r["id"]: r["annual_cost"] for r in item_results}
    cost_values = {r["id"]: r["total_cost"] for r in item_results}
    # Hazard-aware stacking: mortality combines multiplicatively (one joint
    # integration), non-mortality (QoL/harm) QALYs add across items. Each item's
    # effective HR is inverted from its own sim mort_qaly so a single-item stack
    # reproduces the sim exactly (the raw posterior HR does NOT, due to Jensen
    # over the HR/quality draws).
    item_mortality_hrs = {
        r["id"]: effective_hr_for_mortality_qaly(
            config.profile,
            r["mort_qaly"],
            discount_rate=config.qaly_discount_rate,
            baseline_hazard_multiplier=config.sleep_baseline_hazard_multiplier,
        )
        for r in item_results
    }
    item_qol_qalys = {r["id"]: r["total_qaly"] - r["mort_qaly"] for r in item_results}

    def _stack_mortality_qaly(combined_hr: float) -> float:
        return mortality_qaly_for_combined_hr(
            config.profile,
            combined_hr,
            discount_rate=config.qaly_discount_rate,
            baseline_hazard_multiplier=config.sleep_baseline_hazard_multiplier,
        )
    penalty_fn = stack_interaction_penalty_fn or build_stack_interaction_penalty_fn(
        catalog_entries=entries,
        profile=config.profile,
        qaly_discount_rate=config.qaly_discount_rate,
        item_qalys=single_qalys,
        benefit_tag_multipliers=config.sleep_overlap_multipliers,
    )

    portfolio = find_optimal_portfolio_with_costs(
        single_qalys=single_qalys,
        annual_costs=annual_costs,
        cost_values=cost_values,
        wtp=config.wtp,
        horizon_years=config.horizon_years,
        stack_interaction_penalty_fn=penalty_fn,
        marginal_cost_value_fn=marginal_cost_value_fn,
        total_annual_cost_fn=total_annual_cost_fn,
        portfolio_qaly_ceiling=config.portfolio_qaly_ceiling,
        item_mortality_hrs=item_mortality_hrs,
        item_qol_qalys=item_qol_qalys,
        mortality_qaly_fn=_stack_mortality_qaly,
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
