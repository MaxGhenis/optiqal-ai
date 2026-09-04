"""Tests for portable, content-keyed graph manifests."""

from __future__ import annotations

import json
from dataclasses import replace

import numpy as np
import pytest

from optiqal.graph.decl import Graph, Node, SourceRef
from optiqal.graph.errors import ManifestError
from optiqal.graph.kernel import (
    Capabilities,
    Determinism,
    Numeric,
    NumericScope,
)
from optiqal.graph.keys import node_key, seed
from optiqal.graph.manifest import (
    Decision,
    NodeReceipt,
    RunManifest,
    load,
    load_certified,
    save,
)


class _Kernel:
    def __init__(self, ref: str, capabilities: Capabilities, implementation: str):
        self.ref = ref
        self.capabilities = capabilities
        self._implementation = implementation

    def implementation_hash(self) -> str:
        return self._implementation


def _graph() -> Graph:
    return Graph(
        "manifest-test",
        (SourceRef("input", "input"),),
        (
            Node("compute", "compute@1", ("input",), {"scale": 2}),
            Node("gate", "gate@1", ("compute",), role="gate"),
            Node(
                "release",
                "release@1",
                ("compute", "gate"),
                role="release",
            ),
        ),
    )


def _receipt(
    node: Node,
    digit: str,
    input_keys: dict[str, str],
    *,
    hit: bool = False,
    facts: dict[str, object] | None = None,
    tier: str | None = None,
) -> NodeReceipt:
    capabilities = Capabilities(Determinism.DETERMINISTIC, role=node.role)
    implementation = digit * 64
    kernel = _Kernel(node.kernel, capabilities, implementation)
    identity = node_key(
        node,
        input_keys,
        kernel,
        fingerprint="arm64/darwin/py3.14",
    )
    return NodeReceipt(
        key=identity,
        kernel_ref=node.kernel,
        kernel_impl_hash=implementation,
        hit=hit,
        receipt={} if facts is None else facts,
        seed=seed(identity),
        capabilities=capabilities,
        value={"draws": np.array([1.0, 2.0])},
        input_keys=input_keys,
        numerics={name: NumericScope() for name in input_keys},
        artifact_checksums={"raw": "a" * 64},
        tier=tier,
        wall_time=0.25,
    )


def _manifest(*, outcome: str = "pass", tier: str = "certified") -> RunManifest:
    graph = _graph()
    compute_node = graph.node("compute")
    gate_node = graph.node("gate")
    release_node = graph.node("release")
    compute = _receipt(compute_node, "1", {"input": "f" * 64})
    gate = _receipt(
        gate_node,
        "2",
        {"compute": compute.key},
        facts={
            "outcome": outcome,
            "evidence": "fixture",
            "verification_state": "sourced",
        },
    )
    release = _receipt(
        release_node,
        "3",
        {"compute": compute.key, "gate": gate.key},
        tier=tier,
    )
    return RunManifest(
        graph=graph,
        engine_commit="deadbeef",
        platform_fingerprint="arm64/darwin/py3.14",
        source_keys={"input": "f" * 64},
        nodes={
            "compute": compute,
            "gate": gate,
            "release": release,
        },
        decisions=(Decision("owner", "publication", "approved", "2026-09-04"),),
        started_at="2026-09-04T10:00:00Z",
        finished_at="2026-09-04T10:00:01Z",
        wall_time=1.0,
    )


def test_manifest_round_trips_numpy_and_atomic_helpers(tmp_path):
    manifest = _manifest()
    path = save(manifest, tmp_path / "nested" / "manifest.json")
    restored = load(path)
    assert restored.key == manifest.key
    assert restored.graph == manifest.graph
    assert restored.hit_count == 0
    assert restored.miss_count == 3
    assert restored.node("gate").receipt["outcome"] == "pass"
    assert restored["release"].tier == "certified"
    np.testing.assert_array_equal(
        restored.node("compute").value["draws"], np.array([1.0, 2.0])
    )
    assert not restored.node("compute").value["draws"].flags.writeable
    assert load_certified(path).key == manifest.key
    assert RunManifest.load(path).key == manifest.key
    assert RunManifest.load_certified(path).key == manifest.key


def test_manifest_key_excludes_run_observations_and_decisions():
    manifest = _manifest()
    hit_nodes = {
        node_id: replace(receipt, hit=True, wall_time=99)
        for node_id, receipt in manifest.nodes.items()
    }
    observed = replace(
        manifest,
        engine_commit="other",
        platform_fingerprint="other-platform",
        decisions=(Decision("other", "review", "changed", "later"),),
        started_at="later",
        finished_at="later still",
        wall_time=99,
        nodes=hit_nodes,
    )
    assert observed.key == manifest.key
    assert observed.hit_count == 3
    changed_receipt = replace(
        manifest.node("gate"),
        receipt={
            "outcome": "fail",
            "evidence": "changed",
            "verification_state": "sourced",
        },
    )
    assert replace(manifest, nodes={**manifest.nodes, "gate": changed_receipt}).key != (
        manifest.key
    )


def test_decision_mapping_compatibility_and_manifest_lookup_errors():
    current = Decision.from_mapping(
        {"owner": "Max", "kind": "review", "text": "yes", "signed_at": "now"}
    )
    legacy = Decision.from_mapping(
        {"name": "review", "owner": "Max", "signature": "yes"}
    )
    assert dict(current)["kind"] == "review"
    assert legacy.text == "yes"
    with pytest.raises(TypeError, match="require"):
        Decision.from_mapping({"owner": "Max"})
    with pytest.raises(KeyError, match="no receipt"):
        _manifest().node("missing")


