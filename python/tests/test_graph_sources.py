"""Tests for graph source-loader registration and normative projections."""

from __future__ import annotations

import sys
from dataclasses import dataclass, fields
from datetime import date
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

from optiqal.graph.canonical import canonical_json
from optiqal.graph.decl import Graph, SourceRef, compile_graph
from optiqal.graph.errors import GraphRuntimeError, StoreUnavailableError
from optiqal.graph.sources import (
    DEFAULT_SOURCE_LOADERS,
    SOURCE_LOADERS,
    SourceLoaderRegistry,
    load_sources,
)


def _module(monkeypatch, name, **attributes):
    module = ModuleType(name)
    for attribute, value in attributes.items():
        setattr(module, attribute, value)
    monkeypatch.setitem(sys.modules, name, module)
    return module


def _assert_no_descriptive_keys(value):
    if isinstance(value, dict):
        assert not {
            "description",
            "citation",
            "notes",
            "extracted_by",
            "source",
        }.intersection(value)
        for child in value.values():
            _assert_no_descriptive_keys(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _assert_no_descriptive_keys(child)


def test_registry_is_idempotent_sorted_and_returns_read_only_snapshots():
    registry = SourceLoaderRegistry()

    def beta(source):
        return {"name": source.name}

    def alpha(source):
        return {"name": source.name}

    assert registry.register("beta", beta) is beta
    assert registry.register("beta", beta) is beta
    registry.register("alpha", alpha)
    assert registry.get("alpha") is alpha
    assert registry.names() == ("alpha", "beta")

    snapshot = registry.as_mapping()
    registry.register("later", alpha)
    assert tuple(snapshot) == ("beta", "alpha")
    with pytest.raises(TypeError):
        snapshot["other"] = alpha


@pytest.mark.parametrize("name", ["", None, 1])
def test_registry_rejects_invalid_names(name):
    with pytest.raises(ValueError, match="non-empty"):
        SourceLoaderRegistry().register(name, lambda source: source)


def test_registry_rejects_noncallables_conflicts_and_unknown_names():
    registry = SourceLoaderRegistry()
    with pytest.raises(TypeError, match="callable"):
        registry.register("bad", object())

    def first(source):
        return source

    registry.register("one", first)
    with pytest.raises(ValueError, match="already registered"):
        registry.register("one", lambda source: source)
    with pytest.raises(KeyError, match="No source loader"):
        registry.get("missing")


def test_registry_load_detaches_and_validates_normative_content():
    payload = {
        "value": [np.int64(3)],
        "description": "inert",
        "nested": {"source": "inert", "kept": np.array([1, 2])},
    }
    registry = SourceLoaderRegistry()
    registry.register("fixture", lambda source: payload)
    loaded = registry.load(SourceRef("fixture", "fixture"))
    payload["value"].append(4)
    payload["nested"]["kept"][0] = 9

    assert loaded["value"] == [3]
    assert "description" not in loaded
    assert "source" not in loaded["nested"]
    np.testing.assert_array_equal(loaded["nested"]["kept"], [1, 2])
    canonical_json(loaded)
    with pytest.raises(TypeError, match="requires a SourceRef"):
        registry.load("fixture")


@pytest.mark.parametrize("bad", [object(), {1: "not a string key"}])
def test_registry_load_rejects_noncanonical_content(bad):
    registry = SourceLoaderRegistry()
    registry.register("bad", lambda source: bad)
    with pytest.raises(TypeError, match="Source content"):
        registry.load(SourceRef("bad", "bad"))


@pytest.mark.parametrize("bad", [float("nan"), np.array([np.inf])])
def test_registry_load_rejects_nonfinite_content(bad):
    registry = SourceLoaderRegistry()
    registry.register("bad", lambda source: bad)
    with pytest.raises(ValueError, match="non-finite"):
        registry.load(SourceRef("bad", "bad"))


def test_load_sources_accepts_graph_and_compiled_graph():
    registry = SourceLoaderRegistry()
    registry.register("fixture", lambda source: {"loaded": source.name})
    graph = Graph(
        "sources",
        (SourceRef("first", "fixture"), SourceRef("second", "fixture")),
        (),
    )
    declared = load_sources(graph, registry)
    compiled = load_sources(compile_graph(graph), registry)
    assert (
        declared
        == compiled
        == {
            "first": {"loaded": "first"},
            "second": {"loaded": "second"},
        }
    )
    with pytest.raises(TypeError):
        declared["other"] = None


def test_load_sources_validates_arguments_and_loader_availability():
    graph = Graph("empty", (), ())
    with pytest.raises(TypeError, match="Graph or CompiledGraph"):
        load_sources(object())
    with pytest.raises(TypeError, match="SourceLoaderRegistry"):
        load_sources(graph, {})
    missing = Graph("missing", (SourceRef("x", "not-installed"),), ())
    with pytest.raises(KeyError, match="not-installed"):
        load_sources(missing, SourceLoaderRegistry())


def test_default_registry_names_and_alias():
    assert SOURCE_LOADERS is DEFAULT_SOURCE_LOADERS
    assert DEFAULT_SOURCE_LOADERS.names() == (
        "catalog",
        "priors",
        "profile",
        "snapshot",
        "studies",
    )
    assert DEFAULT_SOURCE_LOADERS.get("snapshot:fixture") is (
        DEFAULT_SOURCE_LOADERS.get("snapshot")
    )
    assert DEFAULT_SOURCE_LOADERS.get("profile:fixture") is (
        DEFAULT_SOURCE_LOADERS.get("profile")
    )
    assert DEFAULT_SOURCE_LOADERS.get("study:fixture") is (
        DEFAULT_SOURCE_LOADERS.get("studies")
    )
    assert DEFAULT_SOURCE_LOADERS.get("catalog:fixture") is (
        DEFAULT_SOURCE_LOADERS.get("catalog")
    )


def test_priors_fall_back_to_confounding_numeric_tables():
    loaded = DEFAULT_SOURCE_LOADERS.load(SourceRef("priors", "priors"))
    exercise = loaded["confounding"]["categories"]["exercise"]
    assert exercise == {"alpha": 1.2, "beta": 6.0}
    assert loaded["evidence_adjustments"]["rct"] == {"alpha_multiplier": 1.5}
    assert loaded["study_quality_shrinkage"]["rct_standard"] == {"retention": 0.2}
    _assert_no_descriptive_keys(loaded)


def test_priors_use_optional_loader_and_strip_source_prose(monkeypatch):
    raw = {
        "row": {
            "alpha": 2.0,
            "source": "citation",
            "rationale": "prose",
            "calibration_sources": ["citation"],
        }
    }
    _module(monkeypatch, "optiqal.priors", load_priors=lambda: raw)
    loaded = DEFAULT_SOURCE_LOADERS.load(SourceRef("priors", "priors"))
    raw["row"]["alpha"] = 9.0
    assert loaded == {"row": {"alpha": 2.0}}


def test_optional_module_internal_import_errors_do_not_trigger_fallback(monkeypatch):
    from optiqal.graph import sources

    real_import = sources.importlib.import_module

    def import_with_broken_dependency(name):
        if name == "optiqal.priors":
            raise ModuleNotFoundError("No module named 'dependency'", name="dependency")
        return real_import(name)

    monkeypatch.setattr(
        sources.importlib, "import_module", import_with_broken_dependency
    )
    with pytest.raises(ModuleNotFoundError) as error:
        DEFAULT_SOURCE_LOADERS.load(SourceRef("priors", "priors"))
    assert error.value.name == "dependency"


def test_optional_module_must_expose_its_documented_loader(monkeypatch):
    _module(monkeypatch, "optiqal.priors")
    with pytest.raises(StoreUnavailableError, match="load_priors"):
        DEFAULT_SOURCE_LOADERS.load(SourceRef("priors", "priors"))
    with pytest.raises(GraphRuntimeError, match="expected 'priors'"):
        DEFAULT_SOURCE_LOADERS.load(SourceRef("other", "priors"))


@dataclass
class _Study:
    id: str
    estimate: dict[str, float]
    verified: date
    notes: str = "inert"
    extracted_by: str = "inert"


def test_studies_support_whole_table_and_item_scopes(monkeypatch):
    study = _Study(
        "trial-one",
        {"value": 0.8, "ci_low": 0.7, "ci_high": 0.9},
        date(2026, 9, 4),
    )
    _module(monkeypatch, "optiqal.evidence", load_studies=lambda: [study])
    table = DEFAULT_SOURCE_LOADERS.load(SourceRef("studies", "studies"))
    row = DEFAULT_SOURCE_LOADERS.load(SourceRef("study:trial-one", "studies"))
    assert table == {"trial-one": row}
    assert row["id"] == "trial-one"
    assert row["verified"] == "2026-09-04"
    _assert_no_descriptive_keys(row)


def test_studies_are_empty_before_pr_d_and_unknown_scope_fails():
    assert DEFAULT_SOURCE_LOADERS.load(SourceRef("studies", "studies")) == {}
    with pytest.raises(KeyError, match="Unknown study id"):
        DEFAULT_SOURCE_LOADERS.load(SourceRef("study:not-there", "studies"))
    with pytest.raises(GraphRuntimeError, match="expected 'studies'"):
        DEFAULT_SOURCE_LOADERS.load(SourceRef("study:", "studies"))


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        (42, "mapping or sequence"),
        ([{"value": 1}], "non-empty string id"),
        ({"mapped": {"id": "different"}}, "mapped under"),
        ([{"id": "same"}, {"id": "same"}], "duplicate id"),
        ({"row": [1]}, "not an object"),
    ],
)
def test_study_table_rejects_malformed_results(monkeypatch, rows, message):
    _module(monkeypatch, "optiqal.evidence", load_studies=lambda: rows)
    with pytest.raises((TypeError, ValueError), match=message):
        DEFAULT_SOURCE_LOADERS.load(SourceRef("studies", "studies"))


