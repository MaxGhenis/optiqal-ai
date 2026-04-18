"""
Intervention Combination Module

Combines multiple interventions with interaction adjustments.
Uses multiplicative hazard ratio model with overlap corrections.
"""

from dataclasses import dataclass
from typing import Callable, List, Tuple, Dict, Optional
import numpy as np

from .intervention import Intervention
from .profile import Profile, get_baseline_mortality_multiplier, get_intervention_modifier
from .simulate import simulate_qaly_profile, SimulationResult


# =============================================================================
# INTERVENTION OVERLAP MATRIX
# =============================================================================

# Interventions that share mechanisms get overlap penalties
# Value represents the fraction of the second intervention's effect retained
# when the first is already applied (1.0 = fully additive, 0.0 = fully redundant)

OVERLAP_MATRIX: Dict[Tuple[str, str], float] = {
    # Exercise interventions overlap substantially
    ("walking_30min_daily", "daily_exercise_moderate"): 0.4,  # Walking is subset of moderate exercise
    ("daily_exercise_moderate", "walking_30min_daily"): 0.4,
    ("walking_30min_daily", "strength_training"): 0.8,  # Different mechanisms
    ("strength_training", "walking_30min_daily"): 0.8,
    ("daily_exercise_moderate", "strength_training"): 0.7,  # Some overlap in fitness benefits
    ("strength_training", "daily_exercise_moderate"): 0.7,

    # Diet overlaps
    ("mediterranean_diet", "fish_oil_supplement"): 0.5,  # Mediterranean includes fish
    ("fish_oil_supplement", "mediterranean_diet"): 0.5,

    # Stress/mental health overlaps
    ("meditation_daily", "sleep_8_hours"): 0.8,  # Both affect stress, some overlap
    ("sleep_8_hours", "meditation_daily"): 0.8,

    # Exercise affects sleep
    ("daily_exercise_moderate", "sleep_8_hours"): 0.85,
    ("sleep_8_hours", "daily_exercise_moderate"): 0.85,
    ("walking_30min_daily", "sleep_8_hours"): 0.9,
    ("sleep_8_hours", "walking_30min_daily"): 0.9,
}


def get_overlap_factor(intervention_a: str, intervention_b: str) -> float:
    """
    Get the overlap factor between two interventions.

    Returns the fraction of intervention_b's effect retained when
    intervention_a is already applied.

    Args:
        intervention_a: ID of first intervention (already applied)
        intervention_b: ID of second intervention (being added)

    Returns:
        Overlap factor (1.0 = fully additive, 0.0 = fully redundant)
    """
    return OVERLAP_MATRIX.get((intervention_a, intervention_b), 1.0)


@dataclass
class CombinedEffect:
    """Result of combining multiple interventions."""

    combined_hr: float  # Combined hazard ratio
    individual_hrs: Dict[str, float]  # HR for each intervention
    overlap_adjustments: Dict[Tuple[str, str], float]  # Overlap penalties applied
    effective_log_hr: float  # log(combined_hr) after all adjustments

    @property
    def relative_risk_reduction(self) -> float:
        """1 - HR, the relative risk reduction."""
        return 1.0 - self.combined_hr


