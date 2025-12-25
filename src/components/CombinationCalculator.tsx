"use client";

import { useState, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import {
  getCombinedProfileQaly,
  INTERVENTION_CATEGORIES,
  type CombinedEstimate,
} from "@/lib/qaly/intervention-combinations";
import {
  getBmiCategory,
  type ProfileQuery,
  type SmokingStatus,
  type ActivityLevel,
} from "@/lib/qaly/precomputed-profiles";
import type { UserProfile } from "@/types";
import {
  Loader2,
  TrendingUp,
  TrendingDown,
  Layers,
  Target,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

interface CombinationCalculatorProps {
  profile: UserProfile;
}

// Intervention display names
const INTERVENTION_NAMES: Record<string, string> = {
  walking_30min_daily: "30 min daily walking",
  daily_exercise_moderate: "Moderate exercise (150+ min/week)",
  strength_training: "Strength training",
  mediterranean_diet: "Mediterranean diet",
  fish_oil_supplement: "Fish oil supplement",
  quit_smoking: "Quit smoking",
  moderate_alcohol: "Moderate alcohol intake",
  meditation_daily: "Daily meditation",
  sleep_8_hours: "8 hours sleep nightly",
  daily_sunscreen: "Daily sunscreen",
};

// Convert UserProfile to ProfileQuery
function profileToQuery(profile: UserProfile): ProfileQuery {
  const bmi = profile.weight / ((profile.height / 100) ** 2);

  let smokingStatus: SmokingStatus = "never";
  if (profile.smoker) {
    smokingStatus = "current";
  }

  return {
    age: profile.age,
    sex: profile.sex === "other" ? "male" : profile.sex,
    bmiCategory: getBmiCategory(bmi),
    smokingStatus,
    hasDiabetes: profile.hasDiabetes,
    hasHypertension: profile.hasHypertension,
    activityLevel: profile.activityLevel as ActivityLevel,
  };
}

function formatQALYs(qalys: number): string {
  const sign = qalys >= 0 ? "+" : "";
  return `${sign}${qalys.toFixed(2)}`;
}

export function CombinationCalculator({ profile }: CombinationCalculatorProps) {
  const [selectedInterventions, setSelectedInterventions] = useState<Set<string>>(
    new Set()
  );
  const [isCalculating, setIsCalculating] = useState(false);
  const [result, setResult] = useState<CombinedEstimate | null>(null);
  const [showBreakdown, setShowBreakdown] = useState(false);

  // All available interventions
  const allInterventions = Object.keys(INTERVENTION_CATEGORIES);

  // Toggle intervention selection
  const toggleIntervention = (id: string) => {
    setSelectedInterventions((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(id)) {
        newSet.delete(id);
      } else {
        newSet.add(id);
      }
      return newSet;
    });
  };

  // Calculate combined QALY when selection changes
  useEffect(() => {
    const calculate = async () => {
      if (selectedInterventions.size === 0) {
        setResult(null);
        return;
      }

      setIsCalculating(true);
      try {
        const query = profileToQuery(profile);
        const combined = await getCombinedProfileQaly(
          Array.from(selectedInterventions),
          query,
          {
            applyOverlap: true,
            applyDiminishingReturns: true,
          }
        );
        setResult(combined);
      } catch (error) {
        console.error("Error calculating combined QALY:", error);
        setResult(null);
      } finally {
        setIsCalculating(false);
      }
    };

    calculate();
  }, [selectedInterventions, profile]);

  const isPositive = result && result.totalQaly >= 0;

  return (
    <Card className="mesh-gradient-card border-border/50">
      <CardContent className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-primary/10">
            <Layers className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h3 className="text-lg font-medium">Combination Calculator</h3>
            <p className="text-xs text-muted-foreground">
              Select multiple interventions to see combined impact with overlap
              adjustments
            </p>
          </div>
        </div>

        {/* Intervention Checkboxes */}
        <div className="space-y-3">
          <Label className="text-sm font-medium">Select Interventions</Label>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {allInterventions.map((id) => {
              const category = INTERVENTION_CATEGORIES[id];
              const isSelected = selectedInterventions.has(id);

              return (
                <div
                  key={id}
                  className={`
                    flex items-center gap-3 p-3 rounded-lg border transition-all cursor-pointer
                    ${
                      isSelected
                        ? "bg-primary/10 border-primary/30 hover:bg-primary/15"
                        : "bg-muted/20 border-border/30 hover:bg-muted/30"
                    }
                  `}
                  onClick={() => toggleIntervention(id)}
                >
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => toggleIntervention(id)}
                    className="w-4 h-4 rounded border-border bg-card text-primary focus:ring-primary cursor-pointer"
                  />
                  <div className="flex-1">
                    <p className="text-sm font-medium">
                      {INTERVENTION_NAMES[id]}
                    </p>
                    <p className="text-xs text-muted-foreground capitalize">
                      {category}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Loading State */}
        {isCalculating && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
            <span className="ml-2 text-sm text-muted-foreground">
              Calculating combined impact...
            </span>
          </div>
        )}

        {/* Results */}
        {!isCalculating && result && (
          <div className="space-y-6">
            {/* Total Impact */}
            <div className="bg-muted/30 rounded-xl p-6 text-center space-y-3">
              <p className="text-xs uppercase tracking-wider text-muted-foreground">
                Combined QALY Impact
              </p>
              <div
                className={`text-4xl md:text-5xl font-serif font-semibold ${
                  isPositive ? "gradient-text text-glow" : "text-destructive"
                }`}
              >
                {formatQALYs(result.totalQaly)}
              </div>
              <p className="text-sm text-muted-foreground">
                from {selectedInterventions.size} intervention
                {selectedInterventions.size !== 1 ? "s" : ""}
              </p>
            </div>

            {/* Breakdown Toggle */}
            <button
              type="button"
              onClick={() => setShowBreakdown(!showBreakdown)}
              className="w-full flex items-center justify-between text-foreground bg-muted/30 hover:bg-muted/50 transition-colors rounded-xl px-5 py-4"
            >
              <span className="flex items-center gap-2">
                <Target className="w-4 h-4 text-primary" />
                <span className="text-sm font-medium">
                  View detailed breakdown
                </span>
              </span>
              {showBreakdown ? (
                <ChevronUp className="w-4 h-4" />
              ) : (
                <ChevronDown className="w-4 h-4" />
              )}
            </button>

            {/* Detailed Breakdown */}
            {showBreakdown && (
              <div className="space-y-4">
                {/* Individual Contributions */}
                <div className="bg-muted/20 rounded-xl p-5 border border-border/30">
                  <div className="flex items-center gap-2 mb-4">
                    <TrendingUp className="w-4 h-4 text-primary" />
                    <span className="text-sm font-medium">
                      Individual Contributions
                    </span>
                  </div>
                  <div className="space-y-2">
                    {result.interventionIds.map((id) => {
                      const individualQaly = result.individualQalys[id] || 0;
                      const overlapAdjustment = result.overlapAdjustments[id];
                      const adjustedQaly = overlapAdjustment
                        ? individualQaly * overlapAdjustment
                        : individualQaly;

                      return (
                        <div
                          key={id}
                          className="flex items-center justify-between py-2 border-b border-border/10 last:border-0"
                        >
                          <div className="flex-1">
                            <p className="text-sm font-medium">
                              {INTERVENTION_NAMES[id]}
                            </p>
                            {overlapAdjustment && overlapAdjustment < 1.0 && (
                              <p className="text-xs text-muted-foreground">
                                {formatQALYs(individualQaly)} →{" "}
                                {formatQALYs(adjustedQaly)} (
                                {Math.round(overlapAdjustment * 100)}% after
                                overlap)
                              </p>
                            )}
                          </div>
                          <span
                            className={`text-sm font-medium ${
                              adjustedQaly >= 0
                                ? "text-emerald-400"
                                : "text-red-400"
                            }`}
                          >
                            {formatQALYs(
                              overlapAdjustment ? adjustedQaly : individualQaly
                            )}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Overlap Penalties */}
                {Object.keys(result.overlapAdjustments).length > 0 && (
                  <div className="bg-amber-500/5 border border-amber-500/20 rounded-xl p-5">
                    <div className="flex items-center gap-2 mb-3 text-amber-400">
                      <AlertTriangle className="w-4 h-4" />
                      <span className="text-sm font-medium">
                        Overlap Adjustments Applied
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground mb-3">
                      Some interventions share mechanisms and don't stack
                      additively. For example, walking and moderate exercise both
                      improve cardiovascular health.
                    </p>
                    <div className="space-y-2">
                      {Object.entries(result.overlapAdjustments).map(
                        ([id, factor]) => (
                          <div
                            key={id}
                            className="flex items-center justify-between text-xs"
                          >
                            <span className="text-muted-foreground">
                              {INTERVENTION_NAMES[id]}
                            </span>
                            <span className="text-amber-400 font-medium">
                              {Math.round(factor * 100)}% retained
                            </span>
                          </div>
                        )
                      )}
                    </div>
                  </div>
                )}

                {/* Diminishing Returns */}
                {result.diminishingReturnsFactor < 1.0 && (
                  <div className="bg-muted/20 rounded-xl p-4 border border-border/30">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <TrendingDown className="w-4 h-4 text-muted-foreground" />
                        <span className="text-sm font-medium">
                          Diminishing Returns Factor
                        </span>
                      </div>
                      <span className="text-sm font-medium">
                        {Math.round(result.diminishingReturnsFactor * 100)}%
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-2">
                      Stacking {result.interventionIds.length} interventions
                      reduces marginal effectiveness as baseline risk decreases.
                    </p>
                  </div>
                )}

                {/* Summary Calculation */}
                <div className="bg-primary/5 border border-primary/20 rounded-xl p-4">
                  <p className="text-xs text-muted-foreground">
                    <span className="font-medium text-foreground">
                      Calculation:
                    </span>{" "}
                    Sum of individual QALYs (
                    {formatQALYs(
                      Object.values(result.individualQalys).reduce(
                        (a, b) => a + b,
                        0
                      )
                    )}
                    )
                    {Object.keys(result.overlapAdjustments).length > 0 &&
                      " with overlap corrections"}
                    {result.diminishingReturnsFactor < 1.0 &&
                      ` × ${result.diminishingReturnsFactor.toFixed(2)} (diminishing returns)`}{" "}
                    = {formatQALYs(result.totalQaly)}
                  </p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Empty State */}
        {!isCalculating && selectedInterventions.size === 0 && (
          <div className="text-center py-12">
            <Layers className="h-12 w-12 text-muted-foreground/30 mx-auto mb-3" />
            <p className="text-sm text-muted-foreground">
              Select interventions above to see their combined impact
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
