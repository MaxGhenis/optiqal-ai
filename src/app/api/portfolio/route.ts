/**
 * API Route: /api/portfolio
 *
 * POST endpoint for finding the optimal intervention portfolio using greedy selection.
 * Returns ranked list of intervention combinations with QALY for each combination size.
 */

import { NextRequest, NextResponse } from "next/server";
import { findOptimalPortfolio } from "@/lib/qaly/intervention-combinations";
import { getProfileQALY, ProfileQuery } from "@/lib/qaly/precomputed-profiles";

// =============================================================================
// REQUEST/RESPONSE TYPES
// =============================================================================

export interface PortfolioRequest {
  profile: ProfileQuery;
  excludedInterventions?: string[];
  maxInterventions?: number;
}

export interface PortfolioStep {
  interventionIds: string[];
  totalQaly: number;
  marginalQaly: number;
  addedIntervention: string;
}

export interface PortfolioResponse {
  portfolio: PortfolioStep[];
  availableInterventions: string[];
  error?: string;
}

// =============================================================================
// CONSTANTS
// =============================================================================

/**
 * All available interventions in the system.
 * This should match the interventions we have precomputed data for.
 */
const ALL_INTERVENTIONS = [
  "walking_30min_daily",
  "daily_exercise_moderate",
  "strength_training",
  "mediterranean_diet",
  "fish_oil_supplement",
  "quit_smoking",
  "moderate_alcohol",
  "meditation_daily",
  "sleep_8_hours",
  "daily_sunscreen",
];

// =============================================================================
// VALIDATION
// =============================================================================

const VALID_SEXES = ["male", "female"] as const;
const VALID_BMI_CATEGORIES = ["normal", "overweight", "obese", "severely_obese"] as const;
const VALID_SMOKING_STATUSES = ["never", "former", "current"] as const;
const VALID_ACTIVITY_LEVELS = ["sedentary", "light", "moderate", "active"] as const;

function validateProfile(profile: unknown): ProfileQuery | null {
  if (!profile || typeof profile !== "object") {
    return null;
  }

  const p = profile as Record<string, unknown>;

  // Required fields
  if (typeof p.age !== "number" || p.age < 0 || p.age > 120) {
    return null;
  }
  if (typeof p.sex !== "string" || !VALID_SEXES.includes(p.sex as "male" | "female")) {
    return null;
  }
  if (typeof p.bmiCategory !== "string" || !VALID_BMI_CATEGORIES.includes(p.bmiCategory as typeof VALID_BMI_CATEGORIES[number])) {
    return null;
  }
  if (typeof p.smokingStatus !== "string" || !VALID_SMOKING_STATUSES.includes(p.smokingStatus as typeof VALID_SMOKING_STATUSES[number])) {
    return null;
  }
  if (typeof p.hasDiabetes !== "boolean") {
    return null;
  }

  // Optional fields with defaults
  const hasHypertension = typeof p.hasHypertension === "boolean" ? p.hasHypertension : false;
  const activityLevel = typeof p.activityLevel === "string" && VALID_ACTIVITY_LEVELS.includes(p.activityLevel as typeof VALID_ACTIVITY_LEVELS[number])
    ? (p.activityLevel as typeof VALID_ACTIVITY_LEVELS[number])
    : "light";

  return {
    age: p.age,
    sex: p.sex as "male" | "female",
    bmiCategory: p.bmiCategory as typeof VALID_BMI_CATEGORIES[number],
    smokingStatus: p.smokingStatus as typeof VALID_SMOKING_STATUSES[number],
    hasDiabetes: p.hasDiabetes,
    hasHypertension,
    activityLevel,
  };
}

function validateExcludedInterventions(excluded: unknown): string[] {
  if (!excluded || !Array.isArray(excluded)) {
    return [];
  }

  // Filter to only valid intervention IDs
  return excluded.filter(
    (id) => typeof id === "string" && ALL_INTERVENTIONS.includes(id)
  ) as string[];
}

// =============================================================================
// HANDLER
// =============================================================================

export async function POST(request: NextRequest) {
  try {
    const body: unknown = await request.json();

    if (!body || typeof body !== "object") {
      return NextResponse.json(
        { error: "Invalid request body" },
        { status: 400 }
      );
    }

    const req = body as Record<string, unknown>;

    // Validate profile
    const profile = validateProfile(req.profile);
    if (!profile) {
      return NextResponse.json(
        {
          error:
            "Invalid profile. Required fields: age (0-120), sex (male/female), bmiCategory, smokingStatus, hasDiabetes",
        },
        { status: 400 }
      );
    }

    // Validate excluded interventions
    const excludedInterventions = validateExcludedInterventions(req.excludedInterventions);

    // Validate max interventions
    const maxInterventions =
      typeof req.maxInterventions === "number" && req.maxInterventions > 0
        ? Math.min(req.maxInterventions, 10) // Cap at 10
        : 5;

    // Get available interventions
    const availableInterventions = ALL_INTERVENTIONS.filter(
      (id) => !excludedInterventions.includes(id)
    );

    if (availableInterventions.length === 0) {
      return NextResponse.json(
        { error: "No interventions available after exclusions" },
        { status: 400 }
      );
    }

    // Fetch single-intervention QALYs for all available interventions
    const results = await Promise.all(
      availableInterventions.map(async (id) => {
        const result = await getProfileQALY(id, profile);
        return { id, result };
      })
    );

    // Build single QALY map (exclude null results)
    const singleQalys: Record<string, number> = {};
    for (const { id, result } of results) {
      if (result) {
        singleQalys[id] = result.qalyMedian;
      }
    }

    // Check if we have any valid data
    if (Object.keys(singleQalys).length === 0) {
      return NextResponse.json(
        { error: "No precomputed QALY data available for any interventions with this profile" },
        { status: 500 }
      );
    }

    // Find optimal portfolio
    const portfolio = findOptimalPortfolio(singleQalys, maxInterventions);

    // Return result
    const response: PortfolioResponse = {
      portfolio,
      availableInterventions: Object.keys(singleQalys),
    };

    return NextResponse.json(response, { status: 200 });
  } catch (error) {
    console.error("Error in /api/portfolio:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
