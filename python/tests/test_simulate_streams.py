"""Regressions for independent simulation streams and null mortality arms."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union

import numpy as np
import pytest

from optiqal.analyzer import AnalysisConfig, Decision, analyze
from optiqal.catalog import CATALOG
from optiqal.confounding import ConfoundingPrior
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

#: Seeds at which the quality and log-hazard-ratio streams were formerly identical.
INDEPENDENCE_SEEDS = (42, 1, 7)
#: Fixed reference seeds, so the seeded-versus-independent comparison below is
#: reproducible run to run instead of redrawing from the OS entropy pool.
REFERENCE_SEEDS = (101, 102, 103, 104, 105, 106, 107, 108, 109, 110)


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


@dataclass(frozen=True)
class SampleCall:
    """One ``sample`` call the simulator under test actually made."""

    source: Any
    n: int
    random_state: Optional[Union[int, np.random.Generator]]
    values: np.ndarray


@dataclass(frozen=True)
class NormalCall:
    """One ``Generator.normal`` draw the simulator under test actually made."""

    loc: float
    scale: float
    size: Optional[int]
    values: np.ndarray


class SimulatorSpy:
    """Record the draws a real ``simulate_*`` call makes.

    The former version of this test rebuilt ``SeedSequence(seed).spawn(4)`` by
    hand and correlated its own draws, so it never entered the simulator and
    passed against the coupled engine it was meant to guard. This spy records
    what ``Distribution.sample``, ``ConfoundingPrior.sample`` and the
    quality-offset generator receive and return *inside* the simulator, so
    restoring the coupling fails the test.
    """

    def __init__(self) -> None:
        self.distribution_calls: list[SampleCall] = []
        self.confounding_calls: list[SampleCall] = []
        self.normal_calls: list[NormalCall] = []

    def install(self, monkeypatch: pytest.MonkeyPatch) -> "SimulatorSpy":
        self._patch_sample(monkeypatch, Distribution, self.distribution_calls)
        self._patch_sample(monkeypatch, ConfoundingPrior, self.confounding_calls)
        self._patch_default_rng(monkeypatch)
        return self

    def _patch_sample(
        self,
        monkeypatch: pytest.MonkeyPatch,
        owner: type,
        sink: list[SampleCall],
    ) -> None:
        original = owner.sample

        def spy(inner_self, n=1, random_state=None):
            values = original(inner_self, n, random_state)
            sink.append(
                SampleCall(
                    source=inner_self,
                    n=n,
                    random_state=random_state,
                    values=np.asarray(values),
                )
            )
            return values

        monkeypatch.setattr(owner, "sample", spy)

    def _patch_default_rng(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Wrap every generator the engine builds so normal draws are recorded.

        Quality offsets are drawn straight off a generator rather than through a
        ``Distribution``, and the coupled engine drew them off the very generator
        whose seed it then handed to the hazard-ratio sampler. Patching the
        factory therefore observes both arrangements.
        """
        original_default_rng = np.random.default_rng
        sink = self.normal_calls

        class RecordingGenerator(np.random.Generator):
            def normal(self, loc=0.0, scale=1.0, size=None):
                values = super().normal(loc, scale, size)
                sink.append(
                    NormalCall(
                        loc=float(loc),
                        scale=float(scale),
                        size=size,
                        values=np.asarray(values),
                    )
                )
                return values

        def recording_default_rng(seed=None):
            generator = original_default_rng(seed)
            if isinstance(generator, RecordingGenerator):
                return generator
            return RecordingGenerator(generator.bit_generator)

        monkeypatch.setattr(np.random, "default_rng", recording_default_rng)

    def only_call_from(self, sink: list[SampleCall], source: Any) -> SampleCall:
        matches = [call for call in sink if call.source is source]
        assert len(matches) == 1, f"expected exactly one draw from {source!r}"
        return matches[0]

    def only_quality_offsets(self, n_simulations: int) -> np.ndarray:
        matches = [
            call
            for call in self.normal_calls
            if call.loc == 0.0
            and call.scale == QUALITY_WEIGHT_STD
            and call.size == n_simulations
        ]
        assert len(matches) == 1, "expected exactly one quality-offset draw"
        return matches[0].values


def _standardize(values: np.ndarray) -> np.ndarray:
    return (values - values.mean()) / values.std()


