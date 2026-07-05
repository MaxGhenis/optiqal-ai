"""Contract and sanity regressions for the public baseline bridge."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PYTHON_DIR = Path(__file__).resolve().parent.parent
SCRIPT_PATH = PYTHON_DIR / "scripts" / "web_baseline.py"


def run_web_baseline(payload: dict) -> dict:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
        cwd=PYTHON_DIR,
    )
    return json.loads(result.stdout)


def test_web_baseline_activity_changes_are_monotonic_and_bounded_for_healthy_profile():
    def run(activity_level: str) -> dict:
        return run_web_baseline(
            {
                "profile": {
                    "age": 35,
                    "sex": "female",
                    "weight_kg": 65.0,
                    "height_cm": 165.0,
                    "smoker": False,
                    "has_diabetes": False,
                    "has_hypertension": False,
                    "activity_level": activity_level,
                    "sleep_hours_per_night": 7.0,
                }
            }
        )

    light = run("light")
    moderate = run("moderate")
    active = run("active")

    light_expectancy = light["point_estimate"]["remaining_life_expectancy"]
    moderate_expectancy = moderate["point_estimate"]["remaining_life_expectancy"]
    active_expectancy = active["point_estimate"]["remaining_life_expectancy"]

    light_death_age = light["point_estimate"]["expected_death_age"]
    moderate_death_age = moderate["point_estimate"]["expected_death_age"]
    active_death_age = active["point_estimate"]["expected_death_age"]

    assert 88.0 <= light_death_age <= 96.0
    assert 88.0 <= moderate_death_age <= 97.0
    assert 88.0 <= active_death_age <= 98.0

    assert light_expectancy < moderate_expectancy < active_expectancy
    assert light_death_age < moderate_death_age < active_death_age

    # Small adjacent activity changes should not swing life expectancy by decades.
    assert moderate_expectancy - light_expectancy < 4.0
    assert active_expectancy - moderate_expectancy < 4.0
    assert active_expectancy - light_expectancy < 6.0
    assert active_death_age - light_death_age < 6.0


def test_web_baseline_point_estimate_carries_prediction_intervals():
    """Baseline must surface intervals from the age-at-death distribution, not
    just point estimates, so the predict UI can show uncertainty."""
    response = run_web_baseline(
        {
            "profile": {
                "age": 50,
                "sex": "male",
                "weight_kg": 80.0,
                "height_cm": 178.0,
                "smoker": False,
                "has_diabetes": False,
                "has_hypertension": False,
                "activity_level": "light",
                "sleep_hours_per_night": 7.0,
            }
        }
    )
    pe = response["point_estimate"]
    for field, point in (
        ("remaining_life_expectancy_ci", pe["remaining_life_expectancy"]),
        ("remaining_qalys_ci", pe["remaining_qalys"]),
    ):
        ci = pe.get(field)
        assert isinstance(ci, list) and len(ci) == 2, f"missing {field}"
        assert ci[0] <= ci[1], f"{field} unordered: {ci}"
        assert ci[0] <= point <= ci[1], f"{field} {ci} does not bracket point {point}"
