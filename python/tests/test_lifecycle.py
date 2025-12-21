"""Tests for lifecycle module."""

import pytest
import numpy as np

from optiqal.lifecycle import (
    CDC_LIFE_TABLE,
    CAUSE_FRACTIONS,
    get_mortality_rate,
    get_cause_fraction,
    get_quality_weight,
    LifecycleModel,
    PathwayHRs,
)


class TestCDCLifeTable:
    def test_has_male_and_female(self):
        assert "male" in CDC_LIFE_TABLE
        assert "female" in CDC_LIFE_TABLE

    def test_mortality_increases_with_age(self):
        assert get_mortality_rate(60, "male") > get_mortality_rate(40, "male")
        assert get_mortality_rate(80, "female") > get_mortality_rate(60, "female")

    def test_male_higher_mortality(self):
        assert get_mortality_rate(50, "male") > get_mortality_rate(50, "female")


class TestCauseFractions:
    def test_sum_to_one(self):
        for age in [40, 50, 60, 70, 80]:
            fractions = get_cause_fraction(age)
            total = fractions["cvd"] + fractions["cancer"] + fractions["other"]
            assert abs(total - 1.0) < 0.01

    def test_cvd_increases_with_age(self):
        young = get_cause_fraction(40)
        old = get_cause_fraction(80)
        assert old["cvd"] > young["cvd"]


class TestQualityWeights:
    def test_decreases_with_age(self):
        assert get_quality_weight(40) > get_quality_weight(70)
        assert get_quality_weight(70) > get_quality_weight(90)

    def test_in_valid_range(self):
        for age in [30, 50, 70, 90]:
            q = get_quality_weight(age)
            assert 0 < q <= 1


class TestLifecycleModel:
    @pytest.fixture
    def model(self):
        return LifecycleModel(start_age=40, sex="male")

    def test_no_effect_with_hr_one(self, model):
        result = model.calculate(PathwayHRs(cvd=1.0, cancer=1.0, other=1.0))
        assert abs(result.qaly_gain) < 0.01

    def test_positive_gain_with_protective_hr(self, model):
        result = model.calculate(PathwayHRs(cvd=0.75, cancer=0.87, other=0.90))
        assert result.qaly_gain > 0
        assert result.intervention_qalys > result.baseline_qalys

    def test_pathway_contributions_sum_to_total(self, model):
        result = model.calculate(PathwayHRs(cvd=0.75, cancer=0.87, other=0.90))
        contribution_sum = (
            result.pathway_contributions["cvd"]
            + result.pathway_contributions["cancer"]
            + result.pathway_contributions["other"]
        )
        # Allow some tolerance due to numerical precision
        assert abs(contribution_sum - result.qaly_gain) < 0.01

    def test_discounting_reduces_qalys(self):
        discounted = LifecycleModel(start_age=40, sex="male", discount_rate=0.03)
        undiscounted = LifecycleModel(start_age=40, sex="male", discount_rate=0)

        hrs = PathwayHRs(cvd=0.75, cancer=0.87, other=0.90)

        result_d = discounted.calculate(hrs)
        result_u = undiscounted.calculate(hrs)

        assert result_d.qaly_gain < result_u.qaly_gain

    def test_younger_gains_more_undiscounted(self):
        hrs = PathwayHRs(cvd=0.75, cancer=0.87, other=0.90)

        young = LifecycleModel(start_age=30, sex="male", discount_rate=0)
        old = LifecycleModel(start_age=70, sex="male", discount_rate=0)

        result_young = young.calculate(hrs)
        result_old = old.calculate(hrs)

        assert result_young.life_years_gained > result_old.life_years_gained
