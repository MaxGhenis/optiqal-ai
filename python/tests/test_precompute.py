"""Tests for precompute module."""

import pytest
import json
import tempfile
from pathlib import Path
import numpy as np

from optiqal.intervention import Intervention
from optiqal.precompute import (
    PrecomputedResult,
    PrecomputedIntervention,
    precompute_intervention,
    precompute_all_interventions,
)


class TestPrecomputedResult:
    def test_precomputed_result_creation(self):
        """Test creating a PrecomputedResult with all required fields."""
        result = PrecomputedResult(
            age=40,
            sex="male",
            qaly_median=0.5,
            qaly_mean=0.52,
            qaly_ci95_low=0.3,
            qaly_ci95_high=0.75,
            cvd_contribution=0.3,
            cancer_contribution=0.1,
            other_contribution=0.1,
            life_years_gained=0.8,
            causal_fraction_mean=0.5,
            causal_fraction_ci95_low=0.2,
            causal_fraction_ci95_high=0.8,
            n_samples=5000,
            discount_rate=0.03,
            method="monte_carlo",
        )

        assert result.age == 40
        assert result.sex == "male"
        assert result.qaly_median == 0.5
        assert result.method == "monte_carlo"


class TestPrecomputedIntervention:
    def test_precomputed_intervention_creation(self):
        """Test creating a PrecomputedIntervention."""
        result = PrecomputedResult(
            age=40,
            sex="male",
            qaly_median=0.5,
            qaly_mean=0.52,
            qaly_ci95_low=0.3,
            qaly_ci95_high=0.75,
            cvd_contribution=0.3,
            cancer_contribution=0.1,
            other_contribution=0.1,
            life_years_gained=0.8,
            causal_fraction_mean=0.5,
            causal_fraction_ci95_low=0.2,
            causal_fraction_ci95_high=0.8,
            n_samples=5000,
            discount_rate=0.03,
            method="monte_carlo",
        )

        intervention = PrecomputedIntervention(
            id="test_intervention",
            name="Test Intervention",
            category="exercise",
            description="A test intervention",
            results={"40_male": result},
            summary={
                "qaly_median_all": 0.5,
                "qaly_mean_all": 0.52,
                "qaly_min": 0.5,
                "qaly_max": 0.5,
            },
        )

        assert intervention.id == "test_intervention"
        assert intervention.get_result(40, "male") == result
        assert intervention.get_result(50, "female") is None

    def test_json_serialization(self):
        """Test that PrecomputedIntervention can be serialized to JSON."""
        result = PrecomputedResult(
            age=40,
            sex="male",
            qaly_median=0.5,
            qaly_mean=0.52,
            qaly_ci95_low=0.3,
            qaly_ci95_high=0.75,
            cvd_contribution=0.3,
            cancer_contribution=0.1,
            other_contribution=0.1,
            life_years_gained=0.8,
            causal_fraction_mean=0.5,
            causal_fraction_ci95_low=0.2,
            causal_fraction_ci95_high=0.8,
            n_samples=5000,
            discount_rate=0.03,
            method="monte_carlo",
        )

        intervention = PrecomputedIntervention(
            id="test_intervention",
            name="Test Intervention",
            category="exercise",
            description="A test intervention",
            results={"40_male": result},
            summary={
                "qaly_median_all": 0.5,
                "qaly_mean_all": 0.52,
                "qaly_min": 0.5,
                "qaly_max": 0.5,
            },
        )

        json_str = intervention.to_json()
        data = json.loads(json_str)

        assert data["id"] == "test_intervention"
        assert data["name"] == "Test Intervention"
        assert "40_male" in data["results"]
        assert data["results"]["40_male"]["qaly_median"] == 0.5

    def test_save_and_load(self):
        """Test saving and loading PrecomputedIntervention."""
        result = PrecomputedResult(
            age=40,
            sex="male",
            qaly_median=0.5,
            qaly_mean=0.52,
            qaly_ci95_low=0.3,
            qaly_ci95_high=0.75,
            cvd_contribution=0.3,
            cancer_contribution=0.1,
            other_contribution=0.1,
            life_years_gained=0.8,
            causal_fraction_mean=0.5,
            causal_fraction_ci95_low=0.2,
            causal_fraction_ci95_high=0.8,
            n_samples=5000,
            discount_rate=0.03,
            method="monte_carlo",
        )

        intervention = PrecomputedIntervention(
            id="test_intervention",
            name="Test Intervention",
            category="exercise",
            description="A test intervention",
            results={"40_male": result},
            summary={
                "qaly_median_all": 0.5,
                "qaly_mean_all": 0.52,
                "qaly_min": 0.5,
                "qaly_max": 0.5,
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_intervention.json"
            intervention.save(path)

            loaded = PrecomputedIntervention.load(path)

            assert loaded.id == intervention.id
            assert loaded.name == intervention.name
            assert loaded.category == intervention.category
            assert loaded.description == intervention.description
            assert "40_male" in loaded.results
            assert loaded.results["40_male"].qaly_median == 0.5


class TestPrecomputeIntervention:
    def test_precompute_with_monte_carlo(self):
        """Test precomputing intervention with Monte Carlo."""
        # Create a simple test intervention
        intervention_yaml = """
id: test_walking
name: Test Walking
category: exercise
description: Test walking intervention

evidence:
  quality: high
  primary_study_type: meta-analysis
  sources:
    - citation: "Test et al 2024"
      year: 2024
      sample_size: 1000

confounding:
  prior:
    type: beta
    alpha: 2.5
    beta: 5.0

mortality:
  hazard_ratio: LogNormal(-0.18, 0.08)
  onset_delay: 0
  ramp_up: 0.5
  decay_rate: 0

quality:
  subjective_wellbeing: Normal(0.02, 0.01)

costs:
  hours_per_week: Normal(3.5, 0.5)
  annual_cost_usd: Normal(0, 50)
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(intervention_yaml)
            f.flush()

            intervention = Intervention.from_yaml(Path(f.name))

            # Precompute with small sample size for speed
            result = precompute_intervention(
                intervention,
                ages=[40, 50],
                sexes=["male"],
                use_mcmc=False,
                n_samples=100,  # Small for test speed
                random_seed=42,
            )

            assert result.id == "test_walking"
            assert result.name == "Test Walking"
            assert result.category == "exercise"
            assert "40_male" in result.results
            assert "50_male" in result.results

            # Check that results have required fields
            male_40 = result.results["40_male"]
            assert male_40.age == 40
            assert male_40.sex == "male"
            assert male_40.qaly_median > 0  # Should be positive
            assert male_40.qaly_ci95_low < male_40.qaly_median < male_40.qaly_ci95_high
            assert male_40.method == "monte_carlo"
            assert male_40.n_samples == 100

            # Check summary statistics
            assert "qaly_median_all" in result.summary
            assert "qaly_mean_all" in result.summary
            assert "qaly_min" in result.summary
            assert "qaly_max" in result.summary


class TestPrecomputeAllInterventions:
    def test_precompute_all(self):
        """Test precomputing all interventions from a directory."""
        # Create temporary directory with test interventions
        with tempfile.TemporaryDirectory() as tmpdir:
            intervention_dir = Path(tmpdir) / "interventions"
            intervention_dir.mkdir()

            output_dir = Path(tmpdir) / "output"

            # Create two test intervention files
            intervention1_yaml = """
id: test_intervention_1
name: Test Intervention 1
category: exercise
description: First test intervention

evidence:
  quality: high
  primary_study_type: meta-analysis
  sources:
    - citation: "Test et al 2024"

confounding:
  prior:
    type: beta
    alpha: 2.5
    beta: 5.0

mortality:
  hazard_ratio: LogNormal(-0.18, 0.08)
  onset_delay: 0
"""

            intervention2_yaml = """
id: test_intervention_2
name: Test Intervention 2
category: diet
description: Second test intervention

evidence:
  quality: high
  primary_study_type: rct
  sources:
    - citation: "Test et al 2024"

confounding:
  prior:
    type: beta
    alpha: 8.0
    beta: 2.0

mortality:
  hazard_ratio: LogNormal(-0.15, 0.10)
  onset_delay: 0
"""

            (intervention_dir / "intervention1.yaml").write_text(intervention1_yaml)
            (intervention_dir / "intervention2.yaml").write_text(intervention2_yaml)

            # Precompute all
            results = precompute_all_interventions(
                intervention_dir,
                output_dir,
                ages=[40],
                sexes=["male"],
                use_mcmc=False,
                n_samples=100,
                random_seed=42,
            )

            assert len(results) == 2
            assert (output_dir / "test_intervention_1.json").exists()
            assert (output_dir / "test_intervention_2.json").exists()

            # Load and verify one of the files
            loaded = PrecomputedIntervention.load(output_dir / "test_intervention_1.json")
            assert loaded.id == "test_intervention_1"
            assert loaded.name == "Test Intervention 1"
            assert "40_male" in loaded.results
