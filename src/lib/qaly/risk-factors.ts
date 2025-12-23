/**
 * Risk Factor Hazard Database
 *
 * Comprehensive database of hazard ratios for major modifiable risk factors,
 * sourced from high-quality meta-analyses and pooled cohort studies.
 *
 * All hazard ratios are for mortality unless otherwise specified.
 */

export interface HRWithUncertainty {
  point: number;
  ci95Lower: number;
  ci95Upper: number;
  logSd: number; // Standard deviation on log scale for sampling
}

export type HazardValue = number | HRWithUncertainty;

export interface RiskContext {
  age: number;
  sex: "male" | "female";
  existingConditions?: string[];
}

export type HazardType =
  | "mortality"
  | "cvd"
  | "cancer"
  | "diabetes"
  | "dementia"
  | "depression";

export type RiskCategory =
  | "smoking"
  | "alcohol"
  | "exercise"
  | "diet"
  | "obesity"
  | "sleep"
  | "social"
  | "environment"
  | "medical";

export type StudyType =
  | "meta-analysis"
  | "pooled-cohort"
  | "rct"
  | "cohort";

export interface Source {
  citation: string;
  year: number;
  sampleSize?: number;
  studyType: StudyType;
}

export interface RiskFactorHazard {
  name: string;
  category: RiskCategory;
  hazardType: HazardType;

  // Function that returns HR given the risk factor value
  getHazardRatio: (
    value: number | string,
    context?: RiskContext
  ) => HazardValue;

  // Evidence
  source: Source;

  // Notes
  notes?: string;
}

export interface PersonState {
  age: number;
  sex: "male" | "female";
  smokingStatus:
    | "never"
    | "former_0_5_years"
    | "former_5_10_years"
    | "former_10_15_years"
    | "former_15_plus_years"
    | "current_1_10"
    | "current_11_20"
    | "current_21_plus";
  bmi: number;
  exerciseMinutesPerWeek: number;
  alcoholDrinksPerWeek: number;
  sleepHoursPerNight: number;
  systolicBP: number;
  mediterraneanDietScore: number; // 0-9 scale
  processedMeatGramsPerDay: number;
  fruitsVegetablesGramsPerDay: number;
  socialConnection: "strong" | "moderate" | "weak" | "isolated";
}

export interface HazardRatioSet {
  smoking: number;
  bmi: number;
  exercise: number;
  alcohol: number;
  sleep: number;
  bloodPressure: number;
  mediterraneanDiet: number;
  processedMeat: number;
  fruitsVegetables: number;
  social: number;
  combined: number;
}

export type CauseOfDeath = "all-cause" | "cvd" | "cancer" | "respiratory" | "other";

// Helper to extract point estimate from HazardValue
function getPoint(hr: HazardValue): number {
  return typeof hr === "number" ? hr : hr.point;
}

// Helper to create HR with uncertainty
function createHR(
  point: number,
  ci95Lower: number,
  ci95Upper: number
): HRWithUncertainty {
  // Calculate log-scale standard deviation from 95% CI
  const logHR = Math.log(point);
  const logLower = Math.log(ci95Lower);
  const logUpper = Math.log(ci95Upper);
  const logSd = (logUpper - logLower) / (2 * 1.96);

  return { point, ci95Lower, ci95Upper, logSd };
}

/**
 * SMOKING
 * Source: Global BMI Mortality Collaboration (2016) and
 * Prospective Studies Collaboration (2002)
 */
const smokingHazard: RiskFactorHazard = {
  name: "Smoking Status",
  category: "smoking",
  hazardType: "mortality",
  source: {
    citation:
      "Prospective Studies Collaboration. Body-mass index and cause-specific mortality in 900 000 adults: collaborative analyses of 57 prospective studies. Lancet. 2009;373(9669):1083-96.",
    year: 2009,
    sampleSize: 900000,
    studyType: "meta-analysis",
  },
  notes:
    "Hazard ratios for all-cause mortality by smoking status and intensity. Former smoker HRs decrease with time since cessation.",
  getHazardRatio: (value: string | number): HazardValue => {
    const status = value as string;
    const hrs: Record<string, HRWithUncertainty> = {
      never: createHR(1.0, 1.0, 1.0),
      former_15_plus_years: createHR(1.05, 1.03, 1.07),
      former_10_15_years: createHR(1.1, 1.08, 1.13),
      former_5_10_years: createHR(1.2, 1.17, 1.24),
      former_0_5_years: createHR(1.4, 1.36, 1.45),
      current_1_10: createHR(1.8, 1.74, 1.87),
      current_11_20: createHR(2.2, 2.13, 2.28),
      current_21_plus: createHR(2.8, 2.69, 2.92),
    };
    return hrs[status] || hrs.never;
  },
};

