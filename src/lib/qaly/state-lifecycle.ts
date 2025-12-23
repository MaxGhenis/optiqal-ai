/**
 * State-Based Lifecycle QALY Simulator
 *
 * Simulates year-by-year QALY trajectories from a PersonState.
 * Uses CDC life tables, risk factor hazard ratios, and quality weight adjustments.
 *
 * QALY = ∫₀^∞ S(t) × Q(t) × D(t) dt
 *
 * Where:
 * - S(t) = survival probability at time t (from CDC + state-based hazard ratios)
 * - Q(t) = quality weight at time t (from age + state adjustments)
 * - D(t) = discount factor at time t
 */

import type { PersonState } from "./state";
import { getAge } from "./state";
import {
  getAnnualMortalityRate,
  applyDiscount,
  getCauseFraction,
} from "./lifecycle";
import { DISABILITY_WEIGHTS } from "./conditions";
import type { HealthCondition } from "./types";

/**
 * Year-by-year trajectory entry
 */
export interface YearlyTrajectory {
  year: number;
  age: number;
  survivalProb: number;
  cumulativeSurvival: number;
  qualityWeight: number;
  qalyThisYear: number;
  cumulativeQALY: number;
}

/**
 * QALY distribution with uncertainty
 */
export interface QALYDistribution {
  mean: number;
  median: number;
  ci95: { low: number; high: number };
  percentiles: { p: number; value: number }[];
}

/**
 * Life expectancy with uncertainty
 */
export interface LifeExpectancy {
  expected: number;
  ci95: { low: number; high: number };
}

/**
 * Complete lifecycle simulation result
 */
export interface StateLifecycleResult {
  expectedQALYs: number;
  expectedLifeYears: number;
  qalyDistribution: QALYDistribution;
  trajectory: YearlyTrajectory[];
  lifeExpectancy: LifeExpectancy;
}

/**
 * Simulation options
 */
export interface SimulationOptions {
  discountRate?: number; // default 0.03
  maxAge?: number; // default 100
  nSimulations?: number; // default 1000
}

/**
 * Base quality by age (from GBD 2019 and Sullivan et al. 2006)
 */
export function getBaseQualityByAge(age: number): number {
  if (age < 25) return 0.92;
  if (age < 35) return 0.9;
  if (age < 45) return 0.88;
  if (age < 55) return 0.85;
  if (age < 65) return 0.82;
  if (age < 75) return 0.78;
  if (age < 85) return 0.72;
  return 0.65;
}

/**
 * Get condition decrement (quality loss from a condition)
 */
function getConditionDecrement(condition: {
  type: HealthCondition;
  severity?: "mild" | "moderate" | "severe";
  controlled?: boolean;
}): number {
  const conditionData = DISABILITY_WEIGHTS[condition.type];
  if (!conditionData) return 0;

  // Get base weight for severity
  const severity = condition.severity || "moderate";
  let baseWeight = conditionData[severity];

  // Adjust for treatment/control (30% reduction when controlled)
  if (condition.controlled) {
    baseWeight *= 0.7;
  }

  return baseWeight;
}

/**
 * Get exercise quality bonus
 */
function getExerciseQualityBonus(exercise: {
  aerobicMinutesPerWeek: number;
  strengthSessionsPerWeek: number;
}): number {
  const { aerobicMinutesPerWeek, strengthSessionsPerWeek } = exercise;

  // Bonus for meeting/exceeding CDC recommendations
  let bonus = 0;

  // Aerobic bonus (up to +0.03 at 300+ min/week)
  if (aerobicMinutesPerWeek >= 300) bonus += 0.03;
  else if (aerobicMinutesPerWeek >= 150) bonus += 0.02;
  else if (aerobicMinutesPerWeek >= 75) bonus += 0.01;

  // Strength bonus (up to +0.02 at 3+ sessions/week)
  if (strengthSessionsPerWeek >= 3) bonus += 0.02;
  else if (strengthSessionsPerWeek >= 2) bonus += 0.01;

  return bonus;
}

/**
 * Get sleep quality bonus/penalty
 */
function getSleepQualityBonus(sleep: {
  hoursPerNight: number;
  quality: "poor" | "fair" | "good" | "excellent";
}): number {
  const { hoursPerNight, quality } = sleep;

  let adjustment = 0;

  // Duration adjustment (optimal: 7-8 hours)
  if (hoursPerNight < 6) adjustment -= 0.03;
  else if (hoursPerNight < 7) adjustment -= 0.01;
  else if (hoursPerNight >= 9) adjustment -= 0.02;

  // Quality adjustment
  if (quality === "poor") adjustment -= 0.03;
  else if (quality === "fair") adjustment -= 0.01;
  else if (quality === "excellent") adjustment += 0.01;

  return adjustment;
}

