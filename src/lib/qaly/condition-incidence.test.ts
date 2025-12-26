/**
 * Tests for condition incidence models and quality calculations
 */

import { describe, it, expect } from "vitest";
import {
  CONDITION_DECREMENTS,
  HEALTHY_BASELINE,
  pureAgingDecrement,
  diabetesIncidence,
  cvdRisk10Year,
  cvdIncidenceAnnual,
  strokeIncidenceAnnual,
  chdIncidenceAnnual,
  depressionIncidenceAnnual,
  conditionPrevalence,
  calculateQuality,
  interventionQualityEffect,
  detailedQualityImpact,
  type RiskFactors,
} from "./condition-incidence";
import { createDefaultState } from "./state";

// =============================================================================
// TEST FIXTURES
// =============================================================================

const healthyYoungMale: RiskFactors = {
  age: 30,
  sex: "male",
  bmi: 24,
  systolicBP: 115,
  totalCholesterol: 180,
  hdlCholesterol: 55,
  smokingStatus: "never",
  diabetesStatus: false,
  exerciseMinPerWeek: 200,
};

const unhealthyMiddleAgedMale: RiskFactors = {
  age: 50,
  sex: "male",
  bmi: 32,
  systolicBP: 145,
  totalCholesterol: 240,
  hdlCholesterol: 35,
  smokingStatus: "current",
  smokingPackYears: 20,
  diabetesStatus: false,
  exerciseMinPerWeek: 30,
};

const averageReferenceMale: RiskFactors = {
  age: 40,
  sex: "male",
  bmi: 28.5,
  systolicBP: 128,
  smokingStatus: "never",
  diabetesStatus: false,
  exerciseMinPerWeek: 50,
};

// =============================================================================
// QUALITY DECREMENTS
// =============================================================================

describe("Condition Decrements", () => {
  it("has decrements for all major conditions", () => {
    expect(CONDITION_DECREMENTS.type2_diabetes).toBeDefined();
    expect(CONDITION_DECREMENTS.stroke).toBeDefined();
    expect(CONDITION_DECREMENTS.coronary_heart_disease).toBeDefined();
    expect(CONDITION_DECREMENTS.depression).toBeDefined();
  });

  it("all decrements are negative", () => {
    for (const [condition, data] of Object.entries(CONDITION_DECREMENTS)) {
      expect(data.decrement).toBeLessThan(0);
    }
  });

  it("stroke has larger decrement than diabetes", () => {
    // Stroke is more disabling
    expect(Math.abs(CONDITION_DECREMENTS.stroke.decrement)).toBeGreaterThan(
      Math.abs(CONDITION_DECREMENTS.type2_diabetes.decrement)
    );
  });

  it("decrements have reasonable magnitudes (0.02 to 0.20)", () => {
    for (const [condition, data] of Object.entries(CONDITION_DECREMENTS)) {
      expect(Math.abs(data.decrement)).toBeGreaterThanOrEqual(0.02);
      expect(Math.abs(data.decrement)).toBeLessThanOrEqual(0.20);
    }
  });
});

// =============================================================================
// PURE AGING
// =============================================================================

describe("Pure Aging Decrement", () => {
  it("returns 0 for age 50 and below", () => {
    expect(pureAgingDecrement(30)).toBe(0);
    expect(pureAgingDecrement(50)).toBe(0);
  });

  it("increases after age 50", () => {
    expect(pureAgingDecrement(60)).toBeGreaterThan(0);
    expect(pureAgingDecrement(70)).toBeGreaterThan(pureAgingDecrement(60));
  });

  it("is modest in magnitude (~0.02 per decade)", () => {
    // 10 years = 0.02
    expect(pureAgingDecrement(60)).toBeCloseTo(0.02, 2);
    // 30 years = 0.06
    expect(pureAgingDecrement(80)).toBeCloseTo(0.06, 2);
  });
});

// =============================================================================
// DIABETES INCIDENCE
// =============================================================================

