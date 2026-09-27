"""
High-level analysis orchestrator.

Ties together catalog simulation, portfolio optimization, bundle analysis,
and decision evaluation into a single `analyze()` call.
"""

from dataclasses import dataclass, field, replace
from typing import Callable, Dict, List, Literal, Optional, Tuple

import numpy as np

from .bundles import recommend_bundles
from .catalog import (
    CATALOG,
    CatalogEntry,
    get_catalog,
    simulate_catalog,
    simulate_catalog_entry,
)
from .combination import _saturate_total_qaly, find_optimal_portfolio_with_costs
from .confounding import ConfoundingPrior, publication_bias_correct
from .defaults import (
    DEFAULT_COST_DISCOUNT_RATE,
    DEFAULT_QALY_DISCOUNT_RATE,
    validate_qaly_discount_rate,
)
from .intervention import Distribution, Intervention, MortalityEffect
from .product_composition import ProductChange, UnsupportedProductChangeError
from .profile import Profile
from .simulate import (
    effective_hr_for_mortality_qaly,
    mortality_qaly_for_combined_hr,
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
    # For ADD: the catalog item as simulate_catalog models it, overrides on top
    # For DROP: the exact negation of the ADD with the same overrides; the
    #   item's effect is negated and cost becomes savings
    # For ADJUST: override any of these to model the changed version; unset
    #   cost and QoL overrides count as 0, not the entry's values
    override_hr: Optional[float] = None
    override_cost: Optional[float] = None
    override_qol: Optional[float] = None
    # Product quantities do not establish the catalog's modeled exposure contrast.
    # Supplying this field returns a typed unsupported error before simulation.
    product_change: Optional[ProductChange] = None

    def __post_init__(self) -> None:
        if self.product_change is not None and not isinstance(
            self.product_change, ProductChange
        ):
            raise ValueError("product_change must be a ProductChange or None")


@dataclass
class AnalysisResult:
    """Complete analysis output."""

    config: AnalysisConfig
    item_results: List[dict]  # Per-item simulation results
    item_results_by_id: Dict[str, dict]  # Same, keyed by ID
    portfolio: List[dict]  # Greedy portfolio steps
    bundle_recommendations: List[dict]  # Bundle analysis
    decisions: Optional[List[dict]] = None  # Decision evaluations
    current_stack_ids: List[str] = field(default_factory=list)
    current_stack_annual_cost: float = 0.0
    current_stack_total_qaly: float = 0.0

    @property
    def selected_ids(self) -> List[str]:
        """IDs selected by portfolio optimizer."""
        if not self.portfolio:
            return self.current_stack_ids.copy()
        return self.portfolio[-1]["selected_interventions"]

    @property
    def total_annual_cost(self) -> float:
        if not self.portfolio:
            return self.current_stack_annual_cost
        return self.portfolio[-1]["total_annual_cost"]

    @property
    def total_qaly(self) -> float:
        if not self.portfolio:
            return self.current_stack_total_qaly
        return self.portfolio[-1]["total_qaly"]

    @property
    def total_days(self) -> float:
        return self.total_qaly * 365.25


def _decision_has_mortality_arm(entry: CatalogEntry, decision: Decision) -> bool:
    """Whether the item a decision simulates carries a direct mortality arm.

    A QoL-only catalog entry carries none, so its mortality leg is exactly zero.
    An explicit ``override_hr`` is a mortality claim about the item, so a
    non-null override restores an arm the entry does not itself have; an
    override of exactly 1.0 is still null and stays exact. DROP negates the
    ADD with the same overrides, so the same rule applies to every type.
    """
    if entry.has_direct_mortality_effect:
        return True
    return decision.override_hr is not None and decision.override_hr != 1.0


def _decision_intervention(
    entry: CatalogEntry,
    decision: Decision,
    config: AnalysisConfig,
) -> Intervention:
    """The intervention a decision simulates: the catalog's, HR override on top.

    Starting from ``entry.to_intervention`` keeps everything the catalog
    simulation carries, including the harm model and the interaction tags and
    rules. ``override_hr`` replaces the HR mean with
    ``publication_bias_correct(override_hr, config.pub_bias_shrinkage)`` and
    keeps the entry's ``log_sd`` and confounding prior.
    """
    intervention = entry.to_intervention(
        config.pub_bias_shrinkage, profile=config.profile
    )
    if decision.override_hr is None or not _decision_has_mortality_arm(entry, decision):
        return intervention
    hazard_ratio = Distribution(
        type="lognormal",
        params={
            "hr": publication_bias_correct(
                decision.override_hr, config.pub_bias_shrinkage
            ),
            "log_sd": entry.log_sd,
        },
    )
    mortality = (
        MortalityEffect(hazard_ratio=hazard_ratio)
        if intervention.mortality is None
        else replace(intervention.mortality, hazard_ratio=hazard_ratio)
    )
    return replace(
        intervention,
        mortality=mortality,
        confounding_prior=ConfoundingPrior(
            alpha=entry.conf_alpha, beta=entry.conf_beta
        ),
    )


def _decision_row(label: str, row: dict) -> dict:
    """Project a ``simulate_catalog_entry`` row onto the decision output keys.

    Every probability and interval here comes from the row, which computes
    them from the same total-QALY draws whose mean is ``total_qaly``.
    ``annual_cost`` is the effective annual cost that prices ``total_cost``
    (it includes any bundle allocation), and ``net_value`` is the row's
    ``gross_value``.
    """
    posterior_hr = row["hr_posterior_mean"]
    return {
        "name": label,
        "mort_qaly": row["mort_qaly"],
        "posterior_hr": float(posterior_hr) if posterior_hr is not None else 1.0,
        "harm_qaly": row["harm_qaly"],
        "direct_harm_qaly": row["direct_harm_qaly"],
        "interaction_harm_qaly": row["interaction_harm_qaly"],
        "qol_qaly": row["qol_qaly"],
        "qol_years": row["qol_years"],
        "sleep_qol_annual": row["sleep_qol_annual"],
        "sleep_qol_qaly": row["sleep_qol_qaly"],
        "total_qaly": row["total_qaly"],
        "days": row["days"],
        "annual_cost": row["effective_annual_cost"],
        "total_cost": row["total_cost"],
        "cost_per_qaly": row["cost_per_qaly"],
        "net_value": row["gross_value"],
        "p_benefit": row["p_benefit"],
        "p_harm": row["p_harm"],
        "expected_upside_days": row["expected_upside_days"],
        "expected_downside_days": row["expected_downside_days"],
        "ci_low": row["ci_low"],
        "ci_high": row["ci_high"],
        "net_qaly_ci": list(row["net_qaly_ci"]),
    }


# Decision fields that change sign under DROP: every QALY, day and money
# quantity. ``posterior_hr`` and ``qol_years`` describe the item rather than
# the change and are kept.
_DROP_NEGATED_FIELDS = (
    "mort_qaly",
    "harm_qaly",
    "direct_harm_qaly",
    "interaction_harm_qaly",
    "qol_qaly",
    "sleep_qol_annual",
    "sleep_qol_qaly",
    "total_qaly",
    "days",
    "annual_cost",
    "total_cost",
    "net_value",
)


def _negate_for_drop(add_row: dict) -> dict:
    """The DROP row: the exact negation of the ADD row on the same draws.

    Dropping an item forgoes its whole effect, so the total-QALY change is
    ``-X`` draw by draw, where ``X`` are the ADD draws. Every QALY, day and
    cost quantity is negated (cost becomes savings), intervals are negated
    with their endpoints swapped, P(benefit) and P(harm) swap, and expected
    upside and downside are negated and swap. The fields are transformed from
    the ADD row rather than recomputed from ``-X``, so the identity is exact
    instead of holding only up to percentile-interpolation rounding.

    ``cost_per_qaly`` is None for DROP. Savings per QALY forgone is a
    south-west-quadrant ratio whose decision rule runs the other way (dropping
    pays when it exceeds the WTP), so it is not reported as a cost per QALY
    gained; ``net_value`` carries the decision.
    """
    row = dict(add_row)
    for key in _DROP_NEGATED_FIELDS:
        row[key] = -add_row[key]
    row["p_benefit"], row["p_harm"] = add_row["p_harm"], add_row["p_benefit"]
    row["expected_upside_days"] = -add_row["expected_downside_days"]
    row["expected_downside_days"] = -add_row["expected_upside_days"]
    row["ci_low"], row["ci_high"] = -add_row["ci_high"], -add_row["ci_low"]
    low, high = add_row["net_qaly_ci"]
    row["net_qaly_ci"] = [-high, -low]
    row["cost_per_qaly"] = None
    return row


def _decision_verdict(net_value: float) -> str:
    if net_value > 0:
        return "DO IT"
    if net_value > -2000:
        return "MARGINAL"
    return "SKIP"


def _evaluate_decision(
    decision: Decision,
    config: AnalysisConfig,
) -> Tuple[dict, np.ndarray]:
    """Evaluate one decision; return its row and its total-QALY draws.

    The draws are the per-simulation change in total QALYs the decision
    causes (negated for DROP); the row's point estimate is their mean and its
    probabilities and intervals describe them.
    """
    entry = CATALOG.get(decision.item_id)
    if entry is None:
        raise ValueError(f"Unknown catalog item: {decision.item_id}")
    if decision.type in ("add", "drop"):
        cost_override = decision.override_cost
        qol_override = decision.override_qol
    elif decision.type == "adjust":
        cost_override = (
            decision.override_cost if decision.override_cost is not None else 0.0
        )
        qol_override = (
            decision.override_qol if decision.override_qol is not None else 0.0
        )
    else:
        raise ValueError(f"Unknown decision type: {decision.type}")

    catalog_row, draws = simulate_catalog_entry(
        entry,
        config.profile,
        n_simulations=config.n_simulations,
        random_state=config.random_state,
        pub_bias_shrinkage=config.pub_bias_shrinkage,
        horizon_years=config.horizon_years,
        qaly_discount_rate=config.qaly_discount_rate,
        cost_discount_rate=config.cost_discount_rate,
        wtp=config.wtp,
        active_interaction_tags=config.active_interaction_tags,
        sleep_estimate=config.sleep_estimate,
        intervention=_decision_intervention(entry, decision, config),
        annual_qol_override=qol_override,
        annual_cost_override=cost_override,
    )
    row = _decision_row(decision.label, catalog_row)
    if decision.type == "drop":
        row = _negate_for_drop(row)
        draws = -draws

    row["decision_type"] = decision.type
    row["item_id"] = decision.item_id
    row["label"] = decision.label
    row["verdict"] = _decision_verdict(row["net_value"])
    return row, draws


def _require_catalog_decisions(decisions: List[Decision]) -> None:
    for decision in decisions:
        if decision.product_change is not None:
            raise UnsupportedProductChangeError(decision.product_change)


def evaluate_decisions(
    decisions: List[Decision],
    config: AnalysisConfig,
) -> List[dict]:
    """
    Evaluate specific add/drop/adjust decisions.

    ADD: Simulate the item exactly as ``simulate_catalog`` does (same draws,
    harm model and interaction rules), with any overrides applied on top, and
    compute net value. With no overrides the row matches the item's catalog
    row field for field.
    DROP: The exact negation of the ADD with the same overrides: the item's
    effect is negated and cost becomes savings.
    ADJUST: Simulate with overridden parameters.

    Point estimates, P(benefit), P(harm), the 95% interval (``ci_low``,
    ``ci_high``, in days), the 80% ``net_qaly_ci`` and the expected upside and
    downside all describe the same total-QALY draws (mortality and harms, QoL,
    sleep QoL).

    Returns list of dicts sorted by net_value descending. Product changes raise
    UnsupportedProductChangeError with quantity accounting before any simulation;
    even full ingredient removal needs a separately validated effect mapping.
    """
    _require_catalog_decisions(decisions)
    results = [_evaluate_decision(d, config)[0] for d in decisions]
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
            Used as the baseline for portfolio selection.
        decisions: Optional specific add/drop/adjust decisions to evaluate.
        catalog_entries: Optional custom catalog (default: full CATALOG).

    Returns:
        AnalysisResult with all outputs.
    """
    # Preflight before catalog simulation or portfolio search: product accounting
    # must not be interpreted as a new dose response or a catalog withdrawal.
    if decisions:
        _require_catalog_decisions(decisions)

    if catalog_entries is not None:
        entries = catalog_entries
        if config.categories is not None:
            entries = {
                k: v for k, v in entries.items() if v.category in config.categories
            }
    else:
        entries = get_catalog(config.categories)

    if current_stack is None:
        baseline_stack: List[str] = []
    elif not isinstance(current_stack, list) or any(
        not isinstance(item_id, str) or not item_id for item_id in current_stack
    ):
        raise ValueError("current_stack must be a list of catalog IDs")
    else:
        baseline_stack = current_stack.copy()

    if len(set(baseline_stack)) != len(baseline_stack):
        raise ValueError("current_stack contains duplicate catalog IDs")

    unknown_stack_ids = [
        item_id for item_id in baseline_stack if item_id not in entries
    ]
    if unknown_stack_ids:
        raise ValueError(
            "current_stack contains unknown catalog IDs: "
            + ", ".join(unknown_stack_ids)
        )

    current_stack_groups: Dict[str, str] = {}
    for item_id in baseline_stack:
        exclusive_group = entries[item_id].exclusive_group
        if exclusive_group is None:
            continue
        conflicting_id = current_stack_groups.get(exclusive_group)
        if conflicting_id is not None:
            raise ValueError(
                "current_stack contains mutually exclusive interventions: "
                f"{conflicting_id} and {item_id}"
            )
        current_stack_groups[exclusive_group] = item_id

    # Mutually exclusive alternatives (e.g. two HIIT schedules). The optimizer
    # never selects a second member of a group, whether the first came from
    # the current stack or was selected earlier in the greedy path.
    exclusive_groups = {
        item_id: entry.exclusive_group
        for item_id, entry in entries.items()
        if entry.exclusive_group
    }

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
    annual_costs = {r["id"]: r["effective_annual_cost"] for r in item_results}
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

    baseline_combined_hr = 1.0
    for item_id in baseline_stack:
        baseline_combined_hr *= item_mortality_hrs[item_id]
    baseline_raw_qaly = (
        _stack_mortality_qaly(baseline_combined_hr)
        + sum(item_qol_qalys[item_id] for item_id in baseline_stack)
        + float(penalty_fn(baseline_stack))
    )
    baseline_total_qaly = _saturate_total_qaly(
        baseline_raw_qaly,
        config.portfolio_qaly_ceiling,
    )

    portfolio = find_optimal_portfolio_with_costs(
        single_qalys=single_qalys,
        annual_costs=annual_costs,
        cost_values=cost_values,
        wtp=config.wtp,
        horizon_years=config.horizon_years,
        preselected=baseline_stack,
        stack_interaction_penalty_fn=penalty_fn,
        marginal_cost_value_fn=marginal_cost_value_fn,
        total_annual_cost_fn=total_annual_cost_fn,
        portfolio_qaly_ceiling=config.portfolio_qaly_ceiling,
        item_mortality_hrs=item_mortality_hrs,
        item_qol_qalys=item_qol_qalys,
        mortality_qaly_fn=_stack_mortality_qaly,
        exclusive_groups=exclusive_groups,
    )

    # 3. Bundle recommendations
    selected_ids = (
        portfolio[-1]["selected_interventions"] if portfolio else baseline_stack
    )
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
        current_stack_ids=baseline_stack,
        current_stack_annual_cost=(
            float(total_annual_cost_fn(baseline_stack))
            if total_annual_cost_fn is not None
            else sum(annual_costs[item_id] for item_id in baseline_stack)
        ),
        current_stack_total_qaly=baseline_total_qaly,
    )