@pytest.mark.parametrize("seed", INDEPENDENCE_SEEDS)
def test_simulator_quality_and_log_hr_streams_are_independent(
    walking: Intervention,
    default_profile: Profile,
    monkeypatch: pytest.MonkeyPatch,
    seed: int,
):
    """The simulator's own quality, log-HR and causal draws must not coincide.

    Before stream separation the quality offsets and the hazard-ratio draws both
    came from ``default_rng(random_state)`` on the same seed, so their
    standardized values were identical (correlation 1.000000 at every seed).
    """
    n_simulations = 20_000
    spy = SimulatorSpy().install(monkeypatch)

    simulate_qaly_profile_vectorized(
        walking,
        default_profile,
        n_simulations=n_simulations,
        random_state=seed,
    )

    hazard_ratio = walking.mortality.hazard_ratio
    hr_call = spy.only_call_from(spy.distribution_calls, hazard_ratio)
    confounding_call = spy.only_call_from(
        spy.confounding_calls, walking.confounding_prior
    )
    quality_offsets = spy.only_quality_offsets(n_simulations)

    assert isinstance(hr_call.random_state, np.random.Generator), (
        "the hazard-ratio draw must receive its own Generator, not a raw seed"
    )
    assert isinstance(confounding_call.random_state, np.random.Generator), (
        "the causal-fraction draw must receive its own Generator, not a raw seed"
    )
    assert hr_call.n == n_simulations
    assert confounding_call.n == n_simulations
    assert quality_offsets.shape == (n_simulations,)

    log_mean, log_sd = hazard_ratio._lognormal_params()
    standardized_quality = quality_offsets / QUALITY_WEIGHT_STD
    standardized_log_hr = (np.log(hr_call.values) - log_mean) / log_sd
    standardized_causal = _standardize(confounding_call.values)

    quality_versus_log_hr = float(
        np.corrcoef(standardized_quality, standardized_log_hr)[0, 1]
    )
    quality_versus_causal = float(
        np.corrcoef(standardized_quality, standardized_causal)[0, 1]
    )
    log_hr_versus_causal = float(
        np.corrcoef(standardized_log_hr, standardized_causal)[0, 1]
    )

    assert abs(quality_versus_log_hr) < 0.05
    assert abs(quality_versus_causal) < 0.05
    assert abs(log_hr_versus_causal) < 0.05


def test_simulator_streams_are_distinct_arrays(
    walking: Intervention,
    default_profile: Profile,
    monkeypatch: pytest.MonkeyPatch,
):
    """A coupled simulator reuses one standardized normal draw for both streams."""
    n_simulations = 2_000
    spy = SimulatorSpy().install(monkeypatch)

    simulate_qaly_profile_vectorized(
        walking,
        default_profile,
        n_simulations=n_simulations,
        random_state=42,
    )

    hazard_ratio = walking.mortality.hazard_ratio
    hr_call = spy.only_call_from(spy.distribution_calls, hazard_ratio)
    quality_offsets = spy.only_quality_offsets(n_simulations)
    log_mean, log_sd = hazard_ratio._lognormal_params()

    standardized_quality = quality_offsets / QUALITY_WEIGHT_STD
    standardized_log_hr = (np.log(hr_call.values) - log_mean) / log_sd

    assert not np.allclose(standardized_quality, standardized_log_hr, atol=1e-9)


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


def _analyze_hiit(default_profile: Profile, decision: Decision):
    """Run one decision against the QoL-only ``hiit_2x_week`` entry."""
    entry = CATALOG["hiit_2x_week"]
    assert not entry.has_direct_mortality_effect
    return analyze(
        AnalysisConfig(
            profile=default_profile,
            n_simulations=1_000,
            random_state=42,
        ),
        decisions=[decision],
        catalog_entries={entry.id: entry},
    )


def test_catalog_null_mortality_is_exact_through_analyzer(default_profile: Profile):
    entry = CATALOG["hiit_2x_week"]
    result = _analyze_hiit(
        default_profile,
        Decision(type="add", item_id=entry.id, label=f"ADD: {entry.name}"),
    )

    assert result.item_results_by_id[entry.id]["mort_qaly"] == 0.0
    assert result.decisions[0]["mort_qaly"] == 0.0


