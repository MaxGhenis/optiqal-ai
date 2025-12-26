import { describe, it, expect } from "vitest";
import {
  compareStates,
  computeInterventionImpact,
  compareInterventions,
  identifyStateChanges,
  type StateComparisonResult,
} from "./state-diff";
import { createDefaultState, updateState } from "./state";

describe("identifyStateChanges", () => {
  it("identifies single behavior change", () => {
    const stateA = createDefaultState(40, "male");
    const stateB = updateState(stateA, {
      behaviors: {
        exercise: {
          aerobicMinutesPerWeek: 300,
        },
      },
    });

    const changes = identifyStateChanges(stateA, stateB);

    expect(changes).toContainEqual({
      path: "behaviors.exercise.aerobicMinutesPerWeek",
      before: 150,
      after: 300,
    });
  });

  it("identifies multiple changes", () => {
    const stateA = createDefaultState(40, "male");
    const stateB = updateState(stateA, {
      behaviors: {
        smoking: {
          status: "former",
          packYears: 10,
          yearsQuit: 0,
        },
        exercise: {
          aerobicMinutesPerWeek: 210,
        },
      },
    });

    const changes = identifyStateChanges(stateA, stateB);

    expect(changes.length).toBeGreaterThanOrEqual(2);
    expect(changes.some((c) => c.path.includes("smoking.status"))).toBe(true);
    expect(changes.some((c) => c.path.includes("exercise.aerobicMinutesPerWeek"))).toBe(
      true
    );
  });

  it("returns empty array for identical states", () => {
    const stateA = createDefaultState(40, "male");
    const stateB = createDefaultState(40, "male");

    const changes = identifyStateChanges(stateA, stateB);

    expect(changes).toEqual([]);
  });

  it("identifies biomarker changes", () => {
    const stateA = createDefaultState(40, "male");
    const stateB = updateState(stateA, {
      biomarkers: {
        systolicBP: 140,
        bmi: 30,
      },
    });

    const changes = identifyStateChanges(stateA, stateB);

    expect(changes.some((c) => c.path === "biomarkers.systolicBP")).toBe(true);
    expect(changes.some((c) => c.path === "biomarkers.bmi")).toBe(true);
  });
});

