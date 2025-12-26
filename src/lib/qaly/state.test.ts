import { describe, it, expect } from "vitest";
import {
  type PersonState,
  createDefaultState,
  updateState,
  getAge,
  validateState,
} from "./state";

describe("createDefaultState", () => {
  it("creates valid default state for 30 year old male", () => {
    const state = createDefaultState(30, "male");

    expect(state.demographics.sex).toBe("male");
    expect(state.demographics.birthYear).toBe(new Date().getFullYear() - 30);
    expect(state.conditions).toEqual([]);
    expect(state.behaviors.exercise.aerobicMinutesPerWeek).toBeGreaterThan(0);
    expect(state.behaviors.smoking.status).toBe("never");
  });

  it("creates valid default state for 50 year old female", () => {
    const state = createDefaultState(50, "female");

    expect(state.demographics.sex).toBe("female");
    expect(state.demographics.birthYear).toBe(new Date().getFullYear() - 50);
    expect(state.conditions).toEqual([]);
  });

  it("creates default biomarkers within normal range", () => {
    const state = createDefaultState(40, "male");

    // Check some key biomarkers are present and reasonable
    expect(state.biomarkers.systolicBP).toBeGreaterThanOrEqual(90);
    expect(state.biomarkers.systolicBP).toBeLessThanOrEqual(140);
    expect(state.biomarkers.bmi).toBeGreaterThanOrEqual(18);
    expect(state.biomarkers.bmi).toBeLessThanOrEqual(30);
  });
});

describe("updateState", () => {
  it("merges partial state update", () => {
    const state = createDefaultState(40, "male");
    const updated = updateState(state, {
      behaviors: {
        exercise: {
          aerobicMinutesPerWeek: 300,
        },
      },
    });

    expect(updated.behaviors.exercise.aerobicMinutesPerWeek).toBe(300);
    // Other fields should be preserved
    expect(updated.behaviors.exercise.strengthSessionsPerWeek).toBe(
      state.behaviors.exercise.strengthSessionsPerWeek
    );
    expect(updated.demographics.sex).toBe("male");
  });

  it("adds new condition", () => {
    const state = createDefaultState(50, "female");
    const updated = updateState(state, {
      conditions: [
        { type: "hypertension", controlled: true, yearDiagnosed: 2020 },
      ],
    });

    expect(updated.conditions).toHaveLength(1);
    expect(updated.conditions[0].type).toBe("hypertension");
    expect(updated.conditions[0].controlled).toBe(true);
  });

  it("updates biomarker", () => {
    const state = createDefaultState(45, "male");
    const updated = updateState(state, {
      biomarkers: {
        systolicBP: 150,
      },
    });

    expect(updated.biomarkers.systolicBP).toBe(150);
    // Other biomarkers preserved
    expect(updated.biomarkers.bmi).toBe(state.biomarkers.bmi);
  });

  it("updates nested behavior", () => {
    const state = createDefaultState(35, "female");
    const updated = updateState(state, {
      behaviors: {
        smoking: {
          status: "former",
          packYears: 5,
          yearsQuit: 2,
        },
      },
    });

    expect(updated.behaviors.smoking.status).toBe("former");
    expect(updated.behaviors.smoking.packYears).toBe(5);
    expect(updated.behaviors.smoking.yearsQuit).toBe(2);
  });
});

describe("getAge", () => {
  it("calculates current age from birthYear", () => {
    const currentYear = new Date().getFullYear();
    const state = createDefaultState(40, "male");

    const age = getAge(state);
    expect(age).toBe(40);
  });

  it("calculates age for a specific year", () => {
    const state = createDefaultState(40, "male");
    const futureYear = new Date().getFullYear() + 10;

    const age = getAge(state, futureYear);
    expect(age).toBe(50);
  });

  it("calculates age for past year", () => {
    const state = createDefaultState(40, "male");
    const pastYear = new Date().getFullYear() - 5;

    const age = getAge(state, pastYear);
    expect(age).toBe(35);
  });
});

describe("validateState", () => {
  it("validates valid state", () => {
    const state = createDefaultState(40, "male");
    const result = validateState(state);

    expect(result.valid).toBe(true);
    expect(result.errors).toEqual([]);
  });

  it("catches impossible BMI", () => {
    const state = createDefaultState(40, "male");
    const invalid = updateState(state, {
      biomarkers: {
        bmi: 100,
      },
    });

    const result = validateState(invalid);
    expect(result.valid).toBe(false);
    expect(result.errors).toContain("BMI out of reasonable range (10-80)");
  });

  it("catches impossible blood pressure", () => {
    const state = createDefaultState(40, "male");
    const invalid = updateState(state, {
      biomarkers: {
        systolicBP: 300,
      },
    });

    const result = validateState(invalid);
    expect(result.valid).toBe(false);
    expect(result.errors).toContain("Systolic BP out of reasonable range (60-250)");
  });

  it("catches smoking status without required fields", () => {
    const state = createDefaultState(40, "male");
    const invalid = updateState(state, {
      behaviors: {
        smoking: {
          status: "former",
          // missing packYears and yearsQuit
        },
      },
    });

    const result = validateState(invalid);
    expect(result.valid).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
  });

  it("catches current smoking without cigarettesPerDay", () => {
    const state = createDefaultState(40, "male");
    const invalid = updateState(state, {
      behaviors: {
        smoking: {
          status: "current",
          // missing cigarettesPerDay
        },
      },
    });

    const result = validateState(invalid);
    expect(result.valid).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
  });

  it("catches negative exercise minutes", () => {
    const state = createDefaultState(40, "male");
    const invalid = updateState(state, {
      behaviors: {
        exercise: {
          aerobicMinutesPerWeek: -10,
        },
      },
    });

    const result = validateState(invalid);
    expect(result.valid).toBe(false);
    expect(result.errors).toContain("Exercise minutes cannot be negative");
  });

  it("allows valid former smoker", () => {
    const state = createDefaultState(40, "male");
    const valid = updateState(state, {
      behaviors: {
        smoking: {
          status: "former",
          packYears: 10,
          yearsQuit: 5,
        },
      },
    });

    const result = validateState(valid);
    expect(result.valid).toBe(true);
  });

  it("allows valid current smoker", () => {
    const state = createDefaultState(40, "male");
    const valid = updateState(state, {
      behaviors: {
        smoking: {
          status: "current",
          packYears: 5,
          cigarettesPerDay: 10,
        },
      },
    });

    const result = validateState(valid);
    expect(result.valid).toBe(true);
  });
});