def test_qol_only_item_keeps_its_mortality_arm_under_an_hr_override(
    default_profile: Profile,
):
    """An explicit ``override_hr`` is a mortality claim about the adjusted item.

    ``hiit_2x_week`` carries ``has_direct_mortality_effect=False``, so both the
    catalog path and an un-overridden decision are exactly zero. A decision that
    supplies a hazard ratio is asking what the item would be worth carrying that
    hazard ratio, so the decision path must simulate the arm instead of dropping
    it. Before this fix the override was computed and then discarded, and the
    decision returned exactly 0.0.
    """
    entry = CATALOG["hiit_2x_week"]
    overridden = _analyze_hiit(
        default_profile,
        Decision(
            type="adjust",
            item_id=entry.id,
            label=f"ADJUST: {entry.name}",
            override_hr=0.85,
        ),
    )

    decision = overridden.decisions[0]
    assert decision["mort_qaly"] > 0.0
    assert decision["posterior_hr"] < 1.0
    # The catalog leg is untouched: only the decision asked for a hazard ratio.
    assert overridden.item_results_by_id[entry.id]["mort_qaly"] == 0.0


def test_qol_only_item_keeps_its_mortality_arm_under_an_added_hr_override(
    default_profile: Profile,
):
    """The ADD branch computes an overridden hazard ratio the same way."""
    entry = CATALOG["hiit_2x_week"]
    added = _analyze_hiit(
        default_profile,
        Decision(
            type="add",
            item_id=entry.id,
            label=f"ADD: {entry.name}",
            override_hr=0.85,
        ),
    )

    assert added.decisions[0]["mort_qaly"] > 0.0
    assert added.decisions[0]["posterior_hr"] < 1.0


def test_qol_only_item_stays_exactly_zero_for_a_null_hr_override(
    default_profile: Profile,
):
    """An override of exactly 1.0 is still a null arm and must stay exact."""
    entry = CATALOG["hiit_2x_week"]
    result = _analyze_hiit(
        default_profile,
        Decision(
            type="adjust",
            item_id=entry.id,
            label=f"ADJUST: {entry.name}",
            override_hr=1.0,
        ),
    )

    assert result.decisions[0]["mort_qaly"] == 0.0
    assert result.decisions[0]["posterior_hr"] == 1.0


def test_mortality_bearing_item_is_unaffected_by_the_override_gate(
    default_profile: Profile,
):
    """An entry that already claims mortality keeps its arm with no override."""
    entry = CATALOG["statin_5mg"]
    assert entry.has_direct_mortality_effect
    result = analyze(
        AnalysisConfig(
            profile=default_profile,
            n_simulations=1_000,
            random_state=42,
        ),
        decisions=[Decision(type="add", item_id=entry.id, label=f"ADD: {entry.name}")],
        catalog_entries={entry.id: entry},
    )

    assert result.decisions[0]["mort_qaly"] != 0.0


def test_seeded_walking_mean_matches_independent_runs_within_mc_error(
    walking: Intervention,
    default_profile: Profile,
):
    """Seed 42 is not a lucky draw: it sits within Monte Carlo error of others.

    The reference arm formerly redrew from the OS entropy pool on every run, so
    a three-sigma bound failed roughly one run in a few hundred for reasons no
    code change caused. Ten fixed seeds keep the same comparison and make the
    outcome reproducible.
    """
    n_simulations = 20_000
    assert 42 not in REFERENCE_SEEDS
    seeded = simulate_qaly_profile_vectorized(
        walking,
        default_profile,
        n_simulations=n_simulations,
        random_state=42,
    )
    reference = [
        simulate_qaly_profile_vectorized(
            walking,
            default_profile,
            n_simulations=n_simulations,
            random_state=seed,
        )
        for seed in REFERENCE_SEEDS
    ]

    reference_mean = float(np.mean([result.mean for result in reference]))
    seeded_variance = seeded.std**2 / n_simulations
    reference_mean_variance = float(
        np.mean([result.std**2 / n_simulations for result in reference])
    ) / len(REFERENCE_SEEDS)
    three_standard_errors = 3 * np.sqrt(seeded_variance + reference_mean_variance)

    assert abs(seeded.mean - reference_mean) <= three_standard_errors
