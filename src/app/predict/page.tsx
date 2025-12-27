"use client";

import { useState, useEffect, useMemo, useCallback, useRef } from "react";
import Link from "next/link";
import { Activity, ChevronRight, Minus, Plus } from "lucide-react";
import {
  getPrecomputedBaseline,
  getMissingFields,
  type PartialProfile,
  type UncertainBaselineResult,
} from "@/lib/evidence/baseline";
import {
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ComposedChart,
} from "recharts";

// Debounce hook
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);
  useEffect(() => {
    const handler = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(handler);
  }, [value, delay]);
  return debouncedValue;
}

// Animated number component
function AnimatedNumber({ value, decimals = 1 }: { value: number; decimals?: number }) {
  const [displayed, setDisplayed] = useState(value);

  useEffect(() => {
    const diff = value - displayed;
    if (Math.abs(diff) < 0.1) {
      setDisplayed(value);
      return;
    }
    const step = diff * 0.15;
    const timer = requestAnimationFrame(() => {
      setDisplayed(prev => prev + step);
    });
    return () => cancelAnimationFrame(timer);
  }, [value, displayed]);

  return <>{displayed.toFixed(decimals)}</>;
}

// Arc gauge component for prediction range - shows ages, not remaining years
function PredictionArc({
  currentAge,
  lowAge,
  midAge,
  highAge,
  completeness
}: {
  currentAge: number;
  lowAge: number;
  midAge: number;
  highAge: number;
  completeness: number;
}) {
  const minAge = currentAge;
  const maxAge = 100;
  const ageRange = maxAge - minAge;
  const arcStart = 135;
  const arcEnd = 405;
  const arcRange = arcEnd - arcStart;

  const lowAngle = arcStart + ((lowAge - minAge) / ageRange) * arcRange;
  const midAngle = arcStart + ((midAge - minAge) / ageRange) * arcRange;
  const highAngle = arcStart + ((highAge - minAge) / ageRange) * arcRange;

  const polarToCartesian = (angle: number, radius: number) => {
    const rad = (angle - 90) * Math.PI / 180;
    return {
      x: 200 + radius * Math.cos(rad),
      y: 200 + radius * Math.sin(rad)
    };
  };

  const describeArc = (startAngle: number, endAngle: number, radius: number) => {
    const start = polarToCartesian(startAngle, radius);
    const end = polarToCartesian(endAngle, radius);
    const largeArc = endAngle - startAngle > 180 ? 1 : 0;
    return `M ${start.x} ${start.y} A ${radius} ${radius} 0 ${largeArc} 1 ${end.x} ${end.y}`;
  };

  const midPoint = polarToCartesian(midAngle, 140);

  return (
    <svg viewBox="0 0 400 280" className="w-full max-w-md mx-auto">
      {/* Background arc */}
      <path
        d={describeArc(arcStart, arcEnd, 160)}
        fill="none"
        stroke="hsl(var(--border))"
        strokeWidth="24"
        strokeLinecap="round"
        opacity="0.3"
      />

      {/* Uncertainty range arc */}
      <path
        d={describeArc(lowAngle, highAngle, 160)}
        fill="none"
        stroke="hsl(var(--primary))"
        strokeWidth="24"
        strokeLinecap="round"
        opacity="0.25"
        className="transition-all duration-700 ease-out"
      />

      {/* Progress arc based on completeness */}
      <path
        d={describeArc(arcStart, arcStart + (completeness * arcRange), 160)}
        fill="none"
        stroke="url(#arcGradient)"
        strokeWidth="4"
        strokeLinecap="round"
        className="transition-all duration-500"
      />

      {/* Median indicator */}
      <circle
        cx={midPoint.x}
        cy={midPoint.y}
        r="8"
        fill="hsl(var(--primary))"
        className="transition-all duration-700 ease-out"
      />
      <circle
        cx={midPoint.x}
        cy={midPoint.y}
        r="16"
        fill="hsl(var(--primary))"
        opacity="0.3"
        className="transition-all duration-700 ease-out"
      />

      {/* Gradient definition */}
      <defs>
        <linearGradient id="arcGradient" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="hsl(var(--primary))" />
          <stop offset="100%" stopColor="hsl(var(--coral))" />
        </linearGradient>
      </defs>

      {/* Scale markers - show ages */}
      {[0, 0.33, 0.67, 1].map((fraction, i) => {
        const age = Math.round(minAge + fraction * ageRange);
        const angle = arcStart + fraction * arcRange;
        const inner = polarToCartesian(angle, 145);
        const outer = polarToCartesian(angle, 175);
        const label = polarToCartesian(angle, 190);
        return (
          <g key={i} className="text-muted-foreground">
            <line
              x1={inner.x}
              y1={inner.y}
              x2={outer.x}
              y2={outer.y}
              stroke="currentColor"
              strokeWidth="1"
              opacity="0.3"
            />
            <text
              x={label.x}
              y={label.y}
              textAnchor="middle"
              dominantBaseline="middle"
              className="text-[10px] fill-current opacity-50"
            >
              {age}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// Life timeline visualization
function LifeTimeline({
  currentAge,
  predictedDeathAge,
}: {
  currentAge: number;
  predictedDeathAge: number;
}) {
  const startAge = currentAge;
  const endAge = 100;
  const range = endAge - startAge;

  return (
    <div className="relative h-20 w-full">
      {/* Timeline base */}
      <div className="absolute inset-x-0 top-1/2 h-1 bg-border/30 rounded-full" />

      {/* Life expectancy zone */}
      <div
        className="absolute top-1/2 h-1 bg-gradient-to-r from-primary/60 to-primary/20 rounded-full transition-all duration-700"
        style={{
          left: '0%',
          width: `${((predictedDeathAge - startAge) / range) * 100}%`,
          transform: 'translateY(-50%)'
        }}
      />

      {/* Current age marker */}
      <div className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-primary rounded-full shadow-lg shadow-primary/50" style={{ left: '0%' }} />

      {/* Predicted death age marker */}
      <div
        className="absolute top-1/2 -translate-y-1/2 transition-all duration-700"
        style={{ left: `${((predictedDeathAge - startAge) / range) * 100}%` }}
      >
        <div className="w-4 h-4 bg-coral rounded-full shadow-lg shadow-coral/50" />
      </div>

      {/* Age labels */}
      <div className="absolute -bottom-1 left-0 text-xs text-muted-foreground">{startAge}</div>
      <div
        className="absolute -bottom-1 text-xs text-muted-foreground transition-all duration-700"
        style={{ left: `${((predictedDeathAge - startAge) / range) * 100}%`, transform: 'translateX(-50%)' }}
      >
        {Math.round(predictedDeathAge)}
      </div>
      <div className="absolute -bottom-1 right-0 text-xs text-muted-foreground/50">100</div>

      {/* Labels */}
      <div className="absolute -top-1 left-0 text-[10px] text-primary font-medium">NOW</div>
      <div
        className="absolute -top-1 text-[10px] text-coral font-medium transition-all duration-700"
        style={{ left: `${((predictedDeathAge - startAge) / range) * 100}%`, transform: 'translateX(-50%)' }}
      >
        MEDIAN
      </div>
    </div>
  );
}

// Toggle button component
function ToggleButton({
  selected,
  onClick,
  children
}: {
  selected: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`
        px-4 py-2.5 rounded-lg text-sm font-medium transition-all duration-200
        ${selected
          ? 'bg-primary text-primary-foreground shadow-lg shadow-primary/25'
          : 'bg-card/50 text-muted-foreground hover:text-foreground hover:bg-card border border-border/50'
        }
      `}
    >
      {children}
    </button>
  );
}

// Condition toggle
function ConditionToggle({
  label,
  value,
  onChange
}: {
  label: string;
  value: boolean | undefined;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between py-2">
      <span className="text-sm text-muted-foreground">{label}</span>
      <div className="flex gap-1">
        <button
          onClick={() => onChange(false)}
          className={`
            w-8 h-8 rounded-lg flex items-center justify-center transition-all text-xs font-medium
            ${value === false
              ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
              : 'bg-card/50 text-muted-foreground hover:text-foreground border border-border/50'
            }
          `}
        >
          No
        </button>
        <button
          onClick={() => onChange(true)}
          className={`
            w-8 h-8 rounded-lg flex items-center justify-center transition-all text-xs font-medium
            ${value === true
              ? 'bg-red-500/20 text-red-400 border border-red-500/30'
              : 'bg-card/50 text-muted-foreground hover:text-foreground border border-border/50'
            }
          `}
        >
          Yes
        </button>
      </div>
    </div>
  );
}

// Number input with increment/decrement
function NumberStepper({
  value,
  onChange,
  min,
  max,
  step = 1,
  label,
  unit
}: {
  value: number | undefined;
  onChange: (v: number | undefined) => void;
  min: number;
  max: number;
  step?: number;
  label: string;
  unit?: string;
}) {
  return (
    <div className="flex items-center justify-between py-2">
      <span className="text-sm text-muted-foreground">{label}</span>
      <div className="flex items-center gap-2">
        <button
          onClick={() => onChange(Math.max(min, (value ?? min) - step))}
          className="w-8 h-8 rounded-lg bg-card/50 border border-border/50 flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-card transition-all"
        >
          <Minus className="w-3 h-3" />
        </button>
        <div className="w-16 text-center">
          <span className="text-sm font-medium">{value ?? '—'}</span>
          {unit && <span className="text-xs text-muted-foreground ml-1">{unit}</span>}
        </div>
        <button
          onClick={() => onChange(Math.min(max, (value ?? min) + step))}
          className="w-8 h-8 rounded-lg bg-card/50 border border-border/50 flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-card transition-all"
        >
          <Plus className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
}

export default function PredictPage() {
  const [profile, setProfile] = useState<PartialProfile>({ age: 35 });
  const [useImperial, setUseImperial] = useState(true);
  const [result, setResult] = useState<UncertainBaselineResult | null>(null);
  const [isClient, setIsClient] = useState(false);
  const [panelExpanded, setPanelExpanded] = useState(true);
  const [showStickyPrediction, setShowStickyPrediction] = useState(false);
  const predictionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setIsClient(true);
  }, []);

  const debouncedProfile = useDebounce(profile, 150);

  useEffect(() => {
    if (!isClient) return;
    if (!debouncedProfile.age || debouncedProfile.age < 18 || debouncedProfile.age > 100) {
      setResult(null);
      return;
    }
    getPrecomputedBaseline(debouncedProfile).then(setResult);
  }, [debouncedProfile, isClient]);

  // Track when main prediction scrolls out of view
  useEffect(() => {
    if (!predictionRef.current || !result) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        setShowStickyPrediction(!entry.isIntersecting);
      },
      { threshold: 0, rootMargin: "-80px 0px 0px 0px" }
    );

    observer.observe(predictionRef.current);
    return () => observer.disconnect();
  }, [result]);

  const missingFields = useMemo(
    () => getMissingFields(debouncedProfile),
    [debouncedProfile]
  );

  // Unit conversions
  const cmToFeetInches = (cm: number) => {
    const totalInches = cm / 2.54;
    return { feet: Math.floor(totalInches / 12), inches: Math.round(totalInches % 12) };
  };
  const feetInchesToCm = (feet: number, inches: number) => (feet * 12 + inches) * 2.54;
  const kgToLbs = (kg: number) => Math.round(kg * 2.20462);
  const lbsToKg = (lbs: number) => lbs / 2.20462;

  const updateField = useCallback(<K extends keyof PartialProfile>(key: K, value: PartialProfile[K]) => {
    setProfile((prev) => ({ ...prev, [key]: value }));
  }, []);

  const intervalDisplay = useMemo(() => {
    if (!result) return null;
    const { p5, p50, p95 } = result.predictionInterval.remainingLifeExpectancy;
    return { low: p5, mid: p50, high: p95 };
  }, [result]);

  // Chart data - survival probability by age
  const chartData = useMemo(() => {
    if (!result) return [];
    return result.survivalCurve.map((point) => ({
      age: point.age,
      survival: Math.round(point.qalyP50 * 100),
    }));
  }, [result]);

  const completenessPercent = result ? result.completeness : 0;
  const predictedDeathAge = intervalDisplay ? profile.age! + intervalDisplay.mid : profile.age! + 40;

  // Dynamic background color based on life expectancy
  const bgHue = intervalDisplay
    ? Math.min(180, 140 + (intervalDisplay.mid / 50) * 40)
    : 174;

  return (
    <div
      className="min-h-screen relative overflow-hidden transition-colors duration-1000"
      style={{
        background: `
          radial-gradient(ellipse at 30% 20%, hsla(${bgHue}, 70%, 50%, 0.12) 0%, transparent 50%),
          radial-gradient(ellipse at 70% 80%, hsla(12, 70%, 50%, 0.08) 0%, transparent 50%),
          hsl(220, 25%, 4%)
        `
      }}
    >
      {/* Subtle grid pattern */}
      <div
        className="fixed inset-0 pointer-events-none opacity-[0.02]"
        style={{
          backgroundImage: `
            linear-gradient(hsl(var(--foreground)) 1px, transparent 1px),
            linear-gradient(90deg, hsl(var(--foreground)) 1px, transparent 1px)
          `,
          backgroundSize: '60px 60px'
        }}
      />

      {/* Header - minimal */}
      <header className="fixed top-0 left-0 right-0 z-50 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 group">
            <Activity className="h-5 w-5 text-primary transition-transform group-hover:scale-110" />
            <span className="text-sm font-semibold tracking-wide uppercase opacity-60 group-hover:opacity-100 transition-opacity">
              Optiqal
            </span>
          </Link>
          <button
            onClick={() => setUseImperial(!useImperial)}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            {useImperial ? 'Metric' : 'Imperial'}
          </button>
        </div>
      </header>

      {/* Sticky prediction indicator */}
      {showStickyPrediction && intervalDisplay && (
        <div className="fixed top-14 left-0 right-0 z-40 px-6 py-2 bg-card/90 backdrop-blur-lg border-b border-border/30 animate-in slide-in-from-top-2 duration-200">
          <div className="max-w-7xl mx-auto flex items-center justify-center gap-4">
            <span className="text-sm text-muted-foreground">Life expectancy:</span>
            <span className="text-xl font-medium text-primary">
              {Math.round(profile.age! + intervalDisplay.mid)} years old
            </span>
            <span className="text-xs text-muted-foreground">
              ({Math.round(profile.age! + intervalDisplay.low)} - {Math.round(profile.age! + intervalDisplay.high)})
            </span>
          </div>
        </div>
      )}

      {/* Main content */}
      <main className="min-h-screen flex">
        {/* Left: Prediction visualization */}
        <div className={`flex-1 flex flex-col items-center justify-center p-8 transition-all duration-500 ${panelExpanded ? 'pr-[380px]' : 'pr-20'}`}>

          {/* Central prediction */}
          <div className="text-center space-y-4 max-w-lg">
            {/* Small label */}
            <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground">
              Life expectancy
            </p>

            {/* The big number - death age */}
            <div className="relative" ref={predictionRef}>
              <span
                className="text-[120px] md:text-[160px] lg:text-[200px] font-extralight tracking-tighter leading-none"
                style={{
                  background: 'linear-gradient(180deg, hsl(var(--foreground)) 0%, hsl(var(--muted-foreground)) 100%)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                }}
              >
                {isClient && intervalDisplay ? (
                  <AnimatedNumber value={profile.age! + intervalDisplay.mid} decimals={0} />
                ) : (
                  '—'
                )}
              </span>
              <span className="absolute bottom-8 right-0 translate-x-full text-lg text-muted-foreground font-light ml-2">
                years old
              </span>
            </div>

            {/* Arc gauge */}
            {isClient && intervalDisplay && (
              <div className="mt-[-40px]">
                <PredictionArc
                  currentAge={profile.age!}
                  lowAge={profile.age! + intervalDisplay.low}
                  midAge={profile.age! + intervalDisplay.mid}
                  highAge={profile.age! + intervalDisplay.high}
                  completeness={completenessPercent}
                />
              </div>
            )}

            {/* Range info - death ages */}
            {isClient && intervalDisplay && (
              <div className="flex items-center justify-center gap-6 text-sm">
                <div className="text-center">
                  <div className="text-muted-foreground text-xs uppercase tracking-wider mb-1">5th %ile</div>
                  <div className="font-medium">{Math.round(profile.age! + intervalDisplay.low)}</div>
                </div>
                <div className="w-px h-8 bg-border/50" />
                <div className="text-center">
                  <div className="text-primary text-xs uppercase tracking-wider mb-1">Median</div>
                  <div className="font-medium text-primary">{Math.round(profile.age! + intervalDisplay.mid)}</div>
                </div>
                <div className="w-px h-8 bg-border/50" />
                <div className="text-center">
                  <div className="text-muted-foreground text-xs uppercase tracking-wider mb-1">95th %ile</div>
                  <div className="font-medium">{Math.round(profile.age! + intervalDisplay.high)}</div>
                </div>
              </div>
            )}

            {/* Precision indicator */}
            {isClient && result && (
              <div className="pt-8 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Prediction precision</span>
                  <span className="text-primary font-medium">{Math.round(completenessPercent * 100)}%</span>
                </div>
                <div className="h-1 bg-border/30 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-primary to-primary/50 rounded-full transition-all duration-700"
                    style={{ width: `${completenessPercent * 100}%` }}
                  />
                </div>
                {missingFields.length > 0 && (
                  <p className="text-xs text-muted-foreground">
                    Add {missingFields[0].label.toLowerCase()} to improve by ~{missingFields[0].impactPercent}%
                  </p>
                )}
              </div>
            )}

            {/* Survival curve chart with integrated timeline */}
            {isClient && chartData.length > 0 && (
              <div className="pt-8 w-full max-w-2xl">
                <p className="text-xs uppercase tracking-wider text-muted-foreground mb-3 text-center">
                  Survival probability by age
                </p>
                <div className="h-40 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart
                      data={chartData}
                      margin={{ top: 5, right: 5, left: -20, bottom: 5 }}
                    >
                      <XAxis
                        dataKey="age"
                        tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                        axisLine={{ stroke: "hsl(var(--border))", strokeOpacity: 0.3 }}
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
                          fontSize: "11px",
                        }}
                        formatter={(value) => [`${value}%`, "Survival"]}
                        labelFormatter={(age) => `Age ${age}`}
                      />
                      <Line
                        type="monotone"
                        dataKey="survival"
                        stroke="hsl(var(--primary))"
                        strokeWidth={2}
                        dot={false}
                        isAnimationActive={false}
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
                {/* Timeline directly below chart - same width */}
                <div className="mt-4">
                  <LifeTimeline
                    currentAge={profile.age!}
                    predictedDeathAge={predictedDeathAge}
                  />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right: Profile panel */}
        <div
          className={`
            fixed right-0 top-0 bottom-0 w-[360px] bg-card/80 backdrop-blur-xl border-l border-border/50
            transition-transform duration-500 ease-out z-40
            ${panelExpanded ? 'translate-x-0' : 'translate-x-[calc(100%-48px)]'}
          `}
        >
          {/* Panel toggle */}
          <button
            onClick={() => setPanelExpanded(!panelExpanded)}
            className="absolute left-0 top-1/2 -translate-x-1/2 -translate-y-1/2 w-6 h-12 bg-card border border-border/50 rounded-l-lg flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors"
          >
            <ChevronRight className={`w-4 h-4 transition-transform duration-300 ${panelExpanded ? 'rotate-0' : 'rotate-180'}`} />
          </button>

          <div className="h-full overflow-y-auto p-6 pt-20">
            <div className="space-y-6">
              <div>
                <h2 className="text-lg font-medium mb-1">Your Profile</h2>
                <p className="text-xs text-muted-foreground">
                  More details = narrower prediction range
                </p>
              </div>

              {/* Age */}
              <div className="space-y-3">
                <label className="text-xs uppercase tracking-wider text-muted-foreground">Age</label>
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min={18}
                    max={85}
                    value={profile.age ?? 35}
                    onChange={(e) => updateField("age", parseInt(e.target.value))}
                    className="flex-1 h-1 bg-border/50 rounded-full appearance-none cursor-pointer
                      [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
                      [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer
                      [&::-webkit-slider-thumb]:shadow-lg [&::-webkit-slider-thumb]:shadow-primary/30"
                  />
                  <span className="w-12 text-right font-medium">{profile.age}</span>
                </div>
              </div>

              {/* Sex */}
              <div className="space-y-3">
                <label className="text-xs uppercase tracking-wider text-muted-foreground">Sex</label>
                <div className="grid grid-cols-2 gap-2">
                  <ToggleButton selected={profile.sex === 'male'} onClick={() => updateField('sex', 'male')}>
                    Male
                  </ToggleButton>
                  <ToggleButton selected={profile.sex === 'female'} onClick={() => updateField('sex', 'female')}>
                    Female
                  </ToggleButton>
                </div>
              </div>

              {/* Smoking */}
              <div className="space-y-3">
                <label className="text-xs uppercase tracking-wider text-muted-foreground">Smoking</label>
                <div className="grid grid-cols-2 gap-2">
                  <ToggleButton selected={profile.smoker === false} onClick={() => updateField('smoker', false)}>
                    Non-smoker
                  </ToggleButton>
                  <ToggleButton selected={profile.smoker === true} onClick={() => updateField('smoker', true)}>
                    Smoker
                  </ToggleButton>
                </div>
              </div>

              {/* Height & Weight */}
              <div className="space-y-3">
                <label className="text-xs uppercase tracking-wider text-muted-foreground">Body</label>
                {useImperial ? (
                  <div className="grid grid-cols-3 gap-2">
                    <input
                      type="number"
                      placeholder="ft"
                      value={profile.height ? cmToFeetInches(profile.height).feet : ''}
                      onChange={(e) => {
                        const feet = parseInt(e.target.value) || 0;
                        const currentInches = profile.height ? cmToFeetInches(profile.height).inches : 0;
                        if (feet > 0) updateField("height", feetInchesToCm(feet, currentInches));
                      }}
                      className="px-3 py-2.5 bg-card/50 border border-border/50 rounded-lg text-sm text-center focus:outline-none focus:border-primary/50"
                    />
                    <input
                      type="number"
                      placeholder="in"
                      value={profile.height ? cmToFeetInches(profile.height).inches : ''}
                      onChange={(e) => {
                        const inches = parseInt(e.target.value) || 0;
                        const currentFeet = profile.height ? cmToFeetInches(profile.height).feet : 5;
                        updateField("height", feetInchesToCm(currentFeet, inches));
                      }}
                      className="px-3 py-2.5 bg-card/50 border border-border/50 rounded-lg text-sm text-center focus:outline-none focus:border-primary/50"
                    />
                    <input
                      type="number"
                      placeholder="lbs"
                      value={profile.weight ? kgToLbs(profile.weight) : ''}
                      onChange={(e) => {
                        const lbs = parseInt(e.target.value) || 0;
                        if (lbs > 0) updateField("weight", lbsToKg(lbs));
                      }}
                      className="px-3 py-2.5 bg-card/50 border border-border/50 rounded-lg text-sm text-center focus:outline-none focus:border-primary/50"
                    />
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      type="number"
                      placeholder="cm"
                      value={profile.height ? Math.round(profile.height) : ''}
                      onChange={(e) => {
                        const cm = parseInt(e.target.value) || 0;
                        if (cm > 0) updateField("height", cm);
                      }}
                      className="px-3 py-2.5 bg-card/50 border border-border/50 rounded-lg text-sm text-center focus:outline-none focus:border-primary/50"
                    />
                    <input
                      type="number"
                      placeholder="kg"
                      value={profile.weight ? Math.round(profile.weight) : ''}
                      onChange={(e) => {
                        const kg = parseInt(e.target.value) || 0;
                        if (kg > 0) updateField("weight", kg);
                      }}
                      className="px-3 py-2.5 bg-card/50 border border-border/50 rounded-lg text-sm text-center focus:outline-none focus:border-primary/50"
                    />
                  </div>
                )}
              </div>

              {/* Exercise & Sleep */}
              <div className="space-y-3">
                <label className="text-xs uppercase tracking-wider text-muted-foreground">Lifestyle</label>
                <div className="space-y-1 divide-y divide-border/30">
                  <NumberStepper
                    value={profile.exerciseHoursPerWeek}
                    onChange={(v) => updateField('exerciseHoursPerWeek', v)}
                    min={0}
                    max={20}
                    step={1}
                    label="Exercise"
                    unit="hrs/wk"
                  />
                  <NumberStepper
                    value={profile.sleepHoursPerNight}
                    onChange={(v) => updateField('sleepHoursPerNight', v)}
                    min={4}
                    max={12}
                    step={0.5}
                    label="Sleep"
                    unit="hrs/night"
                  />
                </div>
              </div>

              {/* Conditions */}
              <div className="space-y-3">
                <label className="text-xs uppercase tracking-wider text-muted-foreground">Conditions</label>
                <div className="space-y-1 divide-y divide-border/30">
                  <ConditionToggle
                    label="Diabetes"
                    value={profile.hasDiabetes}
                    onChange={(v) => updateField('hasDiabetes', v)}
                  />
                  <ConditionToggle
                    label="Hypertension"
                    value={profile.hasHypertension}
                    onChange={(v) => updateField('hasHypertension', v)}
                  />
                </div>
              </div>

              {/* Disclaimer */}
              <p className="text-[10px] text-muted-foreground/60 pt-4">
                Statistical predictions based on peer-reviewed research. Not medical advice.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
