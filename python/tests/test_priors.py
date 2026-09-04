"""Frozen-value and fail-closed tests for the central prior registry."""

from __future__ import annotations

import ast
import json
import math
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from optiqal.catalog import EVIDENCE_EFFECT_MULTIPLIERS
from optiqal.confounding import (
    CATEGORY_PRIORS,
    EVIDENCE_ADJUSTMENTS,
    INTERVENTION_PRIORS,
    PROTOCOL_INTERVENTION_PRIORS,
    STUDY_QUALITY_SHRINKAGE,
)
from optiqal.intervention import Intervention
from optiqal.priors import load_priors
from optiqal.qol_evidence import (
    AUTHORED_RESIDUAL_OPTIMISM_PRIOR,
    QOL_STUDY_QUALITY_SHRINKAGE,
    QOL_TRANSPORT_PRIORS,
)

PYTHON_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = Path(__file__).with_name("fixtures") / "priors_2026-09-04.json"
SHIPPED_INTERVENTIONS = PYTHON_ROOT.parent / "src" / "lib" / "qaly" / "interventions"


def _beta_values(rows: dict) -> dict[str, list[float]]:
    return {key: [row["alpha"], row["beta"]] for key, row in rows.items()}


def _runtime_beta_values(rows: dict) -> dict[str, list[float]]:
    return {key: [prior.alpha, prior.beta] for key, prior in rows.items()}


def _literal_projection(priors: dict) -> dict:
    qol = priors["qol_transport"]
    authored = qol["authored_residual_optimism"]
    return {
        "version": priors["version"],
        "confounding": {
            section: _beta_values(priors["confounding"][section])
            for section in (
                "categories",
                "interventions",
                "protocol_interventions",
            )
        },
        "evidence_adjustments": {
            key: row["alpha_multiplier"]
            for key, row in priors["evidence_adjustments"].items()
        },
        "study_quality_retention": {
            key: row["retention"]
            for key, row in priors["study_quality_shrinkage"].items()
        },
        "qol_transport": {
            "study_quality_retention": {
                key: row["retention"]
                for key, row in qol["study_quality_shrinkage"].items()
            },
            "categories": _beta_values(qol["categories"]),
            "authored_residual_optimism": [authored["alpha"], authored["beta"]],
        },
        "evidence_effect_multipliers": {
            key: row["multiplier"]
            for key, row in priors["evidence_effect_multipliers"].items()
        },
    }


def test_loaded_priors_equal_frozen_fixture() -> None:
    expected = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert load_priors() == expected


def test_runtime_tables_equal_frozen_fixture() -> None:
    expected = _literal_projection(json.loads(FIXTURE_PATH.read_text(encoding="utf-8")))
    confounding = expected["confounding"]
    assert _runtime_beta_values(CATEGORY_PRIORS) == confounding["categories"]
    assert _runtime_beta_values(INTERVENTION_PRIORS) == confounding["interventions"]
    assert (
        _runtime_beta_values(PROTOCOL_INTERVENTION_PRIORS)
        == confounding["protocol_interventions"]
    )
    assert EVIDENCE_ADJUSTMENTS == expected["evidence_adjustments"]
    assert STUDY_QUALITY_SHRINKAGE == {
        key: round(1.0 - retention, 12)
        for key, retention in expected["study_quality_retention"].items()
    }

    qol = expected["qol_transport"]
    assert QOL_STUDY_QUALITY_SHRINKAGE == {
        key: round(1.0 - retention, 12)
        for key, retention in qol["study_quality_retention"].items()
    }
    assert _runtime_beta_values(QOL_TRANSPORT_PRIORS) == qol["categories"]
    assert [
        AUTHORED_RESIDUAL_OPTIMISM_PRIOR.alpha,
        AUTHORED_RESIDUAL_OPTIMISM_PRIOR.beta,
    ] == qol["authored_residual_optimism"]
    assert EVIDENCE_EFFECT_MULTIPLIERS == expected["evidence_effect_multipliers"]


def test_runtime_prior_metadata_comes_from_registry() -> None:
    priors = load_priors()
    for section, runtime in (
        ("categories", CATEGORY_PRIORS),
        ("interventions", INTERVENTION_PRIORS),
    ):
        for key, prior in runtime.items():
            row = priors["confounding"][section][key]
            assert prior.rationale == row.get("rationale", "")
            assert prior.calibration_sources == row.get("calibration_sources", [])


def test_load_priors_is_cached() -> None:
    assert load_priors() is load_priors()


