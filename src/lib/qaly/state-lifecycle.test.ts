/**
 * Tests for state-based lifecycle simulator
 */

import { describe, it, expect } from "vitest";
import {
  simulateLifecycleFromState,
  getQualityWeightFromState,
  getBaseQualityByAge,
} from "./state-lifecycle";
import { createDefaultState } from "./state";

describe("State Lifecycle Simulator", () => {
  describe("simulateLifecycleFromState", () => {
    it("returns valid result structure", () => {
      const state = createDefaultState(25, "male");
      const result = simulateLifecycleFromState(state);

      expect(result).toHaveProperty("expectedQALYs");
      expect(result).toHaveProperty("expectedLifeYears");
      expect(result).toHaveProperty("qalyDistribution");
      expect(result).toHaveProperty("trajectory");
      expect(result).toHaveProperty("lifeExpectancy");

      expect(result.expectedQALYs).toBeGreaterThan(0);
      expect(result.expectedLifeYears).toBeGreaterThan(0);
      expect(result.trajectory.length).toBeGreaterThan(0);
    });

    it("younger person has more QALYs than older", () => {
      const young = createDefaultState(25, "male");
      const old = createDefaultState(65, "male");

      const youngResult = simulateLifecycleFromState(young, {
        nSimulations: 100,
      });
      const oldResult = simulateLifecycleFromState(old, { nSimulations: 100 });

      expect(youngResult.expectedQALYs).toBeGreaterThan(oldResult.expectedQALYs);
      expect(youngResult.expectedLifeYears).toBeGreaterThan(
        oldResult.expectedLifeYears
      );
    });

    it("healthier behaviors increase QALYs", () => {
      const average = createDefaultState(40, "female");
      const healthy = createDefaultState(40, "female");

      // Make the healthy person more active
      healthy.behaviors.exercise.aerobicMinutesPerWeek = 300;
      healthy.behaviors.exercise.strengthSessionsPerWeek = 3;

      const averageResult = simulateLifecycleFromState(average, {
        nSimulations: 100,
      });
      const healthyResult = simulateLifecycleFromState(healthy, {
        nSimulations: 100,
      });

      expect(healthyResult.expectedQALYs).toBeGreaterThan(
        averageResult.expectedQALYs
      );
    });

    it("conditions decrease QALYs", () => {
      const healthy = createDefaultState(50, "male");
      const withConditions = createDefaultState(50, "male");

      // Add diabetes
      withConditions.conditions.push({
        type: "diabetes",
        severity: "moderate",
        controlled: true,
      });

      const healthyResult = simulateLifecycleFromState(healthy, {
        nSimulations: 100,
      });
      const conditionsResult = simulateLifecycleFromState(withConditions, {
        nSimulations: 100,
      });

      expect(healthyResult.expectedQALYs).toBeGreaterThan(
        conditionsResult.expectedQALYs
      );
    });

    it("Monte Carlo produces distribution with CI", () => {
      const state = createDefaultState(30, "female");
      const result = simulateLifecycleFromState(state, { nSimulations: 500 });

      expect(result.qalyDistribution.mean).toBeGreaterThan(0);
      expect(result.qalyDistribution.median).toBeGreaterThan(0);
      expect(result.qalyDistribution.ci95.low).toBeLessThan(
        result.qalyDistribution.mean
      );
      expect(result.qalyDistribution.ci95.high).toBeGreaterThan(
        result.qalyDistribution.mean
      );
      expect(result.qalyDistribution.percentiles.length).toBeGreaterThan(0);
    });

    it("discounting reduces QALY values", () => {
      const state = createDefaultState(35, "male");

      const noDiscount = simulateLifecycleFromState(state, {
        discountRate: 0,
        nSimulations: 100,
      });
      const withDiscount = simulateLifecycleFromState(state, {
        discountRate: 0.03,
        nSimulations: 100,
      });

      expect(noDiscount.expectedQALYs).toBeGreaterThan(
        withDiscount.expectedQALYs
      );
    });

    it("trajectory has correct structure", () => {
      const state = createDefaultState(30, "male");
      const result = simulateLifecycleFromState(state, {
        maxAge: 50,
        nSimulations: 100,
      });

      const firstYear = result.trajectory[0];
      expect(firstYear).toHaveProperty("year");
      expect(firstYear).toHaveProperty("age");
      expect(firstYear).toHaveProperty("survivalProb");
      expect(firstYear).toHaveProperty("cumulativeSurvival");
      expect(firstYear).toHaveProperty("qualityWeight");
      expect(firstYear).toHaveProperty("qalyThisYear");
      expect(firstYear).toHaveProperty("cumulativeQALY");

      expect(firstYear.age).toBe(30);
      expect(firstYear.survivalProb).toBeGreaterThan(0.9);
      expect(firstYear.qualityWeight).toBeGreaterThan(0);
      expect(firstYear.qualityWeight).toBeLessThanOrEqual(1);
    });

    it("life expectancy has valid CI", () => {
      const state = createDefaultState(45, "female");
      const result = simulateLifecycleFromState(state, { nSimulations: 500 });

      expect(result.lifeExpectancy.expected).toBeGreaterThan(0);
      expect(result.lifeExpectancy.ci95.low).toBeLessThan(
        result.lifeExpectancy.expected
      );
      expect(result.lifeExpectancy.ci95.high).toBeGreaterThan(
        result.lifeExpectancy.expected
      );
    });

    it("smoking decreases QALYs", () => {
      const nonsmoker = createDefaultState(35, "male");
      const smoker = createDefaultState(35, "male");

      smoker.behaviors.smoking.status = "current";
      smoker.behaviors.smoking.cigarettesPerDay = 15;

      const nonsmokerResult = simulateLifecycleFromState(nonsmoker, {
        nSimulations: 100,
      });
      const smokerResult = simulateLifecycleFromState(smoker, {
        nSimulations: 100,
      });

      expect(nonsmokerResult.expectedQALYs).toBeGreaterThan(
        smokerResult.expectedQALYs
      );
    });
  });

  describe("getQualityWeightFromState", () => {
    it("returns value between 0 and 1", () => {
      const state = createDefaultState(30, "male");
      const quality = getQualityWeightFromState(state, 30);

      expect(quality).toBeGreaterThan(0);
      expect(quality).toBeLessThanOrEqual(1);
    });

    it("quality decreases with conditions", () => {
      const healthy = createDefaultState(40, "female");
      const withConditions = createDefaultState(40, "female");

      withConditions.conditions.push({
        type: "diabetes",
        severity: "moderate",
        controlled: true,
      });

      const healthyQuality = getQualityWeightFromState(healthy, 40);
      const conditionsQuality = getQualityWeightFromState(
        withConditions,
        40
      );

      expect(healthyQuality).toBeGreaterThan(conditionsQuality);
    });

    it("exercise increases quality", () => {
      const sedentary = createDefaultState(35, "male");
      sedentary.behaviors.exercise.aerobicMinutesPerWeek = 0;

      const active = createDefaultState(35, "male");
      active.behaviors.exercise.aerobicMinutesPerWeek = 300;

      const sedentaryQuality = getQualityWeightFromState(sedentary, 35);
      const activeQuality = getQualityWeightFromState(active, 35);

      expect(activeQuality).toBeGreaterThan(sedentaryQuality);
    });

    it("poor sleep decreases quality", () => {
      const goodSleep = createDefaultState(30, "female");
      goodSleep.behaviors.sleep.hoursPerNight = 7.5;
      goodSleep.behaviors.sleep.quality = "good";

      const poorSleep = createDefaultState(30, "female");
      poorSleep.behaviors.sleep.hoursPerNight = 5;
      poorSleep.behaviors.sleep.quality = "poor";

      const goodQuality = getQualityWeightFromState(goodSleep, 30);
      const poorQuality = getQualityWeightFromState(poorSleep, 30);

      expect(goodQuality).toBeGreaterThan(poorQuality);
    });
  });

  describe("getBaseQualityByAge", () => {
    it("quality decreases with age", () => {
      const young = getBaseQualityByAge(25);
      const middle = getBaseQualityByAge(50);
      const old = getBaseQualityByAge(85);

      expect(young).toBeGreaterThan(middle);
      expect(middle).toBeGreaterThan(old);
    });

    it("returns reasonable values", () => {
      const quality40 = getBaseQualityByAge(40);
      expect(quality40).toBeGreaterThan(0.7);
      expect(quality40).toBeLessThan(1.0);
    });
  });
});
