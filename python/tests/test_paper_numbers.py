"""Keep the paper's derived confounding statistics tied to executable results."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from scipy import stats

from optiqal.confounding import CATEGORY_PRIORS, calculate_e_value

REPO_ROOT = Path(__file__).resolve().parents[2]
PAPER_RESULTS_PATH = REPO_ROOT / "docs" / "optiqal_results.py"


def _load_paper_results():
    spec = importlib.util.spec_from_file_location("optiqal_paper_results", PAPER_RESULTS_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.r


def test_paper_confounding_statistics_match_scipy() -> None:
    results = _load_paper_results()
    prior = CATEGORY_PRIORS["exercise"]
    distribution = stats.beta(prior.alpha, prior.beta)

    assert results.confounding.alpha == prior.alpha
    assert results.confounding.beta == prior.beta
    assert results.confounding.mean == pytest.approx(distribution.mean())
    assert results.confounding.standard_deviation == pytest.approx(distribution.std())
    assert results.confounding.ci_lower == pytest.approx(distribution.ppf(0.025))
    assert results.confounding.ci_upper == pytest.approx(distribution.ppf(0.975))
    assert results.confounding.tail_probability_above_45 == pytest.approx(
        distribution.sf(0.45)
    )
    assert results.confounding_ci == "0.8%-49.0%"
    assert results.confounding_tail_above_45 == "0.039"
    assert results.confounding_one_sd_range == "3.7%-29.7%"


@pytest.mark.parametrize(
    ("hazard_ratio", "attribute"),
    [(0.70, "exercise_e_value"), (2.80, "smoking_e_value")],
)
def test_paper_e_values_match_model(hazard_ratio: float, attribute: str) -> None:
    results = _load_paper_results()
    expected, _ = calculate_e_value(hazard_ratio)
    assert getattr(results, attribute) == f"{expected:.2f}"


def test_paper_renders_corrected_values_from_eval_properties() -> None:
    paper = (REPO_ROOT / "docs" / "index.md").read_text(encoding="utf-8")
    appendix = (REPO_ROOT / "docs" / "appendix.md").read_text(encoding="utf-8")
    methodology = (REPO_ROOT / "docs" / "methodology.md").read_text(
        encoding="utf-8"
    )

    for property_name in (
        "confounding_ci",
        "confounding_tail_above_45",
        "confounding_one_sd_range",
        "exercise_e_value",
        "smoking_e_value",
    ):
        assert f"{{eval}}`r.{property_name}`" in paper
    assert "{eval}`r.exercise_e_value`" in appendix
    assert "95% CI: [0.8%, 49.0%]" in methodology

    for stale_text in (
        "95% CI [2%, 45%]",
        "P(f > 0.45) < 0.025",
        "≈ 1.9",
        "E-value ≈ 5.2",
        "95% CI: 7%–30%",
        "vary this prior by ±1 standard deviation",
    ):
        assert stale_text not in paper
