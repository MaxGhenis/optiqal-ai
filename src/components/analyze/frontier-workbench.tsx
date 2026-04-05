"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Activity, ArrowLeft, ChevronDown, ChevronUp, Loader2 } from "lucide-react";
import { LogoLockup } from "@/components/brand/logo";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { DEFAULT_PROFILE, type UserProfile } from "@/types";
import { useLatestRequest } from "@/hooks/use-latest-request";
import type {
  FrontierItem,
  FrontierRequest,
  FrontierResponse,
  FrontierSleepInput,
} from "@/lib/frontier-types";

const STORAGE_KEY = "optiqal-frontier-profile-v1";
const SLEEP_STORAGE_KEY = "optiqal-frontier-sleep-v1";

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});
const timeFormatter = new Intl.DateTimeFormat("en-US", {
  hour: "numeric",
  minute: "2-digit",
  second: "2-digit",
});

function formatCurrency(value: number | null): string {
  if (value === null) return "n/a";
  if (value === 0) return "$0";
  return currency.format(value);
}

function formatCostPerQaly(
  value: number | null,
  pricingStatus?: FrontierItem["pricing_status"]
): string {
  if (value === null) {
    if (pricingStatus === "unpriced") return "Unpriced";
    return "Bundled / free";
  }
  return `${currency.format(value)}/QALY`;
}

