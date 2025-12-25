"use client";

import { useMemo, useState } from "react";
import type { UserProfile } from "@/types";
import {
  calculateBaselineQALYs,
  type BaselineProjection,
} from "@/lib/evidence/baseline";
import { Card, CardContent } from "@/components/ui/card";
import { Heart, Clock, TrendingUp, Info } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ReferenceLine,
  Area,
  AreaChart,
} from "recharts";

interface BaselineCardProps {
  profile: UserProfile;
}

function formatYears(years: number): string {
  if (years >= 1) {
    return `${years.toFixed(1)} years`;
  }
  const months = years * 12;
  if (months >= 1) {
    return `${months.toFixed(0)} months`;
  }
  const days = years * 365;
  return `${days.toFixed(0)} days`;
}

export function BaselineCard({ profile }: BaselineCardProps) {
  const projection = useMemo(
    () => calculateBaselineQALYs(profile),
    [profile]
  );

  // Calculate "improved" projection (e.g., optimal lifestyle)
  const improvedProjection = useMemo(() => {
    const improvedProfile: UserProfile = {
      ...profile,
      smoker: false,
      exerciseHoursPerWeek: Math.max(profile.exerciseHoursPerWeek, 3),
      sleepHoursPerNight: Math.min(Math.max(profile.sleepHoursPerNight, 7), 8),
    };
    return calculateBaselineQALYs(improvedProfile);
  }, [profile]);

  // Combine data for chart
  const chartData = useMemo(() => {
    const data: { age: number; current: number; improved: number; survival: number }[] = [];
    for (let i = 0; i < projection.survivalCurve.length; i++) {
      const current = projection.survivalCurve[i];
      const improved = improvedProjection.survivalCurve[i];
      data.push({
        age: current.age,
        current: Math.round(current.expectedQALY * 100),
        improved: Math.round((improved?.expectedQALY ?? current.expectedQALY) * 100),
        survival: Math.round(current.survivalProbability * 100),
      });
    }
    return data;
  }, [projection.survivalCurve, improvedProjection.survivalCurve]);

  const bmi = profile.weight / Math.pow(profile.height / 100, 2);
  const qalyGain = improvedProjection.remainingQALYs - projection.remainingQALYs;
  const [chartView, setChartView] = useState<"qaly" | "survival">("qaly");

  return (
    <Card className="mesh-gradient-card border-border/50 overflow-hidden">
      <CardContent className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent/10">
            <TrendingUp className="h-5 w-5 text-accent" />
          </div>
          <div>
            <h3 className="text-sm font-medium">Your Baseline Projection</h3>
            <p className="text-xs text-muted-foreground">
              Based on CDC life tables and GBD risk factors
            </p>
          </div>
        </div>

        {/* Main Stats */}
        <div className="grid grid-cols-3 gap-4">
          <div className="text-center p-4 bg-muted/20 rounded-xl border border-border/30">
            <Clock className="w-5 h-5 mx-auto mb-2 text-primary" />
            <p className="text-2xl font-semibold text-primary">
              {projection.remainingLifeExpectancy.toFixed(1)}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              years remaining
            </p>
          </div>
          <div className="text-center p-4 bg-muted/20 rounded-xl border border-border/30">
            <Heart className="w-5 h-5 mx-auto mb-2 text-accent" />
            <p className="text-2xl font-semibold text-accent">
              {projection.remainingQALYs.toFixed(1)}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              QALYs remaining
            </p>
          </div>
          <div className="text-center p-4 bg-muted/20 rounded-xl border border-border/30">
            <div className="w-5 h-5 mx-auto mb-2 text-muted-foreground font-mono text-sm">
              ~{Math.round(projection.expectedDeathAge)}
            </div>
            <p className="text-2xl font-semibold">
              {(projection.currentQualityWeight * 100).toFixed(0)}%
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              current quality
            </p>
          </div>
        </div>

        {/* Risk Factor Summary */}
        <div className="space-y-2">
          <p className="text-xs uppercase tracking-wider text-muted-foreground">
            Your Risk Profile
          </p>
          <div className="flex flex-wrap gap-2">
            <RiskBadge
              label={`BMI ${bmi.toFixed(1)}`}
              status={bmi < 25 ? "good" : bmi < 30 ? "warning" : "bad"}
            />
            <RiskBadge
              label={`${profile.exerciseHoursPerWeek}h exercise/wk`}
              status={
                profile.exerciseHoursPerWeek >= 2.5
                  ? "good"
                  : profile.exerciseHoursPerWeek > 0
                    ? "warning"
                    : "bad"
              }
            />
            <RiskBadge
              label={`${profile.sleepHoursPerNight}h sleep`}
              status={
                profile.sleepHoursPerNight >= 6 &&
                profile.sleepHoursPerNight <= 9
                  ? "good"
                  : "warning"
              }
            />
            {profile.smoker && <RiskBadge label="Smoker" status="bad" />}
          </div>
        </div>

        {/* Survival & QALY Curve */}
        <div className="space-y-3">
          {/* Tab Selector */}
          <div className="flex items-center justify-between">
            <div className="flex gap-1 p-1 bg-muted/30 rounded-lg">
              <button
                onClick={() => setChartView("qaly")}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  chartView === "qaly"
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                Expected QALYs
              </button>
              <button
                onClick={() => setChartView("survival")}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  chartView === "survival"
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                Survival Probability
              </button>
            </div>
            {chartView === "qaly" && qalyGain > 0.1 && (
              <span className="text-xs text-emerald-400">
                +{qalyGain.toFixed(1)} QALYs with optimal lifestyle
              </span>
            )}
          </div>

          <div className="h-48 w-full">
            <ResponsiveContainer width="100%" height="100%">
              {chartView === "qaly" ? (
                <LineChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                  <XAxis
                    dataKey="age"
                    tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                    axisLine={{ stroke: "hsl(var(--border))" }}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                    axisLine={false}
                    tickLine={false}
                    domain={[0, 100]}
                    tickFormatter={(v) => `${v}%`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "8px",
                      fontSize: "12px",
                    }}
                    formatter={(value: number, name: string) => [
                      `${value}%`,
                      name === "current" ? "Current lifestyle" :
                      name === "improved" ? "Optimal lifestyle" : "Survival"
                    ]}
                    labelFormatter={(age) => `Age ${age}`}
                  />
                  <Legend
                    wrapperStyle={{ fontSize: "10px" }}
                    formatter={(value) =>
                      value === "current" ? "Current" :
                      value === "improved" ? "Optimal" : "Survival"
                    }
                  />
                  <ReferenceLine
                    x={Math.round(projection.expectedDeathAge)}
                    stroke="hsl(var(--muted-foreground))"
                    strokeDasharray="3 3"
                    label={{ value: "Expected", fontSize: 9, fill: "hsl(var(--muted-foreground))" }}
                  />
                  <Line
                    type="monotone"
                    dataKey="current"
                    stroke="hsl(var(--accent))"
                    strokeWidth={2}
                    dot={false}
                    name="current"
                  />
                  {qalyGain > 0.1 && (
                    <Line
                      type="monotone"
                      dataKey="improved"
                      stroke="hsl(var(--primary))"
                      strokeWidth={2}
                      strokeDasharray="5 5"
                      dot={false}
                      name="improved"
                    />
                  )}
                </LineChart>
              ) : (
                <AreaChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                  <defs>
                    <linearGradient id="survivalGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis
                    dataKey="age"
                    tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                    axisLine={{ stroke: "hsl(var(--border))" }}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                    axisLine={false}
                    tickLine={false}
                    domain={[0, 100]}
                    tickFormatter={(v) => `${v}%`}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "8px",
                      fontSize: "12px",
                    }}
                    formatter={(value: number) => [`${value}%`, "Survival probability"]}
                    labelFormatter={(age) => `Age ${age}`}
                  />
                  <ReferenceLine
                    x={Math.round(projection.expectedDeathAge)}
                    stroke="hsl(var(--muted-foreground))"
                    strokeDasharray="3 3"
                    label={{ value: "50%", fontSize: 9, fill: "hsl(var(--muted-foreground))" }}
                  />
                  <Area
                    type="monotone"
                    dataKey="survival"
                    stroke="hsl(var(--primary))"
                    strokeWidth={2}
                    fill="url(#survivalGradient)"
                  />
                </AreaChart>
              )}
            </ResponsiveContainer>
          </div>
          <p className="text-xs text-muted-foreground text-center">
            {chartView === "qaly"
              ? "Expected QALY rate = P(alive) × Quality of life"
              : "Probability of being alive at each age based on life tables and risk factors"}
          </p>
        </div>

        {/* Source note */}
        <div className="flex items-start gap-2 text-xs text-muted-foreground bg-muted/20 rounded-lg p-3">
          <Info className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          <p>
            Based on CDC 2022 Life Tables, GBD 2019 disability weights, and
            risk factor meta-analyses. Individual outcomes vary significantly.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

function RiskBadge({
  label,
  status,
}: {
  label: string;
  status: "good" | "warning" | "bad";
}) {
  const styles = {
    good: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
    warning: "bg-amber-500/10 text-amber-400 border-amber-500/30",
    bad: "bg-red-500/10 text-red-400 border-red-500/30",
  };

  return (
    <span
      className={`inline-flex items-center px-2.5 py-1 text-xs rounded-full border ${styles[status]}`}
    >
      {label}
    </span>
  );
}
