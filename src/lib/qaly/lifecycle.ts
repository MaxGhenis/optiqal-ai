/**
 * Rigorous Lifecycle QALY Model
 *
 * Based on whatnut methodology:
 * - CDC National Vital Statistics life tables (2021)
 * - Pathway decomposition: CVD, cancer, other mortality
 * - Age-varying cause-of-death fractions (CDC WONDER 2021)
 * - 3% annual discounting (ICER/NICE standard)
 *
 * QALY = ∫₀^∞ S(t) × Q(t) × D(t) dt
 *
 * Where:
 * - S(t) = survival probability at time t
 * - Q(t) = quality weight at time t
 * - D(t) = discount factor at time t
 */

/**
 * CDC Life Table Data (2021)
 *
 * Probability of dying within one year (qx) by age and sex
 * Source: CDC NVSS Life Tables 2021
 * https://www.cdc.gov/nchs/products/life_tables.htm
 */
export const CDC_LIFE_TABLE: {
  male: Record<number, number>;
  female: Record<number, number>;
} = {
  male: {
    // Probability of dying within one year (qx)
    0: 0.00566,
    1: 0.00039,
    5: 0.00012,
    10: 0.00011,
    15: 0.00050,
    20: 0.00129,
    25: 0.00156,
    30: 0.00175,
    35: 0.00209,
    40: 0.00261,
    45: 0.00369,
    50: 0.00547,
    55: 0.00832,
    60: 0.01206,
    65: 0.01697,
    70: 0.02467,
    75: 0.03711,
    80: 0.05640,
    85: 0.08737,
    90: 0.13510,
    95: 0.19853,
    100: 0.27500,
  },
  female: {
    0: 0.00476,
    1: 0.00031,
    5: 0.00010,
    10: 0.00009,
    15: 0.00025,
    20: 0.00047,
    25: 0.00059,
    30: 0.00073,
    35: 0.00096,
    40: 0.00136,
    45: 0.00204,
    50: 0.00310,
    55: 0.00469,
    60: 0.00692,
    65: 0.01019,
    70: 0.01556,
    75: 0.02502,
    80: 0.04085,
    85: 0.06837,
    90: 0.11295,
    95: 0.17639,
    100: 0.25500,
  },
};

/**
 * Interpolate mortality rate for any age
 */
export function getAnnualMortalityRate(
  age: number,
  sex: "male" | "female"
): number {
  const table = CDC_LIFE_TABLE[sex];
  const ages = Object.keys(table)
    .map(Number)
    .sort((a, b) => a - b);

  // Clamp age to table range
  if (age <= ages[0]) return table[ages[0]];
  if (age >= ages[ages.length - 1]) return table[ages[ages.length - 1]];

  // Find surrounding ages and interpolate
  let lowerAge = ages[0];
  let upperAge = ages[ages.length - 1];

  for (let i = 0; i < ages.length - 1; i++) {
    if (ages[i] <= age && ages[i + 1] > age) {
      lowerAge = ages[i];
      upperAge = ages[i + 1];
      break;
    }
  }

  const lowerRate = table[lowerAge];
  const upperRate = table[upperAge];
  const fraction = (age - lowerAge) / (upperAge - lowerAge);

  // Log-linear interpolation (mortality rates are approximately log-linear)
  return Math.exp(
    Math.log(lowerRate) + fraction * (Math.log(upperRate) - Math.log(lowerRate))
  );
}

/**
 * Calculate survival probability from startAge to targetAge
 *
 * S(t) = ∏ᵢ (1 - qᵢ) for i from startAge to targetAge-1
 */
export function getSurvivalProbability(
  startAge: number,
  targetAge: number,
  sex: "male" | "female"
): number {
  if (targetAge <= startAge) return 1.0;
  if (targetAge > 110) return 0; // Assume no one lives past 110

  let survival = 1.0;
  for (let age = Math.floor(startAge); age < Math.floor(targetAge); age++) {
    const qx = getAnnualMortalityRate(age, sex);
    survival *= 1 - qx;
  }

  // Handle fractional year at start
  const startFraction = startAge - Math.floor(startAge);
  if (startFraction > 0) {
    const qxStart = getAnnualMortalityRate(Math.floor(startAge), sex);
    survival /= 1 - qxStart * startFraction;
  }

  return Math.max(0, survival);
}

/**
 * Age-varying cause-of-death fractions
 *
 * Source: CDC WONDER 2021
 * CVD = heart disease + stroke
 * Cancer = malignant neoplasms
 * Other = all other causes
 */
export const CAUSE_FRACTIONS: Record<
  number,
  { cvd: number; cancer: number; other: number }