def combine_intervention_effects(
    interventions: List[Intervention],
    profile: Optional[Profile] = None,
    apply_overlap: bool = True,
) -> CombinedEffect:
    """
    Combine multiple intervention effects using multiplicative HR model.

    The model:
    1. Start with each intervention's hazard ratio
    2. Apply profile-specific effect modifiers (if profile provided)
    3. Apply overlap corrections for interventions with shared mechanisms
    4. Multiply all adjusted HRs

    Args:
        interventions: List of Intervention objects to combine
        profile: Optional demographic profile for effect modifiers
        apply_overlap: Whether to apply overlap corrections

    Returns:
        CombinedEffect with combined HR and breakdown
    """
    if not interventions:
        return CombinedEffect(
            combined_hr=1.0,
            individual_hrs={},
            overlap_adjustments={},
            effective_log_hr=0.0,
        )

    # Get base HRs with profile modifiers
    individual_hrs = {}
    for intervention in interventions:
        base_hr = intervention.hazard_ratio_mean

        if profile is not None:
            # Apply effect modifier
            modifier = get_intervention_modifier(profile, intervention.category)
            # Modifier adjusts the effect (log HR), not the HR directly
            # HR_modified = exp(log(HR) * modifier)
            log_hr = np.log(base_hr)
            adjusted_log_hr = log_hr * modifier
            base_hr = np.exp(adjusted_log_hr)

        individual_hrs[intervention.id] = base_hr

    # Calculate combined log HR with overlap adjustments
    overlap_adjustments = {}
    intervention_ids = [i.id for i in interventions]

    # Track effective log HRs
    effective_log_hrs = {}

    for i, intervention in enumerate(interventions):
        log_hr = np.log(individual_hrs[intervention.id])

        if apply_overlap and i > 0:
            # Apply overlap corrections for all previous interventions
            cumulative_overlap = 1.0
            for j in range(i):
                prev_id = intervention_ids[j]
                overlap = get_overlap_factor(prev_id, intervention.id)
                if overlap < 1.0:
                    overlap_adjustments[(prev_id, intervention.id)] = overlap
                cumulative_overlap *= overlap

            log_hr *= cumulative_overlap

        effective_log_hrs[intervention.id] = log_hr

    # Sum log HRs
    total_log_hr = sum(effective_log_hrs.values())

    combined_hr = np.exp(total_log_hr)

    # Cap at reasonable minimum (can't reduce mortality by more than 90%)
    combined_hr = max(combined_hr, 0.10)

    return CombinedEffect(
        combined_hr=combined_hr,
        individual_hrs=individual_hrs,
        overlap_adjustments=overlap_adjustments,
        effective_log_hr=total_log_hr,
    )


# =============================================================================
# COMBINED QALY SIMULATION
# =============================================================================

def simulate_combined_qaly(
    interventions: List[Intervention],
    profile: Profile,
    n_simulations: int = 5000,
    discount_rate: float = 0.03,
    apply_overlap: bool = True,
) -> SimulationResult:
    """
    Simulate QALY gains from a combination of interventions.

    This creates a synthetic "combined intervention" with the combined
    hazard ratio and runs the standard simulation.

    Args:
        interventions: List of interventions to combine
        profile: Demographic profile
        n_simulations: Number of Monte Carlo samples
        discount_rate: Annual discount rate for future QALYs
        apply_overlap: Whether to apply overlap corrections

    Returns:
        SimulationResult with combined QALY estimate
    """
    if not interventions:
        raise ValueError("Must provide at least one intervention")

    if len(interventions) == 1:
        # Single intervention - use standard simulation
        return simulate_qaly_profile(
            interventions[0],
            profile,
            n_simulations=n_simulations,
            discount_rate=discount_rate,
        )

    # Combine effects
    combined = combine_intervention_effects(
        interventions,
        profile,
        apply_overlap=apply_overlap,
    )

    # Create synthetic combined intervention
    # Use the first intervention as template, override HR
    base_intervention = interventions[0]

    # For combined interventions, we need to create a modified copy
    # that uses the combined HR
    from copy import deepcopy
    combined_intervention = deepcopy(base_intervention)
    combined_intervention.id = "+".join(i.id for i in interventions)
    combined_intervention.name = " + ".join(i.name for i in interventions)
    combined_intervention.hazard_ratio_mean = combined.combined_hr
    combined_intervention.hazard_ratio_std = 0.0  # TODO: propagate uncertainty

    # Merge cause pathways from all interventions
    merged_pathways = {}
    for intervention in interventions:
        for cause, weight in intervention.cause_pathways.items():
            if cause in merged_pathways:
                # Average the weights, capped at 1.0
                merged_pathways[cause] = min(1.0, (merged_pathways[cause] + weight) / 2)
            else:
                merged_pathways[cause] = weight
    combined_intervention.cause_pathways = merged_pathways

    # Run simulation with combined intervention
    # Note: profile modifiers already applied in combine_intervention_effects,
    # so we pass a neutral profile or skip modifier application
    return simulate_qaly_profile(
        combined_intervention,
        profile,
        n_simulations=n_simulations,
        discount_rate=discount_rate,
    )


# =============================================================================
# QUICK COMBINATION ESTIMATE
# =============================================================================

