import modelResponses from "@/lib/__fixtures__/model-responses.json";

/**
 * Real Python web API responses for the contract tests, written by
 * generate_model_responses.py next to this file. They pin shapes and validity,
 * not numbers: regenerate them when the model changes.
 */
export interface ModelResponseSample {
  name: string;
  request: unknown;
  response: unknown;
}

export const MODEL_RESPONSES = modelResponses as unknown as {
  baseline: ModelResponseSample[];
  frontier: ModelResponseSample[];
};

export function modelResponse(
  kind: "baseline" | "frontier",
  name: string
): unknown {
  const sample = MODEL_RESPONSES[kind].find((candidate) => candidate.name === name);
  if (!sample) {
    throw new Error(`No ${kind} model response fixture named ${name}`);
  }
  return sample.response;
}

export type JsonPath = ReadonlyArray<string | number>;

type JsonContainer = Record<string | number, unknown>;

/** Read the value at `path`, or undefined when any step is missing. */
export function getAt(root: unknown, path: JsonPath): unknown {
  let node: unknown = root;
  for (const key of path) {
    if (typeof node !== "object" || node === null) {
      return undefined;
    }
    node = (node as JsonContainer)[key];
  }
  return node;
}

/** Return one deep copy of `root` with the value at each path replaced. */
export function withValues(
  root: unknown,
  edits: ReadonlyArray<readonly [JsonPath, unknown]>
): unknown {
  const copy = structuredClone(root);
  for (const [path, value] of edits) {
    const parent = getAt(copy, path.slice(0, -1));
    if (path.length === 0 || typeof parent !== "object" || parent === null) {
      throw new Error(`Cannot set ${path.join(".")}: parent is not an object`);
    }
    (parent as JsonContainer)[path[path.length - 1]] = value;
  }
  return copy;
}

/** Return a deep copy of `root` with the value at `path` replaced. */
export function setAt(root: unknown, path: JsonPath, value: unknown): unknown {
  return withValues(root, [[path, value]]);
}

/** Indices of an array at `path`, or none when it is absent. */
export function indicesAt(root: unknown, path: JsonPath): number[] {
  const value = getAt(root, path);
  return Array.isArray(value) ? value.map((_, index) => index) : [];
}