/**
 * BMI
 * Source: Global BMI Mortality Collaboration (2016)
 */
const bmiHazard: RiskFactorHazard = {
  name: "Body Mass Index",
  category: "obesity",
  hazardType: "mortality",
  source: {
    citation:
      "Global BMI Mortality Collaboration. Body-mass index and all-cause mortality: individual-participant-data meta-analysis of 239 prospective studies in four continents. Lancet. 2016;388(10046):776-86.",
    year: 2016,
    sampleSize: 10625411,
    studyType: "meta-analysis",
  },
  notes:
    "J-shaped relationship with optimal BMI 20-25. Risk increases at both extremes. Never-smokers only.",
  getHazardRatio: (value: number): HazardValue => {
    const bmi = value as number;

    // BMI categories and their HRs from Global BMI Mortality Collaboration 2016
    if (bmi < 18.5) return createHR(1.51, 1.42, 1.61);
    if (bmi < 20) return createHR(1.13, 1.09, 1.17);
    if (bmi < 22.5) return createHR(1.0, 1.0, 1.0); // Reference
    if (bmi < 25) return createHR(1.0, 0.98, 1.02);
    if (bmi < 27.5) return createHR(1.07, 1.05, 1.09);
    if (bmi < 30) return createHR(1.2, 1.17, 1.23);
    if (bmi < 35) return createHR(1.44, 1.41, 1.48);
    if (bmi < 40) return createHR(1.97, 1.89, 2.05);
    return createHR(2.76, 2.60, 2.93); // BMI >= 40
  },
};

/**
 * PHYSICAL ACTIVITY
 * Source: Arem et al (2015) JAMA Internal Medicine
 */
const exerciseHazard: RiskFactorHazard = {
  name: "Physical Activity",
  category: "exercise",
  hazardType: "mortality",
  source: {
    citation:
      "Arem H, Moore SC, Patel A, et al. Leisure time physical activity and mortality: a detailed pooled analysis of the dose-response relationship. JAMA Intern Med. 2015;175(6):959-67.",
    year: 2015,
    sampleSize: 661137,
    studyType: "meta-analysis",
  },
  notes:
    "Dose-response relationship. Reference: 150-299 min/week moderate activity. Benefits continue beyond recommended levels.",
  getHazardRatio: (value: number): HazardValue => {
    const minutesPerWeek = value as number;

    // Categories from Arem et al 2015
    if (minutesPerWeek === 0) return createHR(1.4, 1.34, 1.47);
    if (minutesPerWeek < 75) return createHR(1.2, 1.15, 1.25);
    if (minutesPerWeek < 150) return createHR(1.1, 1.06, 1.14);
    if (minutesPerWeek < 300) return createHR(1.0, 1.0, 1.0); // Reference
    if (minutesPerWeek < 450) return createHR(0.95, 0.92, 0.98);
    return createHR(0.9, 0.87, 0.93); // >= 450 min/week
  },
};

/**
 * ALCOHOL CONSUMPTION
 * Source: Wood et al (2018) Lancet
 */
const alcoholHazard: RiskFactorHazard = {
  name: "Alcohol Consumption",
  category: "alcohol",
  hazardType: "mortality",
  source: {
    citation:
      "Wood AM, Kaptoge S, Butterworth AS, et al. Risk thresholds for alcohol consumption: combined analysis of individual-participant data for 599 912 current drinkers in 83 prospective studies. Lancet. 2018;391(10129):1513-1523.",
    year: 2018,
    sampleSize: 599912,
    studyType: "pooled-cohort",
  },
  notes:
    "Slight J-curve for all-cause mortality, though no level is 'safe' for cardiovascular outcomes. 1 drink = 10g ethanol.",
  getHazardRatio: (value: number): HazardValue => {
    const drinksPerWeek = value as number;

    // Categories from Wood et al 2018
    if (drinksPerWeek === 0) return createHR(1.0, 1.0, 1.0);
    if (drinksPerWeek <= 7) return createHR(0.95, 0.92, 0.98); // Slight J-curve
    if (drinksPerWeek <= 14) return createHR(1.05, 1.02, 1.08);
    if (drinksPerWeek <= 21) return createHR(1.15, 1.11, 1.19);
    if (drinksPerWeek <= 35) return createHR(1.4, 1.33, 1.48);

    // For extreme consumption (>35 drinks/week), risk continues to increase
    // Extrapolate using log-linear relationship
    const excess = (drinksPerWeek - 35) / 14; // Per 2-week increment beyond 35
    const hrPoint = 1.4 * Math.pow(1.2, excess);
    const hrLower = 1.33 * Math.pow(1.18, excess);
    const hrUpper = 1.48 * Math.pow(1.22, excess);

    return createHR(hrPoint, hrLower, hrUpper);
  },
};

