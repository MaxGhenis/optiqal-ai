import { describe, expect, it } from "vitest";
import fc from "fast-check";
import { parseBaselineResponse } from "@/lib/baseline-contract";
import { parseFrontierResponse } from "@/lib/frontier-contract";
import {
  MODEL_RESPONSES,
  getAt,
  indicesAt,
  withValues,
  type JsonPath,
} from "@/lib/__fixtures__/model-responses";

/**
 * Response-contract invariants, checked against real Python web API output
 * (src/lib/__fixtures__/model-responses.json) and against responses generated
 * from it by fast-check:
 * - every response the model emits parses, and parsing keeps displayed values;
 * - parse(serialize(parse(x))) equals parse(x);
 * - probabilities and fractions lie in [0, 1], p_benefit + p_harm stays within
 *   the 2-decimal rounding slack of 1, and every interval has low <= high, so
 *   any single mutation that breaks one of these makes the whole parse fail.
 */

const SEED = 20260925;
const RUNS_PER_FIXTURE = 60;

type Parser = (value: unknown) => unknown;
type Edit = readonly [JsonPath, unknown];

const finiteDouble = fc
  .double({ noNaN: true, noDefaultInfinity: true })
  // Normalize -0 so that JSON round trips compare equal.
  .map((value) => value + 0);
const probability = fc.double({ min: 0, max: 1, noNaN: true }).map((value) => value + 0);
const orderedInterval = fc
  .tuple(finiteDouble, finiteDouble)
  .map(([a, b]) => (a <= b ? [a, b] : [b, a]));
// Pairs of 2-decimal probabilities whose sum is at most 1.01, the most that
// rounding two disjoint shares to 2 decimals can produce.
const outcomePair = fc
  .integer({ min: 0, max: 100 })
  .chain((benefit) =>
    fc
      .integer({ min: 0, max: Math.min(100, 101 - benefit) })
      .map((harm) => [benefit / 100, harm / 100] as const)
  );

const invalidProbability = fc.oneof(
  fc.double({ max: -Number.MIN_VALUE, noNaN: true, noDefaultInfinity: true }),
  fc.double({ min: 1, minExcluded: true, noNaN: true, noDefaultInfinity: true }),
  fc.constantFrom(NaN, Infinity, -Infinity, "0.5", null)
);
const reversedInterval = fc
  .tuple(finiteDouble, finiteDouble)
  .filter(([a, b]) => a !== b)
  .map(([a, b]) => (a > b ? [a, b] : [b, a]));
const overlappingOutcomePair = fc
  .integer({ min: 2, max: 100 })
  .chain((benefit) =>
    fc
      .integer({ min: 102 - benefit, max: 100 })
      .map((harm) => [benefit / 100, harm / 100] as const)
  );

interface ConstrainedPaths {
  /** Parents of a p_benefit / p_harm pair. */
  outcomes: JsonPath[];
  probabilities: JsonPath[];
  intervals: JsonPath[];
  /** Numbers the contract leaves unconstrained apart from finiteness. */
  unconstrained: JsonPath[];
}

function frontierPaths(response: unknown): ConstrainedPaths {
  const paths: ConstrainedPaths = {
    outcomes: [],
    probabilities: [],
    intervals: [],
    unconstrained: [],
  };
  for (const index of indicesAt(response, ["items"])) {
    const item = ["items", index];
    paths.outcomes.push(item);
    paths.probabilities.push([...item, "sleep_mortality_relief_fraction"]);
    for (const field of ["net_qaly_ci", "net_days_ci"]) {
      if (getAt(response, [...item, field]) !== undefined) {
        paths.intervals.push([...item, field]);
      }
    }
    for (const field of ["days", "total_qaly", "mort_qaly", "harm_qaly", "total_cost"]) {
      paths.unconstrained.push([...item, field]);
    }
  }
  for (const state of indicesAt(response, ["decision_states"])) {
    for (const option of indicesAt(response, ["decision_states", state, "options"])) {
      const optionPath = ["decision_states", state, "options", option];
      paths.unconstrained.push([...optionPath, "marginal_qaly"]);
      for (const item of indicesAt(response, [...optionPath, "added_items"])) {
        paths.outcomes.push([...optionPath, "added_items", item]);
      }
    }
  }
  if (getAt(response, ["sleep_estimate", "airway"])) {
    for (const field of [
      "upper_airway_probability",
      "nasal_inflammation_probability",
      "mucus_probability",
    ]) {
      paths.probabilities.push(["sleep_estimate", "airway", field]);
    }
  }
  for (const step of indicesAt(response, ["frontier"])) {
    paths.unconstrained.push(["frontier", step, "marginal_qaly"]);
  }
  return paths;
}