def estimate_combined_qaly_from_singles(
    single_qalys: Dict[str, float],
    intervention_ids: List[str],
    apply_overlap: bool = True,
) -> float:
    """
    Quick estimate of combined QALY from precomputed single QALYs.

    This is an approximation that assumes:
    - QALY gains are roughly proportional to log(HR)
    - Overlap corrections apply to the gains

    More accurate than simple addition, less accurate than full simulation.

    Args:
        single_qalys: Dict mapping intervention ID to single QALY gain
        intervention_ids: List of intervention IDs to combine
        apply_overlap: Whether to apply overlap corrections

    Returns:
        Estimated combined QALY gain
    """
    if not intervention_ids:
        return 0.0

    if len(intervention_ids) == 1:
        return single_qalys.get(intervention_ids[0], 0.0)

    # Start with sum of individual QALYs
    total_qaly = 0.0

    for i, int_id in enumerate(intervention_ids):
        qaly = single_qalys.get(int_id, 0.0)

        if apply_overlap and i > 0:
            # Apply cumulative overlap
            cumulative_overlap = 1.0
            for j in range(i):
                prev_id = intervention_ids[j]
                overlap = get_overlap_factor(prev_id, int_id)
                cumulative_overlap *= overlap
            qaly *= cumulative_overlap

        total_qaly += qaly

    return total_qaly


# =============================================================================
# OPTIMAL PORTFOLIO SELECTION
# =============================================================================

def find_optimal_portfolio(
    interventions: List[Intervention],
    profile: Profile,
    max_interventions: int = 5,
    precomputed_qalys: Optional[Dict[str, float]] = None,
) -> List[Tuple[List[str], float]]:
    """
    Find the optimal portfolio of interventions by marginal QALY gain.

    Uses greedy selection: at each step, add the intervention with
    highest marginal QALY gain given what's already selected.

    Args:
        interventions: Available interventions
        profile: Demographic profile
        max_interventions: Maximum number of greedy additions. When
            `preselected` is provided, these are additions beyond the
            preselected base state.
        precomputed_qalys: Optional precomputed single QALYs (faster)

    Returns:
        List of (intervention_ids, cumulative_qaly) tuples for each step
    """
    if precomputed_qalys is None:
        # Compute single intervention QALYs
        precomputed_qalys = {}
        for intervention in interventions:
            result = simulate_qaly_profile(intervention, profile, n_simulations=1000)
            precomputed_qalys[intervention.id] = result.median

    intervention_map = {i.id: i for i in interventions}
    available = set(intervention_map.keys())
    selected = []
    portfolio_path = []

    for _ in range(min(max_interventions, len(interventions))):
        if not available:
            break

        # Find best next intervention
        best_id = None
        best_marginal = -float('inf')
        best_total = 0.0

        current_total = estimate_combined_qaly_from_singles(
            precomputed_qalys,
            selected,
        ) if selected else 0.0

        for int_id in available:
            candidate = selected + [int_id]
            candidate_total = estimate_combined_qaly_from_singles(
                precomputed_qalys,
                candidate,
            )
            marginal = candidate_total - current_total

            if marginal > best_marginal:
                best_marginal = marginal
                best_id = int_id
                best_total = candidate_total

        if best_id is None or best_marginal <= 0:
            break

        selected.append(best_id)
        available.remove(best_id)
        portfolio_path.append((selected.copy(), best_total))

    return portfolio_path


def _saturate_total_qaly(raw_total: float, ceiling: Optional[float]) -> float:
    """Soft-cap a portfolio QALY total at ``ceiling`` with a concave saturation.

    Uses ``saturated = ceiling * (1 - exp(-raw/ceiling))``. At small raw totals
    the saturation is near-linear (slope 1), and as raw → ∞ the saturation
    approaches ``ceiling``. This encodes the biological reality that no stack
    of supplements can add unbounded QALYs — the human lifespan imposes a
    ceiling that greedy additive models don't respect.

    When ``ceiling`` is None (or non-positive), returns ``raw_total`` unchanged.
    """
    if ceiling is None or ceiling <= 0:
        return float(raw_total)
    if raw_total <= 0:
        return float(raw_total)
    return float(ceiling * (1.0 - np.exp(-raw_total / ceiling)))


