"""End-to-end tests for the fast synthetic graph and kernel set."""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest

from optiqal.graph.decl import compile_graph
from optiqal.graph.errors import ManifestError, NodeRejectedError
from optiqal.graph.manifest import load_certified
from optiqal.graph.store import ContentStore
from optiqal.graph.toy import (
    TOY_INTERVENTIONS,
    TOY_PROFILES,
    build_toy_graph,
    build_toy_registry,
    run_toy,
    toy_graph,
    toy_parameter_miss_set,
    toy_registry,
    toy_sources,
)


def test_toy_shape_has_two_interventions_four_profiles_and_every_role():
    graph = toy_graph()
    compiled = compile_graph(graph)
    assert tuple(TOY_INTERVENTIONS) == ("alpha", "beta")
    assert tuple(profile["id"] for profile in TOY_PROFILES) == (
        "p1",
        "p2",
        "p3",
        "p4",
    )
    assert len([node for node in graph.nodes if node.id.startswith("confound/")]) == 2
    assert len([node for node in graph.nodes if node.id.startswith("lifecycle/")]) == 8
    assert len([node for node in graph.nodes if node.id.startswith("card/")]) == 8
    assert {node.role for node in graph.nodes} == {"compute", "gate", "release"}
    assert set(toy_registry().refs()) == {
        "toy-confound@1",
        "toy-gate@1",
        "toy-lifecycle@1",
        "toy-raising-compute@1",
        "toy-raising-gate@1",
        "toy-release@1",
    }
    assert set(toy_sources()) == {source.name for source in graph.sources}
    assert len(compiled.order) == 28
    assert build_toy_graph is toy_graph
    assert set(build_toy_registry().refs()) == set(toy_registry().refs())


def test_default_toy_runs_and_certifies_in_under_ten_seconds(tmp_path):
    started = time.perf_counter()
    manifest = run_toy(ContentStore(tmp_path / "store"))
    elapsed = time.perf_counter() - started
    assert elapsed < 10
    assert manifest.miss_count == len(manifest.nodes)
    assert manifest.node("gate/fail/detached").receipt["outcome"] == "fail"
    raised = manifest.node("gate/raise/detached").receipt
    assert raised["outcome"] == "fail"
    assert raised["evidence"]["exception_type"] == "LookupError"
    assert all(
        receipt.tier == "certified"
        for node_id, receipt in manifest.nodes.items()
        if node_id.startswith("card/")
    )
    path = manifest.save(tmp_path / "manifest.json")
    assert load_certified(path).key == manifest.key


def test_toy_cold_warm_require_and_forbid_paths(tmp_path):
    store = ContentStore(tmp_path / "store")
    cold = run_toy(store)
    warm = run_toy(store)
    required = run_toy(store, resume="require")
    forbidden = run_toy(store, resume="forbid")
    assert cold.hit_count == 0
    assert warm.hit_count == len(warm.nodes)
    assert required.hit_count == len(required.nodes)
    assert forbidden.hit_count == 0
    assert cold.key == warm.key == required.key == forbidden.key
    np.testing.assert_array_equal(
        cold.node("lifecycle/p1/alpha").value,
        forbidden.node("lifecycle/p1/alpha").value,
    )


def test_one_toy_parameter_invalidates_its_exact_descendants(tmp_path):
    store = ContentStore(tmp_path / "store")
    first = run_toy(store, alpha_shrinkage=0.75)
    changed = run_toy(store, alpha_shrinkage=0.5)
    misses = frozenset(
        node_id for node_id, receipt in changed.nodes.items() if not receipt.hit
    )
    assert misses == toy_parameter_miss_set()
    assert first.key != changed.key
    assert changed.hit_count == len(changed.nodes) - len(misses)


def test_attached_failed_and_raising_gates_continue_but_do_not_certify(tmp_path):
    failed = run_toy(ContentStore(tmp_path / "failed"), fail_release=True)
    assert failed.node("gate/p1/alpha").receipt["outcome"] == "fail"
    assert failed.node("card/p1/alpha").tier == "evidence"
    failed_path = failed.save(tmp_path / "failed.json")
    with pytest.raises(ManifestError, match="heuristic|not certified"):
        load_certified(failed_path)

    raised = run_toy(ContentStore(tmp_path / "raised"), raising_gate=True)
    evidence = raised.node("gate/p1/alpha").receipt["evidence"]
    assert raised.node("gate/p1/alpha").receipt["outcome"] == "fail"
    assert evidence["exception_type"] == "LookupError"
    assert raised.node("card/p1/alpha").tier == "evidence"


def test_raising_compute_aborts_and_ephemeral_default_is_supported(tmp_path):
    ephemeral = run_toy()
    assert ephemeral.hit_count == 0
    with pytest.raises(NodeRejectedError, match="synthetic compute failure"):
        run_toy(ContentStore(tmp_path / "store"), raising_compute=True)


@pytest.mark.parametrize(
    ("outcome", "tier"),
    (
        ("pass", "certified"),
        ("not_applicable", "certified"),
        ("evidence_absent", "evidence"),
        ("fail", "evidence"),
        ("unreached", "unreached"),
    ),
)
def test_toy_can_exercise_every_gate_outcome(tmp_path, outcome, tier):
    manifest = run_toy(tmp_path / outcome, gate_outcome=outcome)
    assert manifest.node("gate/p1/alpha").receipt["outcome"] == outcome
    assert manifest.node("card/p1/alpha").tier == tier


def test_toy_selection_is_canonical_and_supports_source_overrides(tmp_path):
    selected = toy_graph(interventions=("beta", "alpha"), profiles=("p3", "p1"))
    canonical = toy_graph(interventions=("alpha", "beta"), profiles=("p1", "p3"))
    assert selected == canonical
    assert len(selected.nodes) == 16

    sources = dict(toy_sources(interventions=("alpha",), profiles=("p1",)))
    sources["intervention:alpha"] = {"id": "alpha", "effect": 0.16}
    overridden = run_toy(
        tmp_path / "overridden",
        interventions=("alpha",),
        profiles=("p1",),
        sources=sources,
    )
    assert overridden.node("confound/alpha").value["effect"] == pytest.approx(0.12)


def test_toy_selection_rejects_invalid_ids():
    with pytest.raises(TypeError, match="sequence"):
        toy_graph(interventions="alpha")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="strings"):
        toy_sources(profiles=(1,))  # type: ignore[list-item]
    with pytest.raises(ValueError, match="repeat"):
        toy_graph(interventions=("alpha", "alpha"))
    with pytest.raises(KeyError, match="unknown"):
        toy_graph(profiles=("unknown",))


def test_registered_toy_kernel_modules_have_no_positional_rng_patterns():
    module_path = __import__("optiqal.graph.toy", fromlist=["__file__"]).__file__
    source = Path(module_path).read_text(encoding="utf-8")
    banned = ("default_rng(" + "", "np.random.seed", "random_state=")
    assert not any(pattern in source for pattern in banned)
