"""Benchmark tests for public-frontier plausibility harness."""

from __future__ import annotations

import json

from optiqal import load_public_policy_override
from optiqal.public_frontier_benchmark import (
    CANONICAL_PUBLIC_FRONTIER_SCENARIOS,
    benchmark_report_from_dict,
    benchmark_report_to_dict,
    build_blank_judge_verdict_template,
    build_public_frontier_benchmark_scenarios,
    build_pairwise_judge_packets,
    compute_hybrid_public_frontier_score,
    compute_pairwise_judge_score,
    evaluate_public_frontier_case,
    generate_stratified_public_frontier_scenarios,
    parse_public_frontier_judge_verdicts,
    render_public_frontier_judge_prompt,
    run_public_frontier_benchmark,
)


def test_canonical_public_frontier_benchmark_exposes_current_policy_gaps():
    report = run_public_frontier_benchmark()

    assert report.total_failures > 0
    assert report.score < 1.0
    by_id = {case.scenario_id: case for case in report.case_results}
    assert any(failure.rule == "banned_visible_ids" for failure in by_id["mild_metabolic_50m_public"].failures)
    assert any(failure.rule == "banned_visible_ids" for failure in by_id["obesity_glp1_52f_public"].failures)


def test_generated_stratified_cases_cover_expected_strata():
    generated = generate_stratified_public_frontier_scenarios(seed=7, cases_per_stratum=2)

    assert len(generated) == 14
    tags = {tag for scenario in generated for tag in scenario.tags}
    assert "healthy_public" in tags
    assert "cardiometabolic_public" in tags
    assert "glp1_public" in tags
    assert "borderline_metabolic_public" in tags
    assert "obesity_glp1_no_diabetes_public" in tags
    assert "airway_sleep" in tags
    assert "duration_only_sleep" in tags


def test_generated_metabolic_strata_respect_intended_bmi_bands():
    generated = generate_stratified_public_frontier_scenarios(seed=42, cases_per_stratum=8)

    for scenario in generated:
        profile = scenario.payload["profile"]
        bmi = profile["weight_kg"] / ((profile["height_cm"] / 100) ** 2)
        if "cardiometabolic_public" in scenario.tags:
            assert bmi >= 30
        if "borderline_metabolic_public" in scenario.tags:
            assert 25 <= bmi < 30


def test_multi_seed_benchmark_builder_prefixes_generated_ids_uniquely():
    scenarios = build_public_frontier_benchmark_scenarios(
        cases_per_stratum=1,
        seed=10,
        seed_count=2,
    )

    ids = [scenario.id for scenario in scenarios]
    assert "healthy_35f_public" in ids
    assert "seed10__healthy_public_1" in ids
    assert "seed11__healthy_public_1" in ids
    assert len(ids) == len(set(ids))


def test_judge_prompt_includes_scenario_rules_and_candidate_summaries():
    scenario = CANONICAL_PUBLIC_FRONTIER_SCENARIOS[0]
    case_result = evaluate_public_frontier_case(scenario)
    prompt = render_public_frontier_judge_prompt(
        scenario,
        case_result.response,
        case_result.response,
    )

    assert scenario.id in prompt
    assert "frontier_top_10" in prompt
    assert '"winner": "A" | "B" | "tie"' in prompt
    assert "required_top_any_of" in prompt


def test_benchmark_report_round_trips_for_pairwise_review():
    report = run_public_frontier_benchmark()
    round_tripped = benchmark_report_from_dict(
        benchmark_report_to_dict(report, include_responses=True)
    )

    assert round_tripped.score == report.score
    assert round_tripped.case_results[0].scenario_id == report.case_results[0].scenario_id
    assert round_tripped.case_results[0].response["meta"]["profile"] == report.case_results[0].response["meta"]["profile"]


