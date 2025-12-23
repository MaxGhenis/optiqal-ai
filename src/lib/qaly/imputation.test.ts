/**
 * Tests for behavior imputation and causal DAG
 */

import { describe, it, expect } from "vitest";
import {
  imputeBehaviors,
  getCausalEffects,
  isCausallyDownstream,
  imputeFullState,
  type ImputationInput,
} from "./imputation";

describe("imputeBehaviors", () => {
  it("returns reasonable values for average person", () => {
    const input: ImputationInput = {
      age: 40,
      sex: "male",
      bmi: 25,
    };

    const result = imputeBehaviors(input);

    // Exercise: should be around 150 min/week
    expect(result.exercise.aerobicMinutesPerWeek).toBeGreaterThan(0);
    expect(result.exercise.aerobicMinutesPerWeek).toBeLessThan(500);
    expect(result.exercise.sd).toBeGreaterThan(0);

    // Diet: Mediterranean adherence 0-1
    expect(result.diet.mediterraneanAdherence).toBeGreaterThanOrEqual(0);
    expect(result.diet.mediterraneanAdherence).toBeLessThanOrEqual(1);
    expect(result.diet.sd).toBeGreaterThan(0);

    // Alcohol: reasonable drinks per week
    expect(result.alcohol.drinksPerWeek).toBeGreaterThanOrEqual(0);
    expect(result.alcohol.drinksPerWeek).toBeLessThan(50);
    expect(result.alcohol.sd).toBeGreaterThan(0);

    // Sleep: 5-10 hours reasonable range
    expect(result.sleep.hoursPerNight).toBeGreaterThan(5);
    expect(result.sleep.hoursPerNight).toBeLessThan(10);
    expect(result.sleep.sd).toBeGreaterThan(0);

    // Social: positive number of relationships
    expect(result.social.closeRelationships).toBeGreaterThan(0);
    expect(result.social.closeRelationships).toBeLessThan(20);
    expect(result.social.sd).toBeGreaterThan(0);
  });

  it("imputes lower exercise for obese person", () => {
    const normalWeight: ImputationInput = {
      age: 40,
      sex: "male",
      bmi: 23,
    };

    const obese: ImputationInput = {
      age: 40,
      sex: "male",
      bmi: 35,
    };

    const normalResult = imputeBehaviors(normalWeight);
    const obeseResult = imputeBehaviors(obese);

    // Obese person should have lower imputed exercise
    expect(obeseResult.exercise.aerobicMinutesPerWeek).toBeLessThan(
      normalResult.exercise.aerobicMinutesPerWeek
    );
  });

  it("imputes better diet for higher education", () => {
    const highSchool: ImputationInput = {
      age: 40,
      sex: "female",
      education: "high_school",
    };

    const college: ImputationInput = {
      age: 40,
      sex: "female",
      education: "college",
    };

    const hsResult = imputeBehaviors(highSchool);
    const collegeResult = imputeBehaviors(college);

    // College educated should have higher Mediterranean adherence
    expect(collegeResult.diet.mediterraneanAdherence).toBeGreaterThan(
      hsResult.diet.mediterraneanAdherence
    );
  });

  it("imputes higher alcohol for males vs females", () => {
    const male: ImputationInput = {
      age: 40,
      sex: "male",
    };

    const female: ImputationInput = {
      age: 40,
      sex: "female",
    };

    const maleResult = imputeBehaviors(male);
    const femaleResult = imputeBehaviors(female);

    // Males drink more on average
    expect(maleResult.alcohol.drinksPerWeek).toBeGreaterThan(
      femaleResult.alcohol.drinksPerWeek
    );
  });

  it("imputes higher alcohol for current smoker", () => {
    const nonSmoker: ImputationInput = {
      age: 40,
      sex: "male",
      smokingStatus: "never",
    };

    const smoker: ImputationInput = {
      age: 40,
      sex: "male",
      smokingStatus: "current",
    };

    const nonSmokerResult = imputeBehaviors(nonSmoker);
    const smokerResult = imputeBehaviors(smoker);

    // Smokers drink more
    expect(smokerResult.alcohol.drinksPerWeek).toBeGreaterThan(
      nonSmokerResult.alcohol.drinksPerWeek
    );
  });

  it("adjusts exercise for age", () => {
    const young: ImputationInput = {
      age: 30,
      sex: "male",
      bmi: 25,
    };

    const older: ImputationInput = {
      age: 70,
      sex: "male",
      bmi: 25,
    };

    const youngResult = imputeBehaviors(young);
    const olderResult = imputeBehaviors(older);

    // Older person exercises less
    expect(olderResult.exercise.aerobicMinutesPerWeek).toBeLessThan(
      youngResult.exercise.aerobicMinutesPerWeek
    );
  });
});

