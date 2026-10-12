export type JsonRecord = Record<string, unknown>;

const ACTIVITY_LEVELS = ["sedentary", "light", "moderate", "active"] as const;
const SEX_VALUES = ["male", "female", "other"] as const;
const COVERAGE_VALUES = ["na", "likely", "mixed", "unlikely"] as const;
const FRICTION_VALUES = ["low", "medium", "high"] as const;
const ACCESS_TIER_VALUES = [
  "behavioral",
  "otc",
  "generic_rx",
  "brand_rx_prior_auth",
  "dme_rx",
  "specialist_device",
  "cash_pay",
  "multiple",
  "none",
] as const;

export function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null;
}

export function parseFiniteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/**
 * Parse a finite number and require it to fall within [min, max] (inclusive).
 * Returns null for non-numbers and for out-of-range values, so callers reject
 * hostile inputs (e.g. age = -1e9, height_cm = 0) before they reach the
 * simulation engine and cause hangs or division-by-zero.
 */
export function parseBoundedNumber(
  value: unknown,
  min: number,
  max: number
): number | null {
  const num = parseFiniteNumber(value);
  if (num === null || num < min || num > max) {
    return null;
  }
  return num;
}

/**
 * Parse a probability or fraction: a finite number in [0, 1]. Model responses
 * that break this are rejected whole rather than displayed.
 */
export function parseProbability(value: unknown): number | null {
  return parseBoundedNumber(value, 0, 1);
}

/**
 * Slack allowed above 1 on p_benefit + p_harm.
 *
 * The web API takes both from the same Monte Carlo draws: p_benefit is the
 * share of simulated QALY gains above zero and p_harm the share below zero
 * (`prob_positive` / `prob_negative` from `_posterior_decision_metrics` in
 * python/optiqal/simulate.py). The events are disjoint, so the unrounded sum
 * is at most 1.
 * build_frontier_response_with_policy in python/optiqal/web_api.py then rounds
 * each one to 2 decimals on its own (`round(float(raw["p_benefit"]), 2)`),
 * which moves each by at most 0.005, so the returned sum is at most
 * 1 + 2 * 0.005 = 1.01. That bound is reached: 9 and 31 of 40 draws round to
 * 0.23 and 0.78. The extra 1e-9 covers binary representation error in adding
 * two 2-decimal numbers.
 */
export const OUTCOME_PROBABILITY_SUM_TOLERANCE = 0.01 + 1e-9;

/**
 * Parse the benefit/harm probabilities of one intervention: each must be a
 * probability, and together they may exceed 1 only by the rounding slack
 * above.
 */
export function parseOutcomeProbabilities(
  pBenefit: unknown,
  pHarm: unknown
): { pBenefit: number; pHarm: number } | null {
  const benefit = parseProbability(pBenefit);
  const harm = parseProbability(pHarm);
  if (
    benefit === null ||
    harm === null ||
    benefit + harm > 1 + OUTCOME_PROBABILITY_SUM_TOLERANCE
  ) {
    return null;
  }
  return { pBenefit: benefit, pHarm: harm };
}