def test_studies_module_requires_load_studies(monkeypatch):
    _module(monkeypatch, "optiqal.evidence")
    with pytest.raises(StoreUnavailableError, match="load_studies"):
        DEFAULT_SOURCE_LOADERS.load(SourceRef("studies", "studies"))


def test_snapshot_loader_passes_name_and_omits_provenance(monkeypatch):
    seen = []

    def load_snapshot(name):
        seen.append(name)
        return {
            "provenance": {"source": "inert", "version": 1},
            "data": {"ages": [20, 21], "rates": [0.01, 0.02]},
        }

    _module(monkeypatch, "optiqal.snapshots", load_snapshot=load_snapshot)
    loaded = DEFAULT_SOURCE_LOADERS.load(
        SourceRef("snapshot:cdc_life_table", "snapshot")
    )
    assert seen == ["cdc_life_table"]
    assert loaded == {"ages": [20, 21], "rates": [0.01, 0.02]}


def test_snapshot_loader_supports_validated_snapshot_objects(monkeypatch):
    snapshot = SimpleNamespace(provenance={"source": "inert"}, data={"value": 3})
    _module(monkeypatch, "optiqal.snapshots", load_snapshot=lambda name: snapshot)
    assert DEFAULT_SOURCE_LOADERS.load(SourceRef("snapshot:fixture", "snapshot")) == {
        "value": 3
    }


