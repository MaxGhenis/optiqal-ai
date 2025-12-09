export interface UserProfile {
  age: number;
  sex: "male" | "female" | "other";
  weight: number; // kg
  height: number; // cm
  smoker: boolean;
  exerciseHoursPerWeek: number;
  sleepHoursPerNight: number;
  existingConditions: string[];
  diet: "omnivore" | "vegetarian" | "vegan" | "pescatarian" | "keto" | "other";
}

export interface QALYImpact {
  totalMinutes: number; // Total QALY impact expressed in minutes
  longevityMinutes: number; // Impact on lifespan
  qualityMinutes: number; // Impact on quality (converted to time equivalent)
  confidenceLevel: "low" | "medium" | "high";
  confidenceInterval: {
    low: number;
    high: number;
  };
}

export interface EvidenceSource {
  title: string;
  year: number;
  type:
    | "meta-analysis"
    | "rct"
    | "cohort"
    | "case-control"
    | "cross-sectional"
    | "expert-opinion";
  sampleSize?: number;
  effectSize?: string;
  summary: string;
}

export interface ChoiceAnalysis {
  id: string;
  choice: string;
  category:
    | "health"
    | "environment"
    | "lifestyle"
    | "diet"
    | "sleep"
    | "exercise"
    | "other";
  impact: QALYImpact;
  evidence: EvidenceSource[];
  mechanismExplanation: string;
  caveats: string[];
  personalizedFactors: string[];
}

export interface AnalysisRequest {
  profile: UserProfile;
  choice: string;
}

export interface AnalysisResponse {
  analysis: ChoiceAnalysis;
  disclaimer: string;
}

// Default: 5'9", 165 lbs (roughly average US male)
export const DEFAULT_PROFILE: UserProfile = {
  age: 35,
  sex: "male",
  weight: 75, // ~165 lbs
  height: 175, // ~5'9"
  smoker: false,
  exerciseHoursPerWeek: 3,
  sleepHoursPerNight: 7,
  existingConditions: [],
  diet: "omnivore",
};
