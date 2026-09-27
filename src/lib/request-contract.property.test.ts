import { describe, expect, it } from "vitest";
import fc from "fast-check";
import { parseBaselineRequest } from "@/lib/baseline-contract";
import { parseFrontierRequest } from "@/lib/frontier-contract";

/**
 * Request-contract invariants (kept from the 2026-09-25 invariants audit):
 * profile normalization is idempotent and agrees across endpoints, ages
 * outside [0, 120] are rejected by both endpoints, and duplicate routine ids
 * never reach the model.
 */

const SEED = 20260925;
const RUNS = 300;

const validProfile = fc.record(
  {
    age: fc.double({ min: 0, max: 120, noNaN: true }).map((value) => value + 0),
    sex: fc.constantFrom("male" as const, "female" as const, "other" as const),
    weight_kg: fc.double({ min: 20, max: 500, noNaN: true }),
    height_cm: fc.double({ min: 50, max: 275, noNaN: true }),
    smoker: fc.boolean(),
    has_diabetes: fc.boolean(),
    has_hypertension: fc.boolean(),
    activity_level: fc.constantFrom(
      "sedentary" as const,
      "light" as const,
      "moderate" as const,
      "active" as const
    ),
    sleep_hours_per_night: fc.oneof(
      fc.constant(null),
      fc.double({ min: 0, max: 24, noNaN: true }).map((value) => value + 0)
    ),
  },
  { requiredKeys: [
    "age",
    "sex",
    "weight_kg",
    "height_cm",
    "smoker",
    "has_diabetes",
    "has_hypertension",
    "activity_level",
  ] }
);

const fixedProfile = {
  age: 35,
  sex: "male",
  weight_kg: 75,
  height_cm: 175,
  smoker: false,
  has_diabetes: false,
  has_hypertension: false,
  activity_level: "light",
  sleep_hours_per_night: 7,
};

describe("request contract properties", () => {
  it("keeps every valid profile field, agrees across endpoints and is idempotent", () => {
    fc.assert(
      fc.property(validProfile, (profile) => {
        const baseline = parseBaselineRequest({ profile });
        const frontier = parseFrontierRequest({ profile });
        expect(baseline).toEqual({ profile });
        expect(frontier).toEqual(baseline);
        expect(parseBaselineRequest(baseline)).toEqual(baseline);
        expect(parseFrontierRequest(frontier)).toEqual(frontier);
        expect(parseFrontierRequest(JSON.parse(JSON.stringify(frontier)))).toEqual(frontier);
      }),
      { seed: SEED, numRuns: RUNS }
    );
  });

  it("rejects ages outside [0, 120] and non-finite ages at both endpoints", () => {
    const outOfRange = fc.oneof(
      fc.double({ max: -Number.MIN_VALUE, noNaN: true }),
      fc.double({ min: 120, minExcluded: true, noNaN: true }),
      fc.constantFrom(NaN, "35", null)
    );
    fc.assert(
      fc.property(outOfRange, (age) => {
        const request = { profile: { ...fixedProfile, age } };
        expect(parseBaselineRequest(request)).toBeNull();
        expect(parseFrontierRequest(request)).toBeNull();
      }),
      { seed: SEED, numRuns: RUNS }
    );
  });

  it("rejects any routine that lists the same intervention id twice", () => {
    const id = fc.string({ minLength: 1, maxLength: 20 });
    fc.assert(
      fc.property(fc.uniqueArray(id, { maxLength: 10 }), id, (others, duplicate) => {
        const ids = [...others, duplicate, duplicate];
        expect(
          parseFrontierRequest({ profile: fixedProfile, current_stack_ids: ids })
        ).toBeNull();
      }),
      { seed: SEED, numRuns: RUNS }
    );
  });
});