describe("Diabetes Incidence", () => {
  it("healthy young person has low diabetes risk", () => {
    const risk = diabetesIncidence(healthyYoungMale);
    expect(risk).toBeLessThan(0.005); // <0.5% annual
  });

  it("unhealthy middle-aged person has higher risk", () => {
    const healthyRisk = diabetesIncidence(healthyYoungMale);
    const unhealthyRisk = diabetesIncidence(unhealthyMiddleAgedMale);
    expect(unhealthyRisk).toBeGreaterThan(healthyRisk * 3);
  });

  it("BMI is major risk factor", () => {
    const normalBMI = diabetesIncidence({ ...averageReferenceMale, bmi: 24 });
    const obeseBMI = diabetesIncidence({ ...averageReferenceMale, bmi: 35 });
    expect(obeseBMI).toBeGreaterThan(normalBMI * 2);
  });

  it("exercise reduces risk", () => {
    const sedentary = diabetesIncidence({
      ...averageReferenceMale,
      exerciseMinPerWeek: 0,
    });
    const active = diabetesIncidence({
      ...averageReferenceMale,
      exerciseMinPerWeek: 200,
    });
    expect(active).toBeLessThan(sedentary);
  });

  it("is capped at 10% annual", () => {
    const extremeRisk = diabetesIncidence({
      ...unhealthyMiddleAgedMale,
      bmi: 45,
      age: 65,
    });
    expect(extremeRisk).toBeLessThanOrEqual(0.1);
  });
});

// =============================================================================
// CVD RISK
// =============================================================================

describe("CVD Risk", () => {
  it("healthy young person has low 10-year risk", () => {
    const risk = cvdRisk10Year(healthyYoungMale);
    expect(risk).toBeLessThan(0.03); // <3%
  });

  it("risk increases with age", () => {
    const young = cvdRisk10Year({ ...averageReferenceMale, age: 40 });
    const old = cvdRisk10Year({ ...averageReferenceMale, age: 60 });
    expect(old).toBeGreaterThan(young * 2);
  });

  it("smoking doubles risk", () => {
    const nonSmoker = cvdRisk10Year({
      ...averageReferenceMale,
      smokingStatus: "never",
    });
    const smoker = cvdRisk10Year({
      ...averageReferenceMale,
      smokingStatus: "current",
    });
    expect(smoker).toBeGreaterThan(nonSmoker * 1.5);
    expect(smoker).toBeLessThan(nonSmoker * 3);
  });

  it("diabetes increases risk", () => {
    const noDM = cvdRisk10Year({ ...averageReferenceMale, diabetesStatus: false });
    const withDM = cvdRisk10Year({ ...averageReferenceMale, diabetesStatus: true });
    expect(withDM).toBeGreaterThan(noDM * 2);
  });

  it("exercise is protective", () => {
    const sedentary = cvdRisk10Year({
      ...averageReferenceMale,
      exerciseMinPerWeek: 0,
    });
    const active = cvdRisk10Year({
      ...averageReferenceMale,
      exerciseMinPerWeek: 200,
    });
    expect(active).toBeLessThan(sedentary);
  });

  it("is capped at 50%", () => {
    const extremeRisk = cvdRisk10Year({
      ...unhealthyMiddleAgedMale,
      age: 70,
      diabetesStatus: true,
    });
    expect(extremeRisk).toBeLessThanOrEqual(0.5);
  });
});

describe("CVD Annual Incidence", () => {
  it("annual is lower than 10-year", () => {
    const annual = cvdIncidenceAnnual(averageReferenceMale);
    const tenYear = cvdRisk10Year(averageReferenceMale);
    expect(annual).toBeLessThan(tenYear);
  });

  it("CHD + stroke roughly sum to CVD", () => {
    const cvd = cvdIncidenceAnnual(averageReferenceMale);
    const chd = chdIncidenceAnnual(averageReferenceMale);
    const stroke = strokeIncidenceAnnual(averageReferenceMale);
    // CHD is 55%, stroke is 25%, so sum is 80% of CVD
    expect(chd + stroke).toBeCloseTo(cvd * 0.8, 3);
  });
});

// =============================================================================
// DEPRESSION INCIDENCE
// =============================================================================

describe("Depression Incidence", () => {
  it("women have higher baseline risk", () => {
    const male = depressionIncidenceAnnual({ ...averageReferenceMale });
    const female = depressionIncidenceAnnual({
      ...averageReferenceMale,
      sex: "female",
    });
    expect(female).toBeGreaterThan(male);
  });

  it("exercise is protective", () => {
    const sedentary = depressionIncidenceAnnual({
      ...averageReferenceMale,
      exerciseMinPerWeek: 0,
    });
    const active = depressionIncidenceAnnual({
      ...averageReferenceMale,
      exerciseMinPerWeek: 200,
    });
    expect(active).toBeLessThan(sedentary);
  });

  it("returns reasonable rates (1-5% annual)", () => {
    const rate = depressionIncidenceAnnual(averageReferenceMale);
    expect(rate).toBeGreaterThan(0.01);
    expect(rate).toBeLessThan(0.06);
  });
});

// =============================================================================
// CONDITION PREVALENCE
// =============================================================================