export function parseBoolean(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

export function parseString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

export function parseEnum<T extends readonly string[]>(
  value: unknown,
  allowed: T
): T[number] | null {
  return typeof value === "string" && allowed.includes(value as T[number])
    ? (value as T[number])
    : null;
}

export function parseOptionalFiniteNumber(
  value: unknown
): number | null | undefined | typeof INVALID {
  if (value === undefined) {
    return undefined;
  }
  if (value === null) {
    return null;
  }
  return parseFiniteNumber(value) ?? INVALID;
}

export function parseOptionalBoundedNumber(
  value: unknown,
  min: number,
  max: number
): number | null | undefined | typeof INVALID {
  if (value === undefined) {
    return undefined;
  }
  if (value === null) {
    return null;
  }
  return parseBoundedNumber(value, min, max) ?? INVALID;
}

export function parseOptionalArray<T>(
  value: unknown,
  itemParser: (item: unknown) => T | null
): T[] | undefined | typeof INVALID {
  if (value === undefined) {
    return undefined;
  }
  if (!Array.isArray(value)) {
    return INVALID;
  }

  const parsed: T[] = [];
  for (const item of value) {
    const next = itemParser(item);
    if (next === null) {
      return INVALID;
    }
    parsed.push(next);
  }
  return parsed;
}

export function parseStringArray(value: unknown): string[] | null {
  if (!Array.isArray(value)) {
    return null;
  }

  const parsed: string[] = [];
  for (const item of value) {
    const next = parseString(item);
    if (next === null) {
      return null;
    }
    parsed.push(next);
  }
  return parsed;
}

export function parseNumberRecord(value: unknown): Record<string, number> | null {
  if (!isRecord(value)) {
    return null;
  }

  const parsed: Record<string, number> = {};
  for (const [key, raw] of Object.entries(value)) {
    const next = parseFiniteNumber(raw);
    if (next === null) {
      return null;
    }
    parsed[key] = next;
  }
  return parsed;
}

export const INVALID = Symbol("invalid-optional-value");

/**
 * Parse an optional [low, high] interval. Absent (undefined or null) gives
 * undefined; anything other than two finite numbers with low <= high is
 * INVALID. Degenerate intervals (low === high) are allowed: the baseline
 * returns [0, 0] past the end of the life table.
 */
export function parseOptionalConfidenceInterval(
  value: unknown
): [number, number] | undefined | typeof INVALID {
  if (value === undefined || value === null) {
    return undefined;
  }
  if (!Array.isArray(value) || value.length !== 2) {
    return INVALID;
  }
  const low = parseFiniteNumber(value[0]);
  const high = parseFiniteNumber(value[1]);
  if (low === null || high === null || low > high) {
    return INVALID;
  }
  return [low, high];
}

export function parseAnalysisProfileInput(value: unknown): {
  age: number;
  sex: "male" | "female" | "other";
  weight_kg: number;
  height_cm: number;
  smoker: boolean;
  has_diabetes: boolean;
  has_hypertension: boolean;
  activity_level: "sedentary" | "light" | "moderate" | "active";
  sleep_hours_per_night?: number | null;
} | null {
  if (!isRecord(value)) {
    return null;
  }

  // Clinically plausible bounds. These also protect the engine: an
  // out-of-range age drives an effectively unbounded life-table loop, and a
  // zero/negative height divides by zero in BMI.
  const age = parseBoundedNumber(value.age, 0, 120);
  const sex = parseEnum(value.sex, SEX_VALUES);
  const weightKg = parseBoundedNumber(value.weight_kg, 20, 500);
  const heightCm = parseBoundedNumber(value.height_cm, 50, 275);
  const smoker = parseBoolean(value.smoker);
  const hasDiabetes = parseBoolean(value.has_diabetes);
  const hasHypertension = parseBoolean(value.has_hypertension);
  const activityLevel = parseEnum(value.activity_level, ACTIVITY_LEVELS);
  const sleepHours = parseOptionalBoundedNumber(value.sleep_hours_per_night, 0, 24);

  if (
    age === null ||
    sex === null ||
    weightKg === null ||
    heightCm === null ||
    smoker === null ||
    hasDiabetes === null ||
    hasHypertension === null ||
    activityLevel === null ||
    sleepHours === INVALID
  ) {
    return null;
  }

  return {
    age,
    sex,
    weight_kg: weightKg,
    height_cm: heightCm,
    smoker,
    has_diabetes: hasDiabetes,
    has_hypertension: hasHypertension,
    activity_level: activityLevel,
    ...(sleepHours !== undefined ? { sleep_hours_per_night: sleepHours } : {}),
  };
}

export function parseAnalysisSleepInput(value: unknown): {
  duration_hours?: number | null;
  recovery_score?: number | null;
  sleep_quality_score?: number | null;
  waso_min?: number | null;
  routine_score?: number | null;
  social_jetlag_min?: number | null;
  latency_min?: number | null;
  breathing_score?: number | null;
  spo2?: number | null;
  snore_pct?: number | null;
  sleep_debt_min?: number | null;
  airway_response_signal?: number | null;
} | null | undefined | typeof INVALID {
  if (value === undefined) {
    return undefined;
  }
  if (value === null) {
    return null;
  }
  if (!isRecord(value)) {
    return INVALID;
  }

  const fields = {
    duration_hours: parseOptionalBoundedNumber(value.duration_hours, 0, 24),
    recovery_score: parseOptionalBoundedNumber(value.recovery_score, 0, 100),
    sleep_quality_score: parseOptionalBoundedNumber(value.sleep_quality_score, 0, 100),
    waso_min: parseOptionalBoundedNumber(value.waso_min, 0, 1440),
    routine_score: parseOptionalBoundedNumber(value.routine_score, 0, 100),
    social_jetlag_min: parseOptionalBoundedNumber(value.social_jetlag_min, 0, 1440),
    latency_min: parseOptionalBoundedNumber(value.latency_min, 0, 1440),
    breathing_score: parseOptionalBoundedNumber(value.breathing_score, 0, 1),
    spo2: parseOptionalBoundedNumber(value.spo2, 0, 100),
    snore_pct: parseOptionalBoundedNumber(value.snore_pct, 0, 100),
    sleep_debt_min: parseOptionalBoundedNumber(value.sleep_debt_min, 0, 1440),
    airway_response_signal: parseOptionalBoundedNumber(
      value.airway_response_signal,
      0,
      1
    ),
  };

  if (Object.values(fields).includes(INVALID)) {
    return INVALID;
  }

  const parsedEntries = Object.entries(fields).filter(([, fieldValue]) => fieldValue !== undefined);
  return Object.fromEntries(parsedEntries);
}

export function parseMetaProfile(value: unknown): {
  age: number;
  sex: string;
  bmi_category: string;
  smoking_status: string;
  has_diabetes: boolean;
  has_hypertension: boolean;
  activity_level: string;
} | null {
  if (!isRecord(value)) {
    return null;
  }

  const age = parseFiniteNumber(value.age);
  const sex = parseString(value.sex);
  const bmiCategory = parseString(value.bmi_category);
  const smokingStatus = parseString(value.smoking_status);
  const hasDiabetes = parseBoolean(value.has_diabetes);
  const hasHypertension = parseBoolean(value.has_hypertension);
  const activityLevel = parseString(value.activity_level);

  if (
    age === null ||
    sex === null ||
    bmiCategory === null ||
    smokingStatus === null ||
    hasDiabetes === null ||
    hasHypertension === null ||
    activityLevel === null
  ) {
    return null;
  }

  return {
    age,
    sex,
    bmi_category: bmiCategory,
    smoking_status: smokingStatus,
    has_diabetes: hasDiabetes,
    has_hypertension: hasHypertension,
    activity_level: activityLevel,
  };
}

export function parseAccessLeaf(value: unknown): {
  tier:
    | "behavioral"
    | "otc"
    | "generic_rx"
    | "brand_rx_prior_auth"
    | "dme_rx"
    | "specialist_device"
    | "cash_pay"
    | "multiple"
    | "none";
  coverage_outlook: "na" | "likely" | "mixed" | "unlikely";
  friction: "low" | "medium" | "high";
  notes: string;
} | null {
  if (!isRecord(value)) {
    return null;
  }

  const tier = parseEnum(value.tier, ACCESS_TIER_VALUES);
  const coverageOutlook = parseEnum(value.coverage_outlook, COVERAGE_VALUES);
  const friction = parseEnum(value.friction, FRICTION_VALUES);
  const notes = parseString(value.notes);

  if (tier === null || coverageOutlook === null || friction === null || notes === null) {
    return null;
  }

  return {
    tier,
    coverage_outlook: coverageOutlook,
    friction,
    notes,
  };
}
