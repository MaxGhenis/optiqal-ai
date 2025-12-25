/**
 * API Route: /api/combinations
 *
 * POST endpoint for calculating combined QALY impact of multiple interventions
 * with overlap and diminishing returns corrections.
 */

import { NextRequest, NextResponse } from "next/server";
import { getCombinedProfileQaly } from "@/lib/qaly/intervention-combinations";
import { ProfileQuery } from "@/lib/qaly/precomputed-profiles";

// =============================================================================
// REQUEST/RESPONSE TYPES
// =============================================================================

export interface CombinationsRequest {
  profile: ProfileQuery;
  selectedInterventions: string[];
  options?: {
    applyOverlap?: boolean;
    applyDiminishingReturns?: boolean;
  };
}

export interface CombinationsResponse {
  totalQaly: number;
  individualQalys: Record<string, number>;
  overlapAdjustments: Record<string, number>;
  diminishingReturnsFactor: number;
  interventionIds: string[];
  error?: string;
}

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

function validateInterventions(interventions: unknown): string[] | null {
  if (!Array.isArray(interventions)) {
    return null;
  }

  // Check all are strings
  if (!interventions.every((i) => typeof i === "string")) {
    return null;
  }

  return interventions as string[];
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
        { error: "Invalid profile. Required fields: age (0-120), sex (male/female), bmiCategory, smokingStatus, hasDiabetes" },
        { status: 400 }
      );
    }

    // Validate interventions
    const interventions = validateInterventions(req.selectedInterventions);
    if (!interventions) {
      return NextResponse.json(
        { error: "Invalid selectedInterventions. Must be an array of strings" },
        { status: 400 }
      );
    }

    // Extract options
    const options = req.options as { applyOverlap?: boolean; applyDiminishingReturns?: boolean } | undefined;

    // Calculate combined QALY
    const result = await getCombinedProfileQaly(interventions, profile, options);

    if (!result) {
      return NextResponse.json(
        { error: "Failed to calculate combined QALY. Check that intervention data exists for the given profile." },
        { status: 500 }
      );
    }

    // Return result
    const response: CombinationsResponse = {
      totalQaly: result.totalQaly,
      individualQalys: result.individualQalys,
      overlapAdjustments: result.overlapAdjustments,
      diminishingReturnsFactor: result.diminishingReturnsFactor,
      interventionIds: result.interventionIds,
    };

    return NextResponse.json(response, { status: 200 });
  } catch (error) {
    console.error("Error in /api/combinations:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
