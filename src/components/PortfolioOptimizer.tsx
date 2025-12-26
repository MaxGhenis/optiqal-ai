"use client";

import { useState, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import type { UserProfile } from "@/types";
import {
  getProfileQALY,
  getBmiCategory,
  type ProfileQuery,
} from "@/lib/qaly/precomputed-profiles";
import {
  findOptimalPortfolio,
  type PortfolioStep,
  INTERVENTION_CATEGORIES,
} from "@/lib/qaly/intervention-combinations";
import {
  TrendingUp,
  Sparkles,
  Loader2,
  Package,
  Target,
  ChevronDown,
  ChevronUp,
  X,
} from "lucide-react";

interface PortfolioOptimizerProps {
  profile: UserProfile;
}

// Intervention display names
const INTERVENTION_NAMES: Record<string, string> = {
  walking_30min_daily: "Walk 30 min daily",
  daily_exercise_moderate: "Moderate exercise daily",
  strength_training: "Strength training",
  mediterranean_diet: "Mediterranean diet",
  fish_oil_supplement: "Fish oil supplement",
  quit_smoking: "Quit smoking",
  moderate_alcohol: "Moderate alcohol",
  meditation_daily: "Meditate daily",
  sleep_8_hours: "Sleep 8 hours",
  daily_sunscreen: "Daily sunscreen",
};

function formatQALY(qaly: number): string {
  const absQaly = Math.abs(qaly);
  if (absQaly >= 1) {
    return `${qaly >= 0 ? "+" : ""}${qaly.toFixed(2)}`;
  }
  if (absQaly >= 0.01) {
    return `${qaly >= 0 ? "+" : ""}${qaly.toFixed(3)}`;
  }
  return `${qaly >= 0 ? "+" : ""}${qaly.toFixed(4)}`;
}

export function PortfolioOptimizer({ profile }: PortfolioOptimizerProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [portfolio, setPortfolio] = useState<PortfolioStep[]>([]);
  const [singleQalys, setSingleQalys] = useState<Record<string, number>>({});
  const [excludedInterventions, setExcludedInterventions] = useState<Set<string>>(new Set());
  const [showExclusions, setShowExclusions] = useState(false);
  const [expandedSteps, setExpandedSteps] = useState<Set<number>>(new Set([0]));

  const toggleExclusion = (interventionId: string) => {
    setExcludedInterventions((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(interventionId)) {
        newSet.delete(interventionId);
      } else {
        newSet.add(interventionId);
      }
      return newSet;
    });
  };

  const toggleStep = (index: number) => {
    setExpandedSteps((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(index)) {
        newSet.delete(index);
      } else {
        newSet.add(index);
      }
      return newSet;
    });
  };

  const calculateOptimalPortfolio = async () => {
    setIsLoading(true);
    try {
      // Convert UserProfile to ProfileQuery
      const bmi = profile.weight / Math.pow(profile.height / 100, 2);
      const smokingStatus = profile.smoker ? "current" : "never";

      const query: ProfileQuery = {
        age: profile.age,
        sex: profile.sex === "other" ? "male" : profile.sex, // Default to male if "other"
        bmiCategory: getBmiCategory(bmi),
        smokingStatus,
        hasDiabetes: profile.hasDiabetes,
        hasHypertension: profile.hasHypertension,
        activityLevel: profile.activityLevel,
      };

      // Get all available interventions
      const allInterventions = Object.keys(INTERVENTION_CATEGORIES);

      // Filter out excluded interventions
      const availableInterventions = allInterventions.filter(
        (id) => !excludedInterventions.has(id)
      );

      // Fetch QALYs for all available interventions
      const qalyResults = await Promise.all(
        availableInterventions.map(async (id) => {
          const result = await getProfileQALY(id, query);
          return { id, qaly: result?.qalyMedian ?? 0 };
        })
      );

      // Build single QALY map
      const qalyMap: Record<string, number> = {};
      for (const { id, qaly } of qalyResults) {
        qalyMap[id] = qaly;
      }

      setSingleQalys(qalyMap);

      // Find optimal portfolio (top 5 interventions)
      const optimalPortfolio = findOptimalPortfolio(qalyMap, 5);
      setPortfolio(optimalPortfolio);

      // Expand the first step by default
      setExpandedSteps(new Set([0]));
    } catch (error) {
      console.error("Error calculating portfolio:", error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Card className="mesh-gradient-card border-border/50 card-highlight">
      <CardContent className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-start gap-4">
          <div className="p-2 rounded-lg bg-primary/10">
            <Target className="h-5 w-5 text-primary" />
          </div>
          <div className="flex-1">
            <h3 className="text-lg font-semibold mb-1">
              Find Your Optimal Portfolio
            </h3>
            <p className="text-sm text-muted-foreground">
              Discover the best combination of lifestyle interventions for maximum
              QALY gain. Automatically accounts for overlap and diminishing returns.
            </p>
          </div>
        </div>

        {/* Exclusions */}
        <div className="space-y-3">
          <button
            type="button"
            onClick={() => setShowExclusions(!showExclusions)}
            className="w-full flex items-center justify-between text-foreground bg-muted/30 hover:bg-muted/50 transition-colors rounded-xl px-4 py-3"
          >
            <span className="flex items-center gap-2 text-sm">
              <Package className="w-4 h-4 text-primary" />
              <span>
                Exclude interventions you already do ({excludedInterventions.size} excluded)
              </span>
            </span>
            {showExclusions ? (
              <ChevronUp className="w-4 h-4" />
            ) : (
              <ChevronDown className="w-4 h-4" />
            )}
          </button>

          {showExclusions && (
            <div className="bg-muted/20 rounded-xl p-4 space-y-2">
              <p className="text-xs text-muted-foreground mb-3">
                Select interventions you're already doing to exclude them from recommendations:
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {Object.entries(INTERVENTION_NAMES).map(([id, name]) => (
                  <label
                    key={id}
                    className="flex items-center gap-3 p-2 rounded-lg hover:bg-muted/30 transition-colors cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={excludedInterventions.has(id)}
                      onChange={() => toggleExclusion(id)}
                      className="w-4 h-4 rounded border-border bg-card text-primary focus:ring-primary"
                    />
                    <span className="text-sm">{name}</span>
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Calculate Button */}
        <Button
          onClick={calculateOptimalPortfolio}
          disabled={isLoading}
          className="w-full btn-glow bg-primary text-primary-foreground hover:bg-primary/90 h-12"
        >
          {isLoading ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Calculating optimal portfolio...
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4 mr-2" />
              Calculate Optimal Portfolio
            </>
          )}
        </Button>

        {/* Results */}
        {portfolio.length > 0 && (
          <div className="space-y-4 pt-4 border-t border-border/30">
            <div className="flex items-center gap-2 text-muted-foreground">
              <TrendingUp className="w-4 h-4 text-primary" />
              <span className="text-sm font-medium">
                Ranked by marginal QALY gain
              </span>
            </div>

            <div className="space-y-3">
              {portfolio.map((step, index) => {
                const isExpanded = expandedSteps.has(index);
                const isFirst = index === 0;

                return (
                  <div
                    key={index}
                    className={`rounded-xl border transition-all ${
                      isFirst
                        ? "bg-primary/5 border-primary/30"
                        : "bg-muted/20 border-border/30"
                    }`}
                  >
                    {/* Step Header */}
                    <button
                      type="button"
                      onClick={() => toggleStep(index)}
                      className="w-full flex items-center justify-between p-4 text-left hover:bg-muted/30 transition-colors rounded-xl"
                    >
                      <div className="flex items-center gap-3 flex-1">
                        <div
                          className={`flex items-center justify-center w-8 h-8 rounded-full text-sm font-semibold ${
                            isFirst
                              ? "bg-primary/20 text-primary"
                              : "bg-muted/50 text-muted-foreground"
                          }`}
                        >
                          {index + 1}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span
                              className={`font-medium ${
                                isFirst ? "text-primary" : ""
                              }`}
                            >
                              {INTERVENTION_NAMES[step.addedIntervention] ||
                                step.addedIntervention}
                            </span>
                            {isFirst && (
                              <span className="text-xs px-2 py-0.5 rounded-full bg-primary/20 text-primary">
                                Best choice
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-4 mt-1 text-sm">
                            <span className="text-emerald-400 font-medium">
                              {formatQALY(step.marginalQaly)} marginal
                            </span>
                            <span className="text-muted-foreground">
                              {formatQALY(step.totalQaly)} cumulative
                            </span>
                          </div>
                        </div>
                      </div>
                      {isExpanded ? (
                        <ChevronUp className="w-4 h-4 text-muted-foreground" />
                      ) : (
                        <ChevronDown className="w-4 h-4 text-muted-foreground" />
                      )}
                    </button>

                    {/* Step Details */}
                    {isExpanded && (
                      <div className="px-4 pb-4 pt-2 space-y-3 border-t border-border/20">
                        <div className="space-y-2">
                          <p className="text-xs text-muted-foreground uppercase tracking-wider">
                            Portfolio at this step
                          </p>
                          <div className="flex flex-wrap gap-2">
                            {step.interventionIds.map((id) => (
                              <span
                                key={id}
                                className={`text-xs px-3 py-1.5 rounded-lg border ${
                                  id === step.addedIntervention
                                    ? "bg-primary/10 border-primary/30 text-primary"
                                    : "bg-muted/30 border-border/30 text-muted-foreground"
                                }`}
                              >
                                {INTERVENTION_NAMES[id] || id}
                              </span>
                            ))}
                          </div>
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                          <div className="bg-muted/30 rounded-lg p-3">
                            <div className="text-xs text-muted-foreground mb-1">
                              Marginal gain
                            </div>
                            <div className="text-lg font-semibold text-emerald-400">
                              {formatQALY(step.marginalQaly)}
                            </div>
                            <div className="text-xs text-muted-foreground mt-1">
                              From adding this intervention
                            </div>
                          </div>
                          <div className="bg-muted/30 rounded-lg p-3">
                            <div className="text-xs text-muted-foreground mb-1">
                              Total portfolio
                            </div>
                            <div className="text-lg font-semibold text-primary">
                              {formatQALY(step.totalQaly)}
                            </div>
                            <div className="text-xs text-muted-foreground mt-1">
                              Cumulative with overlap
                            </div>
                          </div>
                        </div>

                        {index > 0 && (
                          <div className="bg-amber-500/5 border border-amber-500/20 rounded-lg p-3">
                            <p className="text-xs text-amber-200/80">
                              Overlap and diminishing returns are automatically
                              accounted for. Marginal gain is less than the
                              standalone effect ({formatQALY(singleQalys[step.addedIntervention])})
                              due to shared mechanisms with previous interventions.
                            </p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Summary */}
            <div className="bg-primary/5 border border-primary/20 rounded-xl p-4 mt-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">
                  Total portfolio QALY gain:
                </span>
                <span className="text-2xl font-bold gradient-text">
                  {formatQALY(portfolio[portfolio.length - 1]?.totalQaly ?? 0)}
                </span>
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                This is your estimated lifetime QALY gain from implementing all {portfolio.length}{" "}
                interventions, accounting for overlap between similar interventions
                and diminishing returns.
              </p>
            </div>
          </div>
        )}

        {/* Empty state */}
        {!isLoading && portfolio.length === 0 && (
          <div className="text-center py-8 text-muted-foreground">
            <Package className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p className="text-sm">
              Click the button above to find your optimal intervention portfolio
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