def find_optimal_portfolio_with_costs(
    single_qalys: Dict[str, float],
    annual_costs: Dict[str, float],
    cost_values: Optional[Dict[str, float]] = None,
    wtp: float = 200_000,
    horizon_years: float = 40,
    max_interventions: int = 50,
    exclude: Optional[List[str]] = None,
    preselected: Optional[List[str]] = None,
    stack_interaction_penalty_fn: Optional[Callable[[List[str]], float]] = None,
    marginal_cost_value_fn: Optional[Callable[[List[str], str], float]] = None,
    total_annual_cost_fn: Optional[Callable[[List[str]], float]] = None,
    portfolio_qaly_ceiling: Optional[float] = None,
) -> List[Dict]:
    """
    Find optimal portfolio using cost-aware greedy selection.

    At each step, adds the intervention with highest marginal net value,
    accounting for:
    - Explicit stack interaction penalties on the QALY side
    - Monetary cost vs willingness-to-pay

    Stops when no intervention has positive marginal net value.

    Args:
        single_qalys: Dict mapping intervention ID to single QALY gain
        annual_costs: Dict mapping intervention ID to annual recurring cost ($)
        cost_values: Dict mapping intervention ID to the cost value used in
            net value calculations (e.g. discounted lifetime cost). Defaults to
            annual_cost * horizon_years for backward compatibility.
        wtp: Willingness-to-pay per QALY ($/QALY)
        horizon_years: Planning horizon in years
        max_interventions: Maximum portfolio size
        exclude: Intervention IDs to exclude
        preselected: Intervention IDs already selected before greedy ranking
        marginal_cost_value_fn: Optional callback returning the incremental cost
            value of adding `candidate_id` given `selected_ids`. Use for shared
            product pricing so second ingredients from the same bottle are not
            charged again.
        total_annual_cost_fn: Optional callback returning actual annual spend for
            the selected stack.

    Returns:
        List of dicts with step, added_intervention, marginal_qaly,
        marginal_net_value, total_qaly, total_cost, interaction_penalty_qaly
    """
    preselected = [item_id for item_id in (preselected or []) if item_id in single_qalys]
    exclude = set(exclude or []) | set(preselected)
    available = set(single_qalys.keys()) - exclude
    cost_values = cost_values or {
        intervention_id: annual_cost * horizon_years
        for intervention_id, annual_cost in annual_costs.items()
    }
    selected: List[str] = preselected.copy()
    portfolio_path: List[Dict] = []
    penalty_cache: Dict[tuple[str, ...], float] = {}

    def _base_total_qaly(item_ids: List[str]) -> float:
        return sum(single_qalys[s] for s in item_ids)

    def _interaction_penalty(item_ids: List[str]) -> float:
        if stack_interaction_penalty_fn is None:
            return 0.0
        key = tuple(sorted(item_ids))
        if key not in penalty_cache:
            penalty_cache[key] = float(stack_interaction_penalty_fn(item_ids))
        return penalty_cache[key]

    def _total_cost_value(item_ids: List[str]) -> float:
        if marginal_cost_value_fn is None:
            return sum(cost_values.get(item_id, 0.0) for item_id in item_ids)

        total = 0.0
        running: List[str] = []
        for item_id in item_ids:
            total += float(marginal_cost_value_fn(running.copy(), item_id))
            running.append(item_id)
        return total

    def _total_annual_cost(item_ids: List[str]) -> float:
        if total_annual_cost_fn is not None:
            return float(total_annual_cost_fn(item_ids))
        return float(sum(annual_costs.get(item_id, 0.0) for item_id in item_ids))

    while available and len(portfolio_path) < max_interventions:
        best_id = None
        best_marginal_net = -float('inf')
        best_marginal_qaly = 0.0
        best_total_qaly = 0.0
        best_total_raw_qaly = 0.0
        best_interaction_penalty = 0.0
        best_marginal_interaction = 0.0
        best_total_cost_value = 0.0
        best_marginal_cost_value = 0.0
        current_raw_total_qaly = _base_total_qaly(selected) + _interaction_penalty(selected)
        current_total_qaly = _saturate_total_qaly(current_raw_total_qaly, portfolio_qaly_ceiling)
        current_interaction_penalty = _interaction_penalty(selected)
        current_total_cost_value = _total_cost_value(selected)

        for int_id in available:
            candidate_selected = selected + [int_id]
            candidate_base_total_qaly = _base_total_qaly(candidate_selected)
            candidate_interaction_penalty = _interaction_penalty(candidate_selected)
            candidate_raw_total_qaly = candidate_base_total_qaly + candidate_interaction_penalty
            candidate_total_qaly = _saturate_total_qaly(
                candidate_raw_total_qaly, portfolio_qaly_ceiling,
            )
            marginal_qaly = candidate_total_qaly - current_total_qaly

            candidate_total_cost_value = _total_cost_value(candidate_selected)
            marginal_cost_value = candidate_total_cost_value - current_total_cost_value
            marginal_net = marginal_qaly * wtp - marginal_cost_value

            if marginal_net > best_marginal_net:
                best_marginal_net = marginal_net
                best_id = int_id
                best_marginal_qaly = marginal_qaly
                best_total_qaly = candidate_total_qaly
                best_total_raw_qaly = candidate_raw_total_qaly
                best_interaction_penalty = candidate_interaction_penalty
                best_marginal_interaction = candidate_interaction_penalty - current_interaction_penalty
                best_total_cost_value = candidate_total_cost_value
                best_marginal_cost_value = marginal_cost_value

        if best_id is None or best_marginal_net <= 0:
            break

        selected.append(best_id)
        available.remove(best_id)

        portfolio_path.append({
            "step": len(portfolio_path) + 1,
            "added_intervention": best_id,
            "marginal_qaly": best_marginal_qaly,
            "marginal_net_value": best_marginal_net,
            "marginal_interaction_qaly": best_marginal_interaction,
            "interaction_penalty_qaly": best_interaction_penalty,
            "total_qaly": best_total_qaly,
            "total_raw_qaly": best_total_raw_qaly,
            "portfolio_qaly_ceiling": portfolio_qaly_ceiling,
            "total_base_qaly": _base_total_qaly(selected),
            "marginal_cost_value": best_marginal_cost_value,
            "total_cost_value": best_total_cost_value,
            "total_annual_cost": _total_annual_cost(selected),
            "preselected_interventions": preselected.copy(),
            "selected_interventions": selected.copy(),
        })

    return portfolio_path


