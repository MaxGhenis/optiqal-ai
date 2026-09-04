"""Tests for canonical identity, graph keys, and the content store."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

import numpy as np
import pytest

from optiqal.graph.canonical import canonical_json, normative, sha256_domain
from optiqal.graph.decl import Node
from optiqal.graph.errors import StoreCorruptError, StoreMissError
from optiqal.graph.kernel import (
    Capabilities,
    Determinism,
    KernelResult,
    Numeric,
)
from optiqal.graph.keys import (
    artifact_key,
    node_key,
    platform_fingerprint,
    seed,
    source_key,
)
from optiqal.graph.store import ContentStore


class _Choice(StrEnum):
    VALUE = "value"


@dataclass(frozen=True)
class _Declared:
    value: int
    description: str


class _Kernel:
    ref = "identity@1"

    def __init__(self, numeric=Numeric.BITWISE):
        self.capabilities = Capabilities(
            Determinism.DETERMINISTIC,
            numeric=numeric,
        )

    def implementation_hash(self):
        return "implementation-one"

    def run(self, context):
        return KernelResult(None)


def test_canonical_json_supports_closed_values_and_numpy_arrays():
    array = np.arange(12, dtype=np.int16).reshape(3, 4)[:, ::2]
    encoded = canonical_json(
        MappingProxyType(
            {
                "tuple": (_Choice.VALUE, np.int64(2), -0.0),
                "unicode": "QALY Δ",
                "array": array,
            }
        )
    )
    payload = json.loads(encoded)
    assert encoded == canonical_json(payload)
    assert payload["array"]["__ndarray__"]["dtype"] == "<i2"
    assert payload["array"]["__ndarray__"]["shape"] == [3, 2]


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf"), -float("inf"), np.array([1.0, np.nan])],
)
def test_canonical_json_rejects_every_nonfinite_number(value):
    with pytest.raises(ValueError, match="non-finite"):
        canonical_json({"value": value})


@pytest.mark.parametrize(
    "value",
    [{1: "non-string key"}, {"set": {1}}, np.array([object()], dtype=object)],
)
def test_canonical_json_rejects_values_outside_its_grammar(value):
    with pytest.raises(TypeError):
        canonical_json(value)


def test_normative_drops_dataclass_description_but_keeps_mapping_key():
    assert normative(_Declared(1, "inert")) == {"value": 1}
    node = Node("node", "identity@1", params={"description": "normative param"})
    assert normative(node)["params"]["description"] == "normative param"


def test_domain_hash_validates_arguments_and_separates_domains():
    payload = b"same"
    assert sha256_domain("a", payload) != sha256_domain("b", payload)
    with pytest.raises(TypeError, match="domain"):
        sha256_domain(1, payload)
    with pytest.raises(ValueError, match="NUL"):
        sha256_domain("bad\0domain", payload)
    with pytest.raises(TypeError, match="payload"):
        sha256_domain("domain", "not bytes")


def test_keys_bind_only_declared_inputs_and_platform_when_declared(monkeypatch):
    node = Node("node", "identity@1", inputs=("first", "second"))
    inputs = {"first": "a", "second": "b", "unrelated": "ignored"}
    bitwise = _Kernel()
    identity = node_key(node, inputs, bitwise)
    assert identity == node_key(node, {"first": "a", "second": "b"}, bitwise)
    assert identity != node_key(node, {"first": "b", "second": "a"}, bitwise)

    monkeypatch.setattr("optiqal.graph.keys.platform_fingerprint", lambda: "one")
    platform_kernel = _Kernel(Numeric.PLATFORM_BITWISE)
    first_platform = node_key(node, inputs, platform_kernel)
    monkeypatch.setattr("optiqal.graph.keys.platform_fingerprint", lambda: "two")
    assert first_platform != node_key(node, inputs, platform_kernel)
    assert first_platform == node_key(node, inputs, platform_kernel, fingerprint="one")
    assert identity == node_key(node, inputs, bitwise)
    with pytest.raises(TypeError, match="fingerprint"):
        node_key(node, inputs, platform_kernel, fingerprint="")


def test_key_helpers_validate_and_match_seed_formula():
    source = source_key("source", {"value": 1})
    assert source != source_key("other", {"value": 1})
    artifact = artifact_key(source)
    assert len(artifact) == 64
    expected = int.from_bytes(
        hashlib.sha256(b"seed\0" + source.encode()).digest()[:8], "little"
    )
    assert seed(source) == expected
    assert platform_fingerprint().count("/") == 2
    with pytest.raises(ValueError):
        source_key("", {})
    with pytest.raises(ValueError):
        artifact_key("")
    with pytest.raises(ValueError):
        seed("")
    with pytest.raises(KeyError, match="declared input"):
        node_key(Node("node", "identity@1", ("missing",)), {}, _Kernel())


def test_store_round_trips_values_receipts_and_artifacts(tmp_path):
    store = ContentStore(tmp_path / "store")
    key = "a" * 64
    array = np.array([[1.0, 2.0]], dtype=np.float64)
    path = store.put(
        key,
        {"array": array, "tuple": (1, 2)},
        {"draws": b"opaque"},
        {"outcome": "pass"},
    )
    assert path == tmp_path / "store" / "aa" / f"{key}.json"
    assert store.has(key) and store.contains(key)
    loaded = store.get_record(key)
    np.testing.assert_array_equal(loaded.value["array"], array)
    assert loaded.value["tuple"] == [1, 2]
    assert loaded.receipt["outcome"] == "pass"
    assert loaded.artifacts["draws"] == b"opaque"
    assert loaded.artifact_checksums["draws"] == hashlib.sha256(b"opaque").hexdigest()
    assert store.get(key)["tuple"] == [1, 2]
    assert store.put(key, {"ignored": "existing object wins"}) == path


def test_store_distinguishes_misses_and_corruption(tmp_path):
    store = ContentStore(tmp_path)
    key = "b" * 64
    with pytest.raises(StoreMissError):
        store.get(key)
    with pytest.raises(ValueError, match="64 lowercase"):
        store.get("bad")

    path = store.put(key, {"value": 1})
    path.write_bytes(path.read_bytes().replace(b'"value":1', b'"value":2'))
    with pytest.raises(StoreCorruptError, match="checksum"):
        store.get(key)

    artifact_key_value = "c" * 64
    store.put(artifact_key_value, 1, {"raw": b"good"})
    payload = json.loads(store.path(artifact_key_value).read_bytes())
    filename = payload["artifacts"]["raw"]["file"]
    (store.path(artifact_key_value).parent / filename).write_bytes(b"bad")
    with pytest.raises(StoreCorruptError, match="size/SHA-256"):
        store.get(artifact_key_value)


def test_store_validates_inputs_and_canonical_data(tmp_path):
    store = ContentStore(tmp_path)
    key = "d" * 64
    with pytest.raises(TypeError, match="canonical"):
        store.put(key, {"bad": float("nan")})
    with pytest.raises(TypeError, match="artifacts"):
        store.put(key, 1, artifacts=[])
    with pytest.raises(TypeError, match="receipt"):
        store.put(key, 1, receipt=[])
    with pytest.raises(ValueError, match="Unsafe"):
        store.put(key, 1, {"../escape": b"x"})
    with pytest.raises(TypeError, match="must be bytes"):
        store.put(key, 1, {"raw": "x"})


def test_interrupted_atomic_write_leaves_no_visible_object(tmp_path, monkeypatch):
    store = ContentStore(tmp_path)
    key = "e" * 64

    def interrupt(source, destination):
        raise OSError("simulated interruption")

    monkeypatch.setattr(os, "replace", interrupt)
    with pytest.raises(OSError, match="simulated"):
        store.put(key, {"value": 1})
    assert not store.has(key)
    assert not list((tmp_path / "ee").glob("*.tmp"))


def test_write_only_replacement_preserves_incumbent_on_interruption(
    tmp_path, monkeypatch
):
    store = ContentStore(tmp_path)
    key = "f" * 64
    store.put(key, {"value": "incumbent"})

    def interrupt(source, destination):
        raise OSError("simulated interruption")

    monkeypatch.setattr(os, "replace", interrupt)
    with pytest.raises(OSError):
        store.put(key, {"value": "replacement"}, verify_existing=False)
    assert store.get(key) == {"value": "incumbent"}
