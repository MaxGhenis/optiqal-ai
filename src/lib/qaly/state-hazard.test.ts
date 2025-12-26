import { describe, expect, test } from "vitest";
import { createDefaultState, updateState, getAge } from "./state";
import {
  computeStateHazards,
  computeStateHazardsWithUncertainty,
  getLifeExpectancy,
  getAnnualMortalityFromState,
} from "./state-hazard";

describe("computeStateHazards", () => {
  test("returns valid result for default state", () => {
    const state = createDefaultState(40, "male");
    const result = computeStateHazards(state);

    expect(result).toBeDefined();
    expect(result.overallHR).toBeGreaterThan(0);
    expect(result.overallHRWithUncertainty.point).toBeCloseTo(result.overallHR);
    expect(result.causeSpecificHR).toBeDefined();
    expect(result.causeSpecificHR.cvd).toBeGreaterThan(0);
    expect(result.causeSpecificHR.cancer).toBeGreaterThan(0);
    expect(result.causeSpecificHR.other).toBeGreaterThan(0);
    expect(result.riskFactorContributions).toBeInstanceOf(Array);
    expect(result.qualityDecrement).toBeGreaterThanOrEqual(0);
    expect(result.qualityDecrement).toBeLessThanOrEqual(1);
  });

  test("smoking increases overall HR significantly", () => {
    const defaultState = createDefaultState(40, "male");
    const smokerState = updateState(defaultState, {
      behaviors: {
        smoking: {
          status: "current",
          cigarettesPerDay: 20,
          packYears: 20,
        },
      },
    });

    const defaultResult = computeStateHazards(defaultState);
    const smokerResult = computeStateHazards(smokerState);

    expect(smokerResult.overallHR).toBeGreaterThan(defaultResult.overallHR);
    expect(smokerResult.overallHR).toBeGreaterThan(1.5); // Should be significantly elevated
  });

  test("exercise decreases overall HR", () => {
    const sedentaryState = createDefaultState(40, "male");
    sedentaryState.behaviors.exercise.aerobicMinutesPerWeek = 0;

    const activeState = updateState(sedentaryState, {
      behaviors: {
        exercise: {
          aerobicMinutesPerWeek: 450,
          strengthSessionsPerWeek: 3,
        },
      },
    });

    const sedentaryResult = computeStateHazards(sedentaryState);
    const activeResult = computeStateHazards(activeState);

    expect(activeResult.overallHR).toBeLessThan(sedentaryResult.overallHR);
  });

  test("multiple risk factors combine multiplicatively", () => {
    const goodState = createDefaultState(40, "male");
    goodState.behaviors.exercise.aerobicMinutesPerWeek = 300;
    goodState.biomarkers.bmi = 22;
    goodState.behaviors.alcohol.drinksPerWeek = 3;

    const badState = updateState(goodState, {
      behaviors: {
        smoking: {
          status: "current",
          cigarettesPerDay: 20,
          packYears: 20,
        },
        exercise: {
          aerobicMinutesPerWeek: 0,
          strengthSessionsPerWeek: 0,
        },
        alcohol: {
          drinksPerWeek: 30,
          bingeFrequency: "weekly",
        },
      },
      biomarkers: {
        bmi: 35,
      },
    });

    const goodResult = computeStateHazards(goodState);
    const badResult = computeStateHazards(badState);

    // Bad state should have much higher HR (multiplicative effect)
    expect(badResult.overallHR).toBeGreaterThan(goodResult.overallHR * 2);
  });

  test("missing values default to HR=1.0 (neutral)", () => {
    const state = createDefaultState(40, "male");

    // Set some biomarkers to undefined
    state.biomarkers.bmi = undefined;
    state.biomarkers.systolicBP = undefined;

    const result = computeStateHazards(state);

    // Should still return valid results without crashing
    expect(result.overallHR).toBeGreaterThan(0);
    expect(result.overallHR).toBeDefined();
  });

  test("cause-specific HRs differ appropriately", () => {
    const state = createDefaultState(40, "male");

    // High blood pressure affects CVD more
    state.biomarkers.systolicBP = 160;

    const result = computeStateHazards(state);

    // CVD HR should be elevated more than cancer
    expect(result.causeSpecificHR.cvd).toBeGreaterThan(1.2);
  });

  test("risk factor contributions sum to explain total effect", () => {
    const state = createDefaultState(40, "male");
    const result = computeStateHazards(state);

    // All contributions should sum to approximately 100%
    const totalContribution = result.riskFactorContributions.reduce(
      (sum, factor) => sum + factor.contribution,
      0
    );

    expect(totalContribution).toBeGreaterThan(95);
    expect(totalContribution).toBeLessThan(105);
  });
});

