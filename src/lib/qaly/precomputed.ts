/**
 * Precomputed intervention effects for common lifestyle changes
 *
 * These are derived from meta-analyses and high-quality RCTs.
 * They allow instant QALY calculations without calling Claude.
 */

import type { InterventionEffect, MechanismEffect, Distribution } from "./types";
import type { Mechanism } from "./mechanisms";

export interface PrecomputedIntervention {
  id: string;
  name: string;
  description: string;
  counterfactual?: string; // What this is compared against (default: not doing intervention)
  keywords: string[]; // For matching user queries
  category: "exercise" | "diet" | "sleep" | "substance" | "medical" | "stress";
  effect: InterventionEffect;
  sources: {
    citation: string;
    studyType: "meta-analysis" | "rct" | "cohort" | "review";
    year?: number;
    sampleSize?: number;
  }[];
}

export interface MatchResult {
  id: string;
  intervention: PrecomputedIntervention;
  confidence: number; // 0-1, how confident we are this is the right match
  matchedKeywords: string[];
}

// Helper to create normal distribution
const normal = (mean: number, sd: number): Distribution => ({
  type: "normal",
  mean,
  sd,
});

// Helper to create lognormal distribution (for HRs)
const lognormal = (logMean: number, logSd: number): Distribution => ({
  type: "lognormal",
  logMean,
  logSd,
});

// Helper to create mechanism effect
const mech = (
  mechanism: Mechanism,
  direction: "increase" | "decrease",
  effectSize: Distribution,
  evidenceQuality: "strong" | "moderate" | "weak",
  units?: string,
  source?: string
): MechanismEffect => ({
  mechanism,
  direction,
  effectSize,
  evidenceQuality,
  units,
  source,
});

/**
 * Library of precomputed interventions
 */
