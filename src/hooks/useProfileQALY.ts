import { useState, useEffect } from "react";
import type { UserProfile } from "@/types";
import {
  getQALYForPerson,
  getProfileSummary,
  type ProfileResult,
  type SmokingStatus,
  type ActivityLevel,
} from "@/lib/qaly/precomputed-profiles";

export interface ProfileQALYResult {
  qalyMedian: number;
  qalyMean: number;
  qalyCi95Low: number;
  qalyCi95High: number;
  lifeYearsGained: number;
  cvdContribution: number;
  cancerContribution: number;
  otherContribution: number;
  causalFractionMean: number;
  baselineMortalityMultiplier: number;
  interventionEffectModifier: number;
  populationMedian: number | null;
  populationMin: number | null;
  populationMax: number | null;
}

export interface UseProfileQALYState {
  result: ProfileQALYResult | null;
  loading: boolean;
  error: string | null;
}

/**
 * Convert UserProfile smoker boolean to SmokingStatus
 */
function getSmokingStatus(smoker: boolean): SmokingStatus {
  return smoker ? "current" : "never";
}

/**
 * Calculate BMI from weight (kg) and height (cm)
 */
function calculateBMI(weight: number, height: number): number {
  return weight / Math.pow(height / 100, 2);
}

/**
 * Hook to fetch personalized QALY estimate for a given intervention
 */
export function useProfileQALY(
  profile: UserProfile,
  interventionId: string | null
): UseProfileQALYState {
  const [result, setResult] = useState<ProfileQALYResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!interventionId) {
      setResult(null);
      setError(null);
      setLoading(false);
      return;
    }

    let cancelled = false;

    async function fetchQALY() {
      setLoading(true);
      setError(null);

      try {
        const bmi = calculateBMI(profile.weight, profile.height);
        const smokingStatus = getSmokingStatus(profile.smoker);

        // Handle "other" sex by defaulting to male for now
        const sex = profile.sex === "other" ? "male" : profile.sex;

        // Fetch personalized result
        const profileResult = await getQALYForPerson(
          interventionId,
          profile.age,
          sex,
          bmi,
          smokingStatus,
          profile.hasDiabetes,
          profile.hasHypertension,
          profile.activityLevel
        );

        if (!profileResult) {
          if (!cancelled) {
            setError(`No precomputed data available for ${interventionId}`);
            setLoading(false);
          }
          return;
        }

        // Fetch population statistics for comparison
        const summary = await getProfileSummary(interventionId);

        if (!cancelled) {
          setResult({
            qalyMedian: profileResult.qalyMedian,
            qalyMean: profileResult.qalyMean,
            qalyCi95Low: profileResult.qalyCi95Low,
            qalyCi95High: profileResult.qalyCi95High,
            lifeYearsGained: profileResult.lifeYearsGained,
            cvdContribution: profileResult.cvdContribution,
            cancerContribution: profileResult.cancerContribution,
            otherContribution: profileResult.otherContribution,
            causalFractionMean: profileResult.causalFractionMean,
            baselineMortalityMultiplier: profileResult.baselineMortalityMultiplier,
            interventionEffectModifier: profileResult.interventionEffectModifier,
            populationMedian: summary?.medianQALY ?? null,
            populationMin: summary?.minQALY ?? null,
            populationMax: summary?.maxQALY ?? null,
          });
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load QALY data");
          setLoading(false);
        }
      }
    }

    fetchQALY();

    return () => {
      cancelled = true;
    };
  }, [
    interventionId,
    profile.age,
    profile.sex,
    profile.weight,
    profile.height,
    profile.smoker,
    profile.hasDiabetes,
    profile.hasHypertension,
    profile.activityLevel,
  ]);

  return { result, loading, error };
}
