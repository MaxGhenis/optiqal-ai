"""Fast synthetic graph and kernels covering the complete graph runtime.

The toy deliberately keeps one failing gate outside every release ancestry so
the default run is certifiable while still exercising cached failure outcomes.
Optional variants attach a failed or raising gate to a card, or raise from a
compute kernel, for the executor's fail-closed paths.
"""

from __future__ import annotations

import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np

from .decl import Graph, Node, SourceRef, compile_graph
from .executor import run_graph
from .kernel import (
    Capabilities,
    Determinism,
    KernelBase,
    KernelContext,
    KernelRegistry,
    KernelResult,
    Numeric,
)
from .manifest import RunManifest
from .store import ContentStore, ResumePolicy

__all__ = [
    "TOY_INTERVENTIONS",
    "TOY_PROFILES",
    "build_toy_graph",
    "build_toy_registry",
    "run_toy",
    "toy_graph",
    "toy_parameter_miss_set",
    "toy_registry",
    "toy_sources",
]

TOY_INTERVENTIONS: Mapping[str, Mapping[str, object]] = {
    "alpha": {"id": "alpha", "effect": 0.08},
    "beta": {"id": "beta", "effect": 0.04},
}
TOY_PROFILES: tuple[Mapping[str, object], ...] = (
    {"id": "p1", "age": 30, "risk": 0.8},
    {"id": "p2", "age": 45, "risk": 1.0},
    {"id": "p3", "age": 60, "risk": 1.2},
    {"id": "p4", "age": 75, "risk": 1.5},
)


class _ConfoundKernel(KernelBase):
    ref = "toy-confound@1"
    capabilities = Capabilities(Determinism.DETERMINISTIC)

    def run(self, context: KernelContext) -> KernelResult:
        intervention = next(iter(context.inputs.values()))
        effect = float(intervention["effect"])
        shrinkage = float(context.params["shrinkage"])
        adjusted = effect * shrinkage
        return KernelResult(
            {"id": intervention["id"], "effect": adjusted},
            {"raw_effect": effect, "shrinkage": shrinkage},
        )


class _LifecycleKernel(KernelBase):
    ref = "toy-lifecycle@1"
    capabilities = Capabilities(
        Determinism.SEEDED,
        numeric=Numeric.PLATFORM_BITWISE,
        dependencies=("numpy",),
    )

    def run(self, context: KernelContext) -> KernelResult:
        confounded = next(
            value
            for input_id, value in context.inputs.items()
            if input_id.startswith("confound/")
        )
        profile = next(
            value
            for input_id, value in context.inputs.items()
            if input_id.startswith("profile:")
        )
        draw_count = int(context.params["draw_count"])
        center = float(confounded["effect"]) * float(profile["risk"])
        draws = context.rng.normal(loc=center, scale=0.01, size=draw_count)
        return KernelResult(
            draws,
            {
                "draw_count": draw_count,
                "intervention_id": confounded["id"],
                "profile_id": profile["id"],
            },
            {"draws": draws.tobytes(order="C")},
        )


class _GateKernel(KernelBase):
    ref = "toy-gate@1"
    capabilities = Capabilities(
        Determinism.DETERMINISTIC,
        role="gate",
        dependencies=("numpy",),
    )

    def run(self, context: KernelContext) -> KernelResult:
        outcome = str(context.params["outcome"])
        raw_observed = next(iter(context.inputs.values()), None)
        if raw_observed is None:
            observed_mean = 0.0
        elif isinstance(raw_observed, Mapping):
            observed_mean = float(raw_observed["effect"])
        else:
            observed_mean = float(np.asarray(raw_observed).mean())
        verification_state = (
            "sourced" if outcome in {"pass", "not_applicable"} else "heuristic"
        )
        return KernelResult(
            {"outcome": outcome},
            {
                "outcome": outcome,
                "evidence": {"observed_mean": observed_mean},
                "verification_state": verification_state,
            },
        )


class _RaisingGateKernel(KernelBase):
    ref = "toy-raising-gate@1"
    capabilities = Capabilities(Determinism.DETERMINISTIC, role="gate")

    def run(self, context: KernelContext) -> KernelResult:
        raise LookupError(f"synthetic gate failure at {context.node.id}")


