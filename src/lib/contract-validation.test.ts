import { describe, expect, it } from "vitest";
import fc from "fast-check";
import {
  INVALID,
  OUTCOME_PROBABILITY_SUM_TOLERANCE,
  parseOptionalConfidenceInterval,
  parseOutcomeProbabilities,
  parseProbability,
} from "@/lib/contract-validation";

const SEED = 20260925;
const finiteDouble = fc
  .double({ noNaN: true, noDefaultInfinity: true })
  // Normalize -0 so equality checks compare values, not signed zeros.
  .map((value) => value + 0);

describe("parseOptionalConfidenceInterval", () => {
  it("rejects the reversed intervals the 2026-09-25 audit found accepted", () => {
    expect(parseOptionalConfidenceInterval([1, 0])).toBe(INVALID);
    expect(parseOptionalConfidenceInterval([-1, -2])).toBe(INVALID);
    expect(
      parseOptionalConfidenceInterval([Number.MAX_VALUE, -Number.MAX_VALUE])
    ).toBe(INVALID);
  });

  it("accepts ordered and degenerate intervals, including negative ones", () => {
    expect(parseOptionalConfidenceInterval([0.02, 0.21])).toEqual([0.02, 0.21]);
    expect(parseOptionalConfidenceInterval([-2, -1])).toEqual([-2, -1]);
    expect(parseOptionalConfidenceInterval([0, 0])).toEqual([0, 0]);
    expect(parseOptionalConfidenceInterval(undefined)).toBeUndefined();
    expect(parseOptionalConfidenceInterval(null)).toBeUndefined();
  });

  it("accepts a pair of finite numbers exactly when low <= high", () => {
    fc.assert(
      fc.property(finiteDouble, finiteDouble, (a, b) => {
        const parsed = parseOptionalConfidenceInterval([a, b]);
        if (a <= b) {
          expect(parsed).toEqual([a, b]);
        } else {
          expect(parsed).toBe(INVALID);
        }
      }),
      { seed: SEED, numRuns: 500 }
    );
  });

  it("rejects anything that is not a pair of finite numbers", () => {
    fc.assert(
      fc.property(
        fc.oneof(
          fc.array(finiteDouble, { maxLength: 5 }).filter((a) => a.length !== 2),
          fc.tuple(fc.constantFrom(NaN, Infinity, -Infinity), finiteDouble),
          fc.tuple(finiteDouble, fc.constantFrom(NaN, Infinity, -Infinity)),
          fc.tuple(finiteDouble, fc.string()),
          fc.string(),
          fc.dictionary(fc.string(), finiteDouble)
        ),
        (value) => {
          expect(parseOptionalConfidenceInterval(value)).toBe(INVALID);
        }
      ),
      { seed: SEED, numRuns: 500 }
    );
  });
});

describe("parseProbability", () => {
  it("rejects the out-of-range probabilities the audit found accepted", () => {
    expect(parseProbability(2)).toBeNull();
    expect(parseProbability(-0.01)).toBeNull();
    expect(parseProbability(1.00001)).toBeNull();
    expect(parseProbability(0)).toBe(0);
    expect(parseProbability(1)).toBe(1);
  });

  it("accepts a number exactly when it is finite and in [0, 1]", () => {
    fc.assert(
      fc.property(
        fc.oneof(
          finiteDouble,
          fc.double({ min: 0, max: 1, noNaN: true }).map((value) => value + 0),
          fc.constantFrom(NaN, Infinity, -Infinity)
        ),
        (value) => {
          const inRange = Number.isFinite(value) && value >= 0 && value <= 1;
          expect(parseProbability(value)).toBe(inRange ? value : null);
        }
      ),
      { seed: SEED, numRuns: 500 }
    );
  });

  it("rejects non-numbers", () => {
    for (const value of ["0.5", null, undefined, true, [0.5], { value: 0.5 }]) {
      expect(parseProbability(value)).toBeNull();
    }
  });
});