> = {
  40: { cvd: 0.20, cancer: 0.25, other: 0.55 },
  50: { cvd: 0.25, cancer: 0.35, other: 0.40 },
  60: { cvd: 0.30, cancer: 0.35, other: 0.35 },
  70: { cvd: 0.35, cancer: 0.30, other: 0.35 },
  80: { cvd: 0.40, cancer: 0.20, other: 0.40 },
  90: { cvd: 0.45, cancer: 0.12, other: 0.43 },
};

/**
 * Get cause fractions for any age (interpolated)
 */
export function getCauseFraction(age: number): {
  cvd: number;
  cancer: number;
  other: number;
} {
  const ages = Object.keys(CAUSE_FRACTIONS)
    .map(Number)
    .sort((a, b) => a - b);

  // Clamp to range
  if (age <= ages[0]) return CAUSE_FRACTIONS[ages[0]];
  if (age >= ages[ages.length - 1]) return CAUSE_FRACTIONS[ages[ages.length - 1]];

  // Find surrounding ages
  let lowerAge = ages[0];
  let upperAge = ages[ages.length - 1];

  for (let i = 0; i < ages.length - 1; i++) {
    if (ages[i] <= age && ages[i + 1] > age) {
      lowerAge = ages[i];
      upperAge = ages[i + 1];
      break;
    }
  }

  const fraction = (age - lowerAge) / (upperAge - lowerAge);
  const lower = CAUSE_FRACTIONS[lowerAge];
  const upper = CAUSE_FRACTIONS[upperAge];

  return {
    cvd: lower.cvd + fraction * (upper.cvd - lower.cvd),
    cancer: lower.cancer + fraction * (upper.cancer - lower.cancer),
    other: lower.other + fraction * (upper.other - lower.other),
  };
}

/**
 * Apply discount factor
 *
 * D(t) = 1 / (1 + r)^t
 *
 * @param value - Value to discount
 * @param year - Years from present
 * @param rate - Annual discount rate (default 3% per ICER/NICE)
 */
export function applyDiscount(
  value: number,
  year: number,
  rate: number = 0.03
): number {
  if (rate === 0) return value;
  return value / Math.pow(1 + rate, year);
}

/**
 * Calculate discounted QALY for a single year
 */
export function getDiscountedQALY(params: {
  survivalProb: number;
  qualityWeight: number;
  year: number;
  discountRate?: number;
}): number {
  const { survivalProb, qualityWeight, year, discountRate = 0.03 } = params;
  return survivalProb * qualityWeight * applyDiscount(1, year, discountRate);
}

/**
 * Age-varying quality weights
 *
 * Based on Sullivan et al. (2006) and GBD 2019
 */
function getQualityWeight(age: number): number {
  // Quality decreases with age
  if (age < 25) return 0.92;
  if (age < 35) return 0.90;
  if (age < 45) return 0.88;
  if (age < 55) return 0.85;
  if (age < 65) return 0.82;
  if (age < 75) return 0.78;
  if (age < 85) return 0.72;
  return 0.65;
}

/**
 * Pathway-specific hazard ratios
 */
export interface PathwayHRs {
  cvd: number;
  cancer: number;
  other: number;
}

/**
 * Result of lifecycle QALY calculation
 */
export interface LifecycleResult {
  /** Baseline QALYs (no intervention) */
  baselineQALYs: number;

  /** Intervention QALYs */
  interventionQALYs: number;

  /** QALY gain from intervention */
  qalyGain: number;

  /** Contribution from each pathway */
  pathwayContributions: {
    cvd: number;
    cancer: number;
    other: number;
  };

  /** Life years gained (undiscounted) */
  lifeYearsGained: number;

  /** Yearly breakdown */
  yearlyBreakdown: {
    year: number;
    age: number;
    survivalBaseline: number;
    survivalIntervention: number;
    qalyBaseline: number;
    qalyIntervention: number;
  }[];
}

/**
 * Calculate lifecycle QALYs with pathway decomposition
 *
 * This is the core lifecycle integration:
 * QALY = Σᵢ S(i) × Q(i) × D(i)
 *
 * With intervention:
 * - Mortality rate is modified by pathway-specific HRs
 * - HR applied proportionally to each cause fraction
 */