function formatProbability(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function formatRunTime(timestamp: number | null): string {
  if (timestamp === null) {
    return "No completed run yet.";
  }
  return `Last updated ${timeFormatter.format(timestamp)}.`;
}

function hasMeaningfulSleepBurden(results: FrontierResponse | null): boolean {
  if (!results?.sleep_estimate) return false;
  if (results.sleep_estimate.annual_qaly_loss > 0.00005) return true;
  return Object.values(results.sleep_estimate.component_losses).some((value) => value > 0.00005);
}

function humanizeCategory(value: string): string {
  return value.replaceAll("_", " ");
}

function humanizeAccessTier(value: string): string {
  switch (value) {
    case "brand_rx_prior_auth":
      return "Brand Rx + PA";
    case "generic_rx":
      return "Generic Rx";
    case "dme_rx":
      return "Rx + DME";
    case "specialist_device":
      return "Specialist device";
    default:
      return humanizeCategory(value);
  }
}

function humanizeCoverage(value: string): string {
  switch (value) {
    case "na":
      return "No coverage needed";
    case "likely":
      return "Likely covered";
    case "mixed":
      return "Coverage mixed";
    case "unlikely":
      return "Coverage unlikely";
    default:
      return value;
  }
}

const ADVANCED_SLEEP_FIELDS: Array<{
  key: keyof FrontierSleepInput;
  label: string;
}> = [
  { key: "sleep_quality_score", label: "Sleep quality" },
  { key: "waso_min", label: "WASO min" },
  { key: "routine_score", label: "Routine score" },
  { key: "recovery_score", label: "Recovery score" },
  { key: "breathing_score", label: "Breathing score" },
  { key: "spo2", label: "SpO2" },
  { key: "snore_pct", label: "Snore %" },
  { key: "airway_response_signal", label: "Airway response" },
];

function findOptionLabel(
  options: Array<{ id: string; label: string }>,
  optionId: string | null
): string {
  return options.find((option) => option.id === optionId)?.label ?? "None";
}

function describeSequenceTargets(
  step: FrontierResponse["decision_sequence"][number],
  stateLabels: Map<string, string>
): string | null {
  if (step.state_id) {
    return stateLabels.get(step.state_id) ?? null;
  }

  const parts: string[] = [];
  if (step.preferred_state_id) {
    parts.push(`Preferred: ${stateLabels.get(step.preferred_state_id) ?? step.preferred_state_id}`);
  }
  if (step.alternative_state_id) {
    parts.push(`Alternative: ${stateLabels.get(step.alternative_state_id) ?? step.alternative_state_id}`);
  }
  return parts.length > 0 ? parts.join(" · ") : null;
}

function humanizePublicLane(value: FrontierItem["public_lane"]): string {
  switch (value) {
    case "consumer_public":
      return "Broad public";
    case "conditional_public":
      return "Conditional";
    case "personal_only":
      return "Personal only";
    default:
      return value;
  }
}

function buildSleepPayload(
  profile: UserProfile,
  sleep: FrontierSleepInput
): FrontierRequest["sleep_metrics"] {
  const payload: FrontierSleepInput = {
    duration_hours: sleep.duration_hours ?? profile.sleepHoursPerNight,
    recovery_score: sleep.recovery_score ?? null,
    sleep_quality_score: sleep.sleep_quality_score ?? null,
    waso_min: sleep.waso_min ?? null,
    routine_score: sleep.routine_score ?? null,
    social_jetlag_min: sleep.social_jetlag_min ?? null,
    latency_min: sleep.latency_min ?? null,
    breathing_score: sleep.breathing_score ?? null,
    spo2: sleep.spo2 ?? null,
    snore_pct: sleep.snore_pct ?? null,
    sleep_debt_min: sleep.sleep_debt_min ?? null,
    airway_response_signal: sleep.airway_response_signal ?? null,
  };

  return Object.values(payload).some((value) => value !== null && value !== undefined)
    ? payload
    : undefined;
}

function toRequest(profile: UserProfile, sleep: FrontierSleepInput): FrontierRequest {
  return {
    profile: {
      age: profile.age,
      sex: profile.sex,
      weight_kg: profile.weight,
      height_cm: profile.height,
      smoker: profile.smoker,
      has_diabetes: profile.hasDiabetes,
      has_hypertension: profile.hasHypertension,
      activity_level: profile.activityLevel,
      sleep_hours_per_night: profile.sleepHoursPerNight,
    },
    sleep_metrics: buildSleepPayload(profile, sleep),
    n_simulations: 5000,
  };
}

function loadStoredJson<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

export function FrontierWorkbench() {
  const [profile, setProfile] = useState<UserProfile>(DEFAULT_PROFILE);
  const [sleepInputs, setSleepInputs] = useState<FrontierSleepInput>({});
  const [results, setResults] = useState<FrontierResponse | null>(null);
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAdvancedSleep, setShowAdvancedSleep] = useState(false);
  const [showNegatives, setShowNegatives] = useState(false);
  const [requestStatus, setRequestStatus] = useState<string | null>(null);
  const [lastCompletedAt, setLastCompletedAt] = useState<number | null>(null);
  const latestRequest = useLatestRequest();

  useEffect(() => {
    const storedProfile = loadStoredJson<UserProfile>(STORAGE_KEY);
    const storedSleep = loadStoredJson<FrontierSleepInput>(SLEEP_STORAGE_KEY);
    if (storedProfile) {
      setProfile(storedProfile);
    }
    if (storedSleep) {
      setSleepInputs(storedSleep);
    }
  }, []);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
  }, [profile]);

  useEffect(() => {
    localStorage.setItem(SLEEP_STORAGE_KEY, JSON.stringify(sleepInputs));
  }, [sleepInputs]);

  const visibleItems = useMemo(() => {
    if (!results) return [];
    return showNegatives
      ? results.items
      : results.items.filter((item) => item.total_qaly > 0);
  }, [results, showNegatives]);

  const selectedItem = useMemo<FrontierItem | null>(() => {
    if (!results || !selectedItemId) return null;
    return results.items.find((item) => item.id === selectedItemId) ?? null;
  }, [results, selectedItemId]);

  const decisionStateLabels = useMemo(() => {
    const labels = new Map<string, string>();
    if (!results) return labels;
    for (const state of results.decision_states) {
      labels.set(state.id, state.label);
    }
    return labels;
  }, [results]);

  const publicPolicyItemsById = useMemo(() => {
    const items = new Map<string, string>();
    if (!results) return items;
    for (const item of results.public_policy.items) {
      items.set(item.id, item.name);
    }
    return items;
  }, [results]);

  const publicPolicyConditionsById = useMemo(() => {
    const conditions = new Map<string, { label: string; description: string }>();
    if (!results) return conditions;
    for (const condition of results.public_policy.conditions) {
      conditions.set(condition.id, {
        label: condition.label,
        description: condition.description,
      });
    }
    return conditions;
  }, [results]);

  const updateProfile = (key: keyof UserProfile, value: UserProfile[keyof UserProfile]) => {
    setProfile((prev) => ({ ...prev, [key]: value }));
  };

  const updateSleep = (key: keyof FrontierSleepInput, value: number | null) => {
    setSleepInputs((prev) => ({ ...prev, [key]: value }));
  };

  const runAnalysis = async () => {
    const { requestId, controller, supersededPrevious } = latestRequest.beginRequest();

    setLoading(true);
    setError(null);
    setRequestStatus(
      supersededPrevious
        ? "Previous request cancelled. Running latest analysis."
        : "Running live analysis."
    );

    try {
      const response = await fetch("/api/frontier", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(toRequest(profile, sleepInputs)),
        signal: controller.signal,
      });

      const data = (await response.json()) as FrontierResponse | { error: string };
      if (!response.ok || "error" in data) {
        throw new Error("error" in data ? data.error : "Failed to load frontier");
      }

      if (!latestRequest.isCurrentRequest(requestId)) {
        return;
      }
      setResults(data);
      setSelectedItemId(data.frontier[0]?.added_intervention ?? data.items[0]?.id ?? null);
      setLastCompletedAt(Date.now());
      setRequestStatus("Live analysis complete.");
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        return;
      }
      if (!latestRequest.isCurrentRequest(requestId)) {
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to load frontier");
      setResults(null);
      setSelectedItemId(null);
      setRequestStatus(null);
    } finally {
      if (latestRequest.finishRequest(requestId)) {
        setLoading(false);
      }
    }
  };

  const bestFrontierStep = results?.frontier[0] ?? null;
  const showSleepBurden = hasMeaningfulSleepBurden(results);
  const sleepEstimate = showSleepBurden ? results?.sleep_estimate ?? null : null;

  return (
    <div className="min-h-screen mesh-gradient paper-grid relative">
      <div className="noise-overlay fixed inset-0 pointer-events-none" />

      <header className="sticky top-0 z-50 glass border-b border-border/30">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5 group">
            <LogoLockup
              size="sm"
              showDescriptor={false}
              markClassName="transition-transform group-hover:scale-[1.04]"
            />
          </Link>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back
            </Link>
          </Button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-12 space-y-8">
        <div className="grid lg:grid-cols-[0.95fr_1.05fr] gap-6 items-start">
          <div className="space-y-5">
            <div className="section-chip">
              <Activity className="h-4 w-4" />
              Unified catalog frontier
            </div>
            <div className="space-y-3">
              <h1 className="font-serif text-4xl md:text-5xl font-semibold tracking-[-0.04em] leading-[1.02]">
                Rank interventions by marginal $/QALY
              </h1>
              <p className="text-lg text-muted-foreground max-w-2xl leading-relaxed">
                This page now calls the live Python engine. No baked-in threshold.
                It returns an ordered frontier, per-item harm/benefit probabilities,
                transport multipliers, and evidence notes.
              </p>
            </div>
          </div>

          <Card className="decision-card border-primary/15">
            <CardContent className="p-6 space-y-4">
              <p className="text-xs uppercase tracking-[0.22em] text-primary">
                What this replaces
              </p>
              <div className="space-y-3">
                {[
                  "No more precomputed 10-intervention toy set",
                  "No more hidden threshold in the portfolio logic",
                  "Live Monte Carlo over the full catalog",
                  "Sleep burden can feed directly into ranking",
                ].map((item) => (
                  <div
                    key={item}
                    className="surface-panel-soft rounded-2xl px-4 py-3 text-sm text-muted-foreground"
                  >
                    {item}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        <Card className="decision-card">
          <CardContent className="p-6 space-y-6">
            <div className="grid md:grid-cols-4 gap-4">
              <div className="space-y-2">
                <Label htmlFor="age">Age</Label>
                <Input
                  id="age"
                  type="number"
                  value={profile.age}
                  onChange={(event) => updateProfile("age", parseInt(event.target.value || "0", 10) || 0)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="sex">Sex</Label>
                <Select
                  id="sex"
                  value={profile.sex}
                  onChange={(event) => updateProfile("sex", event.target.value as UserProfile["sex"])}
                >
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                  <option value="other">Other</option>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="height">Height (cm)</Label>
                <Input
                  id="height"
                  type="number"
                  value={Math.round(profile.height)}
                  onChange={(event) => updateProfile("height", parseFloat(event.target.value || "0") || 0)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="weight">Weight (kg)</Label>
                <Input
                  id="weight"
                  type="number"
                  value={Math.round(profile.weight)}
                  onChange={(event) => updateProfile("weight", parseFloat(event.target.value || "0") || 0)}
                />
              </div>
            </div>

            <div className="grid md:grid-cols-4 gap-4">
              <div className="space-y-2">
                <Label htmlFor="activity">Activity level</Label>
                <Select
                  id="activity"
                  value={profile.activityLevel}
                  onChange={(event) => updateProfile("activityLevel", event.target.value as UserProfile["activityLevel"])}
                >
                  <option value="sedentary">Sedentary</option>
                  <option value="light">Light</option>
                  <option value="moderate">Moderate</option>
                  <option value="active">Active</option>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="sleepHours">Sleep hours/night</Label>
                <Input
                  id="sleepHours"
                  type="number"
                  step="0.1"
                  value={profile.sleepHoursPerNight}
                  onChange={(event) =>
                    updateProfile("sleepHoursPerNight", parseFloat(event.target.value || "0") || 0)
                  }
                />
              </div>
              <label className="flex items-center gap-3 rounded-xl border border-border/40 px-4 py-3 mt-7">
                <input
                  type="checkbox"
                  checked={profile.smoker}
                  onChange={(event) => updateProfile("smoker", event.target.checked)}
                  className="w-4 h-4 rounded border-border bg-card text-primary focus:ring-primary"
                />
                <span className="text-sm">Current smoker</span>
              </label>
              <label className="flex items-center gap-3 rounded-xl border border-border/40 px-4 py-3 mt-7">
                <input
                  type="checkbox"
                  checked={profile.hasDiabetes}
                  onChange={(event) => updateProfile("hasDiabetes", event.target.checked)}
                  className="w-4 h-4 rounded border-border bg-card text-primary focus:ring-primary"
                />
                <span className="text-sm">Has diabetes</span>
              </label>
            </div>

            <div className="grid md:grid-cols-2 gap-4">
              <label className="flex items-center gap-3 rounded-xl border border-border/40 px-4 py-3">
                <input
                  type="checkbox"
                  checked={profile.hasHypertension}
                  onChange={(event) => updateProfile("hasHypertension", event.target.checked)}
                  className="w-4 h-4 rounded border-border bg-card text-primary focus:ring-primary"
                />
                <span className="text-sm">Has hypertension</span>
              </label>
              <button
                type="button"
                onClick={() => setShowAdvancedSleep((value) => !value)}
                className="flex items-center justify-between rounded-xl border border-border/40 px-4 py-3 text-left hover:bg-muted/20 transition-colors"
              >
                <span className="text-sm font-medium">Advanced sleep inputs</span>
                {showAdvancedSleep ? (
                  <ChevronUp className="w-4 h-4" />
                ) : (
                  <ChevronDown className="w-4 h-4" />
                )}
              </button>
            </div>

            {showAdvancedSleep && (
              <div className="grid md:grid-cols-4 gap-4 rounded-2xl border border-border/40 p-4 bg-muted/10">
                {ADVANCED_SLEEP_FIELDS.map(({ key, label }) => (
                  <div key={key} className="space-y-2">
                    <Label htmlFor={key}>{label}</Label>
                    <Input
                      id={key}
                      type="number"
                      step="0.1"
                      value={sleepInputs[key] ?? ""}
                      onChange={(event) => updateSleep(key, event.target.value === "" ? null : parseFloat(event.target.value))}
                    />
                  </div>
                ))}
              </div>
            )}

            <div className="flex items-center gap-3">
              <Button onClick={runAnalysis} disabled={loading} className="h-11 px-6">
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Running live frontier
                  </>
                ) : (
                  "Run live analysis"
                )}
              </Button>
              <div className="space-y-1 text-sm text-muted-foreground">
                <p>Uses the unified Python catalog with `5,000` Monte Carlo draws.</p>
                <p>{loading ? requestStatus ?? "Running live analysis." : formatRunTime(lastCompletedAt)}</p>
              </div>
            </div>

            {error ? (
              <div className="rounded-2xl border border-destructive/40 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                {error}
              </div>
            ) : null}
          </CardContent>
        </Card>

        {results ? (
          <>
            <div className="grid md:grid-cols-4 gap-4">
              <Card className="decision-card">
                <CardContent className="p-5 space-y-2">
                  <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Rankable now</p>
                  <p className="text-3xl font-serif">{results.meta.rankable_count}</p>
                  <p className="text-sm text-muted-foreground">Broad public items plus any triggered conditional lane.</p>
                </CardContent>
              </Card>
              <Card className="decision-card">
                <CardContent className="p-5 space-y-2">
                  <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Held out</p>
                  <p className="text-3xl font-serif">
                    {Math.max(results.meta.analyzed_count - results.meta.rankable_count, 0)}
                  </p>
                  <p className="text-sm text-muted-foreground">Personal, current-stack, or condition-specific items.</p>
                </CardContent>
              </Card>
              <Card className="decision-card">
                <CardContent className="p-5 space-y-2">
                  <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Top frontier pick</p>
                  <p className="text-lg font-medium">
                    {results.frontier[0]?.added_name ?? "None"}
                  </p>
                </CardContent>
              </Card>
              <Card className="decision-card">
                <CardContent className="p-5 space-y-2">
                  <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Best marginal gain</p>
                  <p className="text-3xl font-serif">
                    {bestFrontierStep ? `${bestFrontierStep.marginal_days.toFixed(1)}d` : "0d"}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {bestFrontierStep
                      ? `${formatCurrency(bestFrontierStep.marginal_cost_value)}/yr marginal`
                      : "$0/yr marginal"}
                  </p>
                </CardContent>
              </Card>
            </div>

            <Card className="decision-card">
              <CardContent className="p-6 space-y-5">
                <div className="flex items-center justify-between gap-4 flex-wrap">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Public policy</p>
                    <h2 className="text-xl font-semibold">Automatic curation map</h2>
                  </div>
                  <p className="text-sm text-muted-foreground max-w-2xl text-right">
                    Generated from intervention specs. The public frontier is not just a sort over all items; it follows these lanes and condition triggers.
                  </p>
                </div>

                <div className="grid lg:grid-cols-3 gap-4">
                  {results.public_policy.lanes.map((lane) => {
                    const sampleNames = lane.item_ids
                      .slice(0, lane.id === "personal_only" ? 4 : 6)
                      .map((itemId) => publicPolicyItemsById.get(itemId) ?? itemId);

                    return (
                      <div
                        key={lane.id}
                        className="rounded-[1.5rem] border border-border/40 bg-muted/5 p-5 space-y-4"
                      >
                        <div className="space-y-1">
                          <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">
                            {humanizePublicLane(lane.id)}
                          </p>
                          <h3 className="text-base font-semibold">{lane.label}</h3>
                          <p className="text-sm text-muted-foreground">{lane.description}</p>
                        </div>

                        <div className="grid grid-cols-2 gap-3 text-sm">
                          <div className="rounded-xl bg-muted/15 px-3 py-2">
                            <p className="text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
                              Items
                            </p>
                            <p className="text-lg font-medium">{lane.item_count}</p>
                          </div>
                          <div className="rounded-xl bg-muted/15 px-3 py-2">
                            <p className="text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
                              Conditions
                            </p>
                            <p className="text-lg font-medium">{lane.condition_ids.length}</p>
                          </div>
                        </div>

                        {lane.condition_ids.length > 0 ? (
                          <div className="flex flex-wrap gap-2">
                            {lane.condition_ids.map((conditionId) => {
                              const condition = publicPolicyConditionsById.get(conditionId);
                              return (
                                <span
                                  key={conditionId}
                                  className="rounded-full bg-primary/8 px-3 py-1 text-xs text-foreground"
                                  title={condition?.description}
                                >
                                  {condition?.label ?? conditionId}
                                </span>
                              );
                            })}
                          </div>
                        ) : null}

                        <div className="space-y-2">
                          <p className="text-sm font-medium">Examples</p>
                          <div className="flex flex-wrap gap-2">
                            {sampleNames.map((name) => (
                              <span
                                key={name}
                                className="rounded-full border border-border/40 px-3 py-1 text-xs text-muted-foreground"
                              >
                                {name}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>

            {sleepEstimate ? (
              <Card className="decision-card">
                <CardContent className="p-6 space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Sleep phenotype</p>
                      <h2 className="text-xl font-semibold">Sleep burden in the model</h2>
                    </div>
                    <div className="text-right">
                      <p className="text-sm text-muted-foreground">Annual burden</p>
                      <p className="text-2xl font-serif">{sleepEstimate.annual_qaly_loss.toFixed(4)} QALY</p>
                    </div>
                  </div>
                  <div className="grid md:grid-cols-3 gap-4">
                    {Object.entries(sleepEstimate.component_losses).map(([key, value]) => (
                      <div key={key} className="rounded-2xl bg-muted/15 px-4 py-3">
                        <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">
                          {humanizeCategory(key)}
                        </p>
                        <p className="text-lg font-medium">{value.toFixed(4)} QALY</p>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            ) : null}

            {results.decision_states.length > 0 ? (
              <Card className="decision-card">
                <CardContent className="p-6 space-y-6">
                  <div className="space-y-3">
                    <div className="flex items-center justify-between gap-4 flex-wrap">
                      <div>
                        <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                          Stateful decisions
                        </p>
                        <h2 className="text-xl font-semibold">Sleep pathway decisions</h2>
                      </div>
                      <p className="text-sm text-muted-foreground max-w-xl text-right">
                        These branches are sequence-aware. They ask what to do first if the sleep phenotype looks airway-heavy, not just which single item has the biggest standalone effect.
                      </p>
                    </div>

                    <div className="grid md:grid-cols-3 gap-3">
                      {results.decision_sequence.map((step) => {
                        const targetDescription = describeSequenceTargets(step, decisionStateLabels);

                        return (
                          <div
                            key={step.id}
                            className="rounded-2xl border border-border/40 bg-muted/10 px-4 py-3"
                          >
                            <p className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
                              Step {step.step}
                            </p>
                            <p className="text-sm font-medium mt-1">{step.label}</p>
                            {targetDescription ? (
                              <p className="mt-2 text-xs text-muted-foreground">
                                {targetDescription}
                              </p>
                            ) : null}
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  <div className="space-y-4">
                    {results.decision_states.map((state) => (
                      <div
                        key={state.id}
                        className="rounded-[1.5rem] border border-border/40 bg-muted/5 p-5 space-y-4"
                      >
                        <div className="flex items-start justify-between gap-4 flex-wrap">
                          <div className="space-y-1">
                            <p className="text-sm font-semibold">{state.label}</p>
                            <p className="text-sm text-muted-foreground max-w-3xl">
                              {state.description}
                            </p>
                          </div>
                          <div className="text-sm text-muted-foreground">
                            Baseline: {state.baseline.adjusted_days.toFixed(1)}d at{" "}
                            {formatCurrency(state.baseline.total_annual_cost)}/yr
                          </div>
                        </div>

                        {"options" in state ? (
                          <>
                            <div className="grid md:grid-cols-2 gap-3">
                              <div className="rounded-2xl bg-muted/15 px-4 py-3">
                                <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">
                                  Best biology
                                </p>
                                <p className="text-base font-medium mt-1">
                                  {findOptionLabel(state.options, state.best_biology_option_id)}
                                </p>
                              </div>
                              <div className="rounded-2xl bg-muted/15 px-4 py-3">
                                <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">
                                  Best likely covered / low-friction
                                </p>
                                <p className="text-base font-medium mt-1">
                                  {findOptionLabel(state.options, state.best_access_option_id)}
                                </p>
                              </div>
                            </div>

                            <div className="overflow-x-auto">
                              <table className="w-full text-sm">
                                <thead className="text-left text-muted-foreground">
                                  <tr className="border-b border-border/40">
                                    <th className="py-3 pr-3 font-medium">Option</th>
                                    <th className="py-3 pr-3 font-medium">Added</th>
                                    <th className="py-3 pr-3 font-medium">Marginal days</th>
                                    <th className="py-3 pr-3 font-medium">Marginal $/QALY</th>
                                    <th className="py-3 pr-3 font-medium">Access</th>
                                    <th className="py-3 font-medium">Coverage</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {state.options.map((option) => {
                                    const isBestBiology = option.id === state.best_biology_option_id;
                                    const isBestAccess = option.id === state.best_access_option_id;

                                    return (
                                      <tr
                                        key={option.id}
                                        className="border-b border-border/20 hover:bg-muted/15 transition-colors"
                                        onClick={() =>
                                          option.added_item_ids[0]
                                            ? setSelectedItemId(option.added_item_ids[0])
                                            : null
                                        }
                                      >
                                        <td className="py-3 pr-3">
                                          <div className="flex flex-wrap items-center gap-2">
                                            <span className="font-medium">{option.label}</span>
                                            {isBestBiology ? (
                                              <span className="rounded-full bg-primary/12 px-2 py-0.5 text-[11px] uppercase tracking-[0.12em] text-primary">
                                                Biology
                                              </span>
                                            ) : null}
                                            {isBestAccess ? (
                                              <span className="rounded-full bg-secondary/60 px-2 py-0.5 text-[11px] uppercase tracking-[0.12em] text-foreground">
                                                Access
                                              </span>
                                            ) : null}
                                          </div>
                                        </td>
                                        <td className="py-3 pr-3 text-muted-foreground">
                                          {option.added_items.length > 0
                                            ? option.added_items.map((item) => item.name).join(", ")
                                            : "None"}
                                        </td>
                                        <td className="py-3 pr-3">{option.marginal_days.toFixed(1)}d</td>
                                        <td className="py-3 pr-3">
                                          {option.marginal_cost_per_qaly === null
                                            ? "Bundled / free"
                                            : `${formatCurrency(option.marginal_cost_per_qaly)}/QALY`}
                                        </td>
                                        <td className="py-3 pr-3">
                                          <div>{humanizeAccessTier(option.access.tier)}</div>
                                          <div className="text-xs text-muted-foreground">
                                            {option.access.friction} friction
                                          </div>
                                        </td>
                                        <td className="py-3">
                                          <div>{humanizeCoverage(option.access.coverage_outlook)}</div>
                                          {option.access.notes ? (
                                            <div className="text-xs text-muted-foreground max-w-xs">
                                              {option.access.notes}
                                            </div>
                                          ) : null}
                                        </td>
                                      </tr>
                                    );
                                  })}
                                </tbody>
                              </table>
                            </div>
                          </>
                        ) : (
                          <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                              <thead className="text-left text-muted-foreground">
                                <tr className="border-b border-border/40">
                                  <th className="py-3 pr-3 font-medium">Step</th>
                                  <th className="py-3 pr-3 font-medium">Add</th>
                                  <th className="py-3 pr-3 font-medium">Marginal days</th>
                                  <th className="py-3 pr-3 font-medium">Marginal $/QALY</th>
                                  <th className="py-3 font-medium">Total days</th>
                                </tr>
                              </thead>
                              <tbody>
                                {state.steps.map((step) => (
                                  <tr
                                    key={`${state.id}-${step.step}`}
                                    className="border-b border-border/20 hover:bg-muted/15 transition-colors"
                                    onClick={() => setSelectedItemId(step.id)}
                                  >
                                    <td className="py-3 pr-3 text-muted-foreground">{step.step}</td>
                                    <td className="py-3 pr-3 font-medium">{step.name}</td>
                                    <td className="py-3 pr-3">{step.marginal_days.toFixed(1)}d</td>
                                    <td className="py-3 pr-3">
                                      {step.marginal_cost_per_qaly === null
                                        ? "Bundled / free"
                                        : `${formatCurrency(step.marginal_cost_per_qaly)}/QALY`}
                                    </td>
                                    <td className="py-3">{step.cumulative_days.toFixed(1)}d</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            ) : null}

            <div className="grid xl:grid-cols-[1.15fr_0.85fr] gap-6 items-start">
              <Card className="decision-card">
                <CardContent className="p-6 space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Ordered frontier</p>
                      <h2 className="text-xl font-semibold">Marginal $/QALY ranking</h2>
                    </div>
                    <p className="text-sm text-muted-foreground">Curated public lane only</p>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    This ranking excludes personal current-stack items and clinician-mediated interventions unless a qualifying pathway is triggered.
                  </p>

                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="text-left text-muted-foreground">
                        <tr className="border-b border-border/40">
                          <th className="py-3 pr-3 font-medium">Step</th>
                          <th className="py-3 pr-3 font-medium">Add</th>
                          <th className="py-3 pr-3 font-medium">Marginal days</th>
                          <th className="py-3 pr-3 font-medium">Marginal $/QALY</th>
                          <th className="py-3 pr-3 font-medium">Penalty</th>
                          <th className="py-3 pr-3 font-medium">Total days</th>
                          <th className="py-3 font-medium">Spend</th>
                        </tr>
                      </thead>
                      <tbody>
                        {results.frontier.map((step) => (
                          <tr
                            key={step.step}
                            onClick={() => setSelectedItemId(step.added_intervention)}
                            className="border-b border-border/20 cursor-pointer hover:bg-muted/15 transition-colors"
                          >
                            <td className="py-3 pr-3 text-muted-foreground">{step.step}</td>
                            <td className="py-3 pr-3 font-medium">{step.added_name}</td>
                            <td className="py-3 pr-3">{step.marginal_days.toFixed(1)}d</td>
                            <td className="py-3 pr-3">
                              {step.marginal_cost_per_qaly === null
                                ? "Bundled / free"
                                : `${formatCurrency(step.marginal_cost_per_qaly)}/QALY`}
                            </td>
                            <td className="py-3 pr-3">{step.interaction_penalty_days.toFixed(1)}d</td>
                            <td className="py-3 pr-3">{step.total_days.toFixed(1)}d</td>
                            <td className="py-3">{formatCurrency(step.total_annual_cost)}/yr</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>

              <Card className="decision-card">
                <CardContent className="p-6 space-y-4">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Selected item</p>
                    <h2 className="text-xl font-semibold">{selectedItem?.name ?? "Pick an intervention"}</h2>
                  </div>

                  {selectedItem ? (
                    <>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="rounded-2xl bg-muted/15 px-4 py-3">
                          <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Standalone effect</p>
                          <p className="text-lg font-medium">{selectedItem.days.toFixed(1)}d</p>
                        </div>
                        <div className="rounded-2xl bg-muted/15 px-4 py-3">
                          <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">$ / QALY</p>
                          <p className="text-lg font-medium">
                            {formatCostPerQaly(
                              selectedItem.cost_per_qaly,
                              selectedItem.pricing_status
                            )}
                          </p>
                        </div>
                        <div className="rounded-2xl bg-muted/15 px-4 py-3">
                          <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">P(benefit)</p>
                          <p className="text-lg font-medium">{formatProbability(selectedItem.p_benefit)}</p>
                        </div>
                        <div className="rounded-2xl bg-muted/15 px-4 py-3">
                          <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">P(harm)</p>
                          <p className="text-lg font-medium">{formatProbability(selectedItem.p_harm)}</p>
                        </div>
                      </div>

                      <div className="space-y-2">
                        <p className="text-sm font-medium">Evidence and assumptions</p>
                        <p className="text-sm text-muted-foreground leading-relaxed">
                          {selectedItem.notes || "No additional notes attached."}
                        </p>
                        {selectedItem.rankability_reason ? (
                          <p className="text-sm text-muted-foreground leading-relaxed">
                            {selectedItem.rankability_reason}
                          </p>
                        ) : null}
                      </div>

                      <div className="space-y-2">
                        <p className="text-sm font-medium">Model modifiers</p>
                        <div className="grid grid-cols-2 gap-3 text-sm">
                          <div className="rounded-xl border border-border/30 px-3 py-2">
                            Transport multiplier: {selectedItem.profile_effect_multiplier.toFixed(3)}
                          </div>
                          <div className="rounded-xl border border-border/30 px-3 py-2">
                            Airway multiplier: {selectedItem.airway_effect_multiplier.toFixed(3)}
                          </div>
                          <div className="rounded-xl border border-border/30 px-3 py-2">
                            Sleep mortality HR: {selectedItem.sleep_mortality_hr_multiplier.toFixed(4)}
                          </div>
                          <div className="rounded-xl border border-border/30 px-3 py-2">
                            Sleep relief fraction: {selectedItem.sleep_mortality_relief_fraction.toFixed(3)}
                          </div>
                        </div>
                      </div>

                      <div className="space-y-2">
                        <p className="text-sm font-medium">Access</p>
                        <div className="grid grid-cols-2 gap-3 text-sm">
                          <div className="rounded-xl border border-border/30 px-3 py-2">
                            Tier: {humanizeAccessTier(selectedItem.access.tier)}
                          </div>
                          <div className="rounded-xl border border-border/30 px-3 py-2">
                            Coverage: {humanizeCoverage(selectedItem.access.coverage_outlook)}
                          </div>
                          <div className="rounded-xl border border-border/30 px-3 py-2">
                            Friction: {selectedItem.access.friction}
                          </div>
                          <div className="rounded-xl border border-border/30 px-3 py-2">
                            {selectedItem.access.notes || "No extra access note."}
                          </div>
                        </div>
                      </div>

                      {selectedItem.sources.length > 0 ? (
                        <div className="space-y-2">
                          <p className="text-sm font-medium">Sources</p>
                          <ul className="space-y-2">
                            {selectedItem.sources.map((source) => (
                              <li key={source}>
                                <a
                                  href={source}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="text-sm text-primary hover:underline break-all"
                                >
                                  {source}
                                </a>
                              </li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                    </>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      Click a frontier row or intervention to inspect evidence, transport, and harm details.
                    </p>
                  )}
                </CardContent>
              </Card>
            </div>

            <Card className="decision-card">
              <CardContent className="p-6 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Catalog results</p>
                    <h2 className="text-xl font-semibold">Standalone intervention library</h2>
                  </div>
                  <label className="flex items-center gap-2 text-sm text-muted-foreground">
                    <input
                      type="checkbox"
                      checked={showNegatives}
                      onChange={(event) => setShowNegatives(event.target.checked)}
                      className="w-4 h-4 rounded border-border bg-card text-primary focus:ring-primary"
                    />
                    Show negative items
                  </label>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="text-left text-muted-foreground">
                      <tr className="border-b border-border/40">
                        <th className="py-3 pr-3 font-medium">Intervention</th>
                        <th className="py-3 pr-3 font-medium">Category</th>
                        <th className="py-3 pr-3 font-medium">Days</th>
                        <th className="py-3 pr-3 font-medium">$ / QALY</th>
                        <th className="py-3 pr-3 font-medium">Annual cost</th>
                        <th className="py-3 pr-3 font-medium">P(+)</th>
                        <th className="py-3 font-medium">P(-)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {visibleItems.map((item) => (
                        <tr
                          key={item.id}
                          onClick={() => setSelectedItemId(item.id)}
                          className={`border-b border-border/20 cursor-pointer transition-colors ${
                            selectedItemId === item.id ? "bg-primary/6" : "hover:bg-muted/15"
                          }`}
                        >
                          <td className="py-3 pr-3">
                            <div className="flex items-center gap-2">
                              <span className="font-medium">{item.name}</span>
                              {item.selected_in_frontier ? (
                                <span className="rounded-full bg-primary/12 px-2 py-0.5 text-[11px] uppercase tracking-[0.12em] text-primary">
                                  Frontier
                                </span>
                              ) : null}
                            </div>
                          </td>
                          <td className="py-3 pr-3 text-muted-foreground capitalize">
                            {humanizeCategory(item.display_category)}
                          </td>
                          <td className="py-3 pr-3">{item.days.toFixed(1)}d</td>
                          <td className="py-3 pr-3">
                            {formatCostPerQaly(item.cost_per_qaly, item.pricing_status)}
                          </td>
                          <td className="py-3 pr-3">
                            {item.pricing_status === "unpriced"
                              ? "Unpriced"
                              : formatCurrency(item.annual_cost)}
                          </td>
                          <td className="py-3 pr-3">{formatProbability(item.p_benefit)}</td>
                          <td className="py-3">{formatProbability(item.p_harm)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </>
        ) : null}

        <p className="text-xs text-muted-foreground text-center max-w-3xl mx-auto">
          Experimental live analysis. Results come from the unified Python catalog,
          not the old precomputed TS profiles. The page now ranks interventions by
          marginal cost-effectiveness and shows evidence notes instead of hiding a
          default threshold.
        </p>
      </main>
    </div>
  );
}