def test_snapshot_fail_closed_paths(monkeypatch):
    with pytest.raises(StoreUnavailableError, match="optiqal.snapshots"):
        DEFAULT_SOURCE_LOADERS.load(SourceRef("snapshot:missing", "snapshot"))
    with pytest.raises(GraphRuntimeError, match="snapshot:<name>"):
        DEFAULT_SOURCE_LOADERS.load(SourceRef("snapshot:", "snapshot"))

    _module(monkeypatch, "optiqal.snapshots")
    with pytest.raises(StoreUnavailableError, match="load_snapshot"):
        DEFAULT_SOURCE_LOADERS.load(SourceRef("snapshot:fixture", "snapshot"))

    _module(
        monkeypatch,
        "optiqal.snapshots",
        load_snapshot=lambda name: {"provenance": {"version": 1}},
    )
    with pytest.raises(ValueError, match="no data block"):
        DEFAULT_SOURCE_LOADERS.load(SourceRef("snapshot:fixture", "snapshot"))


def test_catalog_projection_is_complete_normative_and_item_scoped():
    from optiqal.catalog import CATALOG

    entry = CATALOG["finasteride_1.25mg"]
    row = DEFAULT_SOURCE_LOADERS.load(
        SourceRef("catalog:finasteride_1.25mg", "catalog")
    )
    table = DEFAULT_SOURCE_LOADERS.load(SourceRef("catalog", "catalog"))
    assert table["finasteride_1.25mg"] == row
    assert "notes" not in row and "sources" not in row
    assert row["study_ids"] == []
    assert row["public_lane"] == entry.public_lane
    assert row["public_condition"] == entry.public_condition
    assert (
        row["public_display_category_override"]
        == entry.public_display_category_override
    )
    for item in fields(entry):
        value = getattr(entry, item.name)
        if type(value) in (int, float):
            assert row[item.name] == value
    _assert_no_descriptive_keys(row)
    canonical_json(row)


@dataclass
class _CatalogEntry:
    id: str
    effect: float = 0.5
    study_ids: list[str] | tuple[str, ...] = ()
    public_lane: str = "consumer_public"
    notes: str = "inert"
    sources: list[str] | tuple[str, ...] = ("inert",)


def test_catalog_projection_sorts_study_ids_and_detaches(monkeypatch):
    entry = _CatalogEntry("item", study_ids=["z", "a"])
    _module(monkeypatch, "optiqal.catalog", get_catalog=lambda: {"item": entry})
    loaded = DEFAULT_SOURCE_LOADERS.load(SourceRef("catalog:item", "catalog"))
    entry.study_ids.append("later")
    assert loaded == {
        "id": "item",
        "effect": 0.5,
        "study_ids": ["a", "z"],
        "public_lane": "consumer_public",
    }


