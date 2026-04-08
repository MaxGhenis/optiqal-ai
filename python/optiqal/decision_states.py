"""
Helpers for stateful and sequence-aware intervention evaluation.

These utilities let callers summarize a current state, compare mutually
exclusive options on top of that state, and reason about ordered decisions
without pretending everything is an independent standalone intervention.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Union


@dataclass(frozen=True)
class FrontierStateSpec:
    """Declarative spec for a frontier-style decision state."""

    id: str
    label: str
    description: str
    base_item_ids: Sequence[str]
    exclude: Optional[Sequence[str]] = None
    max_interventions: int = 8


@dataclass(frozen=True)
class ChoiceOptionSpec:
    """Declarative option within a choice state."""

    id: str
    label: str
    added_item_ids: Sequence[str]


@dataclass(frozen=True)
class ChoiceStateSpec:
    """Declarative spec for a mutually exclusive choice state."""

    id: str
    label: str
    description: str
    base_item_ids: Sequence[str]
    options: Sequence[ChoiceOptionSpec]


@dataclass(frozen=True)
class DecisionSequenceStepSpec:
    """Declarative step in an ordered decision sequence."""

    step: int
    id: str
    label: str
    state_id: Optional[str] = None
    preferred_state_id: Optional[str] = None
    alternative_state_id: Optional[str] = None


DecisionStateSpec = Union[FrontierStateSpec, ChoiceStateSpec]


def ordered_unique(item_ids: Iterable[str]) -> List[str]:
    """Deduplicate while preserving order."""
    seen: set[str] = set()
    ordered: List[str] = []
    for item_id in item_ids:
        if item_id in seen:
            continue
        seen.add(item_id)
        ordered.append(item_id)
    return ordered


def build_public_sleep_decision_specs(
    *,
    include_therapy: bool = True,
    include_humidifier: bool = False,
) -> List[DecisionStateSpec]:
    """Return the public app's generic sleep-pathway decision specs."""
    insomnia_rx_options = [
        ChoiceOptionSpec(id="no_insomnia_rx", label="No insomnia Rx", added_item_ids=[]),
        ChoiceOptionSpec(id="trazodone_50mg", label="Use trazodone", added_item_ids=["trazodone_50mg"]),
        ChoiceOptionSpec(id="doxepin_3mg", label="Use doxepin", added_item_ids=["doxepin_3mg"]),
        ChoiceOptionSpec(
            id="daridorexant_25mg",
            label="Use daridorexant",
            added_item_ids=["daridorexant_25mg"],
        ),
        ChoiceOptionSpec(
            id="lemborexant_5mg",
            label="Use lemborexant",
            added_item_ids=["lemborexant_5mg"],
        ),
        ChoiceOptionSpec(
            id="suvorexant_10mg",
            label="Use suvorexant",
            added_item_ids=["suvorexant_10mg"],
        ),
    ]

    conservative_options = [
        ChoiceOptionSpec(id="status_quo", label="No airway support yet", added_item_ids=[]),
        ChoiceOptionSpec(
            id="head_elevation_nightly",
            label="Use head elevation",
            added_item_ids=["head_elevation_nightly"],
        ),
        ChoiceOptionSpec(
            id="nasal_strips_nightly",
            label="Use nasal strips",
            added_item_ids=["nasal_strips_nightly"],
        ),
        ChoiceOptionSpec(
            id="nasacort_nightly",
            label="Use Nasacort",
            added_item_ids=["nasacort_nightly"],
        ),
    ]
    if include_humidifier:
        conservative_options.append(
            ChoiceOptionSpec(
                id="humidifier_nightly",
                label="Use humidifier",
                added_item_ids=["humidifier_nightly"],
            )
        )

    combined_ids = [
        "head_elevation_nightly",
        "nasal_strips_nightly",
        "nasacort_nightly",
    ]
    combined_label = "Combine elevation, strips, and Nasacort"
    if include_humidifier:
        combined_ids.append("humidifier_nightly")
        combined_label = "Combine elevation, strips, Nasacort, and humidifier"

    conservative_options.append(
        ChoiceOptionSpec(
            id="combined_airway_support",
            label=combined_label,
            added_item_ids=combined_ids,
        )
    )

    specs: List[DecisionStateSpec] = [
        ChoiceStateSpec(
            id="conservative_airway_support",
            label="Conservative airway support now",
            description=(
                "Low-friction airway interventions to try while you are still working up the sleep problem "
                "or waiting on formal treatment."
            ),
            base_item_ids=[],
            options=conservative_options,
        ),
    ]

    if not include_therapy:
        return specs

    specs.extend([
        ChoiceStateSpec(
            id="primary_osa_therapy_choice",
            label="If a sleep study confirms mild OSA",
            description=(
                "Primary-airway treatment options after diagnosis. This branch is here to make the app "
                "sequence-aware instead of treating insomnia drugs and airway therapy as interchangeable."
            ),
            base_item_ids=[],
            options=[
                ChoiceOptionSpec(id="status_quo", label="No primary airway treatment yet", added_item_ids=[]),
                ChoiceOptionSpec(id="apap_nightly", label="Start APAP", added_item_ids=["apap_nightly"]),
                ChoiceOptionSpec(
                    id="oral_appliance_custom",
                    label="Start custom oral appliance",
                    added_item_ids=["oral_appliance_custom"],
                ),
            ],
        ),
        ChoiceStateSpec(
            id="rx_after_apap_if_needed",
            label="If insomnia persists after APAP",
            description=(
                "Sleep Rx choices after the airway problem is treated first. This is the public-product version "
                "of the trazodone-vs-DORA comparison."
            ),
            base_item_ids=["apap_nightly"],
            options=insomnia_rx_options,
        ),
        ChoiceStateSpec(
            id="rx_after_oral_appliance_if_needed",
            label="If insomnia persists after oral appliance",
            description=(
                "Sleep Rx choices after a custom oral appliance, so the sequence can branch cleanly based on "
                "the primary airway treatment path."
            ),
            base_item_ids=["oral_appliance_custom"],
            options=insomnia_rx_options,
        ),
    ])
    return specs