function baselinePaths(response: unknown): ConstrainedPaths {
  const paths: ConstrainedPaths = {
    outcomes: [],
    probabilities: [["point_estimate", "current_quality_weight"]],
    intervals: [],
    unconstrained: [
      ["point_estimate", "remaining_life_expectancy"],
      ["point_estimate", "remaining_qalys"],
    ],
  };
  for (const field of ["remaining_life_expectancy_ci", "remaining_qalys_ci"]) {
    if (getAt(response, ["point_estimate", field]) !== undefined) {
      paths.intervals.push(["point_estimate", field]);
    }
  }
  for (const row of indicesAt(response, ["survival_curve"])) {
    paths.probabilities.push(["survival_curve", row, "survival_probability"]);
    paths.probabilities.push(["survival_curve", row, "quality_weight"]);
    paths.unconstrained.push(["survival_curve", row, "expected_qaly"]);
  }
  return paths;
}

/** Arbitrary for valid responses: the fixture with every constrained value redrawn. */
function validResponse(template: unknown, paths: ConstrainedPaths): fc.Arbitrary<unknown> {
  return fc
    .record({
      outcomes: fc.tuple(...paths.outcomes.map(() => outcomePair)),
      probabilities: fc.tuple(...paths.probabilities.map(() => probability)),
      intervals: fc.tuple(...paths.intervals.map(() => orderedInterval)),
      unconstrained: fc.tuple(...paths.unconstrained.map(() => finiteDouble)),
    })
    .map((drawn) =>
      withValues(template, [
        ...paths.outcomes.flatMap((path, index): Edit[] => [
          [[...path, "p_benefit"], drawn.outcomes[index][0]],
          [[...path, "p_harm"], drawn.outcomes[index][1]],
        ]),
        ...paths.probabilities.map((path, index): Edit => [path, drawn.probabilities[index]]),
        ...paths.intervals.map((path, index): Edit => [path, drawn.intervals[index]]),
        ...paths.unconstrained.map((path, index): Edit => [path, drawn.unconstrained[index]]),
      ])
    );
}

/** Arbitrary for a single mutation that breaks one range or ordering rule. */
function invalidMutation(paths: ConstrainedPaths): fc.Arbitrary<Edit[]> {
  const options: fc.Arbitrary<Edit[]>[] = [];
  if (paths.outcomes.length > 0) {
    const parent = fc.constantFrom(...paths.outcomes);
    options.push(
      fc
        .tuple(parent, fc.constantFrom("p_benefit", "p_harm"), invalidProbability)
        .map(([path, field, value]): Edit[] => [[[...path, field], value]]),
      fc.tuple(parent, overlappingOutcomePair).map(([path, [pBenefit, pHarm]]): Edit[] => [
        [[...path, "p_benefit"], pBenefit],
        [[...path, "p_harm"], pHarm],
      ])
    );
  }
  if (paths.probabilities.length > 0) {
    options.push(
      fc
        .tuple(fc.constantFrom(...paths.probabilities), invalidProbability)
        .map(([path, value]): Edit[] => [[path, value]])
    );
  }
  if (paths.intervals.length > 0) {
    options.push(
      fc
        .tuple(fc.constantFrom(...paths.intervals), reversedInterval)
        .map(([path, value]): Edit[] => [[path, value]])
    );
  }
  return fc.oneof(...options);
}

function roundTrip(value: unknown): unknown {
  return JSON.parse(JSON.stringify(value));
}