class _ReleaseKernel(KernelBase):
    ref = "toy-release@1"
    capabilities = Capabilities(
        Determinism.DETERMINISTIC,
        role="release",
        dependencies=("numpy",),
    )

    def run(self, context: KernelContext) -> KernelResult:
        draws = np.asarray(
            next(
                value
                for input_id, value in context.inputs.items()
                if input_id.startswith("lifecycle/")
            )
        )
        return KernelResult(
            {
                "mean": float(draws.mean()),
                "ci_low": float(np.quantile(draws, 0.025)),
                "ci_high": float(np.quantile(draws, 0.975)),
                "p_positive": float((draws > 0).mean()),
            },
            {"assembled": True},
        )


class _RaisingComputeKernel(KernelBase):
    ref = "toy-raising-compute@1"
    capabilities = Capabilities(Determinism.DETERMINISTIC)

    def run(self, context: KernelContext) -> KernelResult:
        raise RuntimeError(f"synthetic compute failure at {context.node.id}")


def toy_registry() -> KernelRegistry:
    """Return a fresh registry containing every synthetic kernel variant."""

    registry = KernelRegistry()
    for kernel in (
        _ConfoundKernel(),
        _LifecycleKernel(),
        _GateKernel(),
        _RaisingGateKernel(),
        _ReleaseKernel(),
        _RaisingComputeKernel(),
    ):
        registry.register(kernel)
    return registry


def _selection(
    requested: Sequence[str] | None,
    available: Sequence[str],
    label: str,
) -> tuple[str, ...]:
    if requested is None:
        return tuple(available)
    if isinstance(requested, str):
        raise TypeError(f"{label} must be a sequence of ids, not a string")
    requested_ids = tuple(requested)
    if any(not isinstance(identifier, str) for identifier in requested_ids):
        raise TypeError(f"{label} ids must be strings")
    if len(set(requested_ids)) != len(requested_ids):
        raise ValueError(f"{label} ids must not repeat")
    unknown = sorted(set(requested_ids) - set(available))
    if unknown:
        raise KeyError(f"Unknown toy {label}: {unknown}")
    requested_set = set(requested_ids)
    return tuple(identifier for identifier in available if identifier in requested_set)


def toy_sources(
    *,
    interventions: Sequence[str] | None = None,
    profiles: Sequence[str] | None = None,
) -> Mapping[str, object]:
    """Return detached normative content for two interventions and four profiles."""

    intervention_ids = _selection(
        interventions, tuple(TOY_INTERVENTIONS), "interventions"
    )
    profiles_by_id = {str(profile["id"]): profile for profile in TOY_PROFILES}
    profile_ids = _selection(profiles, tuple(profiles_by_id), "profiles")
    sources: dict[str, object] = {
        f"intervention:{identifier}": dict(TOY_INTERVENTIONS[identifier])
        for identifier in intervention_ids
    }
    sources.update(
        {
            f"profile:{profile_id}": dict(profiles_by_id[profile_id])
            for profile_id in profile_ids
        }
    )
    return sources