/**
 * Get smoking quality penalty
 */
function getSmokingQualityPenalty(smoking: {
  status: "never" | "former" | "current";
  cigarettesPerDay?: number;
}): number {
  if (smoking.status === "never") return 0;
  if (smoking.status === "former") return 0.01; // Small residual penalty

  // Current smoker
  const cpd = smoking.cigarettesPerDay || 10;
  if (cpd < 10) return 0.02;
  if (cpd < 20) return 0.03;
  return 0.05; // Heavy smoker
}

/**
 * Calculate quality weight from PersonState
 */
export function getQualityWeightFromState(
  state: PersonState,
  age: number
): number {
  let quality = getBaseQualityByAge(age);

  // Apply condition decrements
  for (const condition of state.conditions) {
    quality -= getConditionDecrement(condition);
  }

  // Apply behavior adjustments
  quality += getExerciseQualityBonus(state.behaviors.exercise);
  quality += getSleepQualityBonus(state.behaviors.sleep);
  quality -= getSmokingQualityPenalty(state.behaviors.smoking);

  // Clamp to [0, 1]
  return Math.max(0, Math.min(1, quality));
}

/**
 * Calculate composite hazard ratio from PersonState
 *
 * This combines multiple risk factors multiplicatively:
 * - Smoking
 * - BMI
 * - Exercise
 * - Alcohol
 * - Sleep
 * - Blood pressure
 * - Diet
 */
function getCompositeHazardRatio(state: PersonState): number {
  let hr = 1.0;

  // Smoking (simplified from risk-factors.ts)
  if (state.behaviors.smoking.status === "current") {
    const cpd = state.behaviors.smoking.cigarettesPerDay || 10;
    if (cpd < 10) hr *= 1.8;
    else if (cpd < 20) hr *= 2.2;
    else hr *= 2.8;
  } else if (state.behaviors.smoking.status === "former") {
    hr *= 1.1; // Former smokers
  }

  // BMI (J-shaped curve, optimal 20-25)
  const bmi = state.biomarkers.bmi || 25;
  if (bmi < 18.5) hr *= 1.51;
  else if (bmi < 20) hr *= 1.13;
  else if (bmi < 27.5) hr *= 1.0;
  else if (bmi < 30) hr *= 1.2;
  else if (bmi < 35) hr *= 1.44;
  else if (bmi < 40) hr *= 1.97;
  else hr *= 2.76;

  // Exercise (protective)
  const minutes = state.behaviors.exercise.aerobicMinutesPerWeek;
  if (minutes === 0) hr *= 1.4;
  else if (minutes < 75) hr *= 1.2;
  else if (minutes < 150) hr *= 1.1;
  else if (minutes < 300) hr *= 1.0;
  else if (minutes < 450) hr *= 0.95;
  else hr *= 0.9;

  // Alcohol (slight J-curve)
  const drinks = state.behaviors.alcohol.drinksPerWeek;
  if (drinks === 0) hr *= 1.0;
  else if (drinks <= 7) hr *= 0.95;
  else if (drinks <= 14) hr *= 1.05;
  else if (drinks <= 21) hr *= 1.15;
  else hr *= 1.4;

  // Sleep (U-shaped)
  const sleep = state.behaviors.sleep.hoursPerNight;
  if (sleep < 6) hr *= 1.12;
  else if (sleep >= 9) hr *= 1.3;

  // Blood pressure (log-linear from 115 mmHg)
  const sbp = state.biomarkers.systolicBP || 120;
  if (sbp > 115) {
    const increment = (sbp - 115) / 20;
    hr *= Math.pow(1.5, increment);
  }

  // Conditions (additional mortality risk)
  for (const condition of state.conditions) {
    // Simplified condition-based mortality increase
    const severityMult = condition.severity === "severe" ? 1.5 : condition.severity === "moderate" ? 1.2 : 1.1;
    const controlledMult = condition.controlled ? 0.7 : 1.0;

    // Add base condition mortality (rough estimates)
    if (condition.type.includes("Diabetes")) hr *= 1.5 * severityMult * controlledMult;
    else if (condition.type.includes("Heart")) hr *= 1.8 * severityMult * controlledMult;
    else if (condition.type.includes("Cancer")) hr *= 2.0 * severityMult * controlledMult;
    else if (condition.type.includes("COPD")) hr *= 1.7 * severityMult * controlledMult;
    else hr *= 1.2 * severityMult * controlledMult;
  }

  return hr;
}

/**
 * Simulate a single lifecycle trajectory
 */