@pytest.mark.parametrize(
    ("catalog", "message"),
    [
        ([], "must return a mapping"),
        ({1: {"id": "one"}}, "string ids"),
        ({"mapped": {"id": "different"}}, "mapped under"),
        ({"item": 1}, "not an object"),
        ({"item": {"id": "item", "study_ids": "bad"}}, "invalid study_ids"),
        (
            {"item": {"id": "item", "study_ids": ["same", "same"]}},
            "repeats a study id",
        ),
    ],
)
def test_catalog_rejects_malformed_results(monkeypatch, catalog, message):
    _module(monkeypatch, "optiqal.catalog", get_catalog=lambda: catalog)
    with pytest.raises((TypeError, ValueError), match=message):
        DEFAULT_SOURCE_LOADERS.load(SourceRef("catalog", "catalog"))


def test_catalog_name_and_loader_failures(monkeypatch):
    with pytest.raises(GraphRuntimeError, match="expected 'catalog'"):
        DEFAULT_SOURCE_LOADERS.load(SourceRef("catalog:", "catalog"))
    with pytest.raises(KeyError, match="Unknown catalog id"):
        DEFAULT_SOURCE_LOADERS.load(SourceRef("catalog:not-there", "catalog"))
    _module(monkeypatch, "optiqal.catalog")
    with pytest.raises(StoreUnavailableError, match="get_catalog"):
        DEFAULT_SOURCE_LOADERS.load(SourceRef("catalog", "catalog"))


def test_profile_loader_uses_field_derived_id_and_omits_genetics():
    identifier = "25_male_normal_never_nondiabetic_normotensive_light"
    loaded = DEFAULT_SOURCE_LOADERS.load(SourceRef(f"profile:{identifier}", "profile"))
    assert loaded == {
        "age": 25,
        "sex": "male",
        "bmi_category": "normal",
        "smoking_status": "never",
        "has_diabetes": False,
        "has_hypertension": False,
        "activity_level": "light",
    }
    assert "genetic_profile" not in loaded


def test_profile_loader_rejects_genetic_data(monkeypatch):
    from optiqal import profile as profile_module

    genetic = profile_module.Profile(
        25,
        "male",
        "normal",
        "never",
        False,
        genetic_profile=object(),
    )
    monkeypatch.setattr(
        profile_module, "generate_all_profiles", lambda: iter([genetic])
    )
    with pytest.raises(GraphRuntimeError, match="genetic"):
        DEFAULT_SOURCE_LOADERS.load(SourceRef(f"profile:{genetic.key}", "profile"))


def test_profile_loader_rejects_bad_names_unknown_and_malformed_profiles(monkeypatch):
    with pytest.raises(GraphRuntimeError, match="profile:<id>"):
        DEFAULT_SOURCE_LOADERS.load(SourceRef("profile:", "profile"))
    with pytest.raises(KeyError, match="Unknown profile id"):
        DEFAULT_SOURCE_LOADERS.load(SourceRef("profile:not-there", "profile"))

    fake = _module(
        monkeypatch,
        "optiqal.profile",
        generate_all_profiles=lambda: iter([SimpleNamespace(age=25)]),
    )
    with pytest.raises(TypeError, match="missing fields"):
        DEFAULT_SOURCE_LOADERS.load(SourceRef("profile:any", "profile"))

    bad_key = SimpleNamespace(
        age=25,
        sex="male",
        bmi_category="normal",
        smoking_status="never",
        has_diabetes=False,
        has_hypertension=False,
        activity_level="light",
        genetic_profile=None,
        key="wrong",
    )
    fake.generate_all_profiles = lambda: iter([bad_key])
    with pytest.raises(ValueError, match="does not match its fields"):
        DEFAULT_SOURCE_LOADERS.load(SourceRef("profile:any", "profile"))

    duplicate = SimpleNamespace(**vars(bad_key))
    duplicate.key = "25_male_normal_never_nondiabetic_normotensive_light"
    bad_key.key = duplicate.key
    fake.generate_all_profiles = lambda: iter([bad_key, duplicate])
    with pytest.raises(ValueError, match="duplicate id"):
        DEFAULT_SOURCE_LOADERS.load(SourceRef(f"profile:{duplicate.key}", "profile"))

    del fake.generate_all_profiles
    with pytest.raises(StoreUnavailableError, match="generate_all_profiles"):
        DEFAULT_SOURCE_LOADERS.load(SourceRef("profile:any", "profile"))
