"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import Link from "next/link";
import { Activity, ArrowRight, Check, ChevronDown, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { FEATURES, getLabels } from "@/lib/config";
import {
  getPrecomputedBaseline,
  getMissingFields,
  type PartialProfile,
  type UncertainBaselineResult,
} from "@/lib/evidence/baseline";
import {
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ComposedChart,
} from "recharts";

// Debounce hook for smooth updates
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => clearTimeout(handler);
  }, [value, delay]);

  return debouncedValue;
}

export default function PredictPage() {
  // Partial profile - starts with just age
  const [profile, setProfile] = useState<PartialProfile>({ age: 35 });
  const [useImperial, setUseImperial] = useState(true);
  const [result, setResult] = useState<UncertainBaselineResult | null>(null);
  const [isClient, setIsClient] = useState(false);
  const labels = getLabels();

  // Mark as client-side after hydration
  useEffect(() => {
    setIsClient(true);
  }, []);

  // Debounce profile changes for smoother chart updates
  const debouncedProfile = useDebounce(profile, 150);

  // Calculate prediction with uncertainty (client-side only to avoid hydration mismatch)
  useEffect(() => {
    if (!isClient) return;
    if (!debouncedProfile.age || debouncedProfile.age < 18 || debouncedProfile.age > 100) {
      setResult(null);
      return;
    }
    // Load from precomputed Python Markov model
    getPrecomputedBaseline(debouncedProfile).then(setResult);
  }, [debouncedProfile, isClient]);

  // Missing fields for suggestions
  const missingFields = useMemo(
    () => getMissingFields(debouncedProfile),
    [debouncedProfile]
  );

  // Unit conversion helpers
  const cmToFeetInches = (cm: number) => {
    const totalInches = cm / 2.54;
    const feet = Math.floor(totalInches / 12);
    const inches = Math.round(totalInches % 12);
    return { feet, inches };
  };

  const feetInchesToCm = (feet: number, inches: number) => {
    return (feet * 12 + inches) * 2.54;
  };

  const kgToLbs = (kg: number) => Math.round(kg * 2.20462);
  const lbsToKg = (lbs: number) => lbs / 2.20462;

  // Update profile field
  const updateField = useCallback(<K extends keyof PartialProfile>(
    key: K,
    value: PartialProfile[K]
  ) => {
    setProfile((prev) => ({ ...prev, [key]: value }));
  }, []);

  // Chart data with uncertainty bands
  // For proper area band rendering, we need base and range values
  const chartData = useMemo(() => {
    if (!result) return [];

    return result.survivalCurve.map((point) => ({
      age: point.age,
      qalyMid: Math.round(point.qalyP50 * 100),
      qalyLow: Math.round(point.qalyP5 * 100),
      qalyHigh: Math.round(point.qalyP95 * 100),
      // Range for the band (high - low)
      qalyRange: Math.round((point.qalyP95 - point.qalyP5) * 100),
    }));
  }, [result]);

  // Interval width for display
  const intervalDisplay = useMemo(() => {
    if (!result) return null;

    const { p5, p50, p95 } = result.predictionInterval.remainingQALYs;
    return {
      low: p5.toFixed(1),
      mid: p50.toFixed(1),
      high: p95.toFixed(1),
      width: (p95 - p5).toFixed(1),
    };
  }, [result]);

  // Completeness percentage
  const completenessPercent = result ? Math.round(result.completeness * 100) : 0;

  return (
    <div className="min-h-screen mesh-gradient relative">
      <div className="noise-overlay fixed inset-0 pointer-events-none" />

      {/* Header */}
      <header className="sticky top-0 z-50 glass border-b border-border/30">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5 group">
            <Activity className="h-6 w-6 text-primary transition-transform group-hover:scale-110" />
            <span className="text-lg font-semibold tracking-tight">optiqal</span>
          </Link>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8 md:py-12">
        <div className="grid lg:grid-cols-[1fr,380px] gap-8 lg:gap-12">
          {/* Left: Chart and main prediction */}
          <div className="space-y-6">
            {/* Title */}
            <div className="space-y-2">
              <h1 className="font-serif text-3xl md:text-4xl font-medium">
                Your life expectancy
              </h1>
              <p className="text-muted-foreground">
                Add details to narrow your prediction interval
              </p>
            </div>

            {/* Main prediction display */}
            {!isClient ? (
              <div className="p-6 rounded-2xl bg-card/50 border border-border/50 space-y-4 animate-pulse">
                <div className="h-14 w-48 bg-muted/30 rounded" />
                <div className="h-4 w-64 bg-muted/20 rounded" />
                <div className="h-2 w-full bg-muted/20 rounded" />
              </div>
            ) : result && intervalDisplay ? (
              <div className="p-6 rounded-2xl bg-card/50 border border-border/50 space-y-4">
                <div className="flex items-baseline gap-3">
                  <span className="text-5xl md:text-6xl font-serif font-semibold gradient-text">
                    {intervalDisplay.mid}
                  </span>
                  <span className="text-xl text-muted-foreground">
                    {labels.shortUnit} remaining
                  </span>
                </div>

                <div className="flex items-center gap-4 text-sm">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-primary/30" />
                    <span className="text-muted-foreground">
                      Prediction range: {intervalDisplay.low} – {intervalDisplay.high}
                    </span>
                  </div>
                  <div className="text-muted-foreground">
                    (±{(parseFloat(intervalDisplay.width) / 2).toFixed(1)} years)
                  </div>
                </div>

                {/* Precision meter */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground">Prediction precision</span>
                    <span className="font-medium">{completenessPercent}%</span>
                  </div>
                  <div className="h-2 bg-muted/30 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-primary to-accent rounded-full transition-all duration-500 ease-out"
                      style={{ width: `${completenessPercent}%` }}
                    />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {completenessPercent < 50
                      ? "Add more details below to narrow your prediction interval"
                      : completenessPercent < 80
                        ? "Good precision — a few more details would help"
                        : "Great! Your prediction is well-calibrated"}
                  </p>
                </div>
              </div>
            ) : null}

            {/* Chart */}
            <div className="p-6 rounded-2xl bg-card/50 border border-border/50">
              <h3 className="text-sm font-medium mb-4">Survival probability by age</h3>
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart
                    data={chartData}
                    margin={{ top: 10, right: 10, left: -15, bottom: 5 }}
                  >
                    <defs>
                      <linearGradient id="uncertaintyGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.4} />
                        <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0.15} />
                      </linearGradient>
                    </defs>
                    <XAxis
                      dataKey="age"
                      tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                      axisLine={{ stroke: "hsl(var(--border))" }}
                      tickLine={false}
                    />
                    <YAxis
                      tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
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
                      formatter={(value, name) => [
                        `${value}%`,
                        name === "qalyMid"
                          ? "Expected"
                          : name === "qalyHigh"
                            ? "Upper bound"
                            : "Lower bound",
                      ]}
                      labelFormatter={(age) => `Age ${age}`}
                    />
                    {/* Confidence band: stacked areas */}
                    {/* Base (invisible) - the low bound */}
                    <Area
                      type="monotone"
                      dataKey="qalyLow"
                      stackId="band"
                      stroke="none"
                      fill="transparent"
                      isAnimationActive={false}
                    />
                    {/* The visible band (range from low to high) */}
                    <Area
                      type="monotone"
                      dataKey="qalyRange"
                      stackId="band"
                      stroke="none"
                      fill="url(#uncertaintyGradient)"
                      isAnimationActive={false}
                    />
                    {/* Median line on top */}
                    <Line
                      type="monotone"
                      dataKey="qalyMid"
                      stroke="#3ee0cf"
                      strokeWidth={2}
                      dot={false}
                      isAnimationActive={false}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
              <p className="text-xs text-muted-foreground text-center mt-3">
                Shaded area shows 90% prediction interval — narrower = more certain
              </p>
            </div>

            {/* Next steps suggestion */}
            {missingFields.length > 0 && (
              <div className="p-4 rounded-xl bg-primary/5 border border-primary/20">
                <div className="flex items-start gap-3">
                  <Sparkles className="w-5 h-5 text-primary shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <p className="text-sm font-medium">
                      Add {missingFields[0].label.toLowerCase()} to narrow by ~{missingFields[0].impactPercent}%
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {missingFields.slice(0, 3).map((f) => f.label).join(", ")}{" "}
                      have the biggest impact on precision
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Right: Profile inputs */}
          <div className="space-y-6">
            <div className="sticky top-24 space-y-6">
              <div className="p-6 rounded-2xl bg-card/50 border border-border/50 space-y-6">
                <div className="flex items-center justify-between">
                  <h3 className="font-medium">Your profile</h3>
                  <button
                    onClick={() => setUseImperial(!useImperial)}
                    className="text-xs text-muted-foreground hover:text-foreground"
                  >
                    {useImperial ? "Use metric" : "Use imperial"}
                  </button>
                </div>

                {/* Age */}
                <div className="space-y-2">
                  <Label htmlFor="age">Age</Label>
                  <Input
                    id="age"
                    type="number"
                    min={18}
                    max={100}
                    value={profile.age}
                    onChange={(e) =>
                      updateField("age", parseInt(e.target.value) || 18)
                    }
                    className="text-lg"
                  />
                </div>

                {/* Sex */}
                <div className="space-y-2">
                  <Label>Sex</Label>
                  <div className="grid grid-cols-2 gap-2">
                    {(["male", "female"] as const).map((sex) => (
                      <button
                        key={sex}
                        onClick={() => updateField("sex", sex)}
                        className={`px-4 py-2 rounded-lg border text-sm font-medium transition-all ${
                          profile.sex === sex
                            ? "bg-primary text-primary-foreground border-primary"
                            : "border-border/50 hover:bg-muted/30"
                        }`}
                      >
                        {sex === "male" ? "Male" : "Female"}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Smoking */}
                <div className="space-y-2">
                  <Label>Do you smoke?</Label>
                  <div className="grid grid-cols-2 gap-2">
                    {([false, true] as const).map((smoker) => (
                      <button
                        key={String(smoker)}
                        onClick={() => updateField("smoker", smoker)}
                        className={`px-4 py-2 rounded-lg border text-sm font-medium transition-all ${
                          profile.smoker === smoker
                            ? "bg-primary text-primary-foreground border-primary"
                            : "border-border/50 hover:bg-muted/30"
                        }`}
                      >
                        {smoker ? "Yes" : "No"}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Height & Weight */}
                <div className="space-y-2">
                  <Label>Height & weight</Label>
                  {useImperial ? (
                    <div className="grid grid-cols-3 gap-2">
                      <Input
                        type="number"
                        placeholder="ft"
                        value={
                          profile.height
                            ? cmToFeetInches(profile.height).feet
                            : ""
                        }
                        onChange={(e) => {
                          const feet = parseInt(e.target.value) || 0;
                          const currentInches = profile.height
                            ? cmToFeetInches(profile.height).inches
                            : 0;
                          if (feet > 0) {
                            updateField("height", feetInchesToCm(feet, currentInches));
                          }
                        }}
                      />
                      <Input
                        type="number"
                        placeholder="in"
                        value={
                          profile.height
                            ? cmToFeetInches(profile.height).inches
                            : ""
                        }
                        onChange={(e) => {
                          const inches = parseInt(e.target.value) || 0;
                          const currentFeet = profile.height
                            ? cmToFeetInches(profile.height).feet
                            : 5;
                          updateField("height", feetInchesToCm(currentFeet, inches));
                        }}
                      />
                      <Input
                        type="number"
                        placeholder="lbs"
                        value={profile.weight ? kgToLbs(profile.weight) : ""}
                        onChange={(e) => {
                          const lbs = parseInt(e.target.value) || 0;
                          if (lbs > 0) {
                            updateField("weight", lbsToKg(lbs));
                          }
                        }}
                      />
                    </div>
                  ) : (
                    <div className="grid grid-cols-2 gap-2">
                      <Input
                        type="number"
                        placeholder="cm"
                        value={profile.height ? Math.round(profile.height) : ""}
                        onChange={(e) => {
                          const cm = parseInt(e.target.value) || 0;
                          if (cm > 0) updateField("height", cm);
                        }}
                      />
                      <Input
                        type="number"
                        placeholder="kg"
                        value={profile.weight ? Math.round(profile.weight) : ""}
                        onChange={(e) => {
                          const kg = parseInt(e.target.value) || 0;
                          if (kg > 0) updateField("weight", kg);
                        }}
                      />
                    </div>
                  )}
                </div>

                {/* Exercise */}
                <div className="space-y-2">
                  <Label htmlFor="exercise">Exercise (hours/week)</Label>
                  <Input
                    id="exercise"
                    type="number"
                    min={0}
                    max={30}
                    step={0.5}
                    placeholder="e.g., 3"
                    value={profile.exerciseHoursPerWeek ?? ""}
                    onChange={(e) => {
                      const val = parseFloat(e.target.value);
                      updateField(
                        "exerciseHoursPerWeek",
                        isNaN(val) ? undefined : val
                      );
                    }}
                  />
                </div>

                {/* Sleep */}
                <div className="space-y-2">
                  <Label htmlFor="sleep">Sleep (hours/night)</Label>
                  <Input
                    id="sleep"
                    type="number"
                    min={3}
                    max={12}
                    step={0.5}
                    placeholder="e.g., 7"
                    value={profile.sleepHoursPerNight ?? ""}
                    onChange={(e) => {
                      const val = parseFloat(e.target.value);
                      updateField(
                        "sleepHoursPerNight",
                        isNaN(val) ? undefined : val
                      );
                    }}
                  />
                </div>

                {/* Health conditions */}
                <div className="space-y-3">
                  <Label>Health conditions</Label>
                  <div className="space-y-2">
                    {[
                      { key: "hasDiabetes" as const, label: "Diabetes" },
                      { key: "hasHypertension" as const, label: "Hypertension" },
                    ].map(({ key, label }) => (
                      <button
                        key={key}
                        onClick={() =>
                          updateField(key, profile[key] === undefined ? false : !profile[key])
                        }
                        className={`w-full flex items-center justify-between px-4 py-2 rounded-lg border text-sm transition-all ${
                          profile[key] !== undefined
                            ? profile[key]
                              ? "bg-red-500/10 border-red-500/30 text-red-400"
                              : "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                            : "border-border/50 hover:bg-muted/30 text-muted-foreground"
                        }`}
                      >
                        <span>{label}</span>
                        {profile[key] !== undefined && (
                          <span className="text-xs">
                            {profile[key] ? "Yes" : "No"}
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Disclaimer */}
              <p className="text-xs text-muted-foreground text-center">
                Statistical predictions based on peer-reviewed research.
                Not medical advice.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