function simulateSingleTrajectory(
  state: PersonState,
  options: Required<SimulationOptions>
): { totalQALY: number; lifeYears: number; trajectory: YearlyTrajectory[] } {
  const { discountRate, maxAge } = options;
  const startAge = getAge(state);
  const sex = state.demographics.sex;

  let cumulativeSurvival = 1.0;
  let cumulativeQALY = 0;
  let lifeYears = 0;
  const trajectory: YearlyTrajectory[] = [];

  // Get composite hazard ratio from state
  const compositeHR = getCompositeHazardRatio(state);

  for (let year = 0; year < maxAge - startAge; year++) {
    const currentAge = startAge + year;
    const baseQx = getAnnualMortalityRate(currentAge, sex);

    // Apply state-based hazard ratio
    const adjustedQx = Math.min(1.0, baseQx * compositeHR);

    // Survival this year
    const survivalProb = 1 - adjustedQx;

    // Quality weight
    const qualityWeight = getQualityWeightFromState(state, currentAge);

    // Discount factor
    const discount = applyDiscount(1, year, discountRate);

    // QALY this year
    const qalyThisYear = cumulativeSurvival * qualityWeight * discount;
    cumulativeQALY += qalyThisYear;
    lifeYears += cumulativeSurvival;

    trajectory.push({
      year,
      age: currentAge,
      survivalProb,
      cumulativeSurvival,
      qualityWeight,
      qalyThisYear,
      cumulativeQALY,
    });

    // Update cumulative survival
    cumulativeSurvival *= survivalProb;

    // Stop if survival is negligible
    if (cumulativeSurvival < 0.001) break;
  }

  return { totalQALY: cumulativeQALY, lifeYears, trajectory };
}

/**
 * Calculate percentile from sorted array
 */
function percentile(sorted: number[], p: number): number {
  const index = (p / 100) * (sorted.length - 1);
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  const fraction = index - lower;

  if (upper >= sorted.length) return sorted[sorted.length - 1];
  return sorted[lower] * (1 - fraction) + sorted[upper] * fraction;
}

/**
 * Simulate lifecycle from PersonState with uncertainty
 */
export function simulateLifecycleFromState(
  state: PersonState,
  options?: SimulationOptions
): StateLifecycleResult {
  const opts: Required<SimulationOptions> = {
    discountRate: options?.discountRate ?? 0.03,
    maxAge: options?.maxAge ?? 100,
    nSimulations: options?.nSimulations ?? 1000,
  };

  // For now, run deterministic simulation (Monte Carlo would sample HRs)
  // We'll use nSimulations for future uncertainty sampling
  const baseResult = simulateSingleTrajectory(state, opts);

  // Monte Carlo simulation with small perturbations
  const qalySamples: number[] = [];
  const lifeYearsSamples: number[] = [];

  for (let i = 0; i < opts.nSimulations; i++) {
    // Add small random variation to simulate uncertainty
    // In production, this would sample from HR distributions
    const perturbation = 1 + (Math.random() - 0.5) * 0.1; // ±5%
    const sample = baseResult.totalQALY * perturbation;
    qalySamples.push(sample);

    const lifePerturbation = 1 + (Math.random() - 0.5) * 0.08;
    lifeYearsSamples.push(baseResult.lifeYears * lifePerturbation);
  }

  // Sort for percentile calculations
  qalySamples.sort((a, b) => a - b);
  lifeYearsSamples.sort((a, b) => a - b);

  // Calculate statistics
  const mean = qalySamples.reduce((a, b) => a + b, 0) / qalySamples.length;
  const median = percentile(qalySamples, 50);
  const ci95Low = percentile(qalySamples, 2.5);
  const ci95High = percentile(qalySamples, 97.5);

  const lifeExpMean =
    lifeYearsSamples.reduce((a, b) => a + b, 0) / lifeYearsSamples.length;
  const lifeExpCILow = percentile(lifeYearsSamples, 2.5);
  const lifeExpCIHigh = percentile(lifeYearsSamples, 97.5);

  // Generate percentile distribution
  const percentiles: { p: number; value: number }[] = [];
  for (let p = 5; p <= 95; p += 5) {
    percentiles.push({ p, value: percentile(qalySamples, p) });
  }

  return {
    expectedQALYs: mean,
    expectedLifeYears: lifeExpMean,
    qalyDistribution: {
      mean,
      median,
      ci95: { low: ci95Low, high: ci95High },
      percentiles,
    },
    trajectory: baseResult.trajectory,
    lifeExpectancy: {
      expected: lifeExpMean,
      ci95: { low: lifeExpCILow, high: lifeExpCIHigh },
    },
  };
}
