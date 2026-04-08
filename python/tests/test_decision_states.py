"""Tests for stateful and sequence-aware decision helpers."""

from optiqal.decision_states import (
    build_public_sleep_decision_sequence,
    build_public_sleep_decision_specs,
    ChoiceOptionSpec,
    ChoiceStateSpec,
    DecisionSequenceStepSpec,
    FrontierStateSpec,
    evaluate_choice_set,
    evaluate_decision_states,
    summarize_stack_from_qalys,
)
from optiqal.report import serialize_decision_sequence


def test_summarize_stack_includes_interaction_penalty():
    def penalty(item_ids):
        return -0.01 if set(item_ids) == {"a", "b"} else 0.0

    summary = summarize_stack_from_qalys(
        ["a", "b"],
        {"a": 0.05, "b": 0.04},
        {"a": 100, "b": 200},
        stack_interaction_penalty_fn=penalty,
    )

    assert summary["base_qaly"] == 0.09
    assert summary["interaction_penalty_qaly"] == -0.01
    assert summary["adjusted_qaly"] == 0.08
    assert summary["total_annual_cost"] == 300


def test_evaluate_choice_set_compares_options_from_same_base_state():
    def penalty(item_ids):
        item_set = set(item_ids)
        if item_set == {"base", "good"}:
            return -0.005
        if item_set == {"base", "bad"}:
            return -0.02
        return 0.0

    result = evaluate_choice_set(
        base_item_ids=["base"],
        options={
            "none": [],
            "good": ["good"],
            "bad": ["bad"],
        },
        labels={
            "none": "No add-on",
            "good": "Good option",
            "bad": "Bad option",
        },
        single_qalys={"base": 0.10, "good": 0.04, "bad": 0.05},
        annual_costs={"base": 100, "good": 200, "bad": 100},
        stack_interaction_penalty_fn=penalty,
    )

    assert result["baseline"]["adjusted_qaly"] == 0.1
    assert [row["id"] for row in result["options"]] == ["good", "bad", "none"]
    assert result["options"][0]["marginal_qaly"] == 0.035
    assert result["options"][1]["marginal_qaly"] == 0.03
    assert result["options"][2]["marginal_qaly"] == 0.0


def test_evaluate_decision_states_supports_declarative_frontier_and_choice_specs():
    raw_states = evaluate_decision_states(
        [
            FrontierStateSpec(
                id="frontier",
                label="Frontier",
                description="Next adds",
                base_item_ids=["base"],
                max_interventions=1,
            ),
            ChoiceStateSpec(
                id="choice",
                label="Choice",
                description="Pick one",
                base_item_ids=["base"],
                options=[
                    ChoiceOptionSpec(id="none", label="No add-on", added_item_ids=[]),
                    ChoiceOptionSpec(id="good", label="Good option", added_item_ids=["good"]),
                ],
            ),
        ],
        single_qalys={"base": 0.10, "good": 0.04, "extra": 0.02},
        annual_costs={"base": 100, "good": 200, "extra": 50},
        cost_values={"base": 1000, "good": 2000, "extra": 500},
        horizon_years=10,
    )

    assert raw_states["frontier"]["kind"] == "frontier"
    assert raw_states["frontier"]["label"] == "Frontier"
    assert raw_states["frontier"]["evaluation"]["baseline"]["adjusted_qaly"] == 0.1
    assert raw_states["choice"]["kind"] == "choice"
    assert raw_states["choice"]["description"] == "Pick one"
    assert raw_states["choice"]["evaluation"]["options"][0]["id"] == "good"


def test_serialize_decision_sequence_preserves_state_links():
    rows = serialize_decision_sequence(
        [
            DecisionSequenceStepSpec(
                step=1,
                id="first",
                label="First step",
                state_id="choice",
            ),
            DecisionSequenceStepSpec(
                step=2,
                id="second",
                label="Second step",
                preferred_state_id="preferred",
                alternative_state_id="alternative",
            ),
        ]
    )

    assert rows == [
        {
            "step": 1,
            "id": "first",
            "label": "First step",
            "state_id": "choice",
        },
        {
            "step": 2,
            "id": "second",
            "label": "Second step",
            "preferred_state_id": "preferred",
            "alternative_state_id": "alternative",
        },
    ]


def test_public_sleep_helpers_return_expected_branching_specs():
    specs = build_public_sleep_decision_specs()
    sequence = build_public_sleep_decision_sequence()

    assert [spec.id for spec in specs] == [
        "conservative_airway_support",
        "primary_osa_therapy_choice",
        "rx_after_apap_if_needed",
        "rx_after_oral_appliance_if_needed",
    ]
    assert sequence[-1].preferred_state_id == "rx_after_apap_if_needed"
    assert sequence[-1].alternative_state_id == "rx_after_oral_appliance_if_needed"


def test_public_sleep_helpers_can_build_support_only_specs():
    specs = build_public_sleep_decision_specs(include_therapy=False)
    sequence = build_public_sleep_decision_sequence(include_therapy=False)

    assert [spec.id for spec in specs] == ["conservative_airway_support"]
    assert sequence == [
        DecisionSequenceStepSpec(
            step=1,
            id="conservative_airway_support",
            label="Start with low-friction airway support if the phenotype looks airway-heavy.",
            state_id="conservative_airway_support",
        )
    ]
