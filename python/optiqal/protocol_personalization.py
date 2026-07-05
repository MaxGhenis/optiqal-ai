"""Shared access to Max's personalized protocol assumptions."""

from __future__ import annotations

from typing import Any

from .profile import Profile
from .protocol_ground_up import (
    ProtocolContext,
    apply_spec_to_catalog_entry,
    build_additional_specs,
    build_specs,
    load_baseline,
    resolve_protocol_context,
    resolve_stack_spec,
)
from .protocol_ground_up import (
    load_protocol_items as _load_protocol_items,
)
from .sleep import AirwayContributorEstimate, SleepBurdenEstimate


def load_protocol_baseline(context: ProtocolContext | None = None) -> dict[str, Any]:
    """Load the current personalized protocol baseline from health.db."""
    return load_baseline(resolve_protocol_context(context))


def load_protocol_context() -> ProtocolContext:
    """Load the canonical personalized protocol context.

    Routes through resolve_protocol_context so OPTIQAL_HEALTH_DB /
    OPTIQAL_PROTOCOL_JSON overrides apply here too (e.g. CI fixtures), instead
    of always returning the personal default.
    """
    return resolve_protocol_context()


def load_protocol_items(context: ProtocolContext | None = None) -> list[dict[str, Any]]:
    """Load the protocol inventory with local status metadata."""
    return _load_protocol_items(resolve_protocol_context(context))


def build_protocol_specs(
    baseline: dict[str, Any] | None = None,
    context: ProtocolContext | None = None,
) -> dict[str, Any]:
    """Build personalized protocol assumptions keyed by item id."""
    context = resolve_protocol_context(context)
    baseline = baseline or load_protocol_baseline(context)
    specs = dict(build_specs(baseline, context))
    specs.update(build_additional_specs(baseline, context))
    return specs


def load_protocol_profile() -> Profile:
    """Load the canonical personalized profile used by the protocol pipeline."""
    return load_protocol_context().profile


def apply_protocol_spec(
    *,
    item_id: str,
    base_entry: Any,
    specs: dict[str, Any],
    annual_cost: float | None = None,
):
    """Apply a personalized protocol overlay to a catalog entry when one exists."""
    spec = specs.get(item_id)
    if spec is None:
        return base_entry
    return apply_spec_to_catalog_entry(base_entry, spec, annual_cost=annual_cost)


def protocol_metadata_from_specs(
    specs: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Convert protocol specs into the metadata shape used by exporters."""
    metadata: dict[str, dict[str, Any]] = {}
    for item_id, spec in specs.items():
        resolved = resolve_stack_spec(spec)
        metadata[item_id] = {
            "range_low_qaly": resolved.low_qaly,
            "range_high_qaly": resolved.high_qaly,
            "within_range": None,
            "assumptions": {
                "observed_hr": resolved.observed_hr,
                "log_sd": resolved.log_sd,
                "confounding_prior": {
                    "alpha": resolved.conf_alpha,
                    "beta": resolved.conf_beta,
                },
                "qol_annual": resolved.qol_annual,
                "qol_years": resolved.qol_years,
                "sleep_component_relief": dict(resolved.sleep_component_relief),
                "airway_target_weights": dict(resolved.airway_target_weights),
                "apply_profile_effect_rules": resolved.apply_profile_effect_rules,
                "model_details": resolved.model_details,
            },
            "rationale": resolved.rationale,
            "personalization": resolved.personalization,
            "ground_up_sources": list(resolved.sources),
        }
    return metadata


def protocol_sleep_estimate_from_baseline(
    baseline: dict[str, Any],
) -> SleepBurdenEstimate | None:
    """Rehydrate the shared personalized sleep estimate from baseline data."""
    derived = baseline.get("derived", {})
    component_burdens = derived.get("sleep_component_burdens")
    component_losses = derived.get("sleep_component_losses")
    if not (component_burdens and component_losses):
        return None

    airway = derived.get("sleep_airway") or {}
    return SleepBurdenEstimate(
        component_burdens={k: float(v) for k, v in component_burdens.items()},
        component_losses={k: float(v) for k, v in component_losses.items()},
        annual_qaly_loss=float(derived.get("sleep_burden_annual_qaly", 0.0)),
        mortality_signal=float(derived.get("sleep_mortality_signal", 0.0)),
        airway=(
            AirwayContributorEstimate(
                upper_airway_probability=float(
                    airway.get("upper_airway_probability", 0.0)
                ),
                nasal_inflammation_probability=float(
                    airway.get("nasal_inflammation_probability", 0.0)
                ),
                mucus_probability=float(airway.get("mucus_probability", 0.0)),
                response_signal=float(derived.get("airway_response_signal", 0.0)),
            )
            if airway
            else None
        ),
        component_utility_weight_ids={
            k: str(v)
            for k, v in (
                derived.get("sleep_component_utility_weight_ids") or {}
            ).items()
        },
    )