describe("compareStates", () => {
  it("returns valid comparison result structure", () => {
    const stateA = createDefaultState(40, "male");
    const stateB = updateState(stateA, {
      behaviors: {
        exercise: {
          aerobicMinutesPerWeek: 300,
        },
      },
    });

    const result = compareStates(stateA, stateB, { nSimulations: 100 });

    // Check structure
    expect(result).toHaveProperty("qalyDifference");
    expect(result.qalyDifference).toHaveProperty("mean");
    expect(result.qalyDifference).toHaveProperty("median");
    expect(result.qalyDifference).toHaveProperty("ci95");
    expect(result.qalyDifference.ci95).toHaveProperty("low");
    expect(result.qalyDifference.ci95).toHaveProperty("high");

    expect(result).toHaveProperty("breakdown");
    expect(result.breakdown).toHaveProperty("mortalityQALYs");
    expect(result.breakdown).toHaveProperty("qualityQALYs");

    expect(result).toHaveProperty("lifeExpectancyDifference");
    expect(result).toHaveProperty("changedFactors");
    expect(result).toHaveProperty("probPositive");
    expect(result).toHaveProperty("probMoreThanOneYear");
    expect(result).toHaveProperty("trajectoryComparison");

    // Check that arrays are populated
    expect(Array.isArray(result.changedFactors)).toBe(true);
    expect(Array.isArray(result.trajectoryComparison)).toBe(true);

    // Check probability bounds
    expect(result.probPositive).toBeGreaterThanOrEqual(0);
    expect(result.probPositive).toBeLessThanOrEqual(1);
  });

  it("shows positive QALY impact from exercise increase", () => {
    const stateA = createDefaultState(40, "male");
    const stateB = updateState(stateA, {
      behaviors: {
        exercise: {
          aerobicMinutesPerWeek: 300,
        },
      },
    });

    const result = compareStates(stateA, stateB, { nSimulations: 1000 });

    // Exercise should improve QALYs
    expect(result.qalyDifference.mean).toBeGreaterThan(0);
    expect(result.probPositive).toBeGreaterThan(0.5);
  });

  it("shows large benefit from quitting smoking", () => {
    const stateSmoker = updateState(createDefaultState(40, "male"), {
      behaviors: {
        smoking: {
          status: "current",
          packYears: 20,
          cigarettesPerDay: 20,
        },
      },
    });

    const stateFormer = updateState(stateSmoker, {
      behaviors: {
        smoking: {
          status: "former",
          packYears: 20,
          yearsQuit: 0,
        },
      },
    });

    const result = compareStates(stateSmoker, stateFormer, {
      nSimulations: 1000,
    });

    // Quitting smoking should have large benefit
    expect(result.qalyDifference.mean).toBeGreaterThan(1);
    expect(result.probPositive).toBeGreaterThan(0.95);
    expect(result.lifeExpectancyDifference.mean).toBeGreaterThan(0);
  });

  it("identifies changed factors correctly", () => {
    const stateA = createDefaultState(40, "male");
    const stateB = updateState(stateA, {
      behaviors: {
        exercise: {
          aerobicMinutesPerWeek: 300,
        },
      },
    });

    const result = compareStates(stateA, stateB, { nSimulations: 100 });

    expect(result.changedFactors.length).toBeGreaterThan(0);
    expect(result.changedFactors[0]).toHaveProperty("factor");
    expect(result.changedFactors[0]).toHaveProperty("before");
    expect(result.changedFactors[0]).toHaveProperty("after");
    expect(result.changedFactors[0]).toHaveProperty("hazardRatioChange");
  });

  it("produces trajectory comparison data", () => {
    const stateA = createDefaultState(40, "male");
    const stateB = updateState(stateA, {
      behaviors: {
        exercise: {
          aerobicMinutesPerWeek: 300,
        },
      },
    });

    const result = compareStates(stateA, stateB, { nSimulations: 100 });

    expect(result.trajectoryComparison.length).toBeGreaterThan(0);
    expect(result.trajectoryComparison[0]).toHaveProperty("year");
    expect(result.trajectoryComparison[0]).toHaveProperty("age");
    expect(result.trajectoryComparison[0]).toHaveProperty("survivalA");
    expect(result.trajectoryComparison[0]).toHaveProperty("survivalB");
    expect(result.trajectoryComparison[0]).toHaveProperty("qalyA");
    expect(result.trajectoryComparison[0]).toHaveProperty("qalyB");

    // Survival should decrease over time
    const first = result.trajectoryComparison[0];
    const last = result.trajectoryComparison[result.trajectoryComparison.length - 1];
    expect(last.survivalA).toBeLessThan(first.survivalA);
  });
});

describe("computeInterventionImpact", () => {
  it("applies partial state update and computes impact", () => {
    const baseState = createDefaultState(40, "male");

    const result = computeInterventionImpact(
      baseState,
      {
        behaviors: {
          exercise: {
            aerobicMinutesPerWeek: 300,
          },
        },
      },
      { nSimulations: 100 }
    );

    expect(result.qalyDifference.mean).toBeGreaterThan(0);
    expect(result.changedFactors.length).toBeGreaterThan(0);
  });

  it("handles multiple behavior changes", () => {
    const baseState = createDefaultState(40, "male");

    const result = computeInterventionImpact(
      baseState,
      {
        behaviors: {
          exercise: {
            aerobicMinutesPerWeek: 300,
          },
          diet: {
            mediterraneanAdherence: 0.8,
          },
        },
      },
      { nSimulations: 100 }
    );

    expect(result.qalyDifference.mean).toBeGreaterThan(0);
    expect(result.changedFactors.length).toBeGreaterThanOrEqual(2);
  });
});