def rank_interventions_by_marginal_cost_per_qaly(
    single_qalys: Dict[str, float],
    annual_costs: Dict[str, float],
    cost_values: Optional[Dict[str, float]] = None,
    horizon_years: float = 40,
    max_interventions: int = 50,
    exclude: Optional[List[str]] = None,
    preselected: Optional[List[str]] = None,
    stack_interaction_penalty_fn: Optional[Callable[[List[str]], float]] = None,
    marginal_cost_value_fn: Optional[Callable[[List[str], str], float]] = None,
    total_annual_cost_fn: Optional[Callable[[List[str]], float]] = None,
    exclusive_groups: Optional[Dict[str, str]] = None,
) -> List[Dict]:
    """
    Rank interventions by marginal cost-effectiveness without applying a WTP cutoff.

    At each step, add the remaining intervention with the lowest positive
    marginal cost per QALY, after explicit interaction penalties and shared
    product pricing. Stop when no remaining intervention has positive marginal
    QALY.
    """
    preselected = [item_id for item_id in (preselected or []) if item_id in single_qalys]
    exclude = set(exclude or []) | set(preselected)
    available = set(single_qalys.keys()) - exclude
    cost_values = cost_values or {
        intervention_id: annual_cost * horizon_years
        for intervention_id, annual_cost in annual_costs.items()
    }
    selected: List[str] = preselected.copy()
    ranking: List[Dict] = []
    penalty_cache: Dict[tuple[str, ...], float] = {}

    def _base_total_qaly(item_ids: List[str]) -> float:
        return sum(single_qalys[s] for s in item_ids)

    def _interaction_penalty(item_ids: List[str]) -> float:
        if stack_interaction_penalty_fn is None:
            return 0.0
        key = tuple(sorted(item_ids))
        if key not in penalty_cache:
            penalty_cache[key] = float(stack_interaction_penalty_fn(item_ids))
        return penalty_cache[key]

    def _total_cost_value(item_ids: List[str]) -> float:
        if marginal_cost_value_fn is None:
            return sum(cost_values.get(item_id, 0.0) for item_id in item_ids)

        total = 0.0
        running: List[str] = []
        for item_id in item_ids:
            total += float(marginal_cost_value_fn(running.copy(), item_id))
            running.append(item_id)
        return total

    def _total_annual_cost(item_ids: List[str]) -> float:
        if total_annual_cost_fn is not None:
            return float(total_annual_cost_fn(item_ids))
        return float(sum(annual_costs.get(item_id, 0.0) for item_id in item_ids))

    while available and len(ranking) < max_interventions:
        current_total_qaly = _base_total_qaly(selected) + _interaction_penalty(selected)
        current_interaction_penalty = _interaction_penalty(selected)
        current_total_cost_value = _total_cost_value(selected)
        selected_exclusive_groups = {
            exclusive_groups[item_id]
            for item_id in selected
            if exclusive_groups and item_id in exclusive_groups and exclusive_groups[item_id]
        }

        best_id = None
        best_ratio = float("inf")
        best_marginal_qaly = 0.0
        best_total_qaly = current_total_qaly
        best_interaction_penalty = current_interaction_penalty
        best_marginal_interaction = 0.0
        best_total_cost_value = current_total_cost_value
        best_marginal_cost_value = 0.0

        for int_id in available:
            if exclusive_groups:
                group = exclusive_groups.get(int_id)
                if group and group in selected_exclusive_groups:
                    continue
            candidate_selected = selected + [int_id]
            candidate_base_total_qaly = _base_total_qaly(candidate_selected)
            candidate_interaction_penalty = _interaction_penalty(candidate_selected)
            candidate_total_qaly = candidate_base_total_qaly + candidate_interaction_penalty
            marginal_qaly = candidate_total_qaly - current_total_qaly
            if marginal_qaly <= 0:
                continue

            candidate_total_cost_value = _total_cost_value(candidate_selected)
            marginal_cost_value = candidate_total_cost_value - current_total_cost_value
            if marginal_cost_value <= 0:
                ratio = 0.0
            else:
                ratio = marginal_cost_value / marginal_qaly

            if (
                ratio < best_ratio
                or (ratio == best_ratio and marginal_qaly > best_marginal_qaly)
            ):
                best_id = int_id
                best_ratio = ratio
                best_marginal_qaly = marginal_qaly
                best_total_qaly = candidate_total_qaly
                best_interaction_penalty = candidate_interaction_penalty
                best_marginal_interaction = candidate_interaction_penalty - current_interaction_penalty
                best_total_cost_value = candidate_total_cost_value
                best_marginal_cost_value = marginal_cost_value

        if best_id is None:
            break

        selected.append(best_id)
        available.remove(best_id)
        ranking.append({
            "step": len(ranking) + 1,
            "added_intervention": best_id,
            "marginal_qaly": best_marginal_qaly,
            "marginal_cost_per_qaly": best_ratio,
            "marginal_interaction_qaly": best_marginal_interaction,
            "interaction_penalty_qaly": best_interaction_penalty,
            "total_qaly": best_total_qaly,
            "total_base_qaly": _base_total_qaly(selected),
            "marginal_cost_value": best_marginal_cost_value,
            "total_cost_value": best_total_cost_value,
            "total_annual_cost": _total_annual_cost(selected),
            "preselected_interventions": preselected.copy(),
            "selected_interventions": selected.copy(),
        })

    return ranking