def build_public_sleep_decision_sequence(*, include_therapy: bool = True) -> List[DecisionSequenceStepSpec]:
    """Return the public app's generic sleep-pathway sequence."""
    steps = [
        DecisionSequenceStepSpec(
            step=1,
            id="conservative_airway_support",
            label="Start with low-friction airway support if the phenotype looks airway-heavy.",
            state_id="conservative_airway_support",
        ),
    ]

    if not include_therapy:
        return steps

    steps.extend([
        DecisionSequenceStepSpec(
            step=2,
            id="primary_osa_therapy_choice",
            label="If mild OSA is confirmed, choose the primary airway treatment before chasing better hypnotics.",
            state_id="primary_osa_therapy_choice",
        ),
        DecisionSequenceStepSpec(
            step=3,
            id="rx_after_apap_if_needed",
            label="Only compare insomnia Rx options after primary airway treatment if sleep maintenance is still a problem.",
            preferred_state_id="rx_after_apap_if_needed",
            alternative_state_id="rx_after_oral_appliance_if_needed",
        ),
    ])
    return steps


def summarize_stack_from_qalys(
    item_ids: Sequence[str],
    single_qalys: Mapping[str, float],
    annual_costs: Mapping[str, float],
    *,
    stack_interaction_penalty_fn: Optional[Callable[[List[str]], float]] = None,
    total_annual_cost_fn: Optional[Callable[[List[str]], float]] = None,
    total_cost_value_fn: Optional[Callable[[List[str]], float]] = None,
) -> Dict:
    """
    Summarize a stack using precomputed per-item QALYs plus explicit stack penalties.
    """
    ids = [item_id for item_id in ordered_unique(item_ids) if item_id in single_qalys]
    base_qaly = float(sum(single_qalys[item_id] for item_id in ids))
    interaction_penalty_qaly = (
        float(stack_interaction_penalty_fn(ids))
        if stack_interaction_penalty_fn is not None
        else 0.0
    )
    adjusted_qaly = base_qaly + interaction_penalty_qaly
    total_annual_cost = (
        float(total_annual_cost_fn(ids))
        if total_annual_cost_fn is not None
        else float(sum(annual_costs.get(item_id, 0.0) for item_id in ids))
    )
    total_cost_value = (
        float(total_cost_value_fn(ids))
        if total_cost_value_fn is not None
        else None
    )
    return {
        "item_ids": ids,
        "base_qaly": round(base_qaly, 4),
        "base_days": round(base_qaly * 365.25, 1),
        "interaction_penalty_qaly": round(interaction_penalty_qaly, 4),
        "interaction_penalty_days": round(interaction_penalty_qaly * 365.25, 1),
        "adjusted_qaly": round(adjusted_qaly, 4),
        "adjusted_days": round(adjusted_qaly * 365.25, 1),
        "total_annual_cost": round(total_annual_cost),
        "total_cost_value": round(total_cost_value) if total_cost_value is not None else None,
    }