describe("compareInterventions", () => {
  it("compares multiple interventions against baseline", () => {
    // Start with a sedentary person (0 exercise) to see meaningful exercise benefit
    const baseState = updateState(createDefaultState(40, "male"), {
      behaviors: {
        exercise: {
          aerobicMinutesPerWeek: 0, // Sedentary baseline
          strengthSessionsPerWeek: 0,
        },
        diet: {
          mediterraneanAdherence: 0.3, // Low adherence baseline
        },
      },
    });

    const results = compareInterventions(
      baseState,
      {
        exercise_150min: {
          behaviors: {
            exercise: {
              aerobicMinutesPerWeek: 150, // CDC recommendation - HR changes from 1.4 to 1.0
            },
          },
        },
        mediterranean_diet: {
          behaviors: {
            diet: {
              mediterraneanAdherence: 0.8, // High adherence
            },
          },
        },
      },
      { nSimulations: 100 }
    );

    expect(Object.keys(results)).toContain("exercise_150min");
    expect(Object.keys(results)).toContain("mediterranean_diet");

    expect(results.exercise_150min.qalyDifference.mean).toBeDefined();
    expect(results.mediterranean_diet.qalyDifference.mean).toBeDefined();

    // Both should be positive (exercise: sedentary→active, diet: low→high adherence)
    expect(results.exercise_150min.qalyDifference.mean).toBeGreaterThan(0);
    expect(results.mediterranean_diet.qalyDifference.mean).toBeGreaterThan(0);
  });

  it("can compare smoking cessation vs exercise", () => {
    const smokerState = updateState(createDefaultState(40, "male"), {
      behaviors: {
        smoking: {
          status: "current",
          packYears: 20,
          cigarettesPerDay: 20,
        },
      },
    });

    const results = compareInterventions(
      smokerState,
      {
        quit_smoking: {
          behaviors: {
            smoking: {
              status: "former",
              packYears: 20,
              yearsQuit: 0,
            },
          },
        },
        exercise_300min: {
          behaviors: {
            exercise: {
              aerobicMinutesPerWeek: 300,
            },
          },
        },
      },
      { nSimulations: 200 }
    );

    // Smoking cessation should have larger impact than exercise
    expect(results.quit_smoking.qalyDifference.mean).toBeGreaterThan(
      results.exercise_300min.qalyDifference.mean
    );
  });
});

describe("edge cases and validation", () => {
  it("handles identical states gracefully", () => {
    const state = createDefaultState(40, "male");

    const result = compareStates(state, state, { nSimulations: 100 });

    expect(result.qalyDifference.mean).toBeCloseTo(0, 1);
    expect(result.lifeExpectancyDifference.mean).toBeCloseTo(0, 1);
    expect(result.changedFactors).toEqual([]);
  });

  it("respects custom simulation parameters", () => {
    // Start from sedentary baseline to see meaningful difference
    const stateA = updateState(createDefaultState(40, "male"), {
      behaviors: {
        exercise: {
          aerobicMinutesPerWeek: 0, // Sedentary - HR 1.4
          strengthSessionsPerWeek: 0,
        },
      },
    });
    const stateB = updateState(stateA, {
      behaviors: {
        exercise: {
          aerobicMinutesPerWeek: 300, // Active - HR 1.0
        },
      },
    });

    const resultLowSim = compareStates(stateA, stateB, { nSimulations: 50 });
    const resultHighSim = compareStates(stateA, stateB, { nSimulations: 500 });

    // Both should show positive benefit (HR drops from 1.4 to 1.0)
    expect(resultLowSim.qalyDifference.mean).toBeGreaterThan(0);
    expect(resultHighSim.qalyDifference.mean).toBeGreaterThan(0);

    // Results should be similar regardless of simulation count (deterministic for now)
    // Note: True Monte Carlo uncertainty propagation is TODO
    expect(Math.abs(resultLowSim.qalyDifference.mean - resultHighSim.qalyDifference.mean)).toBeLessThan(0.1);
  });

  it("applies discount rate when specified", () => {
    const stateA = createDefaultState(40, "male");
    const stateB = updateState(stateA, {
      behaviors: {
        exercise: {
          aerobicMinutesPerWeek: 300,
        },
      },
    });

    const resultNoDiscount = compareStates(stateA, stateB, {
      nSimulations: 100,
      discountRate: 0,
    });
    const resultWithDiscount = compareStates(stateA, stateB, {
      nSimulations: 100,
      discountRate: 0.03,
    });

    // Discounting should reduce total QALYs
    expect(resultWithDiscount.qalyDifference.mean).toBeLessThan(
      resultNoDiscount.qalyDifference.mean
    );
  });
});
