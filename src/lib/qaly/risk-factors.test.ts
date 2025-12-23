import { describe, test, expect } from "vitest";
import {
  type RiskFactorHazard,
  type RiskContext,
  type HRWithUncertainty,
  type PersonState,
  type HazardRatioSet,
  RISK_FACTORS,
  getHazardRatiosForState,
  combineHazardRatios,
  getCauseSpecificHR,
} from "./risk-factors";

// Helper to extract point estimate from HazardValue
function getPoint(hr: number | HRWithUncertainty): number {
  return typeof hr === "number" ? hr : hr.point;
}

describe("Risk Factor Hazards", () => {
  describe("Smoking", () => {
    test("never smoker has HR = 1.0", () => {
      const smoking = RISK_FACTORS.smoking;
      expect(getPoint(smoking.getHazardRatio("never"))).toBe(1.0);
    });

    test("current heavy smoker has elevated HR", () => {
      const smoking = RISK_FACTORS.smoking;
      const hr = getPoint(smoking.getHazardRatio("current_21_plus"));
      expect(hr).toBeGreaterThan(2.5);
      expect(hr).toBeLessThan(3.0);
    });

    test("former smoker HR decreases with time since quit", () => {
      const smoking = RISK_FACTORS.smoking;
      const quit5 = getPoint(smoking.getHazardRatio("former_0_5_years"));
      const quit10 = getPoint(smoking.getHazardRatio("former_5_10_years"));
      const quit15 = getPoint(smoking.getHazardRatio("former_15_plus_years"));

      expect(quit5).toBeGreaterThan(quit10);
      expect(quit10).toBeGreaterThan(quit15);
      expect(quit15).toBeGreaterThan(1.0);
    });

    test("has uncertainty bounds", () => {
      const smoking = RISK_FACTORS.smoking;
      const hr = smoking.getHazardRatio("current_21_plus") as HRWithUncertainty;
      expect(hr.ci95Lower).toBeLessThan(hr.point);
      expect(hr.ci95Upper).toBeGreaterThan(hr.point);
    });
  });

  describe("BMI", () => {
    test("optimal BMI (20-22.5) has HR = 1.0", () => {
      const bmi = RISK_FACTORS.bmi;
      expect(getPoint(bmi.getHazardRatio(21))).toBe(1.0);
    });

    test("underweight has elevated HR", () => {
      const bmi = RISK_FACTORS.bmi;
      expect(getPoint(bmi.getHazardRatio(17))).toBeGreaterThan(1.4);
    });

    test("obesity has elevated HR", () => {
      const bmi = RISK_FACTORS.bmi;
      const obese = getPoint(bmi.getHazardRatio(32)); // BMI 30-35
      const severelyObese = getPoint(bmi.getHazardRatio(42)); // BMI 40+

      expect(obese).toBeGreaterThan(1.3);
      expect(severelyObese).toBeGreaterThan(2.5);
      expect(severelyObese).toBeGreaterThan(obese);
    });

    test("J-curve relationship", () => {
      const bmi = RISK_FACTORS.bmi;
      const optimal = getPoint(bmi.getHazardRatio(21));
      const low = getPoint(bmi.getHazardRatio(17));
      const high = getPoint(bmi.getHazardRatio(32));

      expect(low).toBeGreaterThan(optimal);
      expect(high).toBeGreaterThan(optimal);
    });
  });

  describe("Exercise", () => {
    test("150+ min/week is reference (HR = 1.0)", () => {
      const exercise = RISK_FACTORS.exercise;
      expect(getPoint(exercise.getHazardRatio(200))).toBe(1.0);
    });

    test("no exercise has elevated HR", () => {
      const exercise = RISK_FACTORS.exercise;
      expect(getPoint(exercise.getHazardRatio(0))).toBeGreaterThan(1.3);
    });

    test("very high exercise has protective effect", () => {
      const exercise = RISK_FACTORS.exercise;
      expect(getPoint(exercise.getHazardRatio(500))).toBeLessThan(1.0);
    });

    test("dose-response relationship", () => {
      const exercise = RISK_FACTORS.exercise;
      const none = getPoint(exercise.getHazardRatio(0));
      const some = getPoint(exercise.getHazardRatio(100));
      const recommended = getPoint(exercise.getHazardRatio(200));

      expect(none).toBeGreaterThan(some);
      expect(some).toBeGreaterThan(recommended);
    });
  });

  describe("Alcohol", () => {
    test("moderate consumption shows J-curve", () => {
      const alcohol = RISK_FACTORS.alcohol;
      const none = getPoint(alcohol.getHazardRatio(0));
      const moderate = getPoint(alcohol.getHazardRatio(5)); // 1-7 drinks/week
      const heavy = getPoint(alcohol.getHazardRatio(25)); // 22+ drinks/week

      expect(moderate).toBeLessThanOrEqual(none);
      expect(heavy).toBeGreaterThan(none);
      expect(heavy).toBeGreaterThan(1.3);
    });
  });

  describe("Sleep", () => {
    test("7-8 hours is optimal", () => {
      const sleep = RISK_FACTORS.sleep;
      expect(getPoint(sleep.getHazardRatio(7.5))).toBe(1.0);
    });

    test("U-shaped relationship", () => {
      const sleep = RISK_FACTORS.sleep;
      const short = getPoint(sleep.getHazardRatio(5));
      const optimal = getPoint(sleep.getHazardRatio(7.5));
      const long = getPoint(sleep.getHazardRatio(10));

      expect(short).toBeGreaterThan(optimal);
      expect(long).toBeGreaterThan(optimal);
    });
  });

  describe("Blood Pressure", () => {
    test("increases exponentially with SBP", () => {
      const bp = RISK_FACTORS.bloodPressure;
      const normal = getPoint(bp.getHazardRatio(120));
      const elevated = getPoint(bp.getHazardRatio(140));
      const high = getPoint(bp.getHazardRatio(160));

      expect(elevated).toBeGreaterThan(normal);
      expect(high).toBeGreaterThan(elevated);
      expect(high / elevated).toBeGreaterThan(elevated / normal); // Exponential
    });
  });

  describe("Diet", () => {
    test("Mediterranean diet score is protective", () => {
      const diet = RISK_FACTORS.mediterraneanDiet;
      const low = getPoint(diet.getHazardRatio(2)); // Low adherence
      const high = getPoint(diet.getHazardRatio(8)); // High adherence

      expect(high).toBeLessThan(low);
    });

    test("processed meat increases risk", () => {
      const meat = RISK_FACTORS.processedMeat;
      const none = getPoint(meat.getHazardRatio(0));
      const high = getPoint(meat.getHazardRatio(100)); // 100g/day

      expect(high).toBeGreaterThan(none);
    });

    test("fruits/vegetables are protective", () => {
      const produce = RISK_FACTORS.fruitsVegetables;
      const low = getPoint(produce.getHazardRatio(100)); // 100g/day
      const high = getPoint(produce.getHazardRatio(600)); // 600g/day

      expect(high).toBeLessThan(low);
    });
  });

  describe("Social Connection", () => {
    test("strong relationships are protective", () => {
      const social = RISK_FACTORS.socialConnection;
      expect(getPoint(social.getHazardRatio("strong"))).toBe(1.0);
    });

    test("isolation increases mortality risk", () => {
      const social = RISK_FACTORS.socialConnection;
      const isolated = getPoint(social.getHazardRatio("isolated"));

      expect(isolated).toBeGreaterThan(1.4);
    });

    test("dose-response relationship", () => {
      const social = RISK_FACTORS.socialConnection;
      const strong = getPoint(social.getHazardRatio("strong"));
      const moderate = getPoint(social.getHazardRatio("moderate"));
      const weak = getPoint(social.getHazardRatio("weak"));
      const isolated = getPoint(social.getHazardRatio("isolated"));

      expect(moderate).toBeGreaterThan(strong);
      expect(weak).toBeGreaterThan(moderate);
      expect(isolated).toBeGreaterThan(weak);
    });
  });

  describe("combineHazardRatios", () => {
    test("combines HRs multiplicatively", () => {
      const combined = combineHazardRatios([1.5, 2.0, 1.2]);
      expect(combined).toBeCloseTo(3.6, 2);
    });

    test("handles single HR", () => {
      expect(combineHazardRatios([1.5])).toBe(1.5);
    });

    test("handles empty array", () => {
      expect(combineHazardRatios([])).toBe(1.0);
    });

    test("handles reference values", () => {
      expect(combineHazardRatios([1.0, 1.0, 1.0])).toBe(1.0);
    });
  });

  describe("getHazardRatiosForState", () => {
    test("returns all applicable HRs for a person", () => {
      const state: PersonState = {
        age: 50,
        sex: "male",
        smokingStatus: "never",
        bmi: 25,
        exerciseMinutesPerWeek: 150,
        alcoholDrinksPerWeek: 5,
        sleepHoursPerNight: 7,
        systolicBP: 120,
        mediterraneanDietScore: 5,
        processedMeatGramsPerDay: 25,
        fruitsVegetablesGramsPerDay: 400,
        socialConnection: "strong",
      };

      const ratios = getHazardRatiosForState(state);

      expect(ratios.smoking).toBe(1.0);
      expect(ratios.bmi).toBeGreaterThan(1.0); // BMI 25 slightly elevated
      expect(ratios.exercise).toBe(1.0); // At recommended level
      expect(ratios.sleep).toBe(1.0); // Optimal sleep
      expect(ratios.social).toBe(1.0); // Strong relationships
    });

    test("handles extreme values", () => {
      const state: PersonState = {
        age: 50,
        sex: "male",
        smokingStatus: "current_21_plus",
        bmi: 42,
        exerciseMinutesPerWeek: 0,
        alcoholDrinksPerWeek: 30,
        sleepHoursPerNight: 5,
        systolicBP: 160,
        mediterraneanDietScore: 1,
        processedMeatGramsPerDay: 150,
        fruitsVegetablesGramsPerDay: 50,
        socialConnection: "isolated",
      };

      const ratios = getHazardRatiosForState(state);

      // All should be elevated
      expect(ratios.smoking).toBeGreaterThan(2.5);
      expect(ratios.bmi).toBeGreaterThan(2.5);
      expect(ratios.exercise).toBeGreaterThan(1.3);
      expect(ratios.social).toBeGreaterThan(1.4);
    });
  });

  describe("getCauseSpecificHR", () => {
    test("returns CVD-specific HR for blood pressure", () => {
      const state: PersonState = {
        age: 50,
        sex: "male",
        smokingStatus: "never",
        bmi: 25,
        exerciseMinutesPerWeek: 150,
        alcoholDrinksPerWeek: 5,
        sleepHoursPerNight: 7,
        systolicBP: 160,
        mediterraneanDietScore: 5,
        processedMeatGramsPerDay: 25,
        fruitsVegetablesGramsPerDay: 400,
        socialConnection: "strong",
      };

      const cvdHR = getCauseSpecificHR(state, "cvd");
      const allCauseHR = getCauseSpecificHR(state, "all-cause");

      // CVD HR should be higher for blood pressure
      expect(cvdHR).toBeGreaterThan(allCauseHR);
    });

    test("returns cancer-specific HR for smoking", () => {
      const state: PersonState = {
        age: 50,
        sex: "male",
        smokingStatus: "current_21_plus",
        bmi: 25,
        exerciseMinutesPerWeek: 150,
        alcoholDrinksPerWeek: 5,
        sleepHoursPerNight: 7,
        systolicBP: 120,
        mediterraneanDietScore: 5,
        processedMeatGramsPerDay: 25,
        fruitsVegetablesGramsPerDay: 400,
        socialConnection: "strong",
      };

      const cancerHR = getCauseSpecificHR(state, "cancer");

      // Smoking should substantially increase cancer risk
      expect(cancerHR).toBeGreaterThan(2.0);
    });
  });

  describe("Edge Cases", () => {
    test("handles extreme BMI values", () => {
      const bmi = RISK_FACTORS.bmi;
      expect(getPoint(bmi.getHazardRatio(15))).toBeGreaterThan(1.4); // Severe underweight
      expect(getPoint(bmi.getHazardRatio(50))).toBeGreaterThan(2.5); // Severe obesity
    });

    test("handles zero exercise", () => {
      const exercise = RISK_FACTORS.exercise;
      expect(getPoint(exercise.getHazardRatio(0))).toBeGreaterThan(1.0);
    });

    test("handles very high exercise", () => {
      const exercise = RISK_FACTORS.exercise;
      expect(getPoint(exercise.getHazardRatio(1000))).toBeLessThan(1.0);
    });

    test("handles extreme alcohol consumption", () => {
      const alcohol = RISK_FACTORS.alcohol;
      expect(getPoint(alcohol.getHazardRatio(100))).toBeGreaterThan(1.5);
    });
  });

  describe("Source Quality", () => {
    test("all risk factors have citations", () => {
      const factors = [
        RISK_FACTORS.smoking,
        RISK_FACTORS.bmi,
        RISK_FACTORS.exercise,
        RISK_FACTORS.alcohol,
        RISK_FACTORS.sleep,
        RISK_FACTORS.bloodPressure,
        RISK_FACTORS.mediterraneanDiet,
        RISK_FACTORS.processedMeat,
        RISK_FACTORS.fruitsVegetables,
        RISK_FACTORS.socialConnection,
      ];

      factors.forEach((factor) => {
        expect(factor.source.citation).toBeDefined();
        expect(factor.source.year).toBeGreaterThan(2000);
        expect(factor.source.studyType).toBeDefined();
      });
    });

    test("meta-analyses are preferred", () => {
      const factors = [
        RISK_FACTORS.smoking,
        RISK_FACTORS.bmi,
        RISK_FACTORS.exercise,
        RISK_FACTORS.sleep,
        RISK_FACTORS.socialConnection,
      ];

      factors.forEach((factor) => {
        expect(factor.source.studyType).toBe("meta-analysis");
      });
    });
  });
});