describe("Causal DAG", () => {
  it("identifies exercise causal effects", () => {
    const effects = getCausalEffects("exercise");

    expect(effects.length).toBeGreaterThan(0);

    // Exercise should affect BMI
    const bmiEffect = effects.find((e) => e.downstream === "bmi");
    expect(bmiEffect).toBeDefined();
    expect(bmiEffect?.effectSize).toBeLessThan(0); // negative = reduces BMI

    // Exercise should affect BP
    const bpEffect = effects.find((e) => e.downstream === "systolicBP");
    expect(bpEffect).toBeDefined();
    expect(bpEffect?.effectSize).toBeLessThan(0);

    // Exercise should affect HDL
    const hdlEffect = effects.find((e) => e.downstream === "hdlCholesterol");
    expect(hdlEffect).toBeDefined();
    expect(hdlEffect?.effectSize).toBeGreaterThan(0); // positive = increases HDL

    // All effects should have sources
    effects.forEach((effect) => {
      expect(effect.source).toBeDefined();
      expect(effect.source.length).toBeGreaterThan(0);
    });
  });

  it("identifies diet causal effects", () => {
    const effects = getCausalEffects("diet");

    expect(effects.length).toBeGreaterThan(0);

    // Diet should affect BMI
    const bmiEffect = effects.find((e) => e.downstream === "bmi");
    expect(bmiEffect).toBeDefined();

    // Diet should affect LDL
    const ldlEffect = effects.find((e) => e.downstream === "ldlCholesterol");
    expect(ldlEffect).toBeDefined();
    expect(ldlEffect?.effectSize).toBeLessThan(0); // reduces LDL
  });

  it("exercise does NOT causally affect diet", () => {
    // This is the key insight: they're correlated but not causal
    expect(isCausallyDownstream("exercise", "diet")).toBe(false);
    expect(isCausallyDownstream("exercise", "mediterraneanAdherence")).toBe(
      false
    );
  });

  it("diet does NOT causally affect exercise", () => {
    expect(isCausallyDownstream("diet", "exercise")).toBe(false);
    expect(isCausallyDownstream("diet", "aerobicMinutesPerWeek")).toBe(false);
  });

  it("exercise DOES causally affect sleep", () => {
    expect(isCausallyDownstream("exercise", "sleepHours")).toBe(true);

    const effects = getCausalEffects("exercise");
    const sleepEffect = effects.find((e) => e.downstream === "sleepHours");
    expect(sleepEffect).toBeDefined();
    expect(sleepEffect?.effectSize).toBeGreaterThan(0); // improves sleep
  });

  it("smoking cessation causes weight gain", () => {
    const effects = getCausalEffects("smoking_cessation");

    const bmiEffect = effects.find((e) => e.downstream === "bmi");
    expect(bmiEffect).toBeDefined();
    expect(bmiEffect?.effectSize).toBeGreaterThan(0); // positive = weight gain
  });

  it("returns empty array for unknown intervention", () => {
    const effects = getCausalEffects("unknown_intervention");
    expect(effects).toEqual([]);
  });
});

describe("imputeFullState", () => {
  it("creates valid PersonState from minimal input", () => {
    const input: ImputationInput = {
      age: 45,
      sex: "female",
    };

    const result = imputeFullState(input);

    // Should return a state
    expect(result.state).toBeDefined();
    expect(result.state.demographics.sex).toBe("female");

    // Should track what was imputed
    expect(result.imputedFields).toBeDefined();
    expect(result.imputedFields.length).toBeGreaterThan(0);

    // Should include behaviors
    expect(result.imputedFields).toContain("exercise");
    expect(result.imputedFields).toContain("diet");
    expect(result.imputedFields).toContain("alcohol");
    expect(result.imputedFields).toContain("sleep");
    expect(result.imputedFields).toContain("social");

    // Should have confidence scores
    expect(result.confidence).toBeDefined();
    expect(result.confidence.exercise).toBeGreaterThan(0);
    expect(result.confidence.exercise).toBeLessThanOrEqual(1);
  });

  it("uses observed BMI when provided", () => {
    const input: ImputationInput = {
      age: 45,
      sex: "male",
      bmi: 28,
    };

    const result = imputeFullState(input);

    expect(result.state.biomarkers.bmi).toBe(28);
    expect(result.imputedFields).not.toContain("bmi");
    expect(result.confidence.bmi).toBe(1.0); // observed = 100% confidence
  });

  it("uses observed smoking status when provided", () => {
    const input: ImputationInput = {
      age: 45,
      sex: "male",
      smokingStatus: "current",
    };

    const result = imputeFullState(input);

    expect(result.state.behaviors.smoking.status).toBe("current");
    expect(result.imputedFields).not.toContain("smokingStatus");
  });

  it("imputes with lower confidence when little info provided", () => {
    const minimal: ImputationInput = {
      age: 45,
      sex: "male",
    };

    const detailed: ImputationInput = {
      age: 45,
      sex: "male",
      bmi: 25,
      smokingStatus: "never",
      education: "college",
    };

    const minimalResult = imputeFullState(minimal);
    const detailedResult = imputeFullState(detailed);

    // More observations = higher average confidence
    const minimalAvgConfidence =
      Object.values(minimalResult.confidence).reduce((a, b) => a + b, 0) /
      Object.values(minimalResult.confidence).length;

    const detailedAvgConfidence =
      Object.values(detailedResult.confidence).reduce((a, b) => a + b, 0) /
      Object.values(detailedResult.confidence).length;

    expect(detailedAvgConfidence).toBeGreaterThan(minimalAvgConfidence);
  });

  it("creates state that passes validation", () => {
    const input: ImputationInput = {
      age: 35,
      sex: "female",
      bmi: 30,
    };

    const result = imputeFullState(input);

    // Import validateState to check
    const { validateState } = require("./state");
    const validation = validateState(result.state);

    expect(validation.valid).toBe(true);
    expect(validation.errors).toEqual([]);
  });
});