def test_pairwise_packets_and_hybrid_score_work_with_offline_verdicts():
    report = run_public_frontier_benchmark()
    packets = build_pairwise_judge_packets(report, report)

    assert len(packets) == len(CANONICAL_PUBLIC_FRONTIER_SCENARIOS)
    assert packets[0].scenario_id == CANONICAL_PUBLIC_FRONTIER_SCENARIOS[0].id

    verdicts = parse_public_frontier_judge_verdicts(
        [
            {
                "scenario_id": packets[0].scenario_id,
                "winner": "A",
                "confidence": 0.9,
                "summary": "A is safer.",
                "safety_issues": [],
                "ranking_issues": [],
                "best_aspects": {"A": ["safer"], "B": ["none"]},
            },
            {
                "scenario_id": packets[1].scenario_id,
                "winner": "tie",
                "confidence": 0.6,
                "summary": "Roughly equal.",
                "safety_issues": [],
                "ranking_issues": [],
                "best_aspects": {"A": ["stable"], "B": ["stable"]},
            },
        ]
    )
    judge_score = compute_pairwise_judge_score(verdicts)

    assert 0.7 < judge_score < 0.9
    assert compute_hybrid_public_frontier_score(
        hard_score=1.0,
        judge_score=judge_score,
        judge_weight=0.2,
    ) > 0.9
    assert compute_hybrid_public_frontier_score(
        hard_score=0.8,
        judge_score=judge_score,
        judge_weight=0.2,
    ) == 0.8


def test_pairwise_packet_modes_focus_on_changed_representative_cases(tmp_path):
    scenarios = build_public_frontier_benchmark_scenarios(
        cases_per_stratum=2,
        seed=0,
        seed_count=1,
    )
    candidate_path = tmp_path / "candidate-policy.json"
    candidate_path.write_text(json.dumps({
        "conditions": {
            "metabolic_signal": {"profile_score_threshold": 5},
        },
    }, indent=2))

    incumbent = run_public_frontier_benchmark(scenarios)
    candidate = run_public_frontier_benchmark(
        scenarios,
        public_policy=load_public_policy_override(candidate_path),
    )

    all_packets = build_pairwise_judge_packets(candidate, incumbent, scenarios=scenarios)
    changed_packets = build_pairwise_judge_packets(
        candidate,
        incumbent,
        scenarios=scenarios,
        mode="changed",
    )
    unique_packets = build_pairwise_judge_packets(
        candidate,
        incumbent,
        scenarios=scenarios,
        mode="changed_unique",
    )

    assert len(all_packets) == len(scenarios)
    assert len(changed_packets) < len(all_packets)
    assert len(unique_packets) < len(changed_packets)
    assert any(packet.scenario_id == "high_risk_58m_public" for packet in unique_packets)
    assert any(packet.scenario_id == "obesity_glp1_52f_public" for packet in unique_packets)


def test_blank_judge_verdict_template_matches_packets():
    report = run_public_frontier_benchmark()
    packets = build_pairwise_judge_packets(report, report)
    template = build_blank_judge_verdict_template(packets)

    assert len(template) == len(packets)
    assert template[0]["scenario_id"] == packets[0].scenario_id
    assert template[0]["winner"] == "A|B|tie"
    assert template[0]["best_aspects"] == {"A": [], "B": []}


def test_candidate_policy_override_changes_benchmark_outcome(tmp_path):
    candidate_path = tmp_path / "candidate-policy.json"
    candidate_path.write_text(json.dumps({
        "items": {
            "hiit_2x_week": {"public_lane": "personal_only"},
            "strength_maintenance": {"public_lane": "personal_only"},
        }
    }, indent=2))

    report = run_public_frontier_benchmark(
        public_policy=load_public_policy_override(candidate_path)
    )
    healthy_case = next(
        case for case in report.case_results
        if case.scenario_id == "healthy_35f_public"
    )

    assert report.score < 1.0
    assert not healthy_case.passed
    assert any(failure.rule == "required_top_any_of" for failure in healthy_case.failures)


def test_candidate_policy_can_fix_non_diabetic_metformin_leakage(tmp_path):
    candidate_path = tmp_path / "candidate-policy.json"
    candidate_path.write_text(json.dumps({
        "conditions": {
            "metabolic_signal": {"profile_score_threshold": 5},
        },
    }, indent=2))

    incumbent = run_public_frontier_benchmark()
    improved = run_public_frontier_benchmark(
        public_policy=load_public_policy_override(candidate_path)
    )
    by_id = {case.scenario_id: case for case in improved.case_results}

    assert improved.score > incumbent.score
    assert by_id["mild_metabolic_50m_public"].passed
    assert by_id["obesity_glp1_52f_public"].passed
