"""Benchmark tests for public-frontier plausibility harness."""

from __future__ import annotations

from optiqal.public_frontier_benchmark import (
    CANONICAL_PUBLIC_FRONTIER_SCENARIOS,
    evaluate_public_frontier_case,
    generate_stratified_public_frontier_scenarios,
    render_public_frontier_judge_prompt,
    run_public_frontier_benchmark,
)


def test_canonical_public_frontier_benchmark_cases_all_pass_current_policy():
    report = run_public_frontier_benchmark()

    assert report.total_failures == 0
    assert report.score == 1.0
    assert all(case.passed for case in report.case_results)


def test_generated_stratified_cases_cover_expected_strata():
    generated = generate_stratified_public_frontier_scenarios(seed=7, cases_per_stratum=2)

    assert len(generated) == 10
    tags = {tag for scenario in generated for tag in scenario.tags}
    assert "healthy_public" in tags
    assert "cardiometabolic_public" in tags
    assert "glp1_public" in tags
    assert "airway_sleep" in tags
    assert "duration_only_sleep" in tags


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