def _write_modified_priors(tmp_path: Path, mutate) -> Path:
    data = deepcopy(load_priors())
    mutate(data)
    path = tmp_path / "priors.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda data: data.update({"unknown": {}}), "unknown keys"),
        (
            lambda data: data["confounding"]["categories"]["exercise"].update(
                {"unknown": 1}
            ),
            "unknown keys",
        ),
        (
            lambda data: data["confounding"]["interventions"].update(
                {"unknown_item": {"alpha": 1, "beta": 1, "source": "Unknown"}}
            ),
            "unknown keys",
        ),
        (
            lambda data: data["confounding"]["protocol_interventions"].update(
                {"unknown_item": {"alpha": 1, "beta": 1, "source": "Unknown"}}
            ),
            "unknown keys",
        ),
        (
            lambda data: data["confounding"]["categories"]["exercise"].update(
                {"alpha": 0}
            ),
            "alpha must be positive",
        ),
        (
            lambda data: data["confounding"]["categories"]["exercise"].update(
                {"beta": math.nan}
            ),
            "beta must be finite",
        ),
        (
            lambda data: data["study_quality_shrinkage"]["rct_standard"].update(
                {"retention": 1.01}
            ),
            "retention must be in",
        ),
        (
            lambda data: data["evidence_adjustments"]["rct"].update(
                {"alpha_multiplier": math.inf}
            ),
            "alpha_multiplier must be finite",
        ),
        (
            lambda data: data["evidence_effect_multipliers"]["low"].update(
                {"multiplier": -0.1}
            ),
            "multiplier must be positive",
        ),
        (
            lambda data: data["confounding"].pop("categories"),
            "missing keys",
        ),
    ],
)
def test_load_priors_rejects_malformed_values(
    tmp_path: Path, mutate, message: str
) -> None:
    path = _write_modified_priors(tmp_path, mutate)
    with pytest.raises(ValueError, match=message):
        load_priors(path)


def test_shipped_yaml_priors_resolve_to_registry() -> None:
    for path in sorted(SHIPPED_INTERVENTIONS.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if data["id"] not in INTERVENTION_PRIORS:
            continue
        intervention = Intervention.from_yaml(path)
        prior = intervention.confounding_prior
        canonical = INTERVENTION_PRIORS[data["id"]]
        assert prior is not canonical
        assert prior is not None
        assert (prior.alpha, prior.beta) == (canonical.alpha, canonical.beta)
        assert prior.rationale == canonical.rationale
        assert prior.calibration_sources == canonical.calibration_sources


def test_known_yaml_prior_must_match_registry() -> None:
    yaml_text = """
id: walking_30min_daily
name: Walking
category: exercise
confounding:
  prior: {type: beta, alpha: 99, beta: 1}
"""
    with pytest.raises(ValueError, match="does not match priors.yaml"):
        Intervention.from_yaml_string(yaml_text)


def test_known_id_without_inline_prior_keeps_category_fallback() -> None:
    intervention = Intervention.from_yaml_string(
        """
id: quit_smoking
name: Quit smoking
category: substance
"""
    )
    prior = intervention.confounding_prior
    category = CATEGORY_PRIORS["substance"]
    assert prior is not None
    assert (prior.alpha, prior.beta) == (category.alpha, category.beta)


def test_arbitrary_yaml_can_keep_an_inline_prior() -> None:
    intervention = Intervention.from_yaml_string(
        """
id: user_supplied_item
name: User supplied item
category: other
confounding:
  prior: {type: beta, alpha: 2.5, beta: 7.5}
  rationale: User supplied
  calibration_sources: [User source]
"""
    )
    prior = intervention.confounding_prior
    assert prior is not None
    assert (prior.alpha, prior.beta) == (2.5, 7.5)
    assert prior.rationale == "User supplied"
    assert prior.calibration_sources == ["User source"]


def _is_numeric_literal(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, (int, float)) and not isinstance(node.value, bool)
    return (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, (ast.UAdd, ast.USub))
        and isinstance(node.operand, ast.Constant)
        and isinstance(node.operand.value, (int, float))
    )


def test_no_numeric_literal_confounding_prior_constructors_in_runtime_code() -> None:
    violations = []
    for path in sorted((PYTHON_ROOT / "optiqal").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function_name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else node.func.attr
                if isinstance(node.func, ast.Attribute)
                else None
            )
            if function_name != "ConfoundingPrior":
                continue
            values = list(node.args) + [keyword.value for keyword in node.keywords]
            if any(_is_numeric_literal(value) for value in values):
                violations.append(f"{path.relative_to(PYTHON_ROOT)}:{node.lineno}")
    assert not violations, "numeric ConfoundingPrior literals: " + ", ".join(violations)
