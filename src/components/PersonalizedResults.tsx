"use client";

import { useProfileQALY, type ProfileQALYResult } from "@/hooks/useProfileQALY";
import type { UserProfile } from "@/types";
import { Card, CardContent } from "@/components/ui/card";
import {
  TrendingUp,
  TrendingDown,
  Loader2,
  AlertCircle,
  Users,
  Heart,
  Activity,
  Zap,
  Target,
} from "lucide-react";

interface PersonalizedResultsProps {
  profile: UserProfile;
  interventionId: string;
  interventionName: string;
}

/**
 * Format QALY to human-readable string
 */
function formatQALY(qaly: number): string {
  if (Math.abs(qaly) < 0.01) {
    return `${(qaly * 365.25).toFixed(1)} days`;
  }
  if (Math.abs(qaly) < 1) {
    return `${(qaly * 12).toFixed(1)} months`;
  }
  return `${qaly.toFixed(2)} years`;
}

/**
 * Calculate percentile relative to population
 */
function calculatePercentile(
  personalValue: number,
  min: number,
  max: number,
  median: number
): number {
  if (personalValue < median) {
    // Below median: scale 0-50
    return ((personalValue - min) / (median - min)) * 50;
  } else {
    // Above median: scale 50-100
    return 50 + ((personalValue - median) / (max - median)) * 50;
  }
}

/**
 * Display effect modifier breakdown
 */
