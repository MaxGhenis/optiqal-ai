import { describe, it, expect } from "vitest";
import {
  CALIBRATION_DATA,
  CALIBRATED_PRIORS,
  INTERVENTION_SPECIFIC_PRIORS,
  getCalibratedPrior,
  PRIOR_COMPARISON,
} from "./confounding-calibrated";

describe("CALIBRATION_DATA", () => {
  it("should have calibration points for key interventions", () => {
    const interventions = CALIBRATION_DATA.map((d) => d.intervention);
    expect(interventions).toContain("Physical activity (general)");
    expect(interventions).toContain("Mediterranean diet");
    expect(interventions).toContain("Statins");
    expect(interventions).toContain("Smoking cessation");
  });

  it("should have sources for all calibration points", () => {
    for (const point of CALIBRATION_DATA) {
      expect(point.source).toBeTruthy();
      expect(point.year).toBeGreaterThan(2000);
    }
  });

  it("should have valid HR values", () => {
    for (const point of CALIBRATION_DATA) {
      expect(point.observationalHR).toBeGreaterThan(0);
      expect(point.observationalHR).toBeLessThan(2);
      if (point.rctHR !== null) {
        expect(point.rctHR).toBeGreaterThan(0);
        expect(point.rctHR).toBeLessThan(2);
      }
    }
  });

  it("should show exercise RCT effect is null or very small", () => {
    const exercisePoints = CALIBRATION_DATA.filter(
      (d) => d.category === "exercise"
    );
    for (const point of exercisePoints) {
      // RCT HR is either 1.0 (no effect) or null (no RCT available)
      if (point.rctHR !== null) {
        expect(point.rctHR).toBe(1.0); // No causal effect
      }
      // Causal fraction should be small
      expect(point.impliedCausalFraction).toBeLessThanOrEqual(0.2);
    }
  });

  it("should show statin RCT vs observational discrepancy", () => {
    const statin = CALIBRATION_DATA.find((d) => d.intervention === "Statins");
    expect(statin).toBeDefined();
    expect(statin!.observationalHR).toBeCloseTo(0.54, 1);
    expect(statin!.rctHR).toBeCloseTo(0.84, 1);
    expect(statin!.impliedCausalFraction).toBeCloseTo(0.28, 1);
  });
});

describe("CALIBRATED_PRIORS", () => {
  it("should have priors for all categories", () => {
    const categories = [
      "exercise",
      "diet",
      "sleep",
      "stress",
      "substance",
      "medical",
      "social",
      "other",
    ];
    for (const cat of categories) {
      expect(CALIBRATED_PRIORS[cat]).toBeDefined();
      expect(CALIBRATED_PRIORS[cat].alpha).toBeGreaterThan(0);
      expect(CALIBRATED_PRIORS[cat].beta).toBeGreaterThan(0);
    }
  });

  it("should have valid mean causal fractions", () => {
    for (const [category, prior] of Object.entries(CALIBRATED_PRIORS)) {
      const expectedMean = prior.alpha / (prior.alpha + prior.beta);
      expect(prior.mean).toBeCloseTo(expectedMean, 2);
      expect(prior.mean).toBeGreaterThan(0);
      expect(prior.mean).toBeLessThan(1);
    }
  });

  it("should have exercise more skeptical than diet", () => {
    expect(CALIBRATED_PRIORS.exercise.mean).toBeLessThan(
      CALIBRATED_PRIORS.diet.mean
    );
  });

  it("should have diet less skeptical than exercise (PREDIMED)", () => {
    expect(CALIBRATED_PRIORS.diet.mean).toBeGreaterThan(0.4);
    expect(CALIBRATED_PRIORS.exercise.mean).toBeLessThan(0.25);
  });

  it("should have calibration sources for each category", () => {
    for (const [category, prior] of Object.entries(CALIBRATED_PRIORS)) {
      expect(prior.rationale).toBeTruthy();
      // Most categories should have sources (except 'other')
      if (category !== "other") {
        expect(prior.calibrationSources.length).toBeGreaterThan(0);
      }
    }
  });
});

describe("INTERVENTION_SPECIFIC_PRIORS", () => {
  it("should have specific priors for key interventions", () => {
    expect(INTERVENTION_SPECIFIC_PRIORS.walking_30min_daily).toBeDefined();
    expect(INTERVENTION_SPECIFIC_PRIORS.mediterranean_diet).toBeDefined();
    expect(INTERVENTION_SPECIFIC_PRIORS.smoking_cessation).toBeDefined();
  });

  it("should have walking skeptical but not as extreme as general exercise", () => {
    const walking = INTERVENTION_SPECIFIC_PRIORS.walking_30min_daily;
    expect(walking.mean).toBeCloseTo(0.2, 1);
    expect(walking.mean).toBeGreaterThan(CALIBRATED_PRIORS.exercise.mean);
  });

  it("should have Mediterranean diet with high causal fraction", () => {
    const medDiet = INTERVENTION_SPECIFIC_PRIORS.mediterranean_diet;
    expect(medDiet.mean).toBeGreaterThan(0.5);
  });

  it("should have moderate alcohol very skeptical (J-curve is confounded)", () => {
    const alcohol = INTERVENTION_SPECIFIC_PRIORS.moderate_alcohol;
    expect(alcohol.mean).toBeLessThan(0.15);
  });
});

describe("getCalibratedPrior", () => {
  it("should return intervention-specific prior when available", () => {
    const prior = getCalibratedPrior("walking_30min_daily", "exercise");
    expect(prior.mean).toBeCloseTo(0.2, 1);
    expect(prior.sources).toContain("Extrapolated from general exercise calibration");
  });

  it("should fall back to category prior when no specific prior", () => {
    const prior = getCalibratedPrior("unknown_intervention", "exercise");
    expect(prior.mean).toBeCloseTo(CALIBRATED_PRIORS.exercise.mean, 2);
  });

  it("should return valid structure", () => {
    const prior = getCalibratedPrior("anything", "diet");
    expect(prior.alpha).toBeGreaterThan(0);
    expect(prior.beta).toBeGreaterThan(0);
    expect(prior.mean).toBeGreaterThan(0);
    expect(prior.rationale).toBeTruthy();
    expect(Array.isArray(prior.sources)).toBe(true);
  });
});

describe("PRIOR_COMPARISON", () => {
  it("should document changes from old to new priors", () => {
    expect(PRIOR_COMPARISON.exercise.old.mean).toBe(0.33);
    expect(PRIOR_COMPARISON.exercise.new.mean).toBe(0.17);
    expect(PRIOR_COMPARISON.exercise.change).toContain("skeptical");
  });

  it("should show diet became more generous", () => {
    expect(PRIOR_COMPARISON.diet.new.mean).toBeGreaterThan(
      PRIOR_COMPARISON.diet.old.mean
    );
    expect(PRIOR_COMPARISON.diet.change).toContain("generous");
  });

  it("should show medical became more skeptical", () => {
    expect(PRIOR_COMPARISON.medical.new.mean).toBeLessThan(
      PRIOR_COMPARISON.medical.old.mean
    );
  });
});