def toy_graph(
    *,
    alpha_shrinkage: float = 0.75,
    fail_release: bool = False,
    gate_outcome: str | None = None,
    raising_gate: bool = False,
    raising_compute: bool = False,
    interventions: Sequence[str] | None = None,
    profiles: Sequence[str] | None = None,
) -> Graph:
    """Declare the synthetic source-to-card graph and optional failure variants."""

    intervention_ids = _selection(
        interventions, tuple(TOY_INTERVENTIONS), "interventions"
    )
    profiles_by_id = {str(profile["id"]): profile for profile in TOY_PROFILES}
    profile_ids = _selection(profiles, tuple(profiles_by_id), "profiles")
    selected_profiles = tuple(profiles_by_id[profile_id] for profile_id in profile_ids)
    sources = tuple(
        SourceRef(
            f"intervention:{identifier}",
            "toy",
            f"Synthetic intervention {identifier}",
        )
        for identifier in intervention_ids
    ) + tuple(
        SourceRef(
            f"profile:{profile['id']}",
            "toy",
            f"Synthetic profile {profile['id']}",
        )
        for profile in selected_profiles
    )
    nodes: list[Node] = []
    for intervention_id in intervention_ids:
        confound_id = f"confound/{intervention_id}"
        confound_kernel = (
            "toy-raising-compute@1"
            if raising_compute and intervention_id == "alpha"
            else "toy-confound@1"
        )
        nodes.append(
            Node(
                confound_id,
                confound_kernel,
                (f"intervention:{intervention_id}",),
                {
                    "shrinkage": (
                        alpha_shrinkage if intervention_id == "alpha" else 0.75
                    )
                },
                description="Deterministic synthetic confounding adjustment",
            )
        )
        for profile in selected_profiles:
            profile_id = str(profile["id"])
            lifecycle_id = f"lifecycle/{profile_id}/{intervention_id}"
            gate_id = f"gate/{profile_id}/{intervention_id}"
            card_id = f"card/{profile_id}/{intervention_id}"
            nodes.append(
                Node(
                    lifecycle_id,
                    "toy-lifecycle@1",
                    (confound_id, f"profile:{profile_id}"),
                    {"draw_count": 64},
                    description="Seeded synthetic lifetime draws",
                )
            )
            selected_failure = intervention_id == "alpha" and profile_id == "p1"
            gate_kernel = (
                "toy-raising-gate@1"
                if raising_gate and selected_failure
                else "toy-gate@1"
            )
            selected_outcome = (
                (gate_outcome if gate_outcome is not None else "fail")
                if (fail_release or gate_outcome is not None) and selected_failure
                else "pass"
            )
            nodes.append(
                Node(
                    gate_id,
                    gate_kernel,
                    (lifecycle_id,),
                    {"outcome": selected_outcome},
                    role="gate",
                    description="Synthetic release gate",
                )
            )
            nodes.append(
                Node(
                    card_id,
                    "toy-release@1",
                    (lifecycle_id, gate_id),
                    role="release",
                    description="Synthetic released card",
                )
            )
    if intervention_ids:
        nodes.extend(
            (
                Node(
                    "gate/fail/detached",
                    "toy-gate@1",
                    (),
                    {"outcome": "fail"},
                    role="gate",
                    description="Deliberate failed gate outside release ancestry",
                ),
                Node(
                    "gate/raise/detached",
                    "toy-raising-gate@1",
                    (),
                    role="gate",
                    description="Deliberate raising gate outside release ancestry",
                ),
            )
        )
    return Graph("optiqal-toy", sources, tuple(nodes))


def toy_parameter_miss_set() -> frozenset[str]:
    """Return the exact descendants invalidated by ``alpha_shrinkage``."""

    affected = {"confound/alpha"}
    for profile in TOY_PROFILES:
        profile_id = profile["id"]
        affected.update(
            {
                f"lifecycle/{profile_id}/alpha",
                f"gate/{profile_id}/alpha",
                f"card/{profile_id}/alpha",
            }
        )
    return frozenset(affected)


def run_toy(
    store: ContentStore | str | Path | None = None,
    *,
    resume: ResumePolicy = "auto",
    alpha_shrinkage: float = 0.75,
    fail_release: bool = False,
    gate_outcome: str | None = None,
    raising_gate: bool = False,
    raising_compute: bool = False,
    interventions: Sequence[str] | None = None,
    profiles: Sequence[str] | None = None,
    sources: Mapping[str, object] | None = None,
) -> RunManifest:
    """Run a toy variant, using an ephemeral store when none is supplied."""

    compiled = compile_graph(
        toy_graph(
            alpha_shrinkage=alpha_shrinkage,
            fail_release=fail_release,
            gate_outcome=gate_outcome,
            raising_gate=raising_gate,
            raising_compute=raising_compute,
            interventions=interventions,
            profiles=profiles,
        )
    )
    registry = toy_registry()
    loaded_sources = (
        toy_sources(interventions=interventions, profiles=profiles)
        if sources is None
        else sources
    )
    if store is not None:
        resolved_store = (
            store if isinstance(store, ContentStore) else ContentStore(store)
        )
        return run_graph(
            compiled, registry, resolved_store, loaded_sources, resume=resume
        )
    with tempfile.TemporaryDirectory(prefix="optiqal-toy-") as directory:
        ephemeral = ContentStore(Path(directory) / "store")
        return run_graph(compiled, registry, ephemeral, loaded_sources, resume=resume)


# Familiar builder aliases for acceptance fixtures and downstream examples.
build_toy_graph = toy_graph
build_toy_registry = toy_registry
