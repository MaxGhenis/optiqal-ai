"""
Optiqal - Bayesian QALY Estimation for Lifestyle Interventions

This package provides rigorous, evidence-based QALY calculations with:
- Bayesian MCMC inference using PyMC
- CDC life tables for survival modeling
- Pathway decomposition (CVD, cancer, other)
- Confounding adjustment with calibrated priors
- Full uncertainty quantification

Usage:
    from optiqal import Intervention, LifecycleModel, run_mcmc

    # Load intervention from YAML
    walking = Intervention.from_yaml("walking_30min_daily.yaml")

    # Quick Monte Carlo estimate
    result = walking.simulate(age=40, sex="male")
    print(f"QALY gain: {result.median:.2f} (95% CI: {result.ci95})")

    # Full Bayesian MCMC
    trace = run_mcmc(walking, n_samples=2000, chains=4)
    print(f"Posterior mean: {trace.posterior['qaly_gain'].mean():.3f}")
"""

__version__ = "0.1.0"

from .intervention import HarmEffect, InteractionRule, Intervention
from .lifecycle import LifecycleModel, CDC_LIFE_TABLE, CAUSE_FRACTIONS
from .confounding import (
    ConfoundingPrior,
    CATEGORY_PRIORS,
    hr_to_lognormal_params,
    publication_bias_correct,
)
from .simulate import simulate_qaly, simulate_qaly_profile, SimulationResult
from .profile import Profile, generate_all_profiles, get_baseline_mortality_multiplier
from .precompute import (
    precompute_intervention,
    precompute_intervention_profiles,
    PrecomputedResult,
    ProfilePrecomputedResult,
)
from .combination import (
    combine_intervention_effects,
    estimate_combined_qaly_from_singles,
    find_optimal_portfolio,
    find_optimal_portfolio_from_qalys,
    find_optimal_portfolio_with_costs,
    rank_interventions_by_marginal_cost_per_qaly,
    CombinedEffect,
    OVERLAP_MATRIX,
)
from .catalog import (
    CatalogEntry,
    CATALOG,
    PublicPolicy,
    build_public_policy_spec,
    get_default_public_policy,
    get_catalog,
    load_public_policy_override,
    simulate_catalog,
    has_meaningful_public_airway_signal,
    has_meaningful_public_nasal_dryness_signal,
    has_meaningful_public_osa_therapy_signal,
    public_recommendation_lane,
    public_display_category,
    public_display_name,
    is_publicly_rankable,
    public_rankability_reason,
)
from .bundles import Bundle, BUNDLES, recommend_bundles
from .analyzer import AnalysisConfig, AnalysisResult, Decision, analyze
from .report import (
    format_full_report,
    round_cost_per_qaly,
    serialize_bundle_recommendations,
    serialize_choice_evaluation,
    serialize_decision_state_evaluations,
    serialize_decision_sequence,
    serialize_frontier_evaluation,
    serialize_item_results,
    serialize_ranked_steps,
)
from .sleep import (
    SleepMetrics,
    SleepStudyResult,
    SleepBurdenEstimate,
    apply_sleep_study,
    estimate_sleep_burden,
    sleep_utility_lineage,
    sleep_baseline_mortality_multiplier,
    sleep_intervention_mortality_hr_multiplier,
)
from .protocol_personalization import (
    apply_protocol_spec,
    build_protocol_specs,
    load_protocol_baseline,
    load_protocol_context,
    load_protocol_items,
    load_protocol_profile,
    protocol_metadata_from_specs,
    protocol_sleep_estimate_from_baseline,
)
from .stack_interactions import (
    build_stack_interaction_penalty_fn,
    expected_stack_interaction_qaly,
)
from .reference_case import (
    DEFAULT_REFERENCE_CASE,
    NICE_REFERENCE_CASE,
    US_SECOND_PANEL_REFERENCE_CASE,
    MorbidityEffect,
    ReferenceCase,
    UtilityWeight,
    PUBLIC_HEALTH_UTILITY_WEIGHTS,
    discounted_years,
    get_public_health_utility_weight,
    morbidity_qaly,
    morbidity_qaly_breakdown,
    utility_reference_case_status,
)
from .decision_states import (
    build_public_sleep_decision_sequence,
    build_public_sleep_decision_specs,
    ChoiceOptionSpec,
    DecisionSequenceStepSpec,
    ChoiceStateSpec,
    FrontierStateSpec,
    evaluate_decision_states,
    ordered_unique,
    evaluate_frontier_state,
    summarize_stack_from_qalys,
    evaluate_choice_set,
)
from .public_frontier_benchmark import (
    CANONICAL_PUBLIC_FRONTIER_SCENARIOS,
    BENCHMARK_SCENARIOS_PATH,
    JUDGE_PROMPT_TEMPLATE_PATH,
    PublicFrontierBenchmarkRules,
    PublicFrontierBenchmarkScenario,
    PublicFrontierBenchmarkFailure,
    PublicFrontierBenchmarkCaseResult,
    PublicFrontierBenchmarkReport,
    evaluate_public_frontier_case,
    generate_stratified_public_frontier_scenarios,
    render_public_frontier_judge_prompt,
    run_public_frontier_benchmark,
)