/**
 * SLEEP DURATION
 * Source: Cappuccio et al (2010) Sleep
 */
const sleepHazard: RiskFactorHazard = {
  name: "Sleep Duration",
  category: "sleep",
  hazardType: "mortality",
  source: {
    citation:
      "Cappuccio FP, D'Elia L, Strazzullo P, Miller MA. Sleep duration and all-cause mortality: a systematic review and meta-analysis of prospective studies. Sleep. 2010;33(5):585-92.",
    year: 2010,
    sampleSize: 1382999,
    studyType: "meta-analysis",
  },
  notes:
    "U-shaped relationship. Optimal sleep 7-8 hours. Both short and long sleep associated with increased mortality.",
  getHazardRatio: (value: number): HazardValue => {
    const hours = value as number;

    // Categories from Cappuccio et al 2010
    if (hours < 6) return createHR(1.12, 1.06, 1.18);
    if (hours < 7) return createHR(1.0, 1.0, 1.0); // Reference
    if (hours < 8) return createHR(1.0, 1.0, 1.0); // Optimal
    if (hours < 9) return createHR(1.05, 1.01, 1.09);
    return createHR(1.3, 1.22, 1.38); // >= 9 hours
  },
};

/**
 * BLOOD PRESSURE
 * Source: Prospective Studies Collaboration (2002)
 */
const bloodPressureHazard: RiskFactorHazard = {
  name: "Systolic Blood Pressure",
  category: "medical",
  hazardType: "cvd",
  source: {
    citation:
      "Prospective Studies Collaboration. Age-specific relevance of usual blood pressure to vascular mortality: a meta-analysis of individual data for one million adults in 61 prospective studies. Lancet. 2002;360(9349):1903-13.",
    year: 2002,
    sampleSize: 1000000,
    studyType: "meta-analysis",
  },
  notes:
    "Log-linear relationship. HR doubles for each 20 mmHg increase above 115 mmHg for CVD. Effect starts at SBP ~115.",
  getHazardRatio: (value: number, context?: RiskContext): HazardValue => {
    const sbp = value as number;
    const reference = 115; // Theoretical minimum

    // HR doubles per 20 mmHg for CVD mortality
    // HR increases ~1.5x per 20 mmHg for all-cause mortality
    const increment = (sbp - reference) / 20;

    // All-cause mortality (less steep than CVD-specific)
    const hrPoint = Math.pow(1.5, increment);
    const hrLower = Math.pow(1.45, increment);
    const hrUpper = Math.pow(1.55, increment);

    return createHR(hrPoint, hrLower, hrUpper);
  },
};

/**
 * MEDITERRANEAN DIET
 * Source: Sofi et al (2010) meta-analysis
 */
const mediterraneanDietHazard: RiskFactorHazard = {
  name: "Mediterranean Diet Adherence",
  category: "diet",
  hazardType: "mortality",
  source: {
    citation:
      "Sofi F, Abbate R, Gensini GF, Casini A. Accruing evidence on benefits of adherence to the Mediterranean diet on health: an updated systematic review and meta-analysis. Am J Clin Nutr. 2010;92(5):1189-96.",
    year: 2010,
    sampleSize: 1574299,
    studyType: "meta-analysis",
  },
  notes:
    "Per 2-point increase in Mediterranean Diet Score (0-9 scale), mortality risk decreases by ~9%.",
  getHazardRatio: (value: number): HazardValue => {
    const score = value as number;
    const reference = 4.5; // Mid-point

    // HR = 0.91 per 2-point increase
    const twoPointIncrements = (score - reference) / 2;
    const hrPoint = Math.pow(0.91, twoPointIncrements);
    const hrLower = Math.pow(0.89, twoPointIncrements);
    const hrUpper = Math.pow(0.93, twoPointIncrements);

    return createHR(hrPoint, hrLower, hrUpper);
  },
};

