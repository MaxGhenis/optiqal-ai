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
            "airway_response_signal": 0.4,
        },
        "n_simulations": 500,
    }

    response = run_web_frontier(payload)

    assert any(lane["id"] == "consumer_public" for lane in response["public_policy"]["lanes"])
    assert any(condition["id"] == "airway_signal" for condition in response["public_policy"]["conditions"])
    assert any(condition["id"] == "osa_therapy_signal" for condition in response["public_policy"]["conditions"])
    assert any(condition["id"] == "nasal_dryness_signal" for condition in response["public_policy"]["conditions"])
    airway_condition = next(
        condition for condition in response["public_policy"]["conditions"] if condition["id"] == "airway_signal"
    )
    assert airway_condition["evaluation_kind"] == "sleep_any_threshold"
    assert airway_condition["score_threshold"] is None
    assert any(rule["signal"] == "sleep_breathing_burden" for rule in airway_condition["thresholds"])
    policy_items = {item["id"]: item for item in response["public_policy"]["items"]}
    assert policy_items["apap_nightly"]["lane"] == "conditional_public"
    assert policy_items["apap_nightly"]["condition"] == "osa_therapy_signal"
    assert policy_items["humidifier_nightly"]["condition"] == "nasal_dryness_signal"
    assert policy_items["mouth_tape_nightly"]["lane"] == "personal_only"
    assert policy_items["hiit_2x_week"]["lane"] == "consumer_public"

    assert [step["id"] for step in response["decision_sequence"]] == [
        "conservative_airway_support",
        "primary_osa_therapy_choice",
    ]

    state_ids = [state["id"] for state in response["decision_states"]]
    assert state_ids == [
        "conservative_airway_support",
        "primary_osa_therapy_choice",
    ]
    assert "rx_after_apap_if_needed" not in state_ids
    assert "rx_after_oral_appliance_if_needed" not in state_ids

    branching_state = response["decision_states"][-1]
    assert branching_state["kind"] == "choice"
    assert branching_state["best_biology_option_id"] is not None
    exposed_option_item_ids = {
        item_id
        for state in response["decision_states"]
        if state["kind"] == "choice"
        for option in state["options"]
        for item_id in option["added_item_ids"]
    }
    assert exposed_option_item_ids.isdisjoint({
        "trazodone_50mg",
        "doxepin_3mg",
        "daridorexant_25mg",
        "lemborexant_5mg",
        "suvorexant_10mg",
    })


def test_web_frontier_can_emit_support_only_sleep_pathway():
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
            "sleep_hours_per_night": 6.8,
        },
        "sleep_metrics": {
            "duration_hours": 6.8,
            "breathing_score": 0.76,
            "spo2": 95.7,
            "snore_pct": 0.8,
            "airway_response_signal": 0.06,
        },
        "n_simulations": 500,
    }

    response = run_web_frontier(payload)

    assert [step["id"] for step in response["decision_sequence"]] == ["conservative_airway_support"]
    assert [state["id"] for state in response["decision_states"]] == ["conservative_airway_support"]
    frontier_ids = [step["added_intervention"] for step in response["frontier"]]
    assert "head_elevation_nightly" in frontier_ids
    assert "nasacort_nightly" in frontier_ids
    assert "apap_nightly" not in frontier_ids
    assert "oral_appliance_custom" not in frontier_ids
    assert "humidifier_nightly" not in frontier_ids
    assert "mouth_tape_nightly" not in frontier_ids


def test_web_frontier_can_offer_humidifier_when_nasal_dryness_signal_is_strong():
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
            "sleep_hours_per_night": 6.8,
        },
        "sleep_metrics": {
            "duration_hours": 6.8,
            "breathing_score": 0.78,
            "spo2": 95.1,
            "snore_pct": 3.2,
            "airway_response_signal": 0.4,
        },
        "n_simulations": 500,
    }

    response = run_web_frontier(payload)

    support_state = next(
        state for state in response["decision_states"] if state["id"] == "conservative_airway_support"
    )
    option_ids = {option["id"] for option in support_state["options"]}
    assert "humidifier_nightly" in option_ids


def test_frontier_ranker_receives_hazard_aware_combination(monkeypatch):
    """The deployed /frontier path must pass the multiplicative-hazard combiner
    to the ranker (not silently fall back to additive QALY summing).
    """
    import optiqal.web_api as web_api

    captured: dict = {}
    original = web_api.rank_interventions_by_marginal_cost_per_qaly

    def spy(*args, **kwargs):
        captured.update(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(
        web_api, "rank_interventions_by_marginal_cost_per_qaly", spy
    )

    web_api.build_frontier_response(
        {
            "profile": {
                "age": 58,
                "sex": "male",
                "weight_kg": 104.0,
                "height_cm": 172.0,
                "smoker": False,
                "has_diabetes": False,
                "has_hypertension": True,
                "activity_level": "sedentary",
                "sleep_hours_per_night": 6.5,
            },
            "n_simulations": 400,
        }
    )

    assert captured.get("item_mortality_hrs"), "ranker did not receive item HRs"
    fn = captured.get("mortality_qaly_fn")
    assert fn is not None, "ranker did not receive a mortality_qaly_fn"
    # The combiner integrates a joint hazard once, so two HR-0.7 effects yield
    # strictly less than twice one HR-0.7 effect (no shared-survival double-count).
    assert fn(0.7 * 0.7) < 2 * fn(0.7)


def test_web_frontier_items_carry_confidence_intervals():
    """Every ranked item must expose an 80% interval, not just a point estimate.

    The engine runs Monte Carlo draws but historically collapsed them to a
    single number; the UI cannot show uncertainty without these fields.
    """
    payload = {
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
        },
        "n_simulations": 800,
    }

    response = run_web_frontier(payload)
    items = response["items"]
    assert items, "expected ranked items"

    for item in items:
        qaly_ci = item.get("net_qaly_ci")
        days_ci = item.get("net_days_ci")
        assert isinstance(qaly_ci, list) and len(qaly_ci) == 2, (
            f"{item['id']} missing net_qaly_ci"
        )
        assert isinstance(days_ci, list) and len(days_ci) == 2, (
            f"{item['id']} missing net_days_ci"
        )
        assert qaly_ci[0] <= qaly_ci[1], f"{item['id']} net_qaly_ci unordered: {qaly_ci}"
        assert days_ci[0] <= days_ci[1], f"{item['id']} net_days_ci unordered: {days_ci}"
        # days interval is the QALY interval rescaled to days
        assert days_ci[0] == round(qaly_ci[0] * 365.25, 1)
        assert days_ci[1] == round(qaly_ci[1] * 365.25, 1)
