/**
 * NHANES Calibration Factors for Baseline QALY Calculation
 *
 * Generated from NHANES 2017-March 2020 (pre-pandemic) microdata.
 *
 * These factors represent the expected population-level hazard ratio (HR)
 * for mortality risk factors. Life tables already include people with
 * conditions like smoking, obesity, diabetes, etc. To avoid double-counting
 * when applying individual HRs, we calibrate:
 *
 * adjusted_individual_HR = individual_HR / population_HR
 *
 * This ensures that:
 * - A person with average risk factors gets the life table expectancy
 * - A person with below-average risk gets longer expectancy
 * - A person with above-average risk gets shorter expectancy
 *
 * Usage:
 *   const calibrationFactor = getCalibrationFactor(age, sex);
 *   const adjustedHR = individualHR / calibrationFactor;
 *   const adjustedLE = baselineLE * hrToLifeExpectancyMultiplier(adjustedHR);
 */

export interface CalibrationData {
  weightedMeanHR: number;
  n: number;
}

/**
 * Calibration factors by age group and sex.
 * Key format: "ageStart-ageEnd" -> { male: CalibrationData, female: CalibrationData }
 */
/**
 * Note: Some age groups (85+) may be missing if NHANES sample size insufficient
 */
export const CALIBRATION_BY_AGE_SEX: Record<
  string,
  Partial<Record<"male" | "female", CalibrationData>>
> = {
  "18-24": {
    "male": {
      "weightedMeanHR": 1.8136,
      "n": 918
    },
    "female": {
      "weightedMeanHR": 1.8746,
      "n": 920
    }
  },
  "25-34": {
    "male": {
      "weightedMeanHR": 2.4368,
      "n": 1084
    },
    "female": {
      "weightedMeanHR": 2.4272,
      "n": 1214
    }
  },
  "35-44": {
    "male": {
      "weightedMeanHR": 2.605,
      "n": 1018
    },
    "female": {
      "weightedMeanHR": 2.5871,
      "n": 1221
    }
  },
  "45-54": {
    "male": {
      "weightedMeanHR": 2.7883,
      "n": 1124
    },
    "female": {
      "weightedMeanHR": 3.0324,
      "n": 1163
    }
  },
  "55-64": {
    "male": {
      "weightedMeanHR": 3.0901,
      "n": 1450
    },
    "female": {
      "weightedMeanHR": 2.9073,
      "n": 1526
    }
  },
  "65-74": {
    "male": {
      "weightedMeanHR": 2.9299,
      "n": 1105
    },
    "female": {
      "weightedMeanHR": 3.0071,
      "n": 1054
    }
  },
  "75-84": {
    "male": {
      "weightedMeanHR": 2.8262,
      "n": 859
    },
    "female": {
      "weightedMeanHR": 2.9369,
      "n": 893
    }
  },
  "85-100": {}
};

/**
 * Overall calibration factors by sex only.
 */
export const CALIBRATION_BY_SEX: Record<"male" | "female", CalibrationData> = {
  "male": {
    "weightedMeanHR": 2.6415,
    "n": 7558
  },
  "female": {
    "weightedMeanHR": 2.6912,
    "n": 7991
  }
};

/**
 * Overall population calibration factor.
 */
export const CALIBRATION_OVERALL: CalibrationData = {
  weightedMeanHR: 2.6672,
  n: 15549,
};

/**
 * Age group boundaries for lookup.
 */
const AGE_GROUP_BOUNDS: Array<[number, number, string]> = [
  [18, 24, "18-24"],
  [25, 34, "25-34"],
  [35, 44, "35-44"],
  [45, 54, "45-54"],
  [55, 64, "55-64"],
  [65, 74, "65-74"],
  [75, 84, "75-84"],
  [85, 100, "85-100"],
];

/**
 * Get the age group string for a given age.
 */
function getAgeGroup(age: number): string | null {
  for (const [min, max, group] of AGE_GROUP_BOUNDS) {
    if (age >= min && age <= max) {
      return group;
    }
  }
  return null;
}

/**
 * Get the calibration factor (expected population HR) for a given age and sex.
 *
 * @param age - Age in years (18+)
 * @param sex - "male" or "female"
 * @returns The weighted mean HR for this demographic, or overall if not found
 */
export function getCalibrationFactor(
  age: number,
  sex: "male" | "female" | "other"
): number {
  // Use binary sex for lookup (average for "other")
  if (sex === "other") {
    const male = getCalibrationFactor(age, "male");
    const female = getCalibrationFactor(age, "female");
    return (male + female) / 2;
  }

  const ageGroup = getAgeGroup(age);
  if (ageGroup && CALIBRATION_BY_AGE_SEX[ageGroup]?.[sex]) {
    return CALIBRATION_BY_AGE_SEX[ageGroup][sex].weightedMeanHR;
  }

  // Fallback to sex-only calibration
  if (CALIBRATION_BY_SEX[sex]) {
    return CALIBRATION_BY_SEX[sex].weightedMeanHR;
  }

  // Ultimate fallback
  return CALIBRATION_OVERALL.weightedMeanHR;
}

/**
 * Prevalence statistics from NHANES (for reference/validation).
 */
export const POPULATION_PREVALENCE = {
  "smoking": 0.1676,
  "diabetes": 0.1124,
  "hypertension": 0.3173,
  "bmi_categories": {
    "obese1": 0.2147,
    "normal": 0.2647,
    "obese2": 0.1089,
    "overweight": 0.3081,
    "underweight": 0.0157,
    "obese3": 0.0879
  },
  "exercise_categories": {
    "low": 0.1047,
    "recommended": 0.093,
    "high": 0.0793,
    "veryHigh": 0.4734,
    "none": 0.2496
  },
  "sleep_categories": {
    "normal": 0.8129,
    "long": 0.1014,
    "short": 0.0857
  }
};