function EffectModifierBreakdown({
  result,
  profile,
}: {
  result: ProfileQALYResult;
  profile: UserProfile;
}) {
  const bmi = profile.weight / Math.pow(profile.height / 100, 2);
  const modifiers: Array<{
    factor: string;
    impact: number;
    description: string;
  }> = [];

  // Baseline mortality multiplier
  if (result.baselineMortalityMultiplier !== 1.0) {
    const pctChange =
      ((result.baselineMortalityMultiplier - 1.0) * 100).toFixed(0);
    const sign = result.baselineMortalityMultiplier > 1.0 ? "+" : "";
    modifiers.push({
      factor: "Baseline Risk",
      impact: result.baselineMortalityMultiplier - 1.0,
      description: `${sign}${pctChange}% due to ${profile.age}yo ${profile.sex}${profile.hasDiabetes ? ", diabetes" : ""}${profile.hasHypertension ? ", hypertension" : ""}`,
    });
  }

  // Intervention effect modifier
  if (result.interventionEffectModifier !== 1.0) {
    const pctChange =
      ((result.interventionEffectModifier - 1.0) * 100).toFixed(0);
    const sign = result.interventionEffectModifier > 1.0 ? "+" : "";

    // Determine reason
    let reason = "";
    if (bmi >= 30) {
      reason = "obesity (BMI ≥30)";
    } else if (bmi >= 25) {
      reason = "overweight (BMI 25-30)";
    } else if (profile.activityLevel === "sedentary") {
      reason = "sedentary activity";
    } else if (profile.activityLevel === "active") {
      reason = "high activity level";
    }

    if (reason) {
      modifiers.push({
        factor: "Intervention Effect",
        impact: result.interventionEffectModifier - 1.0,
        description: `${sign}${pctChange}% due to ${reason}`,
      });
    }
  }

  if (modifiers.length === 0) {
    return null;
  }

  return (
    <div className="mt-4 space-y-2">
      <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-muted-foreground">
        <Target className="w-3 h-3" />
        <span>Effect Modifiers</span>
      </div>
      <div className="space-y-2">
        {modifiers.map((mod, idx) => (
          <div
            key={idx}
            className="flex items-center justify-between text-xs bg-muted/20 rounded-lg px-3 py-2"
          >
            <div className="flex items-center gap-2">
              {mod.impact >= 0 ? (
                <TrendingUp className="w-3 h-3 text-emerald-400" />
              ) : (
                <TrendingDown className="w-3 h-3 text-red-400" />
              )}
              <span className="text-muted-foreground">{mod.factor}:</span>
              <span className="text-foreground">{mod.description}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Personalized QALY results for a single intervention
 */
export function PersonalizedResults({
  profile,
  interventionId,
  interventionName,
}: PersonalizedResultsProps) {
  const { result, loading, error } = useProfileQALY(profile, interventionId);

  if (loading) {
    return (
      <Card className="mesh-gradient-card border-border/50">
        <CardContent className="p-6">
          <div className="flex items-center justify-center gap-3 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span className="text-sm">Loading personalized estimate...</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="border-amber-500/30 bg-amber-500/5">
        <CardContent className="p-4">
          <div className="flex items-center gap-3 text-amber-400">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            <p className="text-sm">{error}</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!result) {
    return null;
  }

  const isPositive = result.qalyMedian >= 0;
  const hasPopulationData =
    result.populationMedian !== null &&
    result.populationMin !== null &&
    result.populationMax !== null;

  let percentile: number | null = null;
  if (hasPopulationData) {
    percentile = calculatePercentile(
      result.qalyMedian,
      result.populationMin!,
      result.populationMax!,
      result.populationMedian!
    );
  }

  return (
    <Card className="mesh-gradient-card border-primary/50 card-highlight">
      <CardContent className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-primary" />
            <h3 className="text-sm font-medium">Your Personalized Estimate</h3>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-full px-3 py-1">
            <Activity className="w-3 h-3" />
            <span>Profile-based</span>
          </div>
        </div>

        {/* Main QALY Impact */}
        <div className="text-center space-y-2">
          <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
            Estimated QALY Gain
          </p>
          <div
            className={`text-4xl font-serif font-semibold ${
              isPositive ? "gradient-text text-glow" : "text-destructive"
            }`}
          >
            {formatQALY(result.qalyMedian)}
          </div>
          <p className="text-xs text-muted-foreground">
            95% CI: {formatQALY(result.qalyCi95Low)} to{" "}
            {formatQALY(result.qalyCi95High)}
          </p>
        </div>

        {/* Pathway Breakdown */}
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-rose-500/10 rounded-xl p-3 border border-rose-500/20">
            <div className="flex items-center gap-1.5 mb-1">
              <Heart className="w-3 h-3 text-rose-400" />
              <span className="text-[10px] uppercase tracking-wider text-rose-400">
                CVD
              </span>
            </div>
            <p className="text-sm font-semibold text-rose-400">
              {formatQALY(result.cvdContribution)}
            </p>
          </div>
          <div className="bg-purple-500/10 rounded-xl p-3 border border-purple-500/20">
            <div className="flex items-center gap-1.5 mb-1">
              <Activity className="w-3 h-3 text-purple-400" />
              <span className="text-[10px] uppercase tracking-wider text-purple-400">
                Cancer
              </span>
            </div>
            <p className="text-sm font-semibold text-purple-400">
              {formatQALY(result.cancerContribution)}
            </p>
          </div>
          <div className="bg-blue-500/10 rounded-xl p-3 border border-blue-500/20">
            <div className="flex items-center gap-1.5 mb-1">
              <Zap className="w-3 h-3 text-blue-400" />
              <span className="text-[10px] uppercase tracking-wider text-blue-400">
                Other
              </span>
            </div>
            <p className="text-sm font-semibold text-blue-400">
              {formatQALY(result.otherContribution)}
            </p>
          </div>
        </div>

        {/* Life Years */}
        <div className="bg-muted/20 rounded-lg p-3 flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            Life years gained (undiscounted):
          </span>
          <span className="text-sm font-medium">
            {result.lifeYearsGained.toFixed(2)} years
          </span>
        </div>

        {/* Causal Fraction */}
        <div className="bg-amber-500/5 border border-amber-500/20 rounded-lg p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-amber-400">
              Causal fraction
            </span>
            <span className="text-lg font-semibold text-amber-400">
              {(result.causalFractionMean * 100).toFixed(0)}%
            </span>
          </div>
          <p className="text-xs text-muted-foreground">
            Estimated proportion of observed benefit that is truly causal (vs
            confounded)
          </p>
          <div className="h-2 bg-muted/30 rounded-full overflow-hidden mt-2">
            <div
              className="h-full bg-gradient-to-r from-amber-500/70 to-amber-400/70 rounded-full"
              style={{ width: `${result.causalFractionMean * 100}%` }}
            />
          </div>
        </div>

        {/* Effect Modifiers */}
        <EffectModifierBreakdown result={result} profile={profile} />

        {/* Population Comparison */}
        {hasPopulationData && percentile !== null && (
          <div className="bg-muted/20 rounded-xl p-4 border border-border/30 space-y-3">
            <div className="flex items-center gap-2 text-sm">
              <Users className="w-4 h-4 text-primary" />
              <span className="font-medium">Population Comparison</span>
            </div>
            <div className="space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Your result:</span>
                <span className="font-medium">{formatQALY(result.qalyMedian)}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Population median:</span>
                <span className="font-medium">
                  {formatQALY(result.populationMedian!)}
                </span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Your percentile:</span>
                <span
                  className={`font-medium ${
                    percentile >= 50 ? "text-emerald-400" : "text-amber-400"
                  }`}
                >
                  {percentile.toFixed(0)}th
                </span>
              </div>
              <div className="h-2 bg-muted/30 rounded-full overflow-hidden relative">
                <div
                  className="h-full bg-gradient-to-r from-primary/50 to-primary rounded-full"
                  style={{ width: `${percentile}%` }}
                />
                <div
                  className="absolute top-0 w-1 h-full bg-white/80"
                  style={{ left: "50%" }}
                />
              </div>
              <p className="text-xs text-muted-foreground">
                {percentile >= 50
                  ? `You would benefit more than ${percentile.toFixed(0)}% of the population.`
                  : `You would benefit less than ${(100 - percentile).toFixed(0)}% of the population.`}
              </p>
            </div>
          </div>
        )}

        {/* Info note */}
        <div className="flex items-start gap-2 text-xs text-muted-foreground bg-muted/20 rounded-lg p-3">
          <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
          <p>
            This estimate is based on precomputed lifecycle simulations
            specific to your age, sex, BMI category, smoking status, diabetes,
            hypertension, and activity level. Results include pathway
            decomposition (CVD, cancer, other) and confounding adjustment.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