describe("Condition Prevalence", () => {
  it("returns 0 for young age", () => {
    const youngRf = { ...averageReferenceMale, age: 25 };
    expect(conditionPrevalence("type2_diabetes", youngRf)).toBe(0);
  });

  it("increases with age", () => {
    const young = conditionPrevalence("type2_diabetes", {
      ...averageReferenceMale,
      age: 40,
    });
    const old = conditionPrevalence("type2_diabetes", {
      ...averageReferenceMale,
      age: 60,
    });
    expect(old).toBeGreaterThan(young);
  });

  it("is higher for unhealthy profile", () => {
    const healthy = conditionPrevalence("coronary_heart_disease", healthyYoungMale);
    const unhealthy = conditionPrevalence(
      "coronary_heart_disease",
      unhealthyMiddleAgedMale
    );
    expect(unhealthy).toBeGreaterThan(healthy);
  });

  it("obesity class 2 is deterministic from BMI", () => {
    const notObese = conditionPrevalence("obesity_class2", {
      ...averageReferenceMale,
      bmi: 30,
    });
    const obese = conditionPrevalence("obesity_class2", {
      ...averageReferenceMale,
      bmi: 36,
    });
    expect(notObese).toBe(0);
    expect(obese).toBe(1);
  });
});

// =============================================================================
// QUALITY CALCULATION
// =============================================================================

describe("Quality Calculation", () => {
  it("young healthy person has high quality", () => {
    const state = createDefaultState(30, "male");
    state.biomarkers.bmi = 24;
    state.behaviors.exercise.aerobicMinutesPerWeek = 200;
    state.behaviors.smoking.status = "never";

    const quality = calculateQuality(state);
    expect(quality).toBeGreaterThan(0.9);
  });

  it("older person has lower quality", () => {
    const young = createDefaultState(30, "male");
    const old = createDefaultState(70, "male");

    const youngQ = calculateQuality(young);
    const oldQ = calculateQuality(old);
    expect(oldQ).toBeLessThan(youngQ);
  });

  it("quality is between 0 and healthy baseline", () => {
    const state = createDefaultState(40, "male");
    const quality = calculateQuality(state);
    expect(quality).toBeGreaterThan(0);
    expect(quality).toBeLessThanOrEqual(HEALTHY_BASELINE);
  });

  it("unhealthy profile has lower quality", () => {
    const healthy = createDefaultState(50, "male");
    healthy.biomarkers.bmi = 24;
    healthy.behaviors.exercise.aerobicMinutesPerWeek = 200;

    const unhealthy = createDefaultState(50, "male");
    unhealthy.biomarkers.bmi = 35;
    unhealthy.biomarkers.systolicBP = 150;
    unhealthy.behaviors.exercise.aerobicMinutesPerWeek = 0;
    unhealthy.behaviors.smoking.status = "current";

    const healthyQ = calculateQuality(healthy);
    const unhealthyQ = calculateQuality(unhealthy);
    expect(unhealthyQ).toBeLessThan(healthyQ);
  });
});

// =============================================================================
// INTERVENTION QUALITY EFFECT
// =============================================================================

describe("Intervention Quality Effect", () => {
  it("exercise intervention improves quality", () => {
    const base = createDefaultState(40, "male");
    base.behaviors.exercise.aerobicMinutesPerWeek = 30;

    const intervention = createDefaultState(40, "male");
    intervention.behaviors.exercise.aerobicMinutesPerWeek = 180;

    const gain = interventionQualityEffect(base, intervention, 40);
    expect(gain).toBeGreaterThan(0);
  });

  it("longer time horizon = more quality gain", () => {
    const base = createDefaultState(40, "male");
    base.biomarkers.bmi = 30;

    const intervention = createDefaultState(40, "male");
    intervention.biomarkers.bmi = 25;

    const gain20 = interventionQualityEffect(base, intervention, 20);
    const gain40 = interventionQualityEffect(base, intervention, 40);
    expect(gain40).toBeGreaterThan(gain20);
  });

  it("detailed impact shows condition breakdown", () => {
    const base = createDefaultState(50, "male");
    base.biomarkers.bmi = 32;
    base.behaviors.exercise.aerobicMinutesPerWeek = 0;

    const intervention = createDefaultState(50, "male");
    intervention.biomarkers.bmi = 27;
    intervention.behaviors.exercise.aerobicMinutesPerWeek = 180;

    const impacts = detailedQualityImpact(base, intervention, 30);

    // Should have impacts for diabetes, CVD, stroke, depression
    expect(impacts.length).toBeGreaterThan(0);

    // Each impact should have positive quality saved
    for (const impact of impacts) {
      expect(impact.incidenceReduction).toBeGreaterThan(0);
      expect(impact.expectedQualitySaved).toBeGreaterThan(0);
    }
  });
});