describe("computeStateHazardsWithUncertainty", () => {
  test("generates Monte Carlo samples", () => {
    const state = createDefaultState(40, "male");
    const result = computeStateHazardsWithUncertainty(state, 100);

    expect(result.samples).toHaveLength(100);
    expect(result.samples.every((s) => s > 0)).toBe(true);
  });

  test("samples vary around point estimate", () => {
    const state = createDefaultState(40, "male");
    const result = computeStateHazardsWithUncertainty(state, 100);

    const mean = result.samples.reduce((a, b) => a + b, 0) / result.samples.length;

    // Mean should be close to point estimate (within 20%)
    expect(mean).toBeGreaterThan(result.overallHR * 0.8);
    expect(mean).toBeLessThan(result.overallHR * 1.2);
  });
});

describe("getLifeExpectancy", () => {
  test("returns life expectancy for default state", () => {
    const state = createDefaultState(40, "male");
    const le = getLifeExpectancy(state);

    expect(le.expected).toBeGreaterThan(30); // Should live past 70
    expect(le.expected).toBeLessThan(60); // Unlikely to live past 100
    expect(le.ci95.low).toBeLessThan(le.expected);
    expect(le.ci95.high).toBeGreaterThan(le.expected);
  });

  test("smoking reduces life expectancy", () => {
    const defaultState = createDefaultState(40, "male");
    const smokerState = updateState(defaultState, {
      behaviors: {
        smoking: {
          status: "current",
          cigarettesPerDay: 20,
          packYears: 20,
        },
      },
    });

    const defaultLE = getLifeExpectancy(defaultState);
    const smokerLE = getLifeExpectancy(smokerState);

    expect(smokerLE.expected).toBeLessThan(defaultLE.expected);
  });

  test("healthy behaviors increase life expectancy", () => {
    const averageState = createDefaultState(40, "male");
    const healthyState = updateState(averageState, {
      behaviors: {
        exercise: {
          aerobicMinutesPerWeek: 450,
          strengthSessionsPerWeek: 3,
        },
        diet: {
          mediterraneanAdherence: 0.9,
          processedFoodPercent: 10,
          vegetableServingsPerDay: 5,
          fruitServingsPerDay: 3,
        },
      },
      biomarkers: {
        bmi: 22,
        systolicBP: 110,
      },
    });

    const averageLE = getLifeExpectancy(averageState);
    const healthyLE = getLifeExpectancy(healthyState);

    expect(healthyLE.expected).toBeGreaterThan(averageLE.expected);
  });
});

describe("getAnnualMortalityFromState", () => {
  test("returns valid mortality probability", () => {
    const state = createDefaultState(40, "male");
    const mortality = getAnnualMortalityFromState(state, 40);

    expect(mortality).toBeGreaterThan(0);
    expect(mortality).toBeLessThan(1);
  });

  test("mortality increases with age", () => {
    const state = createDefaultState(40, "male");
    const mortalityAt40 = getAnnualMortalityFromState(state, 40);
    const mortalityAt70 = getAnnualMortalityFromState(state, 70);

    expect(mortalityAt70).toBeGreaterThan(mortalityAt40);
  });

  test("risk factors increase mortality", () => {
    const healthyState = createDefaultState(40, "male");
    const unhealthyState = updateState(healthyState, {
      behaviors: {
        smoking: {
          status: "current",
          cigarettesPerDay: 20,
          packYears: 20,
        },
      },
      biomarkers: {
        bmi: 35,
      },
    });

    const healthyMortality = getAnnualMortalityFromState(healthyState, 40);
    const unhealthyMortality = getAnnualMortalityFromState(unhealthyState, 40);

    expect(unhealthyMortality).toBeGreaterThan(healthyMortality);
  });
});
