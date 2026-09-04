"""Regressions for independent simulation streams and null mortality arms."""

from pathlib import Path

import numpy as np
import pytest

from optiqal.analyzer import AnalysisConfig, Decision, analyze
from optiqal.catalog import CATALOG
from optiqal.intervention import Distribution, Intervention, MortalityEffect
from optiqal.lifecycle import QUALITY_WEIGHT_STD
from optiqal.profile import Profile
from optiqal.simulate import (
    simulate_qaly,
    simulate_qaly_profile,
    simulate_qaly_profile_vectorized,
)

INTERVENTIONS_DIR = (
    Path(__file__).resolve().parents[2] / "src" / "lib" / "qaly" / "interventions"
)


@pytest.fixture
def default_profile() -> Profile:
    return Profile(
        age=45,
        sex="male",
        bmi_category="normal",
        smoking_status="never",
        has_diabetes=False,
        has_hypertension=False,
        activity_level="light",
    )


@pytest.fixture
def walking() -> Intervention:
    return Intervention.from_yaml(INTERVENTIONS_DIR / "walking_30min_daily.yaml")


@pytest.mark.parametrize("seed", [42, 1, 7])
def test_quality_and_log_hr_streams_are_independent(walking: Intervention, seed: int):
    """The two normal draws formerly reused the identical standardized values."""
    n_simulations = 20_000
    quality_seed, hr_seed, *_ = np.random.SeedSequence(seed).spawn(4)
    quality_offsets = np.random.default_rng(quality_seed).normal(
        0,
        QUALITY_WEIGHT_STD,
        n_simulations,
    )

    hazard_ratio = walking.mortality.hazard_ratio
    hr_samples = hazard_ratio.sample(n_simulations, np.random.default_rng(hr_seed))
    log_mean, log_sd = hazard_ratio._lognormal_params()

    standardized_quality = quality_offsets / QUALITY_WEIGHT_STD
    standardized_log_hr = (np.log(hr_samples) - log_mean) / log_sd
    correlation = float(np.corrcoef(standardized_quality, standardized_log_hr)[0, 1])

    assert abs(correlation) < 0.05


def test_seeded_vectorized_run_is_bit_reproducible(
    walking: Intervention,
    default_profile: Profile,
):
    first, first_draws = simulate_qaly_profile_vectorized(
        walking,
        default_profile,
        n_simulations=2_000,
        random_state=42,
        return_qaly_gains=True,
    )
    second, second_draws = simulate_qaly_profile_vectorized(
        walking,
        default_profile,
        n_simulations=2_000,
        random_state=42,
        return_qaly_gains=True,
    )

    assert first == second
    assert np.array_equal(first_draws, second_draws)


def test_point_null_hr_is_exactly_zero_on_every_simulator(default_profile: Profile):
    intervention = Intervention(
        id="point_null",
        name="Point null",
        category="other",
        mortality=MortalityEffect(
            hazard_ratio=Distribution(type="point", params={"value": 1.0}),
        ),
    )

    vectorized = simulate_qaly_profile_vectorized(
        intervention,
        default_profile,
        n_simulations=100,
        random_state=42,
    )
    loop = simulate_qaly(
        intervention,
        age=default_profile.age,
        sex=default_profile.sex,
        n_simulations=100,
        random_state=42,
    )
    profile_loop = simulate_qaly_profile(
        intervention,
        default_profile,
        n_simulations=100,
        random_state=42,
    )

    assert vectorized.mean == 0.0
    assert loop.mean == 0.0
    assert profile_loop.mean == 0.0


def test_catalog_null_mortality_is_exact_through_analyzer(default_profile: Profile):
    entry = CATALOG["hiit_2x_week"]
    result = analyze(
        AnalysisConfig(
            profile=default_profile,
            n_simulations=1_000,
            random_state=42,
        ),
        decisions=[
            Decision(
                type="add",
                item_id=entry.id,
                label=f"ADD: {entry.name}",
            )
        ],
        catalog_entries={entry.id: entry},
    )

    assert result.item_results_by_id[entry.id]["mort_qaly"] == 0.0
    assert result.decisions[0]["mort_qaly"] == 0.0


def test_seeded_walking_mean_matches_independent_runs_within_mc_error(
    walking: Intervention,
    default_profile: Profile,
):
    n_simulations = 20_000
    seeded = simulate_qaly_profile_vectorized(
        walking,
        default_profile,
        n_simulations=n_simulations,
        random_state=42,
    )
    unseeded = [
        simulate_qaly_profile_vectorized(
            walking,
            default_profile,
            n_simulations=n_simulations,
        )
        for _ in range(10)
    ]

    unseeded_mean = float(np.mean([result.mean for result in unseeded]))
    seeded_variance = seeded.std**2 / n_simulations
    unseeded_mean_variance = (
        float(np.mean([result.std**2 / n_simulations for result in unseeded])) / 10
    )
    three_standard_errors = 3 * np.sqrt(
        seeded_variance + unseeded_mean_variance
    )

    assert abs(seeded.mean - unseeded_mean) <= three_standard_errors
