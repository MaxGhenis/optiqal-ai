"""End-to-end invariants of the frontier web response.

The engine, decision and optimizer invariants are tested where they live
(test_engine_invariants.py, test_decision_invariants.py). These checks run the
whole public path, ``build_frontier_response``, over a spread of profiles and
assert what a reader of the response relies on: probabilities are
probabilities, intervals are ordered and bracket the estimate they belong to,
the ranked frontier only adds items that help and never pairs exclusive
alternatives, and the response does not depend on ``PYTHONHASHSEED``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from optiqal.catalog import CATALOG
from optiqal.web_api import build_frontier_response

PYTHON_DIR = Path(__file__).resolve().parents[1]

# The response rounds probabilities to 2 decimals, QALYs to 4 and days to 1
# (web_api.build_frontier_response_with_policy). Two probabilities that sum
# to at most 1 can therefore round to a sum of at most 1.01.
PROBABILITY_ROUNDING = 0.005
QALY_ROUNDING = 0.00005
DAY_ROUNDING = 0.05


def _profile(**overrides):
    profile = {
        "age": 40,
        "sex": "male",
        "weight_kg": 80,
        "height_cm": 178,
        "smoker": False,
        "has_diabetes": False,
        "has_hypertension": False,
        "activity_level": "light",
        "sleep_hours_per_night": 7,
    }
    profile.update(overrides)
    return profile


# Synthetic profiles spanning age, sex, risk, sleep input and a current stack.
REQUESTS = {
    "healthy_young_male": {"profile": _profile(age=25, activity_level="active")},
    "female_hypertension": {
        "profile": _profile(
            age=62, sex="female", weight_kg=70, height_cm=165, has_hypertension=True
        )
    },
    "other_sex": {"profile": _profile(age=35, sex="other")},
    "high_risk_short_sleep": {
        "profile": _profile(
            age=75,
            weight_kg=95,
            height_cm=175,
            smoker=True,
            has_diabetes=True,
            has_hypertension=True,
            activity_level="sedentary",
            sleep_hours_per_night=3,
        ),
        "sleep_metrics": {"routine_score": 90},
    },
    "current_stack": {
        "profile": _profile(age=55, sex="female", weight_kg=68, height_cm=165),
        "current_stack_ids": ["statin_5mg"],
    },
    "oldest_modeled": {"profile": _profile(age=99)},
}


@pytest.fixture(scope="module")
def responses():
    return {
        name: build_frontier_response({**request, "n_simulations": 64})
        for name, request in REQUESTS.items()
    }


@pytest.mark.parametrize("name", sorted(REQUESTS))
def test_item_probabilities_are_disjoint_probabilities(responses, name):
    for item in responses[name]["items"]:
        assert 0.0 <= item["p_benefit"] <= 1.0, item["id"]
        assert 0.0 <= item["p_harm"] <= 1.0, item["id"]
        assert item["p_benefit"] + item["p_harm"] <= 1.0 + 2 * PROBABILITY_ROUNDING, (
            item["id"]
        )


@pytest.mark.parametrize("name", sorted(REQUESTS))
def test_item_intervals_bracket_their_point_estimate(responses, name):
    """The 80% interval and the point estimate describe the same total-QALY
    draws, and for shipped items the expected total lies inside the interval
    (event harms enter each draw as an expected loss, so a rare event no longer
    drags the mean outside the interval)."""
    for item in responses[name]["items"]:
        low, high = item["net_qaly_ci"]
        assert low <= high, item["id"]
        assert low - QALY_ROUNDING <= item["total_qaly"] <= high + QALY_ROUNDING, item[
            "id"
        ]
        day_low, day_high = item["net_days_ci"]
        assert day_low <= day_high, item["id"]
        assert day_low - DAY_ROUNDING <= item["days"] <= day_high + DAY_ROUNDING, item[
            "id"
        ]


@pytest.mark.parametrize("name", sorted(REQUESTS))
def test_item_days_are_qalys_in_days(responses, name):
    for item in responses[name]["items"]:
        tolerance = DAY_ROUNDING + QALY_ROUNDING * 365.25
        assert abs(item["days"] - item["total_qaly"] * 365.25) <= tolerance, item["id"]


@pytest.mark.parametrize("name", sorted(REQUESTS))
def test_frontier_adds_only_helpful_items_and_respects_exclusivity(responses, name):
    request = REQUESTS[name]
    steps = responses[name]["frontier"]
    preselected = set(request.get("current_stack_ids", []))
    added = [step["added_intervention"] for step in steps]
    assert len(added) == len(set(added))
    assert not preselected & set(added)
    for step in steps:
        assert step["marginal_qaly"] > 0, step["added_intervention"]
    if steps:
        selected = steps[-1]["selected_interventions"]
        groups = [
            CATALOG[item_id].exclusive_group
            for item_id in selected
            if CATALOG[item_id].exclusive_group
        ]
        assert len(groups) == len(set(groups)), selected


def test_one_remaining_year_bounds_every_effect(responses):
    """Age 99 leaves one modeled year (the engine integrates to age 100).

    Survival to the start of that year is 1 with or without an intervention,
    so no mortality benefit can accrue, and no item can move total QALYs by
    more than the one year that remains.
    """
    for item in responses["oldest_modeled"]["items"]:
        assert item["mort_qaly"] == 0.0, item["id"]
        assert abs(item["total_qaly"]) <= 1.0, item["id"]


_DETERMINISM_SCRIPT = """
import json, sys
from optiqal.web_api import build_frontier_response
requests = json.loads(sys.argv[1])
print(json.dumps([build_frontier_response(r) for r in requests], sort_keys=True))
"""


def test_frontier_response_is_independent_of_hash_seed():
    """Determinism: set and dict iteration order must never reach the output.

    Candidates, ties and exclusive groups used to be scanned in set order, so
    the ranked path could change with PYTHONHASHSEED.
    """
    requests = [
        {**REQUESTS["current_stack"], "n_simulations": 16},
        {**REQUESTS["high_risk_short_sleep"], "n_simulations": 16},
    ]
    outputs = set()
    for seed in ("0", "1", "2", "3"):
        env = {**os.environ, "PYTHONHASHSEED": seed, "OPENBLAS_NUM_THREADS": "1"}
        env["PYTHONPATH"] = str(PYTHON_DIR)
        completed = subprocess.run(
            [sys.executable, "-c", _DETERMINISM_SCRIPT, json.dumps(requests)],
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )
        outputs.add(completed.stdout)
    assert len(outputs) == 1
