"use client";

import { useState, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { Loader2, Info } from "lucide-react";
import {
  getProfileQALY,
  getProfileSummary,
  getBmiCategory,
  type ProfileQuery,
} from "@/lib/qaly/precomputed-profiles";
import type { UserProfile } from "@/types";

// Intervention metadata extracted from YAML files
interface InterventionMeta {
  id: string;
  name: string;
  category: string;
  description: string;
}

const INTERVENTIONS: InterventionMeta[] = [
  {
    id: "walking_30min_daily",
    name: "Walk 30 minutes daily",
    category: "exercise",
    description: "Moderate-paced walking for 30 minutes per day",
  },
  {
    id: "daily_exercise_moderate",
    name: "150 Minutes/Week Moderate Exercise",
    category: "exercise",
    description: "Achieve WHO guidelines of 150 minutes/week moderate-intensity aerobic activity",
  },
  {
    id: "strength_training",
    name: "Strength Training 2x/Week",
    category: "exercise",
    description: "Resistance exercise training 2-3 times per week",
  },
  {
    id: "mediterranean_diet",
    name: "Mediterranean Diet Pattern",
    category: "diet",
    description: "Diet rich in vegetables, fruits, whole grains, legumes, nuts, olive oil, fish",
  },
  {
    id: "quit_smoking",
    name: "Smoking Cessation",
    category: "substance",
    description: "Complete cessation of cigarette smoking",
  },
  {
    id: "moderate_alcohol",
    name: "Limit Alcohol to 1-2 Drinks/Day",
    category: "substance",
    description: "Reduce alcohol consumption from heavy/moderate to moderate levels",
  },
  {
    id: "meditation_daily",
    name: "Daily Mindfulness Meditation",
    category: "stress",
    description: "Practice mindfulness meditation 10-20 minutes daily",
  },
  {
    id: "sleep_8_hours",
    name: "Regular 8 Hours of Sleep",
    category: "sleep",
    description: "Consistent 7.5-8.5 hours of sleep per night",
  },
  {
    id: "fish_oil_supplement",
    name: "Omega-3 Fish Oil Supplement",
    category: "medical",
    description: "Daily supplementation with 1g EPA+DHA omega-3 fatty acids",
  },
  {
    id: "daily_sunscreen",
    name: "Daily Sunscreen SPF 30+",
    category: "medical",
    description: "Daily application of SPF 30+ broad-spectrum sunscreen",
  },
];

// Category colors - using a vibrant, accessible palette
const CATEGORY_COLORS: Record<string, string> = {
  exercise: "#10B981", // Green
  diet: "#F59E0B", // Amber
  substance: "#EF4444", // Red
  stress: "#8B5CF6", // Purple
  sleep: "#3B82F6", // Blue
  medical: "#06B6D4", // Cyan
};

interface ComparisonData {
  intervention: string;
  shortName: string;
  category: string;
  qalyGain: number;
  ciLow: number;
  ciHigh: number;
  errorLow: number;
  errorHigh: number;
  color: string;
}

interface InterventionComparisonProps {
  profile: UserProfile;
}

export function InterventionComparison({ profile }: InterventionComparisonProps) {
  const [isLoading, setIsLoading] = useState(true);
  const [showPersonalized, setShowPersonalized] = useState(true);
  const [personalizedData, setPersonalizedData] = useState<ComparisonData[]>([]);
  const [populationData, setPopulationData] = useState<ComparisonData[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      setIsLoading(true);
      setError(null);

      try {
        // Build profile query from user profile
        const bmi = profile.weight / Math.pow(profile.height / 100, 2);
        const profileQuery: ProfileQuery = {
          age: profile.age,
          sex: profile.sex === "male" || profile.sex === "female" ? profile.sex : "male",
          bmiCategory: getBmiCategory(bmi),
          smokingStatus: profile.smoker ? "current" : "never",
          hasDiabetes: profile.hasDiabetes,
          hasHypertension: profile.hasHypertension,
          activityLevel: profile.activityLevel,
        };

        const personalizedResults: ComparisonData[] = [];
        const populationResults: ComparisonData[] = [];

        // Load data for each intervention
        for (const intervention of INTERVENTIONS) {
          try {
            // Get personalized result
            const personalResult = await getProfileQALY(intervention.id, profileQuery);

            // Get population summary
            const summary = await getProfileSummary(intervention.id);

            if (personalResult) {
              personalizedResults.push({
                intervention: intervention.name,
                shortName: intervention.name.split(" ").slice(0, 3).join(" "),
                category: intervention.category,
                qalyGain: personalResult.qalyMean,
                ciLow: personalResult.qalyCi95Low,
                ciHigh: personalResult.qalyCi95High,
                errorLow: personalResult.qalyMean - personalResult.qalyCi95Low,
                errorHigh: personalResult.qalyCi95High - personalResult.qalyMean,
                color: CATEGORY_COLORS[intervention.category] || "#6B7280",
              });
            }

            if (summary) {
              populationResults.push({
                intervention: intervention.name,
                shortName: intervention.name.split(" ").slice(0, 3).join(" "),
                category: intervention.category,
                qalyGain: summary.medianQALY,
                ciLow: summary.minQALY,
                ciHigh: summary.maxQALY,
                errorLow: summary.medianQALY - summary.minQALY,
                errorHigh: summary.maxQALY - summary.medianQALY,
                color: CATEGORY_COLORS[intervention.category] || "#6B7280",
              });
            }
          } catch (err) {
            console.warn(`Failed to load data for ${intervention.id}:`, err);
          }
        }

        // Sort by QALY gain (descending)
        personalizedResults.sort((a, b) => b.qalyGain - a.qalyGain);
        populationResults.sort((a, b) => b.qalyGain - a.qalyGain);

        setPersonalizedData(personalizedResults);
        setPopulationData(populationResults);
      } catch (err) {
        console.error("Error loading intervention comparison:", err);
        setError(err instanceof Error ? err.message : "Failed to load comparison data");
      } finally {
        setIsLoading(false);
      }
    }

    loadData();
  }, [profile]);

  const displayData = showPersonalized ? personalizedData : populationData;

  if (isLoading) {
    return (
      <Card className="mesh-gradient-card border-border/50">
        <CardContent className="p-6">
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="mesh-gradient-card border-border/50 border-destructive/50">
        <CardContent className="p-6">
          <div className="flex items-center gap-3 text-destructive">
            <Info className="h-5 w-5" />
            <p className="text-sm">{error}</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (displayData.length === 0) {
    return (
      <Card className="mesh-gradient-card border-border/50">
        <CardContent className="p-6">
          <p className="text-sm text-muted-foreground text-center">
            No intervention data available
          </p>
        </CardContent>
      </Card>
    );
  }

  // Custom tooltip
  const CustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload || !payload.length) return null;

    const data = payload[0].payload;
    return (
      <div className="bg-card border border-border rounded-lg p-3 shadow-lg">
        <p className="font-medium text-sm mb-1">{data.intervention}</p>
        <p className="text-xs text-muted-foreground mb-2 capitalize">
          Category: {data.category}
        </p>
        <p className="text-sm">
          <span className="font-medium">{data.qalyGain.toFixed(3)}</span> QALYs
        </p>
        <p className="text-xs text-muted-foreground">
          95% CI: [{data.ciLow.toFixed(3)}, {data.ciHigh.toFixed(3)}]
        </p>
      </div>
    );
  };

  return (
    <Card className="mesh-gradient-card border-border/50">
      <CardContent className="p-6 space-y-6">
        {/* Header */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold">Intervention Comparison</h3>

            {/* Toggle */}
            <div className="flex items-center gap-3">
              <span className={`text-sm ${!showPersonalized ? 'text-primary font-medium' : 'text-muted-foreground'}`}>
                Population Average
              </span>
              <button
                type="button"
                onClick={() => setShowPersonalized(!showPersonalized)}
                className={`relative w-12 h-6 rounded-full transition-colors ${
                  showPersonalized ? 'bg-primary' : 'bg-muted'
                }`}
              >
                <span
                  className={`absolute top-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                    showPersonalized ? 'translate-x-6' : 'translate-x-0.5'
                  }`}
                />
              </button>
              <span className={`text-sm ${showPersonalized ? 'text-primary font-medium' : 'text-muted-foreground'}`}>
                Personalized for You
              </span>
            </div>
          </div>

          <p className="text-sm text-muted-foreground">
            Estimated quality-adjusted life years (QALYs) gained from each intervention.
            Bars show mean estimates with 95% confidence intervals.
          </p>
        </div>

        {/* Chart */}
        <div className="w-full" style={{ height: 500 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={displayData}
              layout="vertical"
              margin={{ top: 5, right: 30, left: 120, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" opacity={0.3} />
              <XAxis
                type="number"
                domain={[0, 'auto']}
                label={{ value: 'QALYs Gained', position: 'insideBottom', offset: -5 }}
                tick={{ fontSize: 12 }}
              />
              <YAxis
                type="category"
                dataKey="shortName"
                width={110}
                tick={{ fontSize: 11 }}
              />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="qalyGain" radius={[0, 4, 4, 0]}>
                {displayData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Legend */}
        <div className="border-t border-border/50 pt-4">
          <p className="text-xs font-medium text-muted-foreground mb-3">Categories</p>
          <div className="flex flex-wrap gap-4">
            {Object.entries(CATEGORY_COLORS).map(([category, color]) => (
              <div key={category} className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded"
                  style={{ backgroundColor: color }}
                />
                <span className="text-xs text-muted-foreground capitalize">
                  {category}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Info box */}
        <div className="bg-muted/30 border border-border/50 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <Info className="h-5 w-5 text-primary flex-shrink-0 mt-0.5" />
            <div className="text-xs text-muted-foreground space-y-1">
              <p>
                <strong>Quality-Adjusted Life Years (QALYs)</strong> combine both
                longevity and quality of life improvements into a single metric.
              </p>
              <p>
                {showPersonalized ? (
                  <>
                    <strong>Personalized estimates</strong> are calculated based on your
                    specific profile (age, sex, BMI, health conditions, activity level).
                  </>
                ) : (
                  <>
                    <strong>Population averages</strong> show the median QALY gain across
                    all demographic profiles in our dataset.
                  </>
                )}
              </p>
              <p>
                Error bars represent 95% confidence intervals, reflecting uncertainty
                in the evidence.
              </p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