def find_optimal_portfolio_from_qalys(
    single_qalys: Dict[str, float],
    max_interventions: int = 10,
    exclude: Optional[List[str]] = None,
) -> List[Dict]:
    """
    Find optimal portfolio using only precomputed QALYs (no Intervention objects needed).

    Simplified version for frontend use.

    Args:
        single_qalys: Dict mapping intervention ID to single QALY gain
        max_interventions: Maximum portfolio size
        exclude: Intervention IDs to exclude (e.g., quit_smoking for never-smokers)

    Returns:
        List of dicts with step, added_intervention, marginal_qaly, total_qaly
    """
    exclude = set(exclude or [])
    available = set(single_qalys.keys()) - exclude
    selected: List[str] = []
    portfolio_path: List[Dict] = []

    for step in range(min(max_interventions, len(available))):
        if not available:
            break

        # Current total
        current_total = estimate_combined_qaly_from_singles(
            single_qalys,
            selected,
        ) if selected else 0.0

        # Find best next intervention
        best_id = None
        best_marginal = -float('inf')
        best_total = 0.0

        for int_id in available:
            candidate = selected + [int_id]
            candidate_total = estimate_combined_qaly_from_singles(
                single_qalys,
                candidate,
            )
            marginal = candidate_total - current_total

            if marginal > best_marginal:
                best_marginal = marginal
                best_id = int_id
                best_total = candidate_total

        if best_id is None or best_marginal <= 0:
            break

        selected.append(best_id)
        available.remove(best_id)
        portfolio_path.append({
            "step": step + 1,
            "added_intervention": best_id,
            "marginal_qaly": best_marginal,
            "total_qaly": best_total,
            "selected_interventions": selected.copy(),
        })

    return portfolio_path
