"""Regenerate model-responses.json from the real Python web API.

The response-contract tests (src/lib/*-contract.test.ts) parse these payloads
to prove that everything the model actually emits crosses the JS boundary.
They are shape/validity fixtures, not pinned numbers: regenerate them whenever
the Python numerics change, and the contract tests should still pass.

Run from the repository root:

    cd python && OPENBLAS_NUM_THREADS=1 .venv/bin/python \
        ../src/lib/__fixtures__/generate_model_responses.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "python"))

from optiqal.web_api import (  # noqa: E402
    build_baseline_response,
    build_frontier_response,
)

# Synthetic profiles only.
DEFAULT_PROFILE = {
    "age": 35,
    "sex": "male",
    "weight_kg": 75,
    "height_cm": 175,
    "smoker": False,
    "has_diabetes": False,
    "has_hypertension": False,
    "activity_level": "light",
    "sleep_hours_per_night": 7,
}

HIGH_RISK_PROFILE = {
    **DEFAULT_PROFILE,
    "age": 75,
    "weight_kg": 130,
    "smoker": True,
    "has_diabetes": True,
    "has_hypertension": True,
    "activity_level": "sedentary",
    "sleep_hours_per_night": 4,
}

HEAVY_SLEEP_METRICS = {
    "duration_hours": 4,
    "spo2": 85,
    "snore_pct": 70,
    "breathing_score": 0.2,
}

BASELINE_CASES = [
    ("male_default", {"profile": DEFAULT_PROFILE}),
    ("female_default", {"profile": {**DEFAULT_PROFILE, "sex": "female"}}),
    # "other" averages the male and female projections.
    ("other_default", {"profile": {**DEFAULT_PROFILE, "sex": "other"}}),
    # Mixed-sex tail case from the 2026-09-25 invariants audit.
    ("other_age_18", {"profile": {**DEFAULT_PROFILE, "age": 18, "sex": "other"}}),
    (
        "high_risk_with_sleep",
        {"profile": HIGH_RISK_PROFILE, "sleep_metrics": HEAVY_SLEEP_METRICS},
    ),
    # Last modeled year: the interval collapses to a single year.
    ("age_110_horizon_end", {"profile": {**DEFAULT_PROFILE, "age": 110}}),
    # Past the life-table horizon: the survival curve is empty.
    ("age_120_past_horizon", {"profile": {**DEFAULT_PROFILE, "age": 120}}),
]

N_SIMULATIONS = 32

FRONTIER_CASES = [
    ("male_default", {"profile": DEFAULT_PROFILE}),
    (
        "other_age_80_sleep",
        {
            "profile": {**DEFAULT_PROFILE, "age": 80, "sex": "other"},
            "sleep_metrics": {"duration_hours": 5, "spo2": 90},
        },
    ),
    (
        "high_risk_current_stack",
        {
            "profile": HIGH_RISK_PROFILE,
            "sleep_metrics": HEAVY_SLEEP_METRICS,
            "current_stack_ids": ["statin_5mg", "hiit_2x_week"],
        },
    ),
    (
        "female_18_current_stack",
        {
            "profile": {
                **DEFAULT_PROFILE,
                "age": 18,
                "sex": "female",
                "activity_level": "active",
                "sleep_hours_per_night": 9,
            },
            "current_stack_ids": ["strength_maintenance"],
        },
    ),
]


def main() -> None:
    fixtures: dict[str, list[dict]] = {"baseline": [], "frontier": []}
    for name, request in BASELINE_CASES:
        fixtures["baseline"].append(
            {
                "name": name,
                "request": request,
                "response": build_baseline_response(request),
            }
        )
    for name, request in FRONTIER_CASES:
        request = {**request, "n_simulations": N_SIMULATIONS}
        fixtures["frontier"].append(
            {
                "name": name,
                "request": request,
                "response": build_frontier_response(request),
            }
        )

    out = HERE / "model-responses.json"
    out.write_text(json.dumps(fixtures, indent=1, sort_keys=True) + "\n")
    print(
        f"Wrote {len(fixtures['baseline'])} baseline and "
        f"{len(fixtures['frontier'])} frontier responses to {out}"
    )


if __name__ == "__main__":
    main()