describe("parseOutcomeProbabilities", () => {
  it("accepts the largest sum the Python rounding can produce", () => {
    // 40 draws, 9 above zero and 31 below: Python's round(9 / 40, 2) is 0.23
    // and round(31 / 40, 2) is 0.78 (both doubles sit just above the .xx5 tie),
    // so the returned pair sums to 1.01 although the shares sum to 1.
    expect(parseOutcomeProbabilities(0.23, 0.78)).toEqual({
      pBenefit: 0.23,
      pHarm: 0.78,
    });
    expect(parseOutcomeProbabilities(0.24, 0.78)).toBeNull();
    expect(parseOutcomeProbabilities(1, 1)).toBeNull();
  });

  it("rejects either probability outside [0, 1]", () => {
    expect(parseOutcomeProbabilities(2, 0)).toBeNull();
    expect(parseOutcomeProbabilities(0.5, -0.01)).toBeNull();
    expect(parseOutcomeProbabilities(1.00001, 0)).toBeNull();
    expect(parseOutcomeProbabilities("0.5", 0.2)).toBeNull();
  });

  it("accepts every pair that 2-decimal rounding of disjoint draw shares can yield", () => {
    // Independent model of the web API: p_benefit and p_harm are the shares a/n
    // and b/n of n draws above and below zero (a + b <= n), each rounded to a
    // multiple of 0.01 that is within half a unit of the share. Either
    // direction is allowed at a tie, so this covers any tie-breaking rule.
    const roundedShare = (count: number, n: number, up: boolean) => {
      const hundredths = (100 * count) / n;
      const candidate = up ? Math.ceil(hundredths) : Math.floor(hundredths);
      const nearest = Math.abs(candidate - hundredths) <= 0.5 + 1e-9;
      return (nearest ? candidate : Math.round(hundredths)) / 100;
    };
    const draws = fc
      .integer({ min: 1, max: 20_000 })
      .chain((n) =>
        fc
          .integer({ min: 0, max: n })
          .chain((a) =>
            fc.tuple(fc.constant(n), fc.constant(a), fc.integer({ min: 0, max: n - a }))
          )
      );
    fc.assert(
      fc.property(draws, fc.boolean(), fc.boolean(), ([n, a, b], upA, upB) => {
        const pBenefit = roundedShare(a, n, upA);
        const pHarm = roundedShare(b, n, upB);
        expect(parseOutcomeProbabilities(pBenefit, pHarm)).toEqual({ pBenefit, pHarm });
      }),
      { seed: SEED, numRuns: 1000 }
    );
  });

  it("rejects in-range pairs whose sum exceeds 1 by more than the rounding slack", () => {
    const overlapping = fc
      .double({ min: 0.02, max: 1, noNaN: true })
      .chain((pBenefit) =>
        fc
          .double({
            min: 1 + OUTCOME_PROBABILITY_SUM_TOLERANCE - pBenefit,
            max: 1,
            minExcluded: true,
            noNaN: true,
          })
          .map((pHarm) => [pBenefit, pHarm] as const)
      );
    fc.assert(
      fc.property(fc.boolean(), overlapping, (swap, [first, second]) => {
        const [pBenefit, pHarm] = swap ? [second, first] : [first, second];
        fc.pre(pBenefit + pHarm > 1 + OUTCOME_PROBABILITY_SUM_TOLERANCE);
        expect(parseOutcomeProbabilities(pBenefit, pHarm)).toBeNull();
      }),
      { seed: SEED, numRuns: 500 }
    );
    // Every pair of whole percentages summing to 102% or more is rejected.
    for (let benefit = 2; benefit <= 100; benefit += 1) {
      for (let harm = 102 - benefit; harm <= 100; harm += 1) {
        expect(parseOutcomeProbabilities(benefit / 100, harm / 100)).toBeNull();
      }
    }
  });

  it("keeps the slack at the 2-decimal rounding bound", () => {
    expect(OUTCOME_PROBABILITY_SUM_TOLERANCE).toBeGreaterThanOrEqual(0.01);
    expect(OUTCOME_PROBABILITY_SUM_TOLERANCE).toBeLessThan(0.0100001);
  });
});