__all__ = [
    "Intervention",
    "HarmEffect",
    "InteractionRule",
    "LifecycleModel",
    "CDC_LIFE_TABLE",
    "CAUSE_FRACTIONS",
    "ConfoundingPrior",
    "CATEGORY_PRIORS",
    "simulate_qaly",
    "simulate_qaly_profile",
    "SimulationResult",
    "Profile",
    "generate_all_profiles",
    "get_baseline_mortality_multiplier",
    "precompute_intervention",
    "precompute_intervention_profiles",
    "PrecomputedResult",
    "ProfilePrecomputedResult",
    "combine_intervention_effects",
    "estimate_combined_qaly_from_singles",
    "find_optimal_portfolio",
    "find_optimal_portfolio_from_qalys",
    "CombinedEffect",
    "OVERLAP_MATRIX",
    "publication_bias_correct",
    "find_optimal_portfolio_with_costs",
    "rank_interventions_by_marginal_cost_per_qaly",
    "CatalogEntry",
    "CATALOG",
    "PublicPolicy",
    "build_public_policy_spec",
    "get_default_public_policy",
    "get_catalog",
    "load_public_policy_override",
    "simulate_catalog",
    "has_meaningful_public_airway_signal",
    "has_meaningful_public_nasal_dryness_signal",
    "has_meaningful_public_osa_therapy_signal",
    "public_recommendation_lane",
    "public_display_category",
    "public_display_name",
    "is_publicly_rankable",
    "public_rankability_reason",
    "Bundle",
    "BUNDLES",
    "recommend_bundles",
    "AnalysisConfig",
    "AnalysisResult",
    "Decision",
    "analyze",
    "format_full_report",
    "round_cost_per_qaly",
    "serialize_bundle_recommendations",
    "serialize_choice_evaluation",
    "serialize_decision_state_evaluations",
    "serialize_decision_sequence",
    "serialize_frontier_evaluation",
    "serialize_item_results",
    "serialize_ranked_steps",
    "SleepMetrics",
    "SleepStudyResult",
    "SleepBurdenEstimate",
    "apply_sleep_study",
    "estimate_sleep_burden",
    "sleep_utility_lineage",
    "sleep_baseline_mortality_multiplier",
    "sleep_intervention_mortality_hr_multiplier",
    "apply_protocol_spec",
    "build_protocol_specs",
    "load_protocol_baseline",
    "load_protocol_context",
    "load_protocol_items",
    "load_protocol_profile",
    "protocol_metadata_from_specs",
    "protocol_sleep_estimate_from_baseline",
    "build_stack_interaction_penalty_fn",
    "expected_stack_interaction_qaly",
    "DEFAULT_REFERENCE_CASE",
    "NICE_REFERENCE_CASE",
    "US_SECOND_PANEL_REFERENCE_CASE",
    "MorbidityEffect",
    "ReferenceCase",
    "UtilityWeight",
    "PUBLIC_HEALTH_UTILITY_WEIGHTS",
    "discounted_years",
    "get_public_health_utility_weight",
    "morbidity_qaly",
    "morbidity_qaly_breakdown",
    "utility_reference_case_status",
    "ChoiceOptionSpec",
    "build_public_sleep_decision_sequence",
    "build_public_sleep_decision_specs",
    "DecisionSequenceStepSpec",
    "ChoiceStateSpec",
    "FrontierStateSpec",
    "evaluate_decision_states",
    "ordered_unique",
    "evaluate_frontier_state",
    "summarize_stack_from_qalys",
    "evaluate_choice_set",
    "CANONICAL_PUBLIC_FRONTIER_SCENARIOS",
    "BENCHMARK_SCENARIOS_PATH",
    "JUDGE_PROMPT_TEMPLATE_PATH",
    "PublicFrontierBenchmarkRules",
    "PublicFrontierBenchmarkScenario",
    "PublicFrontierBenchmarkFailure",
    "PublicFrontierBenchmarkCaseResult",
    "PublicFrontierBenchmarkReport",
    "evaluate_public_frontier_case",
    "generate_stratified_public_frontier_scenarios",
    "render_public_frontier_judge_prompt",
    "run_public_frontier_benchmark",
]


# Lazy import for Bayesian module (requires optional dependencies)
def run_mcmc(*args, **kwargs):
    """Run MCMC inference. Requires optiqal[bayesian] installation."""
    from .bayesian import run_mcmc as _run_mcmc

    return _run_mcmc(*args, **kwargs)