@pytest.mark.parametrize(
    ("outcome", "tier", "message"),
    [
        ("fail", "evidence", "not certified"),
        ("unreached", "unreached", "not certified"),
        ("pass", "evidence", "does not match"),
    ],
)
def test_certified_loader_rederives_tiers(outcome, tier, message, tmp_path):
    manifest = _manifest(outcome=outcome, tier=tier)
    path = manifest.save(tmp_path / "manifest.json")
    with pytest.raises(ManifestError, match=message):
        load_certified(path)


def test_certified_loader_rejects_heuristic_and_bad_gate_receipts(tmp_path):
    manifest = _manifest()
    gate = manifest.node("gate")
    heuristic = replace(
        manifest,
        nodes={
            **manifest.nodes,
            "gate": replace(
                gate,
                receipt={
                    "outcome": "pass",
                    "evidence": "unverified",
                    "verification_state": "heuristic",
                },
            ),
        },
    )
    path = heuristic.save(tmp_path / "heuristic.json")
    with pytest.raises(ManifestError, match="heuristic"):
        load_certified(path)

    with pytest.raises(ValueError, match="Gate outcome"):
        replace(gate, receipt={"outcome": "surprise", "evidence": "bad"})


def test_certified_loader_allows_authored_and_requires_a_release(tmp_path):
    manifest = _manifest()
    gate = replace(
        manifest.node("gate"),
        receipt={
            "outcome": "pass",
            "evidence": "authored quality-of-life effect",
            "verification_state": "authored",
        },
    )
    authored = replace(manifest, nodes={**manifest.nodes, "gate": gate})
    path = authored.save(tmp_path / "authored.json")
    assert load_certified(path).key == authored.key

    empty = RunManifest(
        graph=Graph("empty", (), ()),
        engine_commit="",
        platform_fingerprint="arm64/darwin/py3.14",
        source_keys={},
        nodes={},
    )
    with pytest.raises(ManifestError, match="at least one release"):
        empty.validate_certified()


def test_manifest_detects_tampering_schema_counters_and_bad_files(tmp_path):
    manifest = _manifest()
    payload = json.loads(manifest.to_json())
    payload["nodes"]["release"]["tier"] = "evidence"
    with pytest.raises(ManifestError, match="key mismatch"):
        RunManifest.from_json(json.dumps(payload))

    payload = json.loads(manifest.to_json())
    payload["schema_version"] = 0
    with pytest.raises(ManifestError, match="schema version"):
        RunManifest.from_json(json.dumps(payload))

    payload = json.loads(manifest.to_json())
    payload["hit_count"] = 10
    with pytest.raises(ManifestError, match="counters"):
        RunManifest.from_json(json.dumps(payload))

    payload = json.loads(manifest.to_json())
    payload["schema_version"] = True
    with pytest.raises(ManifestError, match="schema version"):
        RunManifest.from_json(json.dumps(payload))

    payload = json.loads(manifest.to_json())
    payload["graph"]["nodes"].append("junk")
    with pytest.raises(ManifestError, match="contain objects"):
        RunManifest.from_json(json.dumps(payload))

    payload = json.loads(manifest.to_json())
    del payload["nodes"]["release"]["value"]
    with pytest.raises(ManifestError, match="fields do not match schema"):
        RunManifest.from_json(json.dumps(payload))

    payload = json.loads(manifest.to_json())
    payload["graph"]["nodes"][0]["params"]["scale"] = 3
    with pytest.raises(ManifestError, match="declared identity"):
        RunManifest.from_json(json.dumps(payload))

    with pytest.raises(ManifestError, match="object"):
        RunManifest.from_json("[]")
    with pytest.raises(ManifestError, match="UTF-8"):
        RunManifest.from_json(b"\xff")
    with pytest.raises(ManifestError, match="Cannot read"):
        load(tmp_path / "missing.json")
    with pytest.raises(TypeError, match="RunManifest"):
        save("not a manifest", tmp_path / "bad.json")


def test_manifest_constructors_validate_every_portable_field():
    base = _manifest().node("compute")
    for changes in (
        {"key": "bad"},
        {"hit": 1},
        {"seed": -1},
        {"capabilities": object()},
        {"receipt": []},
        {"receipt": {"bad": float("nan")}},
        {"input_keys": {"": "key"}},
        {"numerics": {}},
        {"artifact_checksums": {"raw": "bad"}},
        {"tier": "evidence"},
        {"wall_time": -1},
    ):
        with pytest.raises((TypeError, ValueError)):
            replace(base, **changes)

    release = _manifest().node("release")
    with pytest.raises(ValueError, match="requires"):
        replace(release, tier=None)

    manifest = _manifest()
    for changes in (
        {"graph": object()},
        {"source_keys": {}},
        {"nodes": {}},
        {"nodes": {**manifest.nodes, "compute": manifest.node("gate")}},
        {"decisions": (object(),)},
        {"wall_time": float("inf")},
    ):
        with pytest.raises((TypeError, ValueError)):
            replace(manifest, **changes)


def test_manifest_restores_platform_and_tolerance_numeric_scopes():
    manifest = _manifest()
    compute = replace(
        manifest.node("compute"),
        numerics={
            "input": NumericScope(
                Numeric.PLATFORM_BITWISE,
                platform="arm64/darwin/py3.14",
            )
        },
    )
    restored = RunManifest.from_json(
        replace(manifest, nodes={**manifest.nodes, "compute": compute}).to_json()
    )
    assert restored.node("compute").numerics["input"].platform.endswith("py3.14")
