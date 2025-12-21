"""Tests for intervention module."""

import pytest
import numpy as np

from optiqal.intervention import Distribution, Intervention, MortalityEffect


class TestDistribution:
    def test_point_distribution(self):
        dist = Distribution(type="point", params={"value": 0.85})
        assert dist.mean == 0.85
        samples = dist.sample(100)
        assert all(s == 0.85 for s in samples)

    def test_normal_distribution(self):
        dist = Distribution(type="normal", params={"mean": 0, "sd": 1})
        assert dist.mean == 0
        samples = dist.sample(10000, random_state=42)
        assert abs(np.mean(samples)) < 0.1
        assert abs(np.std(samples) - 1) < 0.1

    def test_lognormal_distribution(self):
        dist = Distribution(type="lognormal", params={"log_mean": -0.2, "log_sd": 0.1})
        samples = dist.sample(10000, random_state=42)
        assert all(s > 0 for s in samples)
        # Mean of lognormal: exp(mu + sigma^2/2)
        expected_mean = np.exp(-0.2 + 0.1**2 / 2)
        assert abs(dist.mean - expected_mean) < 0.01

    def test_beta_distribution(self):
        dist = Distribution(type="beta", params={"alpha": 2, "beta": 5})
        samples = dist.sample(10000, random_state=42)
        assert all(0 <= s <= 1 for s in samples)
        assert abs(dist.mean - 2/7) < 0.01

    def test_uniform_distribution(self):
        dist = Distribution(type="uniform", params={"min": 0.7, "max": 0.9})
        samples = dist.sample(10000, random_state=42)
        assert all(0.7 <= s <= 0.9 for s in samples)
        assert abs(dist.mean - 0.8) < 0.01


class TestDistributionShorthand:
    def test_parse_normal(self):
        dist = Distribution.from_dict("Normal(-4, 2)")
        assert dist.type == "normal"
        assert dist.params["mean"] == -4
        assert dist.params["sd"] == 2

    def test_parse_lognormal(self):
        dist = Distribution.from_dict("LogNormal(-0.18, 0.08)")
        assert dist.type == "lognormal"
        assert dist.params["log_mean"] == -0.18
        assert dist.params["log_sd"] == 0.08

    def test_parse_beta(self):
        dist = Distribution.from_dict("Beta(2.5, 5.0)")
        assert dist.type == "beta"
        assert dist.params["alpha"] == 2.5
        assert dist.params["beta"] == 5.0


class TestInterventionFromDict:
    @pytest.fixture
    def walking_yaml(self):
        return """
id: walking_30min
name: Walking 30 minutes daily
category: exercise
description: Daily walking for 30 minutes

mortality:
  hazard_ratio:
    type: lognormal
    log_mean: -0.18
    log_sd: 0.08
  onset_delay: 0
  ramp_up: 0.5

evidence:
  quality: moderate
  primary_study_type: meta-analysis
  sources:
    - citation: "Aune et al. 2016"
      doi: "10.1001/jamainternmed.2015.8254"

caveats:
  - Observational evidence only
  - Healthy user bias possible
"""

    def test_load_from_yaml_string(self, walking_yaml):
        intervention = Intervention.from_yaml_string(walking_yaml)
        assert intervention.id == "walking_30min"
        assert intervention.name == "Walking 30 minutes daily"
        assert intervention.category == "exercise"

    def test_mortality_effect_parsed(self, walking_yaml):
        intervention = Intervention.from_yaml_string(walking_yaml)
        assert intervention.mortality is not None
        assert intervention.mortality.hazard_ratio.type == "lognormal"
        assert intervention.mortality.hazard_ratio.mean < 1  # Protective

    def test_confounding_prior_assigned(self, walking_yaml):
        intervention = Intervention.from_yaml_string(walking_yaml)
        # Should get exercise category prior
        assert intervention.confounding_prior is not None
        assert intervention.confounding_prior.mean < 0.5  # Skeptical


class TestInterventionPathwayHRs:
    def test_no_mortality_returns_ones(self):
        intervention = Intervention(
            id="test",
            name="Test",
            category="other",
            mortality=None,
        )
        hrs = intervention.to_pathway_hrs()
        assert hrs["cvd"] == 1.0
        assert hrs["cancer"] == 1.0
        assert hrs["other"] == 1.0

    def test_protective_effect_all_pathways(self):
        hr_dist = Distribution(type="point", params={"value": 0.8})
        intervention = Intervention(
            id="test",
            name="Test",
            category="exercise",
            mortality=MortalityEffect(hazard_ratio=hr_dist),
        )
        hrs = intervention.to_pathway_hrs(causal_fraction=1.0)
        assert hrs["cvd"] < 1.0
        assert hrs["cancer"] < 1.0
        assert hrs["other"] < 1.0

    def test_confounding_adjustment(self):
        hr_dist = Distribution(type="point", params={"value": 0.8})
        intervention = Intervention(
            id="test",
            name="Test",
            category="exercise",
            mortality=MortalityEffect(hazard_ratio=hr_dist),
        )
        full = intervention.to_pathway_hrs(causal_fraction=1.0)
        partial = intervention.to_pathway_hrs(causal_fraction=0.5)

        # Partial causation should show weaker effect
        assert partial["cvd"] > full["cvd"]
