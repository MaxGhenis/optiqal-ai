"""Contract tests for the public web frontier bridge."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PYTHON_DIR = Path("/Users/maxghenis/optiqal-ai/python")
SCRIPT_PATH = PYTHON_DIR / "scripts" / "web_frontier.py"


def run_web_frontier(payload: dict) -> dict:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
        cwd=PYTHON_DIR,
    )
    return json.loads(result.stdout)


def test_web_frontier_emits_branching_sleep_sequence_and_states():
    payload = {
        "profile": {
            "age": 39,
            "sex": "male",
            "weight_kg": 74.8,
            "height_cm": 178.0,
            "smoker": False,
            "has_diabetes": False,
            "has_hypertension": False,
            "activity_level": "active",
            "sleep_hours_per_night": 7.0,
        },
        "sleep_metrics": {
            "duration_hours": 6.8,
            "breathing_score": 0.78,
            "spo2": 95.1,
            "snore_pct": 3.2,
        },
        "n_simulations": 500,
    }

    response = run_web_frontier(payload)

    assert response["decision_sequence"][-1] == {
        "step": 3,
        "id": "rx_after_apap_if_needed",
        "label": "Only compare insomnia Rx options after primary airway treatment if sleep maintenance is still a problem.",
        "preferred_state_id": "rx_after_apap_if_needed",
        "alternative_state_id": "rx_after_oral_appliance_if_needed",
    }

    state_ids = [state["id"] for state in response["decision_states"]]
    assert state_ids == [
        "conservative_airway_support",
        "primary_osa_therapy_choice",
        "rx_after_apap_if_needed",
        "rx_after_oral_appliance_if_needed",
    ]

    branching_state = response["decision_states"][-1]
    assert branching_state["kind"] == "choice"
    assert branching_state["best_biology_option_id"] is not None
