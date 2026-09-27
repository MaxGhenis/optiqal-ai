"""Keep the paper's derived statistics and summaries tied to executable results."""

from __future__ import annotations

import dataclasses
import importlib.util
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from scipy import stats

from optiqal.confounding import CATEGORY_PRIORS, calculate_e_value

REPO_ROOT = Path(__file__).resolve().parents[2]
PAPER_RESULTS_PATH = REPO_ROOT / "docs" / "optiqal_results.py"


def _load_paper_results():
    spec = importlib.util.spec_from_file_location(
        "optiqal_paper_results", PAPER_RESULTS_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.r


_PAPER_RESULTS = _load_paper_results()


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
    methodology = (REPO_ROOT / "docs" / "methodology.md").read_text(encoding="utf-8")

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


def _displayed_table_rows(results) -> list[tuple[str, float, float]]:
    """Parse (category, QALYs, life years) from the rendered intervention table."""
    rows = []
    for line in results.intervention_table().splitlines()[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        _, category, qalys, _, life_years, _ = cells
        rows.append((category, float(qalys), float(life_years)))
    return rows


def _parse_range(text: str) -> tuple[float, float]:
    low, high = text.split("-")
    return float(low), float(high)


def test_paper_summary_ranges_match_the_displayed_estimates() -> None:
    # Audit regression: the abstract said 0.05-1.15 while the lowest of the
    # ten displayed estimates (consistent_bedtime) is 0.07.
    results = _load_paper_results()
    table = _displayed_table_rows(results)

    assert results.qaly_range == "0.07-1.15"
    assert results.life_years_range == "0.2-4.4"
    assert results.months_range == "2-53"
    assert results.intervention_count == len(table) == 10
    assert results.category_count == len({row[0] for row in table}) == 5

    qalys = [row[1] for row in table]
    life_years = [row[2] for row in table]
    assert _parse_range(results.qaly_range) == (min(qalys), max(qalys))
    assert _parse_range(results.life_years_range) == (min(life_years), max(life_years))
    months = [row.life_years * 12 for row in results.all_interventions()]
    assert results.months_range == f"{min(months):.0f}-{max(months):.0f}"


def test_paper_ranges_cover_every_intervention_the_paper_defines() -> None:
    results = _load_paper_results()
    intervention_type = type(results.exercise)
    defined = {
        id(value)
        for value in vars(results).values()
        if isinstance(value, intervention_type)
    }
    assert defined == {id(row) for row in results.all_interventions()}


def test_paper_renders_summary_ranges_from_eval_properties() -> None:
    paper = (REPO_ROOT / "docs" / "index.md").read_text(encoding="utf-8")
    for property_name in (
        "qaly_range",
        "life_years_range",
        "months_range",
        "intervention_count",
        "category_count",
    ):
        assert f"{{eval}}`r.{property_name}`" in paper
    assert "0.05-1.15" not in paper


_NON_NEGATIVE = st.floats(min_value=0.0, max_value=10.0, allow_nan=False)


@settings(max_examples=200, deadline=None)
@given(
    rows=st.lists(
        st.tuples(
            _NON_NEGATIVE,
            _NON_NEGATIVE,
            st.sampled_from(("exercise", "diet", "sleep", "stress", "substance")),
        ),
        min_size=10,
        max_size=10,
    )
)
def test_paper_summaries_track_edited_estimates(rows) -> None:
    # Editing any displayed literal must move the summaries with it.
    results = type(_PAPER_RESULTS)()
    names = [
        name
        for name, value in vars(results).items()
        if isinstance(value, type(results.exercise))
    ]
    for name, (qaly, life_years, category) in zip(names, rows, strict=True):
        edited = dataclasses.replace(
            getattr(results, name),
            qaly_mean=qaly,
            life_years=life_years,
            category=category,
        )
        setattr(results, name, edited)

    qalys = [row[0] for row in rows]
    life_years = [row[1] for row in rows]
    assert results.qaly_range == f"{min(qalys):.2f}-{max(qalys):.2f}"
    assert results.life_years_range == f"{min(life_years):.1f}-{max(life_years):.1f}"
    assert (
        results.months_range == f"{min(life_years) * 12:.0f}-{max(life_years) * 12:.0f}"
    )
    assert results.intervention_count == len(rows)
    assert results.category_count == len({row[2] for row in rows})

    # Each displayed value lies inside its summary range, whose ends are attained.
    low, high = _parse_range(results.qaly_range)
    shown = [float(row.qaly) for row in results.all_interventions()]
    assert all(low <= value <= high for value in shown)
    assert low in shown and high in shown