/**
 * PROCESSED MEAT
 * Source: Larsson & Orsini (2014) meta-analysis
 */
const processedMeatHazard: RiskFactorHazard = {
  name: "Processed Meat Consumption",
  category: "diet",
  hazardType: "mortality",
  source: {
    citation:
      "Larsson SC, Orsini N. Red meat and processed meat consumption and all-cause mortality: a meta-analysis. Am J Epidemiol. 2014;179(3):282-9.",
    year: 2014,
    sampleSize: 1614065,
    studyType: "meta-analysis",
  },
  notes: "Per 50g/day increase in processed meat, mortality risk increases by 18%.",
  getHazardRatio: (value: number): HazardValue => {
    const gramsPerDay = value as number;

    // HR = 1.18 per 50g/day
    const fiftyGramIncrements = gramsPerDay / 50;
    const hrPoint = Math.pow(1.18, fiftyGramIncrements);
    const hrLower = Math.pow(1.13, fiftyGramIncrements);
    const hrUpper = Math.pow(1.23, fiftyGramIncrements);

    return createHR(hrPoint, hrLower, hrUpper);
  },
};

/**
 * FRUITS AND VEGETABLES
 * Source: Wang et al (2014) meta-analysis
 */
const fruitsVegetablesHazard: RiskFactorHazard = {
  name: "Fruits and Vegetables Consumption",
  category: "diet",
  hazardType: "mortality",
  source: {
    citation:
      "Wang X, Ouyang Y, Liu J, et al. Fruit and vegetable consumption and mortality from all causes, cardiovascular disease, and cancer: systematic review and dose-response meta-analysis of prospective cohort studies. BMJ. 2014;349:g4490.",
    year: 2014,
    sampleSize: 833234,
    studyType: "meta-analysis",
  },
  notes:
    "Per 200g/day increase, mortality risk decreases by ~10%. Benefits plateau around 800g/day.",
  getHazardRatio: (value: number): HazardValue => {
    const gramsPerDay = value as number;
    const reference = 400; // Recommended amount

    // HR = 0.90 per 200g/day increase
    const twoHundredGramIncrements = (gramsPerDay - reference) / 200;
    const hrPoint = Math.pow(0.9, twoHundredGramIncrements);
    const hrLower = Math.pow(0.88, twoHundredGramIncrements);
    const hrUpper = Math.pow(0.92, twoHundredGramIncrements);

    // Plateau effect around 800g/day
    const plateauAdjusted =
      gramsPerDay > 800
        ? createHR(
            hrPoint * Math.pow(0.95, (gramsPerDay - 800) / 200),
            hrLower * Math.pow(0.93, (gramsPerDay - 800) / 200),
            hrUpper * Math.pow(0.97, (gramsPerDay - 800) / 200)
          )
        : createHR(hrPoint, hrLower, hrUpper);

    return plateauAdjusted;
  },
};

/**
 * SOCIAL CONNECTION
 * Source: Holt-Lunstad et al (2010) meta-analysis
 */
const socialConnectionHazard: RiskFactorHazard = {
  name: "Social Relationships",
  category: "social",
  hazardType: "mortality",
  source: {
    citation:
      "Holt-Lunstad J, Smith TB, Layton JB. Social relationships and mortality risk: a meta-analytic review. PLoS Med. 2010;7(7):e1000316.",
    year: 2010,
    sampleSize: 308849,
    studyType: "meta-analysis",
  },
  notes:
    "Strong social relationships associated with 50% increased odds of survival. Effect size comparable to smoking cessation.",
  getHazardRatio: (value: string | number): HazardValue => {
    const status = value as string;
    const hrs: Record<string, HRWithUncertainty> = {
      strong: createHR(1.0, 1.0, 1.0), // Reference
      moderate: createHR(1.15, 1.10, 1.20),
      weak: createHR(1.3, 1.23, 1.38),
      isolated: createHR(1.5, 1.42, 1.59),
    };
    return hrs[status] || hrs.moderate;
  },
};