const cases: Array<{
  kind: "baseline" | "frontier";
  name: string;
  response: unknown;
  parse: Parser;
  paths: ConstrainedPaths;
}> = [
  ...MODEL_RESPONSES.baseline.map((sample) => ({
    kind: "baseline" as const,
    name: sample.name,
    response: sample.response,
    parse: parseBaselineResponse,
    paths: baselinePaths(sample.response),
  })),
  ...MODEL_RESPONSES.frontier.map((sample) => ({
    kind: "frontier" as const,
    name: sample.name,
    response: sample.response,
    parse: parseFrontierResponse,
    paths: frontierPaths(sample.response),
  })),
];

describe("real model responses cross the JS contract", () => {
  it("covers sex other, a high-risk profile and nonempty current stacks", () => {
    const names = cases.map((entry) => `${entry.kind}:${entry.name}`);
    expect(names).toEqual(
      expect.arrayContaining([
        "baseline:other_default",
        "baseline:high_risk_with_sleep",
        "frontier:other_age_80_sleep",
        "frontier:high_risk_current_stack",
        "frontier:female_18_current_stack",
        // 40 draws: independent rounding can return p_benefit + p_harm = 1.01.
        "frontier:high_risk_age_45_40_draws",
      ])
    );
    const frontier = cases.filter((entry) => entry.kind === "frontier");
    // The mutation tests below need every constrained kind to be present.
    expect(frontier.some((entry) => entry.paths.intervals.length > 0)).toBe(true);
    expect(
      frontier.some((entry) =>
        entry.paths.outcomes.some((path) => path.includes("added_items"))
      )
    ).toBe(true);
    expect(
      frontier.some((entry) => entry.paths.probabilities.some((path) => path.includes("airway")))
    ).toBe(true);
  });

  it.each(cases.map((entry) => [`${entry.kind}:${entry.name}`, entry] as const))(
    "%s parses and keeps every displayed value",
    (_, { kind, response, parse }) => {
      const parsed = parse(response);
      expect(parsed).not.toBeNull();
      if (kind === "frontier") {
        expect(getAt(parsed, ["items"])).toEqual(getAt(response, ["items"]));
        expect(getAt(parsed, ["frontier"])).toEqual(getAt(response, ["frontier"]));
        expect(getAt(parsed, ["sleep_estimate"])).toEqual(getAt(response, ["sleep_estimate"]));
      } else {
        expect(getAt(parsed, ["survival_curve"])).toEqual(getAt(response, ["survival_curve"]));
        expect(getAt(parsed, ["risk"])).toEqual(getAt(response, ["risk"]));
        for (const field of [
          "remaining_life_expectancy",
          "remaining_qalys",
          "current_quality_weight",
          "remaining_life_expectancy_ci",
          "remaining_qalys_ci",
        ]) {
          expect(getAt(parsed, ["point_estimate", field])).toEqual(
            getAt(response, ["point_estimate", field])
          );
        }
      }
      expect(parse(roundTrip(parsed))).toEqual(parsed);
    }
  );
});

describe.each(cases.map((entry) => [`${entry.kind}:${entry.name}`, entry] as const))(
  "generated responses from %s",
  (_, { response, parse, paths }) => {
    it("parse, and parse(serialize(parse(x))) equals parse(x)", () => {
      fc.assert(
        fc.property(validResponse(response, paths), (generated) => {
          const parsed = parse(generated);
          expect(parsed).not.toBeNull();
          expect(parse(roundTrip(parsed))).toEqual(parsed);
        }),
        { seed: SEED, numRuns: RUNS_PER_FIXTURE }
      );
    });

    const hasConstraints =
      paths.outcomes.length + paths.probabilities.length + paths.intervals.length > 0;
    it.runIf(hasConstraints)(
      "are rejected after any mutation that breaks a range or ordering rule",
      () => {
        fc.assert(
          fc.property(
            validResponse(response, paths),
            invalidMutation(paths),
            (generated, edits) => {
              expect(parse(generated)).not.toBeNull();
              expect(parse(withValues(generated, edits))).toBeNull();
            }
          ),
          { seed: SEED, numRuns: RUNS_PER_FIXTURE }
        );
      }
    );
  }
);
