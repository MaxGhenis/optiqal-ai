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

    def test_lognormal_hr_parameterization_mean_equals_hr(self):
        """hr-centered lognormal should produce E[HR] == hr exactly."""
        dist = Distribution(type="lognormal", params={"hr": 0.80, "log_sd": 0.15})
        # .mean returns the hr exactly (short-circuited, no FP drift).
        assert dist.mean == 0.80
        # Large-sample Monte Carlo mean matches.
        samples = dist.sample(200_000, random_state=7)
        assert abs(float(np.mean(samples)) - 0.80) < 0.005

    def test_lognormal_hr_null_samples_mean_to_one(self):
        """hr=1.0 with nonzero log_sd gives MC mean exactly 1.0, no harm bias."""
        dist = Distribution(type="lognormal", params={"hr": 1.0, "log_sd": 0.12})
        samples = dist.sample(200_000, random_state=7)
        assert abs(float(np.mean(samples)) - 1.0) < 0.003
        # Median < 1 because mean-centering shifts the log_mean to -sigma^2/2.
        assert float(np.median(samples)) < 1.0

    def test_lognormal_hr_takes_precedence_over_log_mean(self):
        """When both hr and log_mean are supplied to from_dict, hr wins."""
        dist = Distribution.from_dict({
            "type": "lognormal",
            "hr": 0.85,
            "log_mean": 999.0,  # should be ignored
            "log_sd": 0.10,
        })
        assert dist.mean == 0.85
        assert "log_mean" not in dist.params  # raw key not stored

    def test_lognormal_params_helper_resolves_both_parameterizations(self):
        """_lognormal_params() must return usable (log_mean, log_sd) for both forms.

        This is the path used by bayesian.py and any other caller that needs
        the raw (log_mean, log_sd) tuple. Hr-keyed lognormals must not
        KeyError here — the helper must mean-center internally.
        """
        hr_keyed = Distribution(type="lognormal", params={"hr": 0.80, "log_sd": 0.15})
        log_mean, log_sd = hr_keyed._lognormal_params()
        # log_mean = log(0.80) - 0.15**2/2 = -0.2231 - 0.01125 = -0.2344
        assert abs(log_mean - (np.log(0.80) - 0.15 ** 2 / 2)) < 1e-9
        assert log_sd == 0.15

        raw_keyed = Distribution(type="lognormal", params={"log_mean": -0.18, "log_sd": 0.10})
        log_mean_raw, log_sd_raw = raw_keyed._lognormal_params()
        assert log_mean_raw == -0.18
        assert log_sd_raw == 0.10

    def test_lognormal_raw_log_mean_still_works(self):
        """Existing YAML using log_mean continues to work unchanged."""
        dist = Distribution.from_dict({
            "type": "lognormal",
            "log_mean": -0.223,
            "log_sd": 0.12,
        })
        assert "log_mean" in dist.params
        assert dist.params["log_mean"] == pytest.approx(-0.223)
        # Under raw semantics, mean = exp(log_mean + sigma^2/2).
        expected_mean = np.exp(-0.223 + 0.12 ** 2 / 2)
        assert dist.mean == pytest.approx(expected_mean, abs=1e-6)

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

lineage:
  model_version: canonical-v1-draft
  estimand: Lifetime net QALY delta versus not doing the intervention
  studies:
    - id: aune2016_main
      citation: "Aune et al. 2016"
      year: 2016
      study_type: meta-analysis
      sample_size: 459833
      role: direct-effect
      notes: Primary pooled walking estimate
  parameter_lineage:
    - parameter: mortality.hazard_ratio
      derivation: meta-analytic pooled log-HR mapped to LogNormal
      source_ids: [aune2016_main]
      assumptions:
        - Transportable to similar baseline populations with confounding shrinkage
  prior_lineage:
    - parameter: confounding.causal_fraction
      family: beta
      rationale: Exercise mortality estimates are heavily confounded
      source_ids: [aune2016_main]
  notes:
    - Draft lineage fixture for parser coverage

caveats:
  - Observational evidence only
  - Healthy user bias possible

harm_model:
  - id: gi_upset
    description: Mild GI upset while adapting
    annual_qaly_loss:
      type: point
      value: 0.002

interaction_tags: [sedating, serotonergic]

interaction_rules:
  - id: sedation_stack
    requires_tags: [sedating]
    minimum_matches: 2
    description: Extra grogginess when stacked with other sedating agents
    annual_qaly_loss:
      type: point
      value: 0.001
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

    def test_lineage_parsed(self, walking_yaml):
        intervention = Intervention.from_yaml_string(walking_yaml)
        assert intervention.lineage is not None
        assert intervention.lineage.model_version == "canonical-v1-draft"
        assert intervention.lineage.estimand.startswith("Lifetime net QALY delta")
        assert len(intervention.lineage.studies) == 1
        assert intervention.lineage.studies[0]["study_type"] == "meta-analysis"
        assert intervention.lineage.parameter_lineage[0]["parameter"] == "mortality.hazard_ratio"
        assert intervention.lineage.prior_lineage[0]["family"] == "beta"

    def test_harm_model_and_interaction_rules_parsed(self, walking_yaml):
        intervention = Intervention.from_yaml_string(walking_yaml)
        assert len(intervention.harm_model) == 1
        assert intervention.harm_model[0].annual_qaly_loss is not None
        assert intervention.harm_model[0].annual_qaly_loss.mean == pytest.approx(0.002)
        assert intervention.interaction_tags == ["sedating", "serotonergic"]
        assert len(intervention.interaction_rules) == 1
        assert intervention.interaction_rules[0].minimum_matches == 2


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
