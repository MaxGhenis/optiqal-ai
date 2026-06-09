"""Input-bound guards for the web API.

These protect the FastAPI engine on the direct (non-Next) path: an
out-of-range age drives an effectively unbounded life-table loop, a zero
height divides by zero in BMI, and an unbounded ``n_simulations`` lets one
request exhaust CPU/memory.
"""

from __future__ import annotations

import pytest

from optiqal import web_api

VALID_PROFILE = {
    "age": 39,
    "sex": "male",
    "weight_kg": 74.8,
    "height_cm": 178.0,
    "smoker": False,
    "has_diabetes": False,
    "has_hypertension": False,
    "activity_level": "active",
}


@pytest.mark.parametrize(
    "field,value",
    [
        ("age", -1_000_000),
        ("age", 500),
        ("height_cm", 0),
        ("weight_kg", 0),
    ],
)
def test_baseline_rejects_out_of_range_profile(field, value):
    payload = {"profile": {**VALID_PROFILE, field: value}}
    with pytest.raises(ValueError):
        web_api.build_baseline_response(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("age", -1_000_000),
        ("height_cm", 0),
        ("weight_kg", 0),
    ],
)
def test_frontier_rejects_out_of_range_profile(field, value):
    payload = {"profile": {**VALID_PROFILE, field: value}}
    with pytest.raises(ValueError):
        web_api.build_frontier_response(payload)


def test_frontier_clamps_n_simulations():
    payload = {"profile": dict(VALID_PROFILE), "n_simulations": 100_000_000}
    response = web_api.build_frontier_response(payload)
    assert response["meta"]["n_simulations"] == 20_000


def test_bounded_simulations_floor_and_default():
    assert web_api._bounded_simulations(0) == 1
    assert web_api._bounded_simulations(-5) == 1
    assert web_api._bounded_simulations("not a number") == 5000
    assert web_api._bounded_simulations(3000) == 3000