def evaluate_choice_set(
    *,
    base_item_ids: Sequence[str],
    options: Mapping[str, Sequence[str]],
    labels: Optional[Mapping[str, str]],
    single_qalys: Mapping[str, float],
    annual_costs: Mapping[str, float],
    stack_interaction_penalty_fn: Optional[Callable[[List[str]], float]] = None,
    total_annual_cost_fn: Optional[Callable[[List[str]], float]] = None,
    total_cost_value_fn: Optional[Callable[[List[str]], float]] = None,
) -> Dict:
    """
    Compare mutually exclusive options conditional on a base state.

    `options` maps an option id to the ordered items that should be added on
    top of `base_item_ids`. The base should already have any mutually exclusive
    incumbents removed.
    """
    baseline = summarize_stack_from_qalys(
        base_item_ids,
        single_qalys,
        annual_costs,
        stack_interaction_penalty_fn=stack_interaction_penalty_fn,
        total_annual_cost_fn=total_annual_cost_fn,
        total_cost_value_fn=total_cost_value_fn,
    )

    option_rows: List[Dict] = []
    for option_id, option_items in options.items():
        added_item_ids = [item_id for item_id in ordered_unique(option_items) if item_id in single_qalys]
        combined_ids = ordered_unique(list(base_item_ids) + added_item_ids)
        total = summarize_stack_from_qalys(
            combined_ids,
            single_qalys,
            annual_costs,
            stack_interaction_penalty_fn=stack_interaction_penalty_fn,
            total_annual_cost_fn=total_annual_cost_fn,
            total_cost_value_fn=total_cost_value_fn,
        )
        marginal_qaly = total["adjusted_qaly"] - baseline["adjusted_qaly"]
        marginal_cost_value = None
        if total["total_cost_value"] is not None and baseline["total_cost_value"] is not None:
            marginal_cost_value = total["total_cost_value"] - baseline["total_cost_value"]
        option_rows.append({
            "id": option_id,
            "label": labels.get(option_id, option_id) if labels is not None else option_id,
            "added_item_ids": added_item_ids,
            "stack": total,
            "marginal_qaly": round(marginal_qaly, 4),
            "marginal_days": round(marginal_qaly * 365.25, 1),
            "marginal_annual_cost": round(total["total_annual_cost"] - baseline["total_annual_cost"]),
            "marginal_cost_value": round(marginal_cost_value) if marginal_cost_value is not None else None,
            "marginal_cost_per_qaly": (
                round(marginal_cost_value / marginal_qaly)
                if marginal_cost_value is not None and marginal_qaly > 0
                else None
            ),
        })

    option_rows.sort(
        key=lambda row: (
            row["marginal_qaly"],
            -(row["marginal_cost_value"] if row["marginal_cost_value"] is not None else 0),
        ),
        reverse=True,
    )

    return {
        "baseline": baseline,
        "options": option_rows,
    }