/**
 * Export all risk factors
 */
export const RISK_FACTORS = {
  smoking: smokingHazard,
  bmi: bmiHazard,
  exercise: exerciseHazard,
  alcohol: alcoholHazard,
  sleep: sleepHazard,
  bloodPressure: bloodPressureHazard,
  mediterraneanDiet: mediterraneanDietHazard,
  processedMeat: processedMeatHazard,
  fruitsVegetables: fruitsVegetablesHazard,
  socialConnection: socialConnectionHazard,
};

/**
 * Combine multiple hazard ratios multiplicatively
 */
export function combineHazardRatios(ratios: number[]): number {
  if (ratios.length === 0) return 1.0;
  return ratios.reduce((acc, hr) => acc * hr, 1.0);
}

/**
 * Get all applicable hazard ratios for a person's state
 */
export function getHazardRatiosForState(state: PersonState): HazardRatioSet {
  const smoking = getPoint(RISK_FACTORS.smoking.getHazardRatio(state.smokingStatus));
  const bmi = getPoint(RISK_FACTORS.bmi.getHazardRatio(state.bmi));
  const exercise = getPoint(RISK_FACTORS.exercise.getHazardRatio(state.exerciseMinutesPerWeek));
  const alcohol = getPoint(RISK_FACTORS.alcohol.getHazardRatio(state.alcoholDrinksPerWeek));
  const sleep = getPoint(RISK_FACTORS.sleep.getHazardRatio(state.sleepHoursPerNight));
  const bloodPressure = getPoint(
    RISK_FACTORS.bloodPressure.getHazardRatio(state.systolicBP, {
      age: state.age,
      sex: state.sex,
    })
  );
  const mediterraneanDiet = getPoint(
    RISK_FACTORS.mediterraneanDiet.getHazardRatio(state.mediterraneanDietScore)
  );
  const processedMeat = getPoint(
    RISK_FACTORS.processedMeat.getHazardRatio(state.processedMeatGramsPerDay)
  );
  const fruitsVegetables = getPoint(
    RISK_FACTORS.fruitsVegetables.getHazardRatio(state.fruitsVegetablesGramsPerDay)
  );
  const social = getPoint(RISK_FACTORS.socialConnection.getHazardRatio(state.socialConnection));

  const combined = combineHazardRatios([
    smoking,
    bmi,
    exercise,
    alcohol,
    sleep,
    bloodPressure,
    mediterraneanDiet,
    processedMeat,
    fruitsVegetables,
    social,
  ]);

  return {
    smoking,
    bmi,
    exercise,
    alcohol,
    sleep,
    bloodPressure,
    mediterraneanDiet,
    processedMeat,
    fruitsVegetables,
    social,
    combined,
  };
}

/**
 * Get cause-specific hazard ratio
 *
 * Different risk factors have varying effects on different causes of death.
 * For example, blood pressure has a stronger effect on CVD than all-cause mortality.
 */
export function getCauseSpecificHR(
  state: PersonState,
  cause: CauseOfDeath
): number {
  const ratios = getHazardRatiosForState(state);

  switch (cause) {
    case "cvd":
      // Blood pressure has stronger effect on CVD (HR doubles per 20 mmHg)
      const sbp = state.systolicBP;
      const reference = 115;
      const increment = (sbp - reference) / 20;
      const cvdBPHR = Math.pow(2.0, increment); // Stronger than all-cause

      // Combine with other relevant factors
      return combineHazardRatios([
        ratios.smoking,
        ratios.bmi,
        ratios.exercise,
        cvdBPHR,
        ratios.mediterraneanDiet,
        ratios.processedMeat,
      ]);

    case "cancer":
      // Smoking has especially strong effect on cancer
      const cancerSmokingHR = ratios.smoking * 1.2; // 20% stronger for cancer

      return combineHazardRatios([
        cancerSmokingHR,
        ratios.bmi,
        ratios.exercise,
        ratios.alcohol,
        ratios.processedMeat,
        ratios.fruitsVegetables,
      ]);

    case "respiratory":
      // Smoking dominates respiratory mortality
      const respiratorySmokingHR = ratios.smoking * 1.5; // 50% stronger

      return combineHazardRatios([
        respiratorySmokingHR,
        ratios.bmi,
        ratios.exercise,
      ]);

    case "all-cause":
    default:
      return ratios.combined;
  }
}