export function calculateLifecycleQALYs(params: {
  startAge: number;
  sex: "male" | "female";
  pathwayHRs: PathwayHRs;
  discountRate?: number;
  maxAge?: number;
  qualityWeight?: number; // Override age-based quality
}): LifecycleResult {
  const {
    startAge,
    sex,
    pathwayHRs,
    discountRate = 0.03,
    maxAge = 100,
    qualityWeight: customQuality,
  } = params;

  let baselineQALYs = 0;
  let interventionQALYs = 0;
  let baselineLifeYears = 0;
  let interventionLifeYears = 0;

  // Track pathway contributions
  let cvdContribution = 0;
  let cancerContribution = 0;
  let otherContribution = 0;

  // Cumulative survival
  let baselineSurvival = 1.0;
  let interventionSurvival = 1.0;

  const yearlyBreakdown: LifecycleResult["yearlyBreakdown"] = [];

  for (let year = 0; year < maxAge - startAge; year++) {
    const currentAge = startAge + year;
    const baseQx = getAnnualMortalityRate(currentAge, sex);
    const causeFractions = getCauseFraction(currentAge);
    const quality = customQuality ?? getQualityWeight(currentAge);
    const discount = applyDiscount(1, year, discountRate);

    // Baseline QALY for this year
    const baselineQALY = baselineSurvival * quality * discount;
    baselineQALYs += baselineQALY;
    baselineLifeYears += baselineSurvival;

    // Calculate intervention mortality rate
    // Each cause's mortality is modified by its pathway-specific HR
    const interventionQx =
      baseQx *
      (causeFractions.cvd * pathwayHRs.cvd +
        causeFractions.cancer * pathwayHRs.cancer +
        causeFractions.other * pathwayHRs.other);

    // Intervention QALY for this year
    const interventionQALY = interventionSurvival * quality * discount;
    interventionQALYs += interventionQALY;
    interventionLifeYears += interventionSurvival;

    // Track pathway contributions
    // Contribution = QALY gained × (pathway's share of mortality reduction)
    const qalyDiff = interventionQALY - baselineQALY;
    if (qalyDiff > 0) {
      const totalMortalityReduction =
        causeFractions.cvd * (1 - pathwayHRs.cvd) +
        causeFractions.cancer * (1 - pathwayHRs.cancer) +
        causeFractions.other * (1 - pathwayHRs.other);

      if (totalMortalityReduction > 0) {
        cvdContribution +=
          (qalyDiff * causeFractions.cvd * (1 - pathwayHRs.cvd)) /
          totalMortalityReduction;
        cancerContribution +=
          (qalyDiff * causeFractions.cancer * (1 - pathwayHRs.cancer)) /
          totalMortalityReduction;
        otherContribution +=
          (qalyDiff * causeFractions.other * (1 - pathwayHRs.other)) /
          totalMortalityReduction;
      }
    }

    yearlyBreakdown.push({
      year,
      age: currentAge,
      survivalBaseline: baselineSurvival,
      survivalIntervention: interventionSurvival,
      qalyBaseline: baselineQALY,
      qalyIntervention: interventionQALY,
    });

    // Update survival for next year
    baselineSurvival *= 1 - baseQx;
    interventionSurvival *= 1 - interventionQx;

    // Stop if survival is negligible
    if (baselineSurvival < 0.001 && interventionSurvival < 0.001) {
      break;
    }
  }

  return {
    baselineQALYs,
    interventionQALYs,
    qalyGain: interventionQALYs - baselineQALYs,
    pathwayContributions: {
      cvd: cvdContribution,
      cancer: cancerContribution,
      other: otherContribution,
    },
    lifeYearsGained: interventionLifeYears - baselineLifeYears,
    yearlyBreakdown,
  };
}

/**
 * Convert overall HR to pathway-specific HRs
 *
 * Uses pathway weights from meta-analyses (Aune et al. 2016)
 */
export function hrToPathwayHRs(
  overallHR: number,
  weights: { cvd: number; cancer: number; other: number } = {
    cvd: 0.50, // CVD gets most benefit
    cancer: 0.30,
    other: 0.20,
  }
): PathwayHRs {
  // Convert overall HR to log scale
  const logHR = Math.log(overallHR);

  // Distribute effect across pathways proportionally to weights
  // Larger weight = more of the effect goes to that pathway
  return {
    cvd: Math.exp(logHR * weights.cvd * 2), // Scale so weights sum to ~1 effect
    cancer: Math.exp(logHR * weights.cancer * 2),
    other: Math.exp(logHR * weights.other * 2),
  };
}

/**
 * Standard pathway HRs from Aune et al. 2016 meta-analysis
 */
export const STANDARD_PATHWAY_HRS: PathwayHRs = {
  cvd: 0.75, // HR 0.75 for CVD mortality
  cancer: 0.87, // HR 0.87 for cancer mortality
  other: 0.90, // HR 0.90 for other mortality
};