def evaluate_frontier_state(
    *,
    base_item_ids: Sequence[str],
    single_qalys: Mapping[str, float],
    annual_costs: Mapping[str, float],
    cost_values: Mapping[str, float],
    horizon_years: float,
    max_interventions: int = 8,
    exclude: Optional[Sequence[str]] = None,
    stack_interaction_penalty_fn: Optional[Callable[[List[str]], float]] = None,
    marginal_cost_value_fn: Optional[Callable[[List[str], str], float]] = None,
    total_annual_cost_fn: Optional[Callable[[List[str]], float]] = None,
    total_cost_value_fn: Optional[Callable[[List[str]], float]] = None,
    exclusive_groups: Optional[Mapping[str, str]] = None,
) -> Dict:
    """
    Evaluate the next-step frontier conditional on a base state.

    Returns the summarized baseline state plus the raw greedy ranking steps
    needed to extend it.
    """
    from .combination import rank_interventions_by_marginal_cost_per_qaly

    baseline = summarize_stack_from_qalys(
        base_item_ids,
        single_qalys,
        annual_costs,
        stack_interaction_penalty_fn=stack_interaction_penalty_fn,
        total_annual_cost_fn=total_annual_cost_fn,
        total_cost_value_fn=total_cost_value_fn,
    )
    ranking = rank_interventions_by_marginal_cost_per_qaly(
        single_qalys=single_qalys,
        annual_costs=annual_costs,
        cost_values=cost_values,
        horizon_years=horizon_years,
        max_interventions=max_interventions,
        exclude=list(exclude) if exclude is not None else None,
        preselected=list(base_item_ids),
        stack_interaction_penalty_fn=stack_interaction_penalty_fn,
        marginal_cost_value_fn=marginal_cost_value_fn,
        total_annual_cost_fn=total_annual_cost_fn,
        exclusive_groups=dict(exclusive_groups) if exclusive_groups is not None else None,
    )
    return {
        "baseline": baseline,
        "steps": ranking,
    }


def evaluate_decision_states(
    specs: Sequence[DecisionStateSpec],
    *,
    single_qalys: Mapping[str, float],
    annual_costs: Mapping[str, float],
    cost_values: Mapping[str, float],
    horizon_years: float,
    stack_interaction_penalty_fn: Optional[Callable[[List[str]], float]] = None,
    marginal_cost_value_fn: Optional[Callable[[List[str], str], float]] = None,
    total_annual_cost_fn: Optional[Callable[[List[str]], float]] = None,
    total_cost_value_fn: Optional[Callable[[List[str]], float]] = None,
    exclusive_groups: Optional[Mapping[str, str]] = None,
) -> Dict[str, Dict]:
    """Evaluate a declarative set of decision-state specs."""
    states: Dict[str, Dict] = {}
    for spec in specs:
        if isinstance(spec, FrontierStateSpec):
            evaluation = evaluate_frontier_state(
                base_item_ids=spec.base_item_ids,
                single_qalys=single_qalys,
                annual_costs=annual_costs,
                cost_values=cost_values,
                horizon_years=horizon_years,
                max_interventions=spec.max_interventions,
                exclude=spec.exclude,
                stack_interaction_penalty_fn=stack_interaction_penalty_fn,
                marginal_cost_value_fn=marginal_cost_value_fn,
                total_annual_cost_fn=total_annual_cost_fn,
                total_cost_value_fn=total_cost_value_fn,
                exclusive_groups=exclusive_groups,
            )
            states[spec.id] = {
                "kind": "frontier",
                "label": spec.label,
                "description": spec.description,
                "evaluation": evaluation,
            }
            continue

        option_map = {
            option.id: list(option.added_item_ids)
            for option in spec.options
        }
        option_labels = {
            option.id: option.label
            for option in spec.options
        }
        evaluation = evaluate_choice_set(
            base_item_ids=spec.base_item_ids,
            options=option_map,
            labels=option_labels,
            single_qalys=single_qalys,
            annual_costs=annual_costs,
            stack_interaction_penalty_fn=stack_interaction_penalty_fn,
            total_annual_cost_fn=total_annual_cost_fn,
            total_cost_value_fn=total_cost_value_fn,
        )
        states[spec.id] = {
            "kind": "choice",
            "label": spec.label,
            "description": spec.description,
            "evaluation": evaluation,
        }

    return states
