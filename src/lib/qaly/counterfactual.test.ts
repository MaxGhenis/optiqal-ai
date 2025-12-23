/**
 * Tests for counterfactual simulation with imputation-based causal inference
 */

import { describe, it, expect } from "vitest";
import { simulateCausalIntervention } from "./counterfactual";

describe("Counterfactual Simulation", () => {
  it("should return valid result structure", () => {
    const result = simulateCausalIntervention(
      { age: 40, sex: "male", bmi: 32 },
      {
        variable: "exercise",
        change: { exercise: { aerobicMinutesPerWeek: 150 } },
      },
      { nSimulations: 100 }
    );

    expect(result).toHaveProperty("causalEffect");
    expect(result).toHaveProperty("naiveEffect");
    expect(result).toHaveProperty("confoundingAbsorbed");
    expect(result).toHaveProperty("baselineState");
    expect(result).toHaveProperty("counterfactualState");
    expect(result).toHaveProperty("naiveComparisonState");
    expect(result).toHaveProperty("causalChanges");
    expect(result).toHaveProperty("heldFixed");

    expect(result.causalEffect).toHaveProperty("mean");
    expect(result.causalEffect).toHaveProperty("ci95");
    expect(result.naiveEffect).toHaveProperty("mean");
    expect(result.naiveEffect).toHaveProperty("ci95");
  });

  it("should show causal effect <= naive effect (confounding absorbed)", () => {
    const result = simulateCausalIntervention(
      { age: 40, sex: "male", bmi: 32 },
      {
        variable: "exercise",
        change: { exercise: { aerobicMinutesPerWeek: 150 } },
      },
      { nSimulations: 100 }
    );

    // Causal effect should be smaller than naive effect
    // because naive comparison includes confounding from correlated behaviors
    expect(result.causalEffect.mean).toBeLessThanOrEqual(
      result.naiveEffect.mean
    );
    expect(result.confoundingAbsorbed).toBeGreaterThanOrEqual(0);
  });

  it("should NOT change diet in counterfactual when intervening on exercise", () => {
    const result = simulateCausalIntervention(
      { age: 40, sex: "male", bmi: 32 },
      {
        variable: "exercise",
        change: { exercise: { aerobicMinutesPerWeek: 150 } },
      },
      { nSimulations: 100 }
    );

    // Diet should be held fixed (same in baseline and counterfactual)
    expect(
      result.baselineState.behaviors.diet.mediterraneanAdherence
    ).toEqual(
      result.counterfactualState.behaviors.diet.mediterraneanAdherence
    );

    // But naive comparison state should have different (better) diet
    expect(
      result.naiveComparisonState.behaviors.diet.mediterraneanAdherence
    ).toBeGreaterThan(
      result.baselineState.behaviors.diet.mediterraneanAdherence
    );
  });

  it("should impute different baseline for obese vs lean person", () => {
    const obeseResult = simulateCausalIntervention(
      { age: 40, sex: "male", bmi: 32 },
      {
        variable: "exercise",
        change: { exercise: { aerobicMinutesPerWeek: 150 } },
      },
      { nSimulations: 100 }
    );

    const leanResult = simulateCausalIntervention(
      { age: 40, sex: "male", bmi: 22 },
      {
        variable: "exercise",
        change: { exercise: { aerobicMinutesPerWeek: 150 } },
      },
      { nSimulations: 100 }
    );

    // Obese person should have imputed worse diet/exercise at baseline
    expect(
      obeseResult.baselineState.behaviors.diet.mediterraneanAdherence
    ).toBeLessThan(
      leanResult.baselineState.behaviors.diet.mediterraneanAdherence
    );

    expect(
      obeseResult.baselineState.behaviors.exercise.aerobicMinutesPerWeek
    ).toBeLessThan(
      leanResult.baselineState.behaviors.exercise.aerobicMinutesPerWeek
    );
  });

  it("should propagate causal downstream effects (exercise → BMI reduction)", () => {
    const result = simulateCausalIntervention(
      { age: 40, sex: "male", bmi: 32 },
      {
        variable: "exercise",
        change: { exercise: { aerobicMinutesPerWeek: 150 } },
      },
      { nSimulations: 100, propagateCausalEffects: true }
    );

    // Exercise should cause BMI reduction
    expect(result.counterfactualState.biomarkers.bmi).toBeLessThan(
      result.baselineState.biomarkers.bmi
    );

    // Should be in causalChanges
    const bmiChange = result.causalChanges.find(
      (c) => c.variable === "biomarkers.bmi"
    );
    expect(bmiChange).toBeDefined();
    expect(bmiChange?.after).toBeLessThan(bmiChange?.before || 0);
  });

  it("should NOT propagate causal effects when disabled", () => {
    const result = simulateCausalIntervention(
      { age: 40, sex: "male", bmi: 32 },
      {
        variable: "exercise",
        change: { exercise: { aerobicMinutesPerWeek: 150 } },
      },
      { nSimulations: 100, propagateCausalEffects: false }
    );

    // BMI should stay the same when propagation is disabled
    expect(result.counterfactualState.biomarkers.bmi).toEqual(
      result.baselineState.biomarkers.bmi
    );
  });

  it("should handle smoking intervention", () => {
    const result = simulateCausalIntervention(
      { age: 50, sex: "female", smokingStatus: "current" },
      {
        variable: "smoking",
        change: { smoking: { status: "never" } },
      },
      { nSimulations: 100 }
    );

    expect(result.baselineState.behaviors.smoking.status).toBe("current");
    expect(result.counterfactualState.behaviors.smoking.status).toBe("never");
    expect(result.causalEffect.mean).toBeGreaterThan(0);
  });

  it("should handle diet intervention", () => {
    const result = simulateCausalIntervention(
      { age: 45, sex: "male", bmi: 28 },
      {
        variable: "diet",
        change: {
          diet: {
            mediterraneanAdherence: 0.8,
            vegetableServingsPerDay: 5,
          },
        },
      },
      { nSimulations: 100 }
    );

    expect(
      result.counterfactualState.behaviors.diet.mediterraneanAdherence
    ).toBe(0.8);
    expect(result.counterfactualState.behaviors.diet.vegetableServingsPerDay).toBe(5);
    expect(result.causalEffect.mean).toBeGreaterThan(0);
  });
});
