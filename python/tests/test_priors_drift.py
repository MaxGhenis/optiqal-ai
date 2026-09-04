"""Guard documented and shipped confounding priors against registry drift."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from optiqal.priors import load_priors

REPO_ROOT = Path(__file__).resolve().parents[2]
METHODOLOGY_PATH = REPO_ROOT / "docs" / "methodology.md"
PAPER_PATH = REPO_ROOT / "docs" / "index.md"
INTERVENTIONS_DIR = REPO_ROOT / "src" / "lib" / "qaly" / "interventions"

EXPECTED_CATEGORIES = frozenset(
    {
        "exercise",
        "diet",
        "sleep",
        "stress",
        "substance",
        "medical",
        "social",
        "other",
    }
)

_METHODOLOGY_LABELS = {
    "Exercise interventions": "exercise",
    "Diet interventions": "diet",
    "Sleep interventions": "sleep",
    "Stress/meditation": "stress",
    "Substance interventions": "substance",
    "Medical interventions": "medical",
    "Social interventions": "social",
    "Other interventions": "other",
}
_NUMBER = r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
_BETA = re.compile(rf"Beta\(\s*(?P<alpha>{_NUMBER})\s*,\s*(?P<beta>{_NUMBER})\s*\)")
_METHODOLOGY_BLOCK = re.compile(
    rf"^\*\*(?P<label>[^*\n]+)\*\*[^\n]*:\s*\n"
    rf"- Prior: \$\\text\{{Beta\}}\(\s*(?P<alpha>{_NUMBER})\s*,\s*"
    rf"(?P<beta>{_NUMBER})\s*\)\$",
    re.MULTILINE,
)


def _registry_category_values() -> dict[str, tuple[float, float]]:
    rows = load_priors()["confounding"]["categories"]
    assert set(rows) == EXPECTED_CATEGORIES
    return {
        category: (float(row["alpha"]), float(row["beta"]))
        for category, row in rows.items()
    }


def _parse_methodology_categories() -> dict[str, tuple[float, float]]:
    text = METHODOLOGY_PATH.read_text(encoding="utf-8")
    section = text.split("### Beta Prior Distributions", maxsplit=1)[1].split(
        "### Monte Carlo Sampling", maxsplit=1
    )[0]
    parsed: dict[str, tuple[float, float]] = {}
    for match in _METHODOLOGY_BLOCK.finditer(section):
        label = match.group("label")
        assert label in _METHODOLOGY_LABELS, f"Unknown methodology category: {label}"
        category = _METHODOLOGY_LABELS[label]
        assert category not in parsed, f"Duplicate methodology category: {category}"
        parsed[category] = (
            float(match.group("alpha")),
            float(match.group("beta")),
        )
    assert set(parsed) == EXPECTED_CATEGORIES
    return parsed


def _markdown_cells(row: str) -> list[str]:
    assert row.startswith("|") and row.endswith("|")
    return [cell.strip() for cell in row[1:-1].split("|")]


def _parse_paper_categories() -> dict[str, tuple[float, float]]:
    lines = PAPER_PATH.read_text(encoding="utf-8").splitlines()
    header = "| Category | Prior | Mean | Calibration Source |"
    assert lines.count(header) == 1, "Expected exactly one category prior table"
    start = lines.index(header)
    assert re.fullmatch(r"\|(?:\s*:?-+:?\s*\|){4}", lines[start + 1])

    parsed: dict[str, tuple[float, float]] = {}
    for row in lines[start + 2 :]:
        if not row.startswith("|"):
            break
        cells = _markdown_cells(row)
        assert len(cells) == 4, f"Malformed category prior row: {row}"
        category = cells[0].casefold()
        assert category not in parsed, f"Duplicate paper category: {category}"
        match = _BETA.fullmatch(cells[1])
        assert match is not None, f"Malformed Beta prior in paper row: {row}"
        parsed[category] = (
            float(match.group("alpha")),
            float(match.group("beta")),
        )
    assert set(parsed) == EXPECTED_CATEGORIES
    return parsed


def _mapping(value: Any, *, path: Path, field: str) -> dict[str, Any]:
    assert isinstance(value, dict), f"{path}: {field} must be a mapping"
    return value


def _parse_intervention_yaml_priors() -> dict[str, tuple[float, float]]:
    paths = sorted(INTERVENTIONS_DIR.glob("*.yaml"))
    assert paths, f"No intervention YAMLs found in {INTERVENTIONS_DIR}"

    parsed: dict[str, tuple[float, float]] = {}
    for path in paths:
        document = _mapping(
            yaml.safe_load(path.read_text(encoding="utf-8")),
            path=path,
            field="document",
        )
        item_id = document.get("id")
        assert item_id == path.stem, f"{path}: id must match the filename"
        assert item_id not in parsed, f"Duplicate intervention id: {item_id}"

        confounding = _mapping(
            document.get("confounding"), path=path, field="confounding"
        )
        prior = _mapping(confounding.get("prior"), path=path, field="confounding.prior")
        assert set(prior) == {"type", "alpha", "beta"}, (
            f"{path}: confounding.prior must contain exactly type, alpha, and beta"
        )
        assert prior["type"] == "beta", f"{path}: confounding.prior must be Beta"
        assert isinstance(prior["alpha"], int | float), f"{path}: alpha must be numeric"
        assert isinstance(prior["beta"], int | float), f"{path}: beta must be numeric"
        parsed[item_id] = (float(prior["alpha"]), float(prior["beta"]))

    assert len(parsed) == len(paths), "Every intervention YAML must have one prior"
    return parsed


def test_methodology_category_priors_match_registry() -> None:
    assert _parse_methodology_categories() == _registry_category_values()


def test_paper_category_priors_match_registry() -> None:
    assert _parse_paper_categories() == _registry_category_values()


def test_intervention_yaml_priors_match_registry() -> None:
    actual = _parse_intervention_yaml_priors()
    registry = load_priors()["confounding"]["interventions"]
    expected = {
        item_id: (float(registry[item_id]["alpha"]), float(registry[item_id]["beta"]))
        for item_id in actual
    }
    assert actual == expected
