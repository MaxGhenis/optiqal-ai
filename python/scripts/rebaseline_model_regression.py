"""Regenerate the golden fixture for tests/test_model_regression.py.

Run ONLY after an intentional model change, and commit the resulting fixture
diff together with the change that caused it (the diff is the reviewable
record of what moved). Running this casually to silence a red test defeats
the entire point of a golden regression fixture.

Usage:
    cd python && uv run --all-extras python scripts/rebaseline_model_regression.py

Bounds policy: each tracked scalar gets a window of +/-15% around the newly
computed value, widened to an absolute half-width of 0.0015 QALY near zero so
Monte Carlo jitter cannot flap the suite. Ordering prefixes pin the top five
options (three for short lists), matching the prior fixture's intent.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_PYTHON = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_PYTHON))
sys.path.insert(0, str(REPO_PYTHON / "tests"))

from test_model_regression import (  # noqa: E402
    SUBSET_IDS,
    canonical_confirmed_mild_osa_estimate,
    canonical_wearable_sleep_estimate,
    run_subset_analysis,
    subset_entries,
)

from optiqal import (  # noqa: E402
    build_public_sleep_decision_specs,
    build_stack_interaction_penalty_fn,
    evaluate_decision_states,
    serialize_decision_state_evaluations,
)

FIXTURE_PATH = REPO_PYTHON / "tests" / "fixtures" / "model_regression.json"


def bounds(value: float) -> list[float]:
    half = max(abs(value) * 0.15, 0.0015)
    return [round(value - half, 4), round(value + half, 4)]


def subset_fixture(sleep_estimate, tracked: dict[str, list[str]]) -> dict:
    result = run_subset_analysis(sleep_estimate)
    ordered = [
        row["id"]
        for row in sorted(
            result.item_results, key=lambda row: row["total_qaly"], reverse=True
        )
    ]
    items = {}
    for item_id, fields in tracked.items():
        row = result.item_results_by_id[item_id]
        items[item_id] = {field: bounds(float(row[field])) for field in fields}
    return {"ordered_ids_prefix": ordered[:5], "items": items}


def decision_states_fixture() -> dict:
    analysis = run_subset_analysis(canonical_confirmed_mild_osa_estimate())
    single_qalys = {
        item_id: row["total_qaly"]
        for item_id, row in analysis.item_results_by_id.items()
    }
    annual_costs = {
        item_id: row["annual_cost"]
        for item_id, row in analysis.item_results_by_id.items()
    }
    cost_values = {
        item_id: row["total_cost"]
        for item_id, row in analysis.item_results_by_id.items()
    }
    entries = subset_entries()
    exclusive_groups = {
        item_id: entry.exclusive_group
        for item_id, entry in entries.items()
        if entry.exclusive_group
    }
    stack_penalty_fn = build_stack_interaction_penalty_fn(
        entries,
        analysis.config.profile,
        analysis.config.qaly_discount_rate,
        item_qalys=single_qalys,
        benefit_tag_multipliers=analysis.config.sleep_overlap_multipliers,
    )
    serialized = serialize_decision_state_evaluations(
        evaluate_decision_states(
            build_public_sleep_decision_specs(),
            single_qalys=single_qalys,
            annual_costs=annual_costs,
            cost_values=cost_values,
            horizon_years=analysis.config.horizon_years,
            stack_interaction_penalty_fn=stack_penalty_fn,
            total_cost_value_fn=lambda item_ids: sum(
                cost_values[item_id] for item_id in item_ids
            ),
            exclusive_groups=exclusive_groups,
        ),
        item_name_by_id={item_id: entry.name for item_id, entry in entries.items()},
    )

    prior = json.loads(FIXTURE_PATH.read_text())[
        "public_sleep_decision_states_confirmed_mild_osa"
    ]
    ordered_prefixes = {}
    ranges: dict[str, dict] = {}
    for state_id in prior["ordered_option_prefix_by_state"]:
        options = serialized[state_id]["options"]
        prefix_len = len(prior["ordered_option_prefix_by_state"][state_id])
        ordered_prefixes[state_id] = [option["id"] for option in options[:prefix_len]]
    for state_id, tracked_options in prior["ranges"].items():
        actual_by_id = {
            option["id"]: option for option in serialized[state_id]["options"]
        }
        ranges[state_id] = {
            option_id: {
                field: bounds(float(actual_by_id[option_id][field]))
                for field in field_ranges
            }
            for option_id, field_ranges in tracked_options.items()
        }
    return {
        "ordered_option_prefix_by_state": ordered_prefixes,
        "ranges": ranges,
    }


def main() -> None:
    prior = json.loads(FIXTURE_PATH.read_text())
    tracked_wearable = {
        item_id: list(fields)
        for item_id, fields in prior["wearable_only_subset"]["items"].items()
    }
    tracked_confirmed = {
        item_id: list(fields)
        for item_id, fields in prior["confirmed_mild_osa_subset"]["items"].items()
    }
    assert set(tracked_wearable) <= set(SUBSET_IDS)

    fixture = {
        "wearable_only_subset": subset_fixture(
            canonical_wearable_sleep_estimate(), tracked_wearable
        ),
        "confirmed_mild_osa_subset": subset_fixture(
            canonical_confirmed_mild_osa_estimate(), tracked_confirmed
        ),
        "public_sleep_decision_states_confirmed_mild_osa": decision_states_fixture(),
    }
    FIXTURE_PATH.write_text(json.dumps(fixture, indent=1) + "\n")
    print(f"Rebaselined {FIXTURE_PATH}")
    for scenario in ("wearable_only_subset", "confirmed_mild_osa_subset"):
        print(f"  {scenario}: {fixture[scenario]['ordered_ids_prefix']}")


if __name__ == "__main__":
    main()
