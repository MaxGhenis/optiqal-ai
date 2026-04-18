import type { BaselineRequest, BaselineResponse } from "@/lib/baseline-types";
import {
  INVALID,
  isRecord,
  parseAnalysisProfileInput,
  parseAnalysisSleepInput,
  parseFiniteNumber,
  parseMetaProfile,
  parseNumberRecord,
  parseOptionalArray,
} from "@/lib/contract-validation";

function parseSurvivalRow(value: unknown): BaselineResponse["survival_curve"][number] | null {
  if (!isRecord(value)) {
    return null;
  }

  const age = parseFiniteNumber(value.age);
  const survivalProbability = parseFiniteNumber(value.survival_probability);
  const qualityWeight = parseFiniteNumber(value.quality_weight);
  const expectedQaly = parseFiniteNumber(value.expected_qaly);

  if (
    age === null ||
    survivalProbability === null ||
    qualityWeight === null ||
    expectedQaly === null
  ) {
    return null;
  }

  return {
    age,
    survival_probability: survivalProbability,
    quality_weight: qualityWeight,
    expected_qaly: expectedQaly,
  };
}

function parseSleepEstimate(value: unknown): BaselineResponse["sleep_estimate"] | null {
  if (value === null) {
    return null;
  }
  if (!isRecord(value)) {
    return null;
  }

  const annualQalyLoss = parseFiniteNumber(value.annual_qaly_loss);
  const mortalitySignal = parseFiniteNumber(value.mortality_signal);
  const baselineHazardMultiplier = parseFiniteNumber(value.baseline_hazard_multiplier);
  const componentLosses = parseNumberRecord(value.component_losses);

  if (
    annualQalyLoss === null ||
    mortalitySignal === null ||
    baselineHazardMultiplier === null ||
    componentLosses === null
  ) {
    return null;
  }

  return {
    annual_qaly_loss: annualQalyLoss,
    mortality_signal: mortalitySignal,
    baseline_hazard_multiplier: baselineHazardMultiplier,
    component_losses: componentLosses,
  };
}

export function parseBaselineRequest(value: unknown): BaselineRequest | null {
  if (!isRecord(value)) {
    return null;
  }

  const profile = parseAnalysisProfileInput(value.profile);
  const sleepMetrics = parseAnalysisSleepInput(value.sleep_metrics);

  if (profile === null || sleepMetrics === INVALID) {
    return null;
  }

  return {
    profile,
    ...(sleepMetrics !== undefined ? { sleep_metrics: sleepMetrics } : {}),
  };
}

export function parseBaselineResponse(value: unknown): BaselineResponse | null {
  if (!isRecord(value) || !isRecord(value.meta) || !isRecord(value.point_estimate) || !isRecord(value.risk)) {
    return null;
  }

  const model = typeof value.meta.model === "string" ? value.meta.model : null;
  const qalyDiscountRate = parseFiniteNumber(value.meta.qaly_discount_rate);
  const explicitInputsOnly =
    typeof value.meta.explicit_inputs_only === "boolean" ? value.meta.explicit_inputs_only : null;
  const profile = parseMetaProfile(value.meta.profile);

  const remainingLifeExpectancy = parseFiniteNumber(value.point_estimate.remaining_life_expectancy);
  const expectedDeathAge = parseFiniteNumber(value.point_estimate.expected_death_age);
  const remainingQalys = parseFiniteNumber(value.point_estimate.remaining_qalys);
  const currentQualityWeight = parseFiniteNumber(value.point_estimate.current_quality_weight);

  const lifestyleMultiplier = parseFiniteNumber(value.risk.lifestyle_multiplier);
  const conditionMultiplier = parseFiniteNumber(value.risk.condition_multiplier);
  const sleepMultiplier = parseFiniteNumber(value.risk.sleep_multiplier);
  const rawMultiplier = parseFiniteNumber(value.risk.raw_multiplier);
  const calibrationFactor = parseFiniteNumber(value.risk.calibration_factor);
  const calibratedMultiplier = parseFiniteNumber(value.risk.calibrated_multiplier);

  const survivalCurve = parseOptionalArray(value.survival_curve, parseSurvivalRow);
  const sleepEstimate = parseSleepEstimate(value.sleep_estimate);

  if (
    model === null ||
    qalyDiscountRate === null ||
    explicitInputsOnly === null ||
    profile === null ||
    remainingLifeExpectancy === null ||
    expectedDeathAge === null ||
    remainingQalys === null ||
    currentQualityWeight === null ||
    lifestyleMultiplier === null ||
    conditionMultiplier === null ||
    sleepMultiplier === null ||
    rawMultiplier === null ||
    calibrationFactor === null ||
    calibratedMultiplier === null ||
    survivalCurve === INVALID ||
    (value.sleep_estimate !== null && sleepEstimate === null)
  ) {
    return null;
  }

  return {
    meta: {
      model,
      qaly_discount_rate: qalyDiscountRate,
      explicit_inputs_only: explicitInputsOnly,
      profile,
    },
    point_estimate: {
      remaining_life_expectancy: remainingLifeExpectancy,
      expected_death_age: expectedDeathAge,
      remaining_qalys: remainingQalys,
      current_quality_weight: currentQualityWeight,
    },
    risk: {
      lifestyle_multiplier: lifestyleMultiplier,
      condition_multiplier: conditionMultiplier,
      sleep_multiplier: sleepMultiplier,
      raw_multiplier: rawMultiplier,
      calibration_factor: calibrationFactor,
      calibrated_multiplier: calibratedMultiplier,
    },
    survival_curve: survivalCurve ?? [],
    sleep_estimate: sleepEstimate,
  };
}