export const PRECOMPUTED_INTERVENTIONS: Record<string, PrecomputedIntervention> = {
  // ==================== EXERCISE ====================
  walking_30min_daily: {
    id: "walking_30min_daily",
    name: "Walk 30 minutes daily",
    description: "Moderate-paced walking for 30 minutes per day",
    keywords: [
      "walk",
      "walking",
      "30 minutes",
      "daily walk",
      "step",
      "steps",
      "10000 steps",
      "10k steps",
    ],
    category: "exercise",
    effect: {
      description: "30 minutes of daily walking",
      category: "exercise",
      mechanismEffects: [
        mech("blood_pressure", "decrease", normal(-4, 2), "strong", "mmHg", "Cornelissen 2013"),
        mech("lipid_profile", "decrease", normal(-5, 3), "moderate", "% LDL", "Mann 2014"),
        mech("insulin_sensitivity", "increase", normal(15, 8), "strong", "%", "Colberg 2016"),
        mech("systemic_inflammation", "decrease", normal(-15, 8), "moderate", "% CRP"),
        mech("adiposity", "decrease", normal(-2, 1.5), "moderate", "% body fat"),
        mech("sleep_quality", "increase", normal(0.3, 0.15), "moderate", "SD"),
        mech("neurotransmitter_balance", "increase", normal(0.25, 0.15), "moderate", "SD"),
        mech("cardiac_output", "increase", normal(8, 4), "moderate", "%"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.18, 0.08), // HR ~0.84
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "high",
      keySources: [],
      caveats: ["Benefits may plateau with higher baseline activity"],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Hamer & Chida, 2008. Walking and primary prevention: a meta-analysis",
        studyType: "meta-analysis",
        year: 2008,
        sampleSize: 459833,
      },
      {
        citation: "Cornelissen & Smart, 2013. Exercise training for blood pressure",
        studyType: "meta-analysis",
        year: 2013,
      },
    ],
  },

  running_moderate: {
    id: "running_moderate",
    name: "Run 3x per week",
    description: "Moderate running/jogging 3 times per week, 20-30 minutes",
    keywords: ["run", "running", "jog", "jogging", "cardio"],
    category: "exercise",
    effect: {
      description: "Running 3x per week",
      category: "exercise",
      mechanismEffects: [
        mech("blood_pressure", "decrease", normal(-6, 3), "strong", "mmHg"),
        mech("lipid_profile", "decrease", normal(-8, 4), "strong", "% LDL"),
        mech("insulin_sensitivity", "increase", normal(25, 12), "strong", "%"),
        mech("systemic_inflammation", "decrease", normal(-25, 10), "strong", "% CRP"),
        mech("adiposity", "decrease", normal(-4, 2), "strong", "% body fat"),
        mech("cardiac_output", "increase", normal(15, 6), "strong", "%"),
        mech("lung_function", "increase", normal(10, 5), "strong", "% VO2max"),
        mech("bone_density", "increase", normal(1.5, 1), "moderate", "%"),
        mech("bdnf_levels", "increase", normal(20, 10), "moderate", "%"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.25, 0.1), // HR ~0.78
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "high",
      keySources: [],
      caveats: ["Risk of injury increases with intensity"],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Lee et al., 2014. Leisure-time running and all-cause mortality",
        studyType: "cohort",
        year: 2014,
        sampleSize: 55137,
      },
    ],
  },

  strength_training: {
    id: "strength_training",
    name: "Strength training 2x per week",
    description: "Resistance/weight training twice weekly",
    keywords: [
      "strength",
      "weights",
      "resistance",
      "gym",
      "lifting",
      "lift weights",
      "weight training",
      "resistance training",
    ],
    category: "exercise",
    effect: {
      description: "Strength training 2x per week",
      category: "exercise",
      mechanismEffects: [
        mech("muscle_mass", "increase", normal(5, 3), "strong", "%"),
        mech("bone_density", "increase", normal(2, 1), "strong", "%"),
        mech("insulin_sensitivity", "increase", normal(20, 10), "strong", "%"),
        mech("metabolic_rate", "increase", normal(5, 3), "moderate", "%"),
        mech("blood_pressure", "decrease", normal(-3, 2), "moderate", "mmHg"),
        mech("balance_proprioception", "increase", normal(0.4, 0.2), "moderate", "SD"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.15, 0.08), // HR ~0.86
        onsetDelay: 0,
        rampUpPeriod: 1,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "high",
      keySources: [],
      caveats: ["Benefits most pronounced in older adults"],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Momma et al., 2022. Muscle-strengthening activities and mortality",
        studyType: "meta-analysis",
        year: 2022,
      },
    ],
  },

  // ==================== SMOKING ====================
  quit_smoking: {
    id: "quit_smoking",
    name: "Quit smoking",
    description: "Complete smoking cessation",
    keywords: [
      "quit smoking",
      "stop smoking",
      "give up smoking",
      "cigarettes",
      "tobacco",
      "smoking cessation",
    ],
    category: "substance",
    effect: {
      description: "Quit smoking",
      category: "substance",
      mechanismEffects: [
        mech("lung_function", "increase", normal(15, 8), "strong", "% improvement"),
        mech("systemic_inflammation", "decrease", normal(-40, 15), "strong", "% CRP"),
        mech("endothelial_function", "increase", normal(30, 12), "strong", "%"),
        mech("blood_pressure", "decrease", normal(-5, 3), "strong", "mmHg"),
        mech("oxidative_stress", "decrease", normal(-35, 15), "strong", "%"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.55, 0.15), // HR ~0.58 (dramatic reduction)
        onsetDelay: 0,
        rampUpPeriod: 5, // Full benefit takes years
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "high",
      keySources: [],
      caveats: [
        "Benefits depend on years smoked and pack-years",
        "Full mortality benefit takes 10-15 years",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Thun et al., 2013. 50-year trends in smoking-related mortality",
        studyType: "cohort",
        year: 2013,
        sampleSize: 200000,
      },
      {
        citation: "Jha et al., 2013. 21st-century hazards of smoking",
        studyType: "cohort",
        year: 2013,
      },
    ],
  },

  // ==================== ALCOHOL ====================
  reduce_alcohol_moderate: {
    id: "reduce_alcohol_moderate",
    name: "Reduce alcohol to moderate levels",
    description: "Reduce drinking to 1-2 drinks per day or less",
    keywords: [
      "alcohol",
      "drinking",
      "drink less",
      "reduce alcohol",
      "cut down drinking",
      "less beer",
      "less wine",
    ],
    category: "substance",
    effect: {
      description: "Reduce alcohol to moderate levels",
      category: "substance",
      mechanismEffects: [
        mech("blood_pressure", "decrease", normal(-4, 2), "strong", "mmHg"),
        mech("lipid_profile", "decrease", normal(-5, 3), "moderate", "% triglycerides"),
        mech("sleep_quality", "increase", normal(0.3, 0.15), "moderate", "SD"),
        mech("systemic_inflammation", "decrease", normal(-10, 6), "moderate", "% CRP"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.12, 0.08), // HR ~0.89
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "moderate",
      keySources: [],
      caveats: ["Effect size depends on baseline consumption"],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Wood et al., 2018. Risk thresholds for alcohol consumption",
        studyType: "meta-analysis",
        year: 2018,
        sampleSize: 599912,
      },
    ],
  },

  quit_alcohol: {
    id: "quit_alcohol",
    name: "Quit alcohol completely",
    description: "Complete alcohol abstinence",
    keywords: ["quit drinking", "stop drinking", "no alcohol", "sober", "abstain"],
    category: "substance",
    effect: {
      description: "Quit alcohol completely",
      category: "substance",
      mechanismEffects: [
        mech("blood_pressure", "decrease", normal(-6, 3), "strong", "mmHg"),
        mech("sleep_quality", "increase", normal(0.4, 0.2), "strong", "SD"),
        mech("systemic_inflammation", "decrease", normal(-20, 10), "moderate", "% CRP"),
        mech("glucose_regulation", "increase", normal(10, 5), "moderate", "%"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.08, 0.1), // HR ~0.92 (modest, J-curve debate)
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "moderate",
      keySources: [],
      caveats: [
        "J-curve debate: moderate drinking may have some benefits",
        "Benefits larger for heavy drinkers",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "GBD 2016 Alcohol Collaborators. Alcohol use and burden",
        studyType: "meta-analysis",
        year: 2018,
      },
    ],
  },

  // ==================== DIET ====================
  mediterranean_diet: {
    id: "mediterranean_diet",
    name: "Adopt Mediterranean diet",
    description: "Follow Mediterranean dietary pattern",
    keywords: [
      "mediterranean",
      "mediterranean diet",
      "olive oil",
      "fish",
      "vegetables",
      "healthy eating",
    ],
    category: "diet",
    effect: {
      description: "Mediterranean diet",
      category: "diet",
      mechanismEffects: [
        mech("systemic_inflammation", "decrease", normal(-20, 10), "strong", "% CRP"),
        mech("lipid_profile", "decrease", normal(-10, 5), "strong", "% LDL"),
        mech("blood_pressure", "decrease", normal(-3, 2), "moderate", "mmHg"),
        mech("insulin_sensitivity", "increase", normal(15, 8), "strong", "%"),
        mech("gut_microbiome", "increase", normal(0.3, 0.15), "moderate", "SD diversity"),
        mech("oxidative_stress", "decrease", normal(-15, 8), "moderate", "%"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.22, 0.1), // HR ~0.80
        onsetDelay: 0,
        rampUpPeriod: 1,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "high",
      keySources: [],
      caveats: ["Adherence is key; partial adoption shows partial benefits"],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Estruch et al., 2018. PREDIMED trial (retracted and republished)",
        studyType: "rct",
        year: 2018,
        sampleSize: 7447,
      },
      {
        citation: "Sofi et al., 2014. Mediterranean diet and health status meta-analysis",
        studyType: "meta-analysis",
        year: 2014,
      },
    ],
  },

  reduce_processed_food: {
    id: "reduce_processed_food",
    name: "Reduce ultra-processed food",
    description: "Cut ultra-processed food intake by 50%",
    keywords: [
      "processed food",
      "junk food",
      "fast food",
      "packaged food",
      "whole foods",
      "eat clean",
    ],
    category: "diet",
    effect: {
      description: "Reduce ultra-processed food by 50%",
      category: "diet",
      mechanismEffects: [
        mech("systemic_inflammation", "decrease", normal(-12, 6), "moderate", "% CRP"),
        mech("adiposity", "decrease", normal(-2, 1.5), "moderate", "% body fat"),
        mech("insulin_sensitivity", "increase", normal(10, 6), "moderate", "%"),
        mech("gut_microbiome", "increase", normal(0.2, 0.1), "weak", "SD"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.12, 0.08), // HR ~0.89
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "moderate",
      keySources: [],
      caveats: ["Observational data; RCT evidence limited"],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Lane et al., 2024. Ultra-processed food and mortality",
        studyType: "meta-analysis",
        year: 2024,
      },
    ],
  },

  increase_vegetables: {
    id: "increase_vegetables",
    name: "Eat more vegetables",
    description: "Increase vegetable intake to 5+ servings daily",
    keywords: [
      "vegetables",
      "veggies",
      "greens",
      "salad",
      "more vegetables",
      "eat vegetables",
      "plant based",
    ],
    category: "diet",
    effect: {
      description: "Increase vegetables to 5+ servings daily",
      category: "diet",
      mechanismEffects: [
        mech("systemic_inflammation", "decrease", normal(-10, 5), "moderate", "% CRP"),
        mech("blood_pressure", "decrease", normal(-2, 1.5), "moderate", "mmHg"),
        mech("gut_microbiome", "increase", normal(0.25, 0.12), "moderate", "SD"),
        mech("oxidative_stress", "decrease", normal(-10, 6), "moderate", "%"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.1, 0.06), // HR ~0.90
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "moderate",
      keySources: [],
      caveats: ["Benefits plateau around 5 servings/day"],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Aune et al., 2017. Fruit and vegetable intake and mortality",
        studyType: "meta-analysis",
        year: 2017,
      },
    ],
  },

  reduce_sugar: {
    id: "reduce_sugar",
    name: "Reduce added sugar",
    description: "Cut added sugar intake by 50%",
    keywords: ["sugar", "reduce sugar", "cut sugar", "less sugar", "no sugar", "sweets"],
    category: "diet",
    effect: {
      description: "Reduce added sugar by 50%",
      category: "diet",
      mechanismEffects: [
        mech("insulin_sensitivity", "increase", normal(15, 8), "strong", "%"),
        mech("adiposity", "decrease", normal(-2, 1.5), "moderate", "% body fat"),
        mech("systemic_inflammation", "decrease", normal(-8, 5), "moderate", "% CRP"),
        mech("lipid_profile", "decrease", normal(-8, 5), "moderate", "% triglycerides"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.08, 0.06), // HR ~0.92
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "moderate",
      keySources: [],
      caveats: ["Effect depends on baseline sugar intake"],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Malik et al., 2010. Sugar-sweetened beverages and cardiometabolic risk",
        studyType: "meta-analysis",
        year: 2010,
      },
    ],
  },

  // ==================== SLEEP ====================
  improve_sleep_8hrs: {
    id: "improve_sleep_8hrs",
    name: "Improve sleep to 7-8 hours",
    description: "Consistently sleep 7-8 hours per night",
    keywords: [
      "sleep",
      "sleep more",
      "8 hours sleep",
      "better sleep",
      "sleep quality",
      "insomnia",
    ],
    category: "sleep",
    effect: {
      description: "Improve sleep to 7-8 hours nightly",
      category: "sleep",
      mechanismEffects: [
        mech("sleep_quality", "increase", normal(0.5, 0.2), "strong", "SD"),
        mech("systemic_inflammation", "decrease", normal(-15, 8), "moderate", "% CRP"),
        mech("insulin_sensitivity", "increase", normal(12, 6), "moderate", "%"),
        mech("stress_hormones", "decrease", normal(-15, 8), "moderate", "% cortisol"),
        mech("cognitive_reserve", "increase", normal(0.2, 0.1), "moderate", "SD"),
        mech("neurotransmitter_balance", "increase", normal(0.2, 0.1), "moderate", "SD"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.1, 0.06), // HR ~0.90
        onsetDelay: 0,
        rampUpPeriod: 0.25,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "moderate",
      keySources: [],
      caveats: ["Both short and long sleep associated with increased mortality"],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Cappuccio et al., 2010. Sleep duration and mortality meta-analysis",
        studyType: "meta-analysis",
        year: 2010,
        sampleSize: 1382999,
      },
    ],
  },

  // ==================== STRESS ====================
  meditation_daily: {
    id: "meditation_daily",
    name: "Daily meditation",
    description: "10-20 minutes of daily meditation or mindfulness",
    keywords: [
      "meditation",
      "meditate",
      "mindfulness",
      "mindful",
      "stress reduction",
      "relaxation",
    ],
    category: "stress",
    effect: {
      description: "Daily meditation practice",
      category: "stress",
      mechanismEffects: [
        mech("stress_hormones", "decrease", normal(-15, 8), "moderate", "% cortisol"),
        mech("blood_pressure", "decrease", normal(-3, 2), "moderate", "mmHg"),
        mech("systemic_inflammation", "decrease", normal(-8, 5), "weak", "% CRP"),
        mech("sleep_quality", "increase", normal(0.2, 0.1), "moderate", "SD"),
        mech("neurotransmitter_balance", "increase", normal(0.15, 0.1), "weak", "SD"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.05, 0.08), // HR ~0.95 (modest, less evidence)
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "moderate",
      keySources: [],
      caveats: [
        "Mortality evidence is limited",
        "Quality of life benefits may be larger than mortality benefits",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Goyal et al., 2014. Meditation programs for psychological stress",
        studyType: "meta-analysis",
        year: 2014,
      },
    ],
  },

  // ==================== MEDICAL ====================
  blood_pressure_medication: {
    id: "blood_pressure_medication",
    name: "Take blood pressure medication",
    description: "Antihypertensive medication as prescribed",
    keywords: ["blood pressure medication", "hypertension", "bp medication", "antihypertensive"],
    category: "medical",
    effect: {
      description: "Blood pressure medication",
      category: "medical",
      mechanismEffects: [
        mech("blood_pressure", "decrease", normal(-15, 5), "strong", "mmHg"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.2, 0.08), // HR ~0.82
        onsetDelay: 0,
        rampUpPeriod: 0.1,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "high",
      keySources: [],
      caveats: ["Effect depends on baseline BP; assumes good adherence"],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Ettehad et al., 2016. Blood pressure lowering for CVD prevention",
        studyType: "meta-analysis",
        year: 2016,
        sampleSize: 613815,
      },
    ],
  },

  statin_therapy: {
    id: "statin_therapy",
    name: "Take statin medication",
    description: "Statin therapy for cholesterol management",
    keywords: ["statin", "cholesterol medication", "lipitor", "atorvastatin"],
    category: "medical",
    effect: {
      description: "Statin therapy",
      category: "medical",
      mechanismEffects: [
        mech("lipid_profile", "decrease", normal(-35, 10), "strong", "% LDL"),
        mech("systemic_inflammation", "decrease", normal(-20, 10), "moderate", "% CRP"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.12, 0.06), // HR ~0.89
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "high",
      keySources: [],
      caveats: [
        "NNT varies by baseline risk",
        "Some patients experience side effects",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "CTT Collaboration, 2010. Efficacy of cholesterol-lowering therapy",
        studyType: "meta-analysis",
        year: 2010,
        sampleSize: 170000,
      },
    ],
  },

  // ==================== SOCIAL ====================
  social_connection: {
    id: "social_connection",
    name: "Increase social connection",
    description: "Regular social activities and maintaining relationships",
    keywords: [
      "social",
      "friends",
      "community",
      "loneliness",
      "lonely",
      "relationships",
      "social activities",
    ],
    category: "stress",
    effect: {
      description: "Increase social connection",
      category: "other",
      mechanismEffects: [
        mech("stress_hormones", "decrease", normal(-10, 6), "moderate", "% cortisol"),
        mech("systemic_inflammation", "decrease", normal(-10, 6), "moderate", "% CRP"),
        mech("neurotransmitter_balance", "increase", normal(0.2, 0.12), "weak", "SD"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.2, 0.12), // HR ~0.82 (social isolation is a major risk factor)
        onsetDelay: 0,
        rampUpPeriod: 1,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "moderate",
      keySources: [],
      caveats: ["Effect size varies; loneliness is a stronger predictor than social isolation"],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Holt-Lunstad et al., 2010. Social relationships and mortality risk",
        studyType: "meta-analysis",
        year: 2010,
        sampleSize: 308849,
      },
    ],
  },

  // ==================== WEIGHT ====================
  lose_weight_10pct: {
    id: "lose_weight_10pct",
    name: "Lose 10% body weight",
    description: "Sustained 10% weight loss from baseline",
    keywords: [
      "lose weight",
      "weight loss",
      "diet",
      "slim down",
      "reduce weight",
      "obesity",
      "overweight",
    ],
    category: "diet",
    effect: {
      description: "Lose 10% body weight",
      category: "diet",
      mechanismEffects: [
        mech("adiposity", "decrease", normal(-10, 3), "strong", "% body fat"),
        mech("insulin_sensitivity", "increase", normal(30, 12), "strong", "%"),
        mech("blood_pressure", "decrease", normal(-5, 2), "strong", "mmHg"),
        mech("lipid_profile", "decrease", normal(-10, 5), "strong", "% LDL"),
        mech("systemic_inflammation", "decrease", normal(-25, 10), "strong", "% CRP"),
        mech("joint_health", "increase", normal(0.3, 0.15), "moderate", "SD"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.15, 0.1), // HR ~0.86
        onsetDelay: 0,
        rampUpPeriod: 1,
        decayRate: 0.1, // Weight regain is common
      },
      quality: null,
      costs: null,
      evidenceQuality: "moderate",
      keySources: [],
      caveats: [
        "Benefits depend on baseline BMI",
        "Weight maintenance is challenging",
        "Intentional vs unintentional weight loss matters",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Ma et al., 2017. Weight loss and mortality: systematic review",
        studyType: "meta-analysis",
        year: 2017,
      },
    ],
  },

  // ==================== COFFEE/TEA ====================
  coffee_moderate: {
    id: "coffee_moderate",
    name: "Drink 3-4 cups of coffee daily",
    description: "Moderate coffee consumption (3-4 cups/day)",
    keywords: ["coffee", "caffeine", "espresso"],
    category: "diet",
    effect: {
      description: "3-4 cups coffee daily",
      category: "diet",
      mechanismEffects: [
        mech("cognitive_reserve", "increase", normal(0.15, 0.1), "moderate", "SD"),
        mech("systemic_inflammation", "decrease", normal(-5, 4), "weak", "% CRP"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.12, 0.06), // HR ~0.89
        onsetDelay: 0,
        rampUpPeriod: 0,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "moderate",
      keySources: [],
      caveats: ["Observational data; causation debated"],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Poole et al., 2017. Coffee consumption and health: umbrella review",
        studyType: "meta-analysis",
        year: 2017,
      },
    ],
  },

  green_tea: {
    id: "green_tea",
    name: "Drink green tea daily",
    description: "2-3 cups of green tea daily",
    keywords: ["green tea", "tea", "matcha"],
    category: "diet",
    effect: {
      description: "2-3 cups green tea daily",
      category: "diet",
      mechanismEffects: [
        mech("systemic_inflammation", "decrease", normal(-8, 4), "moderate", "% CRP"),
        mech("blood_pressure", "decrease", normal(-2, 1.5), "moderate", "mmHg"),
        mech("lipid_profile", "decrease", normal(-5, 3), "moderate", "% LDL"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.08, 0.05), // HR ~0.92
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "moderate",
      keySources: [],
      caveats: ["Most evidence from Asian populations"],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Tang et al., 2015. Green tea and mortality: systematic review",
        studyType: "meta-analysis",
        year: 2015,
      },
    ],
  },

  // ==================== MORE EXERCISE ====================
  swimming: {
    id: "swimming",
    name: "Swim regularly",
    description: "Swimming 2-3 times per week",
    keywords: ["swim", "swimming", "pool", "laps"],
    category: "exercise",
    effect: {
      description: "Swimming 2-3x per week",
      category: "exercise",
      mechanismEffects: [
        mech("cardiac_output", "increase", normal(12, 5), "moderate", "%"),
        mech("lung_function", "increase", normal(8, 4), "moderate", "% VO2max"),
        mech("blood_pressure", "decrease", normal(-5, 3), "moderate", "mmHg"),
        mech("joint_health", "increase", normal(0.25, 0.12), "moderate", "SD"),
        mech("systemic_inflammation", "decrease", normal(-12, 6), "moderate", "% CRP"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.18, 0.09), // HR ~0.84
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "moderate",
      keySources: [],
      caveats: ["Low-impact; good for joint issues"],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Chase et al., 2008. Relation of swimming with mortality",
        studyType: "cohort",
        year: 2008,
      },
    ],
  },

  cycling: {
    id: "cycling",
    name: "Cycle regularly",
    description: "Cycling 3+ times per week",
    keywords: ["cycle", "cycling", "bike", "biking", "bicycle"],
    category: "exercise",
    effect: {
      description: "Cycling 3x per week",
      category: "exercise",
      mechanismEffects: [
        mech("cardiac_output", "increase", normal(15, 6), "strong", "%"),
        mech("blood_pressure", "decrease", normal(-5, 3), "moderate", "mmHg"),
        mech("adiposity", "decrease", normal(-3, 2), "moderate", "% body fat"),
        mech("insulin_sensitivity", "increase", normal(20, 10), "moderate", "%"),
        mech("lung_function", "increase", normal(8, 4), "moderate", "% VO2max"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.22, 0.1), // HR ~0.80
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "moderate",
      keySources: [],
      caveats: ["Commuter cycling may have additional benefits"],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Celis-Morales et al., 2017. Cycling and mortality in UK Biobank",
        studyType: "cohort",
        year: 2017,
        sampleSize: 263450,
      },
    ],
  },

  yoga: {
    id: "yoga",
    name: "Practice yoga regularly",
    description: "Yoga practice 2-3 times per week",
    keywords: ["yoga", "yogic", "asana", "stretching"],
    category: "exercise",
    effect: {
      description: "Yoga 2-3x per week",
      category: "exercise",
      mechanismEffects: [
        mech("blood_pressure", "decrease", normal(-4, 2), "moderate", "mmHg"),
        mech("stress_hormones", "decrease", normal(-12, 6), "moderate", "% cortisol"),
        mech("balance_proprioception", "increase", normal(0.3, 0.15), "moderate", "SD"),
        mech("systemic_inflammation", "decrease", normal(-10, 6), "weak", "% CRP"),
        mech("sleep_quality", "increase", normal(0.2, 0.1), "moderate", "SD"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.1, 0.08), // HR ~0.90
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "moderate",
      keySources: [],
      caveats: ["Benefits vary by style; evidence weaker than aerobic exercise"],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Cramer et al., 2017. Yoga for cardiovascular disease risk",
        studyType: "meta-analysis",
        year: 2017,
      },
    ],
  },

  // ==================== FOOD/SUPPLEMENTS ====================
  daily_nut_consumption: {
    id: "daily_nut_consumption",
    name: "Eat a handful of nuts daily",
    description: "One ounce (28g) of mixed nuts per day",
    keywords: [
      "nuts",
      "nut",
      "almonds",
      "walnuts",
      "cashews",
      "pistachios",
      "peanuts",
      "handful of nuts",
      "daily nuts",
      "tree nuts",
    ],
    category: "diet",
    effect: {
      description: "Daily nut consumption (1 oz/28g)",
      category: "diet",
      mechanismEffects: [
        mech("lipid_profile", "decrease", normal(-8, 4), "strong", "% LDL", "Aune 2016"),
        mech("systemic_inflammation", "decrease", normal(-10, 5), "moderate", "% CRP"),
        mech("blood_pressure", "decrease", normal(-2, 1.5), "moderate", "mmHg"),
        mech("insulin_sensitivity", "increase", normal(10, 5), "moderate", "%"),
        mech("adiposity", "decrease", normal(-0.5, 0.3), "weak", "kg"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.22, 0.06), // HR ~0.80, from Aune meta-analysis
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "high",
      keySources: [],
      caveats: [
        "Observational evidence primarily; PREDIMED provides RCT support",
        "Healthy user bias possible but RCT-calibrated prior used",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Aune et al., 2016. Nut consumption and mortality",
        studyType: "meta-analysis",
        year: 2016,
        sampleSize: 819000,
      },
      {
        citation: "PREDIMED, 2013. Mediterranean diet with nuts",
        studyType: "rct",
        year: 2013,
        sampleSize: 7447,
      },
    ],
  },

  walnut_consumption: {
    id: "walnut_consumption",
    name: "Eat walnuts regularly",
    description: "Walnuts 3-4 times per week or daily",
    keywords: [
      "walnuts",
      "walnut",
      "omega-3 nuts",
      "brain nuts",
    ],
    category: "diet",
    effect: {
      description: "Regular walnut consumption",
      category: "diet",
      mechanismEffects: [
        mech("lipid_profile", "decrease", normal(-10, 5), "strong", "% LDL"),
        mech("systemic_inflammation", "decrease", normal(-12, 6), "moderate", "% CRP"),
        mech("blood_pressure", "decrease", normal(-3, 2), "moderate", "mmHg"),
        mech("neurotransmitter_balance", "increase", normal(0.15, 0.1), "weak", "SD"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.24, 0.08), // HR ~0.78
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "moderate",
      keySources: [],
      caveats: ["Walnut-specific evidence sparser than general nut meta-analyses"],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Guasch-Ferré et al., 2017. Frequency of nut consumption and mortality",
        studyType: "cohort",
        year: 2017,
      },
    ],
  },

  fish_twice_weekly: {
    id: "fish_twice_weekly",
    name: "Eat fish twice per week",
    description: "Fatty fish (salmon, mackerel, sardines) 2x weekly",
    keywords: [
      "fish",
      "salmon",
      "mackerel",
      "sardines",
      "omega-3",
      "fatty fish",
      "seafood",
      "fish oil",
    ],
    category: "diet",
    effect: {
      description: "Fatty fish 2x per week",
      category: "diet",
      mechanismEffects: [
        mech("lipid_profile", "decrease", normal(-5, 3), "strong", "% triglycerides"),
        mech("systemic_inflammation", "decrease", normal(-8, 4), "moderate", "% CRP"),
        mech("blood_pressure", "decrease", normal(-2, 1.5), "moderate", "mmHg"),
        mech("cardiac_output", "increase", normal(3, 2), "moderate", "%"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.12, 0.05), // HR ~0.89
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "high",
      keySources: [],
      caveats: [
        "Mercury concerns for some fish types",
        "Benefits mainly from replacing red meat",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Zheng et al., 2012. Fish consumption and mortality",
        studyType: "meta-analysis",
        year: 2012,
        sampleSize: 672000,
      },
    ],
  },

  berry_consumption: {
    id: "berry_consumption",
    name: "Eat berries daily",
    description: "Blueberries, strawberries, or mixed berries daily",
    keywords: [
      "berries",
      "blueberries",
      "strawberries",
      "raspberries",
      "blackberries",
      "antioxidants",
      "polyphenols",
    ],
    category: "diet",
    effect: {
      description: "Daily berry consumption",
      category: "diet",
      mechanismEffects: [
        mech("systemic_inflammation", "decrease", normal(-10, 6), "moderate", "% CRP"),
        mech("blood_pressure", "decrease", normal(-3, 2), "moderate", "mmHg"),
        mech("insulin_sensitivity", "increase", normal(8, 5), "weak", "%"),
        mech("neurotransmitter_balance", "increase", normal(0.1, 0.08), "weak", "SD"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.08, 0.06), // HR ~0.92
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "moderate",
      keySources: [],
      caveats: [
        "Evidence primarily from cohort studies",
        "Specific berry types may have different effects",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Aune et al., 2017. Fruit and vegetable intake and mortality",
        studyType: "meta-analysis",
        year: 2017,
      },
    ],
  },

  olive_oil_daily: {
    id: "olive_oil_daily",
    name: "Use olive oil as primary fat",
    description: "Extra virgin olive oil as main cooking/dressing fat",
    keywords: [
      "olive oil",
      "evoo",
      "extra virgin",
      "mediterranean fat",
    ],
    category: "diet",
    effect: {
      description: "Olive oil as primary fat source",
      category: "diet",
      mechanismEffects: [
        mech("lipid_profile", "decrease", normal(-6, 3), "strong", "% LDL"),
        mech("systemic_inflammation", "decrease", normal(-12, 6), "moderate", "% CRP"),
        mech("blood_pressure", "decrease", normal(-3, 2), "moderate", "mmHg"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.15, 0.06), // HR ~0.86
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "high",
      keySources: [],
      caveats: ["PREDIMED provides strong RCT evidence for CVD outcomes"],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "PREDIMED, 2018. Olive oil and cardiovascular events",
        studyType: "rct",
        year: 2018,
        sampleSize: 7447,
      },
      {
        citation: "Guasch-Ferré et al., 2022. Olive oil consumption and mortality",
        studyType: "cohort",
        year: 2022,
      },
    ],
  },

  // ==================== SUPPLEMENTS ====================
  vitamin_d_supplement: {
    id: "vitamin_d_supplement",
    name: "Take vitamin D supplement",
    description: "Daily vitamin D3 supplementation (1000-4000 IU)",
    keywords: [
      "vitamin d",
      "vitamin d3",
      "cholecalciferol",
      "sunshine vitamin",
      "d3 supplement",
    ],
    category: "medical",
    effect: {
      description: "Daily vitamin D supplementation",
      category: "medical",
      mechanismEffects: [
        mech("bone_density", "increase", normal(2, 1), "strong", "%"),
        mech("immune_function", "increase", normal(0.15, 0.1), "moderate", "SD"),
        mech("systemic_inflammation", "decrease", normal(-5, 4), "weak", "% CRP"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.06, 0.04), // HR ~0.94 - modest effect
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: {
        hoursPerWeek: { type: "point", value: 0 },
        annualCost: normal(50, 20),
        activityDisutility: { type: "point", value: 0 },
      },
      evidenceQuality: "moderate",
      keySources: [],
      caveats: [
        "Most benefit seen in those deficient at baseline",
        "Mega-doses not more effective and potentially harmful",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Autier et al., 2014. Vitamin D and health outcomes meta-analysis",
        studyType: "meta-analysis",
        year: 2014,
      },
    ],
  },

  omega3_supplement: {
    id: "omega3_supplement",
    name: "Take omega-3 fish oil supplement",
    description: "Daily omega-3 fatty acid supplement (1-2g EPA+DHA)",
    keywords: [
      "omega-3",
      "omega 3",
      "fish oil",
      "epa",
      "dha",
      "fatty acids",
      "fish oil supplement",
    ],
    category: "medical",
    effect: {
      description: "Daily omega-3 fish oil supplement",
      category: "medical",
      mechanismEffects: [
        mech("lipid_profile", "decrease", normal(-8, 4), "strong", "% triglycerides"),
        mech("systemic_inflammation", "decrease", normal(-10, 5), "moderate", "% CRP"),
        mech("blood_pressure", "decrease", normal(-2, 1.5), "moderate", "mmHg"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.08, 0.05), // HR ~0.92
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: {
        hoursPerWeek: { type: "point", value: 0 },
        annualCost: normal(150, 50),
        activityDisutility: { type: "point", value: 0 },
      },
      evidenceQuality: "moderate",
      keySources: [],
      caveats: [
        "RCT evidence mixed; dietary fish may be more effective",
        "Benefits may be larger for those not eating fish",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Aung et al., 2018. Omega-3 fatty acids and cardiovascular disease",
        studyType: "meta-analysis",
        year: 2018,
      },
    ],
  },

  magnesium_supplement: {
    id: "magnesium_supplement",
    name: "Take magnesium supplement",
    description: "Daily magnesium supplementation (200-400mg)",
    keywords: [
      "magnesium",
      "mag",
      "magnesium supplement",
      "magnesium glycinate",
      "magnesium citrate",
    ],
    category: "medical",
    effect: {
      description: "Daily magnesium supplementation",
      category: "medical",
      mechanismEffects: [
        mech("blood_pressure", "decrease", normal(-2, 1.5), "moderate", "mmHg"),
        mech("sleep_quality", "increase", normal(0.15, 0.1), "moderate", "SD"),
        mech("insulin_sensitivity", "increase", normal(5, 3), "weak", "%"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.05, 0.04), // HR ~0.95 - modest
        onsetDelay: 0,
        rampUpPeriod: 0.25,
        decayRate: 0,
      },
      quality: null,
      costs: {
        hoursPerWeek: { type: "point", value: 0 },
        annualCost: normal(60, 25),
        activityDisutility: { type: "point", value: 0 },
      },
      evidenceQuality: "moderate",
      keySources: [],
      caveats: ["Benefits most clear in those with low dietary intake"],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Fang et al., 2016. Magnesium intake and mortality meta-analysis",
        studyType: "meta-analysis",
        year: 2016,
      },
    ],
  },

  // ==================== FASTING/CALORIC RESTRICTION ====================
  intermittent_fasting: {
    id: "intermittent_fasting",
    name: "Practice intermittent fasting",
    description: "16:8 or similar time-restricted eating pattern",
    keywords: [
      "intermittent fasting",
      "fasting",
      "16:8",
      "time restricted eating",
      "skip breakfast",
      "eating window",
      "IF",
    ],
    category: "diet",
    effect: {
      description: "Intermittent fasting (16:8 pattern)",
      category: "diet",
      mechanismEffects: [
        mech("insulin_sensitivity", "increase", normal(15, 8), "moderate", "%"),
        mech("adiposity", "decrease", normal(-2, 1.5), "moderate", "% body fat"),
        mech("systemic_inflammation", "decrease", normal(-10, 6), "weak", "% CRP"),
        mech("autophagy", "increase", normal(0.2, 0.15), "weak", "SD"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.08, 0.08), // HR ~0.92 - uncertain
        onsetDelay: 0,
        rampUpPeriod: 0.25,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "low",
      keySources: [],
      caveats: [
        "Long-term mortality evidence is limited",
        "Not suitable for everyone (diabetics, eating disorders, pregnant)",
        "Benefits may be mainly from caloric reduction",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Mattson et al., 2017. Impact of intermittent fasting on health",
        studyType: "review",
        year: 2017,
      },
    ],
  },

  caloric_restriction: {
    id: "caloric_restriction",
    name: "Practice caloric restriction",
    description: "Moderate caloric restriction (10-20% below maintenance)",
    keywords: [
      "caloric restriction",
      "eat less",
      "calorie deficit",
      "CR",
      "calorie restriction",
      "reduce calories",
    ],
    category: "diet",
    effect: {
      description: "Moderate caloric restriction (10-20%)",
      category: "diet",
      mechanismEffects: [
        mech("adiposity", "decrease", normal(-5, 3), "strong", "% body fat"),
        mech("insulin_sensitivity", "increase", normal(20, 10), "strong", "%"),
        mech("systemic_inflammation", "decrease", normal(-15, 8), "moderate", "% CRP"),
        mech("blood_pressure", "decrease", normal(-4, 2), "strong", "mmHg"),
        mech("cellular_senescence", "decrease", normal(-0.1, 0.08), "weak", "SD"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.12, 0.1), // HR ~0.89 - extrapolated from animal/observational
        onsetDelay: 0,
        rampUpPeriod: 1,
        decayRate: 0.1, // Hard to maintain
      },
      quality: null,
      costs: null,
      evidenceQuality: "low",
      keySources: [],
      caveats: [
        "Human mortality evidence extrapolated from animal studies",
        "Adherence is challenging long-term",
        "Not recommended for elderly or underweight individuals",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Most et al., 2017. CALERIE study (human CR trial)",
        studyType: "rct",
        year: 2017,
      },
    ],
  },

  // ==================== MORE SPECIFIC EXERCISES ====================
  hiit_training: {
    id: "hiit_training",
    name: "Do HIIT workouts",
    description: "High-intensity interval training 2-3x per week",
    keywords: [
      "hiit",
      "high intensity",
      "interval training",
      "tabata",
      "sprint intervals",
      "intense workout",
    ],
    category: "exercise",
    effect: {
      description: "HIIT training 2-3x per week",
      category: "exercise",
      mechanismEffects: [
        mech("cardiac_output", "increase", normal(18, 8), "strong", "%"),
        mech("insulin_sensitivity", "increase", normal(25, 12), "strong", "%"),
        mech("adiposity", "decrease", normal(-4, 2), "strong", "% body fat"),
        mech("lung_function", "increase", normal(12, 6), "strong", "% VO2max"),
        mech("mitochondrial_function", "increase", normal(0.3, 0.15), "moderate", "SD"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.22, 0.1), // HR ~0.80
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "moderate",
      keySources: [],
      caveats: [
        "Higher injury risk than moderate exercise",
        "May not be suitable for all fitness levels",
        "Recovery time important",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Weston et al., 2014. HIIT for cardiometabolic health",
        studyType: "meta-analysis",
        year: 2014,
      },
    ],
  },

  standing_desk: {
    id: "standing_desk",
    name: "Use a standing desk",
    description: "Alternate sitting and standing while working",
    keywords: [
      "standing desk",
      "stand up desk",
      "sit stand desk",
      "stand while working",
      "less sitting",
    ],
    category: "exercise",
    effect: {
      description: "Standing desk (alternating sit/stand)",
      category: "exercise",
      mechanismEffects: [
        mech("metabolic_rate", "increase", normal(3, 2), "weak", "%"),
        mech("blood_pressure", "decrease", normal(-1, 1), "weak", "mmHg"),
        mech("insulin_sensitivity", "increase", normal(5, 4), "weak", "%"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.04, 0.05), // HR ~0.96 - modest
        onsetDelay: 0,
        rampUpPeriod: 0,
        decayRate: 0,
      },
      quality: null,
      costs: {
        hoursPerWeek: { type: "point", value: 0 },
        annualCost: normal(300, 150), // One-time desk cost amortized
        activityDisutility: { type: "point", value: 0 },
      },
      evidenceQuality: "low",
      keySources: [],
      caveats: [
        "Evidence for mortality reduction is weak",
        "Breaking up sitting may matter more than total standing time",
        "Doesn't replace actual exercise",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Buckley et al., 2015. Standing-based office work",
        studyType: "review",
        year: 2015,
      },
    ],
  },

  // ==================== MORE SUPPLEMENTS ====================
  creatine_supplement: {
    id: "creatine_supplement",
    name: "Take creatine supplement",
    description: "Daily creatine monohydrate supplementation (3-5g)",
    keywords: [
      "creatine",
      "creatine monohydrate",
      "creatine supplement",
      "strength supplement",
    ],
    category: "medical",
    effect: {
      description: "Daily creatine supplementation (3-5g)",
      category: "medical",
      mechanismEffects: [
        mech("muscle_mass", "increase", normal(2, 1.5), "strong", "%", "Forbes 2018"),
        mech("cognitive_reserve", "increase", normal(0.15, 0.1), "moderate", "SD", "Avgerinos 2018"),
        mech("bone_density", "increase", normal(1, 0.8), "weak", "%"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.03, 0.05), // HR ~0.97 - minimal direct mortality effect
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: {
        hoursPerWeek: { type: "point", value: 0 },
        annualCost: normal(80, 30),
        activityDisutility: { type: "point", value: 0 },
      },
      evidenceQuality: "moderate",
      keySources: [],
      caveats: [
        "Benefits most evident in vegetarians and older adults",
        "Muscle and cognitive benefits well-established; mortality effects indirect",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Forbes et al., 2018. Creatine supplementation and muscle mass meta-analysis",
        studyType: "meta-analysis",
        year: 2018,
      },
      {
        citation: "Avgerinos et al., 2018. Creatine and cognitive function meta-analysis",
        studyType: "meta-analysis",
        year: 2018,
      },
    ],
  },

  probiotic_supplement: {
    id: "probiotic_supplement",
    name: "Take probiotic supplement",
    description: "Daily multi-strain probiotic supplement",
    keywords: [
      "probiotic",
      "probiotics",
      "gut health",
      "digestive health",
      "microbiome supplement",
    ],
    category: "medical",
    effect: {
      description: "Daily probiotic supplementation",
      category: "medical",
      mechanismEffects: [
        mech("gut_microbiome", "increase", normal(0.25, 0.15), "moderate", "SD diversity", "McFarland 2016"),
        mech("systemic_inflammation", "decrease", normal(-8, 5), "weak", "% CRP"),
        mech("immune_function", "increase", normal(0.15, 0.1), "moderate", "SD"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.04, 0.06), // HR ~0.96 - modest
        onsetDelay: 0,
        rampUpPeriod: 0.25,
        decayRate: 0,
      },
      quality: null,
      costs: {
        hoursPerWeek: { type: "point", value: 0 },
        annualCost: normal(200, 80),
        activityDisutility: { type: "point", value: 0 },
      },
      evidenceQuality: "low",
      keySources: [],
      caveats: [
        "Strain-specific effects vary widely",
        "Long-term mortality benefits uncertain",
        "May help with specific digestive conditions",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "McFarland et al., 2016. Meta-analysis of probiotics for health",
        studyType: "meta-analysis",
        year: 2016,
      },
    ],
  },

  // ==================== MORE SLEEP ====================
  consistent_bedtime: {
    id: "consistent_bedtime",
    name: "Maintain consistent sleep schedule",
    description: "Go to bed and wake up at the same time daily",
    keywords: [
      "consistent bedtime",
      "sleep schedule",
      "regular sleep",
      "same bedtime",
      "sleep routine",
      "circadian rhythm",
    ],
    category: "sleep",
    effect: {
      description: "Consistent sleep schedule (±30 min variability)",
      category: "sleep",
      mechanismEffects: [
        mech("sleep_quality", "increase", normal(0.3, 0.15), "strong", "SD", "Phillips 2017"),
        mech("stress_hormones", "decrease", normal(-10, 6), "moderate", "% cortisol"),
        mech("insulin_sensitivity", "increase", normal(8, 5), "moderate", "%"),
        mech("systemic_inflammation", "decrease", normal(-8, 5), "weak", "% CRP"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.06, 0.05), // HR ~0.94
        onsetDelay: 0,
        rampUpPeriod: 0.25,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "moderate",
      keySources: [],
      caveats: [
        "Circadian rhythm disruption is harmful",
        "Effects compound with overall sleep duration",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Phillips et al., 2017. Irregular sleep and metabolic abnormalities",
        studyType: "cohort",
        year: 2017,
      },
    ],
  },

  blue_light_blocking: {
    id: "blue_light_blocking",
    name: "Block blue light before bed",
    description: "Use blue light blocking glasses or filters 2-3 hours before bed",
    keywords: [
      "blue light",
      "blue light blocking",
      "blue light glasses",
      "screen filter",
      "night mode",
      "melatonin",
    ],
    category: "sleep",
    effect: {
      description: "Blue light blocking 2-3h before bed",
      category: "sleep",
      mechanismEffects: [
        mech("sleep_quality", "increase", normal(0.2, 0.12), "moderate", "SD", "Shechter 2018"),
        mech("stress_hormones", "decrease", normal(-5, 4), "weak", "% cortisol"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.03, 0.05), // HR ~0.97 - small effect
        onsetDelay: 0,
        rampUpPeriod: 0.1,
        decayRate: 0,
      },
      quality: null,
      costs: {
        hoursPerWeek: { type: "point", value: 0 },
        annualCost: normal(30, 15), // Glasses or software
        activityDisutility: { type: "point", value: 0 },
      },
      evidenceQuality: "low",
      keySources: [],
      caveats: [
        "Effects most pronounced in those with screen exposure before bed",
        "Some studies show minimal effects",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Shechter et al., 2018. Blue light blocking and sleep",
        studyType: "rct",
        year: 2018,
      },
    ],
  },

  sleep_apnea_treatment: {
    id: "sleep_apnea_treatment",
    name: "Treat sleep apnea (CPAP)",
    description: "Use CPAP or other treatment for obstructive sleep apnea",
    keywords: [
      "sleep apnea",
      "cpap",
      "cpap machine",
      "apnea treatment",
      "osa",
      "obstructive sleep apnea",
    ],
    category: "medical",
    effect: {
      description: "CPAP treatment for sleep apnea",
      category: "medical",
      mechanismEffects: [
        mech("sleep_quality", "increase", normal(0.8, 0.3), "strong", "SD", "Epstein 2009"),
        mech("blood_pressure", "decrease", normal(-4, 2.5), "strong", "mmHg", "Martinez-Garcia 2013"),
        mech("cardiac_output", "increase", normal(10, 5), "moderate", "%"),
        mech("systemic_inflammation", "decrease", normal(-12, 7), "moderate", "% CRP"),
        mech("neurotransmitter_balance", "increase", normal(0.2, 0.12), "moderate", "SD"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.18, 0.1), // HR ~0.84 - substantial for those with severe OSA
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: {
        hoursPerWeek: { type: "point", value: 0.5 }, // Setup and maintenance
        annualCost: normal(800, 300), // Equipment and supplies
        activityDisutility: { type: "point", value: -0.05 }, // Some discomfort
      },
      evidenceQuality: "high",
      keySources: [],
      caveats: [
        "Effects strongest in severe OSA",
        "Adherence is critical (must use nightly)",
        "Benefits vs no treatment; assumes moderate-severe OSA diagnosis",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Epstein et al., 2009. CPAP clinical guideline",
        studyType: "review",
        year: 2009,
      },
      {
        citation: "Martinez-Garcia et al., 2013. CPAP and cardiovascular outcomes",
        studyType: "cohort",
        year: 2013,
        sampleSize: 939,
      },
    ],
  },

  // ==================== SOCIAL ====================
  regular_social_interaction: {
    id: "regular_social_interaction",
    name: "Regular social interaction",
    description: "Spend time with friends/family 2-3 times per week",
    keywords: [
      "social interaction",
      "spend time with friends",
      "socialize",
      "social activities",
      "see friends",
      "family time",
    ],
    category: "stress",
    effect: {
      description: "Regular social interaction (2-3x/week)",
      category: "other",
      mechanismEffects: [
        mech("stress_hormones", "decrease", normal(-12, 7), "moderate", "% cortisol"),
        mech("neurotransmitter_balance", "increase", normal(0.25, 0.15), "moderate", "SD"),
        mech("systemic_inflammation", "decrease", normal(-12, 7), "moderate", "% CRP", "Holt-Lunstad 2010"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.22, 0.12), // HR ~0.80 - major effect
        onsetDelay: 0,
        rampUpPeriod: 1,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "moderate",
      keySources: [],
      caveats: [
        "Quality of relationships matters more than quantity",
        "Baseline social isolation determines effect size",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Holt-Lunstad et al., 2010. Social relationships and mortality",
        studyType: "meta-analysis",
        year: 2010,
        sampleSize: 308849,
      },
    ],
  },

  marriage_partnership: {
    id: "marriage_partnership",
    name: "Marriage or committed partnership",
    description: "Being in a stable marriage or long-term partnership",
    keywords: [
      "marriage",
      "get married",
      "partnership",
      "long-term relationship",
      "spouse",
      "partner",
    ],
    category: "stress",
    effect: {
      description: "Stable marriage/partnership",
      category: "other",
      mechanismEffects: [
        mech("stress_hormones", "decrease", normal(-15, 8), "moderate", "% cortisol"),
        mech("systemic_inflammation", "decrease", normal(-10, 6), "moderate", "% CRP"),
        mech("neurotransmitter_balance", "increase", normal(0.2, 0.12), "weak", "SD"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.15, 0.08), // HR ~0.86
        onsetDelay: 0,
        rampUpPeriod: 2,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "moderate",
      keySources: [],
      caveats: [
        "Quality of relationship is paramount - poor relationships may increase mortality",
        "Selection effects possible (healthier people marry)",
        "Benefits may be stronger for men than women",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Rendall et al., 2011. Marital status and mortality",
        studyType: "cohort",
        year: 2011,
      },
    ],
  },

  volunteering: {
    id: "volunteering",
    name: "Regular volunteering",
    description: "Volunteer work 2-4 hours per week",
    keywords: [
      "volunteer",
      "volunteering",
      "volunteer work",
      "community service",
      "helping others",
    ],
    category: "stress",
    effect: {
      description: "Volunteering 2-4 hours per week",
      category: "other",
      mechanismEffects: [
        mech("neurotransmitter_balance", "increase", normal(0.2, 0.12), "moderate", "SD"),
        mech("stress_hormones", "decrease", normal(-10, 6), "moderate", "% cortisol"),
        mech("systemic_inflammation", "decrease", normal(-8, 5), "weak", "% CRP"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.12, 0.08), // HR ~0.89
        onsetDelay: 0,
        rampUpPeriod: 1,
        decayRate: 0,
      },
      quality: null,
      costs: {
        hoursPerWeek: { type: "point", value: 3 }, // 2-4 hours
        annualCost: { type: "point", value: 0 },
        activityDisutility: { type: "point", value: 0.05 }, // Generally enjoyable
      },
      evidenceQuality: "moderate",
      keySources: [],
      caveats: [
        "Benefits may plateau beyond 2-3 hours/week",
        "Selection bias possible (healthier people volunteer)",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Okun et al., 2013. Volunteering and mortality meta-analysis",
        studyType: "meta-analysis",
        year: 2013,
      },
    ],
  },

  // ==================== ENVIRONMENT ====================
  air_purifier: {
    id: "air_purifier",
    name: "Use HEPA air purifier",
    description: "Run HEPA air purifier in main living spaces",
    keywords: [
      "air purifier",
      "hepa filter",
      "air filter",
      "air quality",
      "clean air",
      "indoor air",
    ],
    category: "medical",
    effect: {
      description: "HEPA air purifier in home",
      category: "medical",
      mechanismEffects: [
        mech("lung_function", "increase", normal(3, 2), "moderate", "% FEV1", "Fisk 2013"),
        mech("systemic_inflammation", "decrease", normal(-8, 5), "moderate", "% CRP"),
        mech("blood_pressure", "decrease", normal(-2, 1.5), "weak", "mmHg"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.06, 0.06), // HR ~0.94
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: {
        hoursPerWeek: { type: "point", value: 0.1 }, // Minimal maintenance
        annualCost: normal(200, 80), // Device + filter replacement
        activityDisutility: { type: "point", value: 0 },
      },
      evidenceQuality: "moderate",
      keySources: [],
      caveats: [
        "Benefits larger in polluted areas",
        "Effects most evident for respiratory and cardiovascular health",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Fisk et al., 2013. Air filtration and health: systematic review",
        studyType: "review",
        year: 2013,
      },
    ],
  },

  move_walkable_city: {
    id: "move_walkable_city",
    name: "Move to walkable neighborhood",
    description: "Live in a walkable, bikeable urban environment",
    keywords: [
      "walkable city",
      "walkable neighborhood",
      "urban living",
      "walkability",
      "move to city",
      "bikeable",
    ],
    category: "exercise",
    effect: {
      description: "Living in walkable neighborhood",
      category: "exercise",
      mechanismEffects: [
        mech("adiposity", "decrease", normal(-2, 1.5), "moderate", "% body fat", "Sallis 2016"),
        mech("blood_pressure", "decrease", normal(-3, 2), "moderate", "mmHg"),
        mech("insulin_sensitivity", "increase", normal(10, 6), "moderate", "%"),
        mech("cardiac_output", "increase", normal(5, 3), "weak", "%"),
        mech("neurotransmitter_balance", "increase", normal(0.15, 0.1), "weak", "SD"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.1, 0.08), // HR ~0.90
        onsetDelay: 0,
        rampUpPeriod: 1,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "moderate",
      keySources: [],
      caveats: [
        "Effects mediated by increased physical activity",
        "May have trade-offs (pollution, noise, housing costs)",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Sallis et al., 2016. Built environment and health outcomes",
        studyType: "review",
        year: 2016,
      },
    ],
  },

  reduce_noise_pollution: {
    id: "reduce_noise_pollution",
    name: "Reduce noise pollution exposure",
    description: "Minimize chronic noise exposure through soundproofing, relocation, or earplugs",
    keywords: [
      "noise pollution",
      "reduce noise",
      "quiet environment",
      "soundproofing",
      "noise reduction",
      "earplugs",
    ],
    category: "stress",
    effect: {
      description: "Reducing chronic noise exposure",
      category: "other",
      mechanismEffects: [
        mech("stress_hormones", "decrease", normal(-10, 6), "moderate", "% cortisol", "Basner 2014"),
        mech("blood_pressure", "decrease", normal(-3, 2), "moderate", "mmHg"),
        mech("sleep_quality", "increase", normal(0.25, 0.15), "moderate", "SD"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.06, 0.06), // HR ~0.94
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: {
        hoursPerWeek: { type: "point", value: 0 },
        annualCost: normal(400, 200), // Soundproofing or moving costs amortized
        activityDisutility: { type: "point", value: 0 },
      },
      evidenceQuality: "moderate",
      keySources: [],
      caveats: [
        "Effects depend on baseline noise exposure",
        "Chronic traffic noise particularly harmful",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Basner et al., 2014. Noise and cardiovascular disease WHO review",
        studyType: "review",
        year: 2014,
      },
    ],
  },

  // ==================== MENTAL HEALTH ====================
  therapy_counseling: {
    id: "therapy_counseling",
    name: "Regular therapy/counseling",
    description: "Weekly or biweekly psychotherapy sessions",
    keywords: [
      "therapy",
      "counseling",
      "therapist",
      "psychotherapy",
      "mental health",
      "see therapist",
      "talk therapy",
    ],
    category: "stress",
    effect: {
      description: "Regular therapy/counseling",
      category: "stress",
      mechanismEffects: [
        mech("neurotransmitter_balance", "increase", normal(0.4, 0.2), "strong", "SD", "Cuijpers 2013"),
        mech("stress_hormones", "decrease", normal(-20, 10), "strong", "% cortisol"),
        mech("sleep_quality", "increase", normal(0.25, 0.15), "moderate", "SD"),
        mech("systemic_inflammation", "decrease", normal(-10, 6), "weak", "% CRP"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.08, 0.08), // HR ~0.92
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: {
        hoursPerWeek: { type: "point", value: 1.5 }, // Session + travel
        annualCost: normal(3000, 1500), // Weekly sessions
        activityDisutility: { type: "point", value: 0 },
      },
      evidenceQuality: "moderate",
      keySources: [],
      caveats: [
        "Most effective for those with diagnosed mental health conditions",
        "Effect size varies by therapy type and condition",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Cuijpers et al., 2013. Psychotherapy for depression meta-analysis",
        studyType: "meta-analysis",
        year: 2013,
      },
    ],
  },

  gratitude_practice: {
    id: "gratitude_practice",
    name: "Daily gratitude practice",
    description: "Daily gratitude journaling or reflection",
    keywords: [
      "gratitude",
      "gratitude practice",
      "gratitude journal",
      "thankfulness",
      "appreciation",
      "count blessings",
    ],
    category: "stress",
    effect: {
      description: "Daily gratitude practice",
      category: "stress",
      mechanismEffects: [
        mech("neurotransmitter_balance", "increase", normal(0.2, 0.12), "moderate", "SD", "Wood 2010"),
        mech("stress_hormones", "decrease", normal(-8, 5), "weak", "% cortisol"),
        mech("sleep_quality", "increase", normal(0.15, 0.1), "moderate", "SD"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.04, 0.06), // HR ~0.96 - modest
        onsetDelay: 0,
        rampUpPeriod: 0.25,
        decayRate: 0,
      },
      quality: null,
      costs: {
        hoursPerWeek: { type: "point", value: 0.5 }, // 5 min daily
        annualCost: { type: "point", value: 10 }, // Journal
        activityDisutility: { type: "point", value: 0.02 }, // Slight positive
      },
      evidenceQuality: "low",
      keySources: [],
      caveats: [
        "Mortality evidence very limited",
        "Well-being benefits better established than physical health effects",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Wood et al., 2010. Gratitude and well-being meta-analysis",
        studyType: "meta-analysis",
        year: 2010,
      },
    ],
  },

  nature_exposure: {
    id: "nature_exposure",
    name: "Regular nature exposure",
    description: "Spend 2+ hours per week in natural environments",
    keywords: [
      "nature",
      "nature exposure",
      "time in nature",
      "outdoor time",
      "green space",
      "forest",
      "park",
    ],
    category: "stress",
    effect: {
      description: "Nature exposure 2+ hours/week",
      category: "other",
      mechanismEffects: [
        mech("stress_hormones", "decrease", normal(-12, 7), "moderate", "% cortisol", "White 2019"),
        mech("blood_pressure", "decrease", normal(-3, 2), "moderate", "mmHg"),
        mech("neurotransmitter_balance", "increase", normal(0.2, 0.12), "moderate", "SD"),
        mech("systemic_inflammation", "decrease", normal(-8, 5), "weak", "% CRP"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.08, 0.06), // HR ~0.92
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: {
        hoursPerWeek: { type: "point", value: 2.5 }, // 2+ hours + travel
        annualCost: { type: "point", value: 0 },
        activityDisutility: { type: "point", value: 0.05 }, // Generally enjoyable
      },
      evidenceQuality: "moderate",
      keySources: [],
      caveats: [
        "Benefits may combine with physical activity effects",
        "120 minutes/week appears to be threshold",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "White et al., 2019. Nature exposure and health: 20,000 person study",
        studyType: "cohort",
        year: 2019,
        sampleSize: 19806,
      },
    ],
  },

  // ==================== MORE DIET ====================
  increase_fiber: {
    id: "increase_fiber",
    name: "Increase dietary fiber",
    description: "Increase fiber intake to 25-30g per day",
    keywords: [
      "fiber",
      "dietary fiber",
      "more fiber",
      "eat fiber",
      "whole grains",
      "high fiber",
    ],
    category: "diet",
    effect: {
      description: "Increase fiber to 25-30g/day",
      category: "diet",
      mechanismEffects: [
        mech("gut_microbiome", "increase", normal(0.3, 0.15), "strong", "SD diversity", "Reynolds 2019"),
        mech("lipid_profile", "decrease", normal(-8, 4), "strong", "% LDL"),
        mech("blood_pressure", "decrease", normal(-2, 1.5), "moderate", "mmHg"),
        mech("insulin_sensitivity", "increase", normal(10, 6), "moderate", "%"),
        mech("systemic_inflammation", "decrease", normal(-10, 6), "moderate", "% CRP"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.15, 0.06), // HR ~0.86
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "high",
      keySources: [],
      caveats: [
        "Benefits dose-dependent up to 25-30g/day",
        "Type of fiber matters (soluble vs insoluble)",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Reynolds et al., 2019. Carbohydrate quality and health: Lancet meta-analysis",
        studyType: "meta-analysis",
        year: 2019,
        sampleSize: 244000,
      },
    ],
  },

  reduce_red_meat: {
    id: "reduce_red_meat",
    name: "Reduce red meat consumption",
    description: "Reduce red and processed meat to <2 servings per week",
    keywords: [
      "red meat",
      "reduce red meat",
      "less meat",
      "eat less meat",
      "processed meat",
      "beef",
      "pork",
    ],
    category: "diet",
    effect: {
      description: "Reduce red/processed meat to <2 servings/week",
      category: "diet",
      mechanismEffects: [
        mech("systemic_inflammation", "decrease", normal(-10, 6), "moderate", "% CRP", "Etemadi 2017"),
        mech("lipid_profile", "decrease", normal(-5, 3), "moderate", "% LDL"),
        mech("gut_microbiome", "increase", normal(0.15, 0.1), "weak", "SD"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.1, 0.06), // HR ~0.90
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "moderate",
      keySources: [],
      caveats: [
        "Processed meat appears more harmful than unprocessed red meat",
        "Replacement matters (plant protein vs white meat)",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Etemadi et al., 2017. Red meat and mortality: NIH-AARP study",
        studyType: "cohort",
        year: 2017,
        sampleSize: 536969,
      },
    ],
  },

  adequate_hydration: {
    id: "adequate_hydration",
    name: "Maintain adequate hydration",
    description: "Drink 6-8 glasses of water daily",
    keywords: [
      "hydration",
      "drink water",
      "water intake",
      "stay hydrated",
      "drink more water",
    ],
    category: "diet",
    effect: {
      description: "Adequate daily hydration (6-8 glasses water)",
      category: "diet",
      mechanismEffects: [
        mech("blood_pressure", "decrease", normal(-2, 1.5), "weak", "mmHg"),
        mech("metabolic_rate", "increase", normal(3, 2), "weak", "%"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.04, 0.05), // HR ~0.96 - modest
        onsetDelay: 0,
        rampUpPeriod: 0.1,
        decayRate: 0,
      },
      quality: null,
      costs: null,
      evidenceQuality: "low",
      keySources: [],
      caveats: [
        "Evidence for mortality benefit is weak",
        "Benefits most clear in preventing kidney stones and dehydration",
        "Individual needs vary by activity level and climate",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Dmitrieva et al., 2024. Hydration and chronic disease",
        studyType: "cohort",
        year: 2024,
      },
    ],
  },

  // ==================== MORE SUPPLEMENTS ====================
  b_vitamin_complex: {
    id: "b_vitamin_complex",
    name: "Take B vitamin complex",
    description: "Daily B-complex vitamin supplement",
    keywords: [
      "b vitamins",
      "b complex",
      "vitamin b",
      "b12",
      "folate",
      "b vitamin complex",
    ],
    category: "medical",
    effect: {
      description: "Daily B-complex supplementation",
      category: "medical",
      mechanismEffects: [
        mech("neurotransmitter_balance", "increase", normal(0.15, 0.1), "moderate", "SD", "Clarke 2007"),
        mech("cognitive_reserve", "increase", normal(0.12, 0.08), "moderate", "SD"),
        mech("systemic_inflammation", "decrease", normal(-5, 4), "weak", "% CRP"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.04, 0.05), // HR ~0.96
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: {
        hoursPerWeek: { type: "point", value: 0 },
        annualCost: normal(60, 25),
        activityDisutility: { type: "point", value: 0 },
      },
      evidenceQuality: "moderate",
      keySources: [],
      caveats: [
        "Benefits strongest in those with deficiency",
        "B12 particularly important for vegetarians/vegans and older adults",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Clarke et al., 2007. B vitamins and homocysteine lowering",
        studyType: "meta-analysis",
        year: 2007,
      },
    ],
  },

  coq10_supplement: {
    id: "coq10_supplement",
    name: "Take CoQ10 supplement",
    description: "Daily Coenzyme Q10 supplementation (100-200mg)",
    keywords: [
      "coq10",
      "coenzyme q10",
      "ubiquinone",
      "coenzyme",
      "heart supplement",
    ],
    category: "medical",
    effect: {
      description: "Daily CoQ10 supplementation (100-200mg)",
      category: "medical",
      mechanismEffects: [
        mech("mitochondrial_function", "increase", normal(0.2, 0.12), "moderate", "SD", "Hernandez-Camacho 2018"),
        mech("blood_pressure", "decrease", normal(-3, 2), "moderate", "mmHg"),
        mech("cardiac_output", "increase", normal(5, 3), "weak", "%"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.05, 0.06), // HR ~0.95
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: {
        hoursPerWeek: { type: "point", value: 0 },
        annualCost: normal(250, 100),
        activityDisutility: { type: "point", value: 0 },
      },
      evidenceQuality: "moderate",
      keySources: [],
      caveats: [
        "Benefits most evident in heart failure patients",
        "May reduce statin side effects",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Hernandez-Camacho et al., 2018. CoQ10 supplementation meta-analysis",
        studyType: "meta-analysis",
        year: 2018,
      },
    ],
  },

  curcumin_supplement: {
    id: "curcumin_supplement",
    name: "Take curcumin/turmeric supplement",
    description: "Daily curcumin supplement with piperine for absorption",
    keywords: [
      "curcumin",
      "turmeric",
      "turmeric supplement",
      "anti-inflammatory supplement",
    ],
    category: "medical",
    effect: {
      description: "Daily curcumin supplementation",
      category: "medical",
      mechanismEffects: [
        mech("systemic_inflammation", "decrease", normal(-15, 8), "moderate", "% CRP", "Sahebkar 2014"),
        mech("oxidative_stress", "decrease", normal(-12, 7), "moderate", "%"),
        mech("joint_health", "increase", normal(0.15, 0.1), "moderate", "SD"),
      ],
      mortality: {
        hazardRatio: lognormal(-0.05, 0.06), // HR ~0.95
        onsetDelay: 0,
        rampUpPeriod: 0.5,
        decayRate: 0,
      },
      quality: null,
      costs: {
        hoursPerWeek: { type: "point", value: 0 },
        annualCost: normal(150, 60),
        activityDisutility: { type: "point", value: 0 },
      },
      evidenceQuality: "moderate",
      keySources: [],
      caveats: [
        "Bioavailability is key - needs piperine or lipid formulation",
        "Most studied for inflammatory conditions",
      ],
      profileAdjustments: [],
    },
    sources: [
      {
        citation: "Sahebkar et al., 2014. Curcumin and inflammatory markers meta-analysis",
        studyType: "meta-analysis",
        year: 2014,
      },
    ],
  },
};

/**
 * Match a user's query to a precomputed intervention
 */
export function matchIntervention(query: string): MatchResult | null {
  const normalizedQuery = query.toLowerCase().trim();
  const queryWords = normalizedQuery.split(/\s+/).filter((w) => w.length > 2); // Ignore tiny words

  let bestMatch: MatchResult | null = null;
  let bestScore = 0;

  for (const intervention of Object.values(PRECOMPUTED_INTERVENTIONS)) {
    let score = 0;
    const matchedKeywords: string[] = [];

    for (const keyword of intervention.keywords) {
      const normalizedKeyword = keyword.toLowerCase();
      const keywordWords = normalizedKeyword.split(/\s+/);

      // Exact phrase match (highest priority)
      if (normalizedQuery.includes(normalizedKeyword)) {
        // Longer keyword phrases are more specific, give them more weight
        score += 3 + keywordWords.length;
        matchedKeywords.push(keyword);
      }
      // Exact word match (single word keyword matches exactly a query word)
      else if (keywordWords.length === 1 && queryWords.includes(normalizedKeyword)) {
        score += 2;
        matchedKeywords.push(keyword);
      }
      // Stemmed/partial word match (only if keyword is 4+ chars to avoid false positives)
      else if (
        normalizedKeyword.length >= 4 &&
        queryWords.some(
          (word) =>
            word.length >= 4 &&
            (normalizedKeyword.startsWith(word.slice(0, -1)) || word.startsWith(normalizedKeyword.slice(0, -1)))
        )
      ) {
        score += 1;
        matchedKeywords.push(keyword);
      }
    }

    // Boost for multiple distinct keyword matches
    if (matchedKeywords.length > 1) {
      score *= 1 + matchedKeywords.length * 0.2;
    }

    if (score > bestScore) {
      bestScore = score;
      bestMatch = {
        id: intervention.id,
        intervention,
        confidence: Math.min(score / 10, 1), // Normalize to 0-1
        matchedKeywords,
      };
    }
  }

  // Require minimum confidence
  if (bestMatch && bestMatch.confidence < 0.2) {
    return null;
  }

  return bestMatch;
}

/**
 * Get precomputed effect by ID
 */
export function getPrecomputedEffect(id: string): InterventionEffect | null {
  const intervention = PRECOMPUTED_INTERVENTIONS[id];
  return intervention?.effect ?? null;
}
