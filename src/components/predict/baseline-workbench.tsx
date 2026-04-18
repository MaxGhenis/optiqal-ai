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
  BaselineRequest,
  BaselineResponse,
  BaselineSleepInput,
} from "@/lib/baseline-types";

const STORAGE_KEY = "optiqal-baseline-profile-v1";
const SLEEP_STORAGE_KEY = "optiqal-baseline-sleep-v1";

function loadStoredJson<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

const timeFormatter = new Intl.DateTimeFormat("en-US", {
  hour: "numeric",
  minute: "2-digit",
  second: "2-digit",
});

function formatRunTime(timestamp: number | null): string {
  if (timestamp === null) {
    return "No completed run yet.";
  }
  return `Last updated ${timeFormatter.format(timestamp)}.`;
}

function buildSleepPayload(
  profile: UserProfile,
  sleep: BaselineSleepInput
): BaselineRequest["sleep_metrics"] {
  const payload: BaselineSleepInput = {
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

function toRequest(profile: UserProfile, sleep: BaselineSleepInput): BaselineRequest {
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
  };
}

function formatProbability(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function humanizeKey(value: string): string {
  return value.replaceAll("_", " ");
}

export function BaselineWorkbench() {
  const [profile, setProfile] = useState<UserProfile>(DEFAULT_PROFILE);
  const [sleepInputs, setSleepInputs] = useState<BaselineSleepInput>({});
  const [results, setResults] = useState<BaselineResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAdvancedSleep, setShowAdvancedSleep] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const [requestStatus, setRequestStatus] = useState<string | null>(null);
  const [lastCompletedAt, setLastCompletedAt] = useState<number | null>(null);
  const latestRequest = useLatestRequest();

  useEffect(() => {
    const storedProfile = loadStoredJson<UserProfile>(STORAGE_KEY);
    const storedSleep = loadStoredJson<BaselineSleepInput>(SLEEP_STORAGE_KEY);
    if (storedProfile) setProfile(storedProfile);
    if (storedSleep) setSleepInputs(storedSleep);
    setHydrated(true);
  }, []);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
  }, [profile]);

  useEffect(() => {
    localStorage.setItem(SLEEP_STORAGE_KEY, JSON.stringify(sleepInputs));
  }, [sleepInputs]);

  const updateProfile = (key: keyof UserProfile, value: UserProfile[keyof UserProfile]) => {
    setProfile((prev) => ({ ...prev, [key]: value }));
  };

  const updateSleep = (key: keyof BaselineSleepInput, value: number | null) => {
    setSleepInputs((prev) => ({ ...prev, [key]: value }));
  };

  const runAnalysis = async () => {
    const { requestId, controller, supersededPrevious } = latestRequest.beginRequest();

    setLoading(true);
    setError(null);
    setRequestStatus(
      supersededPrevious
        ? "Previous request cancelled. Running latest baseline."
        : "Running baseline."
    );

    try {
      const response = await fetch("/api/baseline", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(toRequest(profile, sleepInputs)),
        signal: controller.signal,
      });

      const data = (await response.json()) as BaselineResponse | { error: string };
      if (!response.ok || "error" in data) {
        throw new Error("error" in data ? data.error : "Failed to load baseline");
      }

      if (!latestRequest.isCurrentRequest(requestId)) {
        return;
      }
      setResults(data);
      setLastCompletedAt(Date.now());
      setRequestStatus("Baseline complete.");
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        return;
      }
      if (!latestRequest.isCurrentRequest(requestId)) {
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to load baseline");
      setResults(null);
      setRequestStatus(null);
    } finally {
      if (latestRequest.finishRequest(requestId)) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    if (!hydrated) return;
    void runAnalysis();
    // We only want the first post-hydration fetch here.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hydrated]);

  const curvePreview = useMemo(() => {
    if (!results) return [];
    return results.survival_curve.filter((point, index) => index === 0 || point.age % 10 === 0);
  }, [results]);

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
              Canonical baseline
            </div>
            <div className="space-y-3">
              <h1 className="font-serif text-4xl md:text-5xl font-semibold tracking-[-0.04em] leading-[1.02]">
                Project remaining life years and QALYs
              </h1>
              <p className="text-lg text-muted-foreground max-w-2xl leading-relaxed">
                This replaces the old precomputed predictor. It now calls the same Python
                lifecycle, profile, and sleep logic that powers the rest of the product.
              </p>
            </div>
          </div>

          <Card className="decision-card border-primary/15">
            <CardContent className="p-6 space-y-4">
              <p className="text-xs uppercase tracking-[0.22em] text-primary">
                What changed
              </p>
              <div className="space-y-3">
                {[
                  "0% QALY discount instead of the old precomputed 3% path",
                  "Explicit profile inputs instead of browser-side imputation",
                  "Sleep can feed into baseline hazard through the shared sleep model",
                  "One engine for frontier ranking and baseline projection",
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
                  onChange={(event) =>
                    updateProfile("age", parseInt(event.target.value || "0", 10) || 0)
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="sex">Sex</Label>
                <Select
                  id="sex"
                  value={profile.sex}
                  onChange={(event) =>
                    updateProfile("sex", event.target.value as UserProfile["sex"])
                  }
                >
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                  <option value="other">Other / average</option>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="weight">Weight (kg)</Label>
                <Input
                  id="weight"
                  type="number"
                  value={profile.weight}
                  onChange={(event) =>
                    updateProfile("weight", Number(event.target.value) || 0)
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="height">Height (cm)</Label>
                <Input
                  id="height"
                  type="number"
                  value={profile.height}
                  onChange={(event) =>
                    updateProfile("height", Number(event.target.value) || 0)
                  }
                />
              </div>
            </div>

            <div className="grid md:grid-cols-4 gap-4">
              <div className="space-y-2">
                <Label htmlFor="activity">Activity level</Label>
                <Select
                  id="activity"
                  value={profile.activityLevel}
                  onChange={(event) =>
                    updateProfile(
                      "activityLevel",
                      event.target.value as UserProfile["activityLevel"]
                    )
                  }
                >
                  <option value="sedentary">Sedentary</option>
                  <option value="light">Light</option>
                  <option value="moderate">Moderate</option>
                  <option value="active">Active</option>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="sleep-hours">Sleep hours</Label>
                <Input
                  id="sleep-hours"
                  type="number"
                  step="0.1"
                  value={profile.sleepHoursPerNight}
                  onChange={(event) =>
                    updateProfile("sleepHoursPerNight", Number(event.target.value) || 0)
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="smoker">Smoking</Label>
                <Select
                  id="smoker"
                  value={profile.smoker ? "yes" : "no"}
                  onChange={(event) => updateProfile("smoker", event.target.value === "yes")}
                >
                  <option value="no">No</option>
                  <option value="yes">Yes</option>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="diabetes">Diabetes</Label>
                <Select
                  id="diabetes"
                  value={profile.hasDiabetes ? "yes" : "no"}
                  onChange={(event) =>
                    updateProfile("hasDiabetes", event.target.value === "yes")
                  }
                >
                  <option value="no">No</option>
                  <option value="yes">Yes</option>
                </Select>
              </div>
            </div>

            <div className="grid md:grid-cols-4 gap-4 items-end">
              <div className="space-y-2">
                <Label htmlFor="hypertension">Hypertension</Label>
                <Select
                  id="hypertension"
                  value={profile.hasHypertension ? "yes" : "no"}
                  onChange={(event) =>
                    updateProfile("hasHypertension", event.target.value === "yes")
                  }
                >
                  <option value="no">No</option>
                  <option value="yes">Yes</option>
                </Select>
              </div>

              <div className="md:col-span-3 flex justify-between items-end gap-4 flex-wrap">
                <div className="text-sm text-muted-foreground space-y-1">
                  <p>Calls the shared Python baseline engine.</p>
                  <p>{loading ? requestStatus ?? "Running baseline." : formatRunTime(lastCompletedAt)}</p>
                </div>
                <Button onClick={runAnalysis} disabled={loading}>
                  {loading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Running baseline
                    </>
                  ) : (
                    "Run baseline"
                  )}
                </Button>
              </div>
            </div>

            <button
              className="w-full flex items-center justify-between rounded-2xl border border-border/50 px-4 py-3 text-sm text-muted-foreground hover:text-foreground hover:border-border transition-colors"
              onClick={() => setShowAdvancedSleep((prev) => !prev)}
              type="button"
            >
              <span>Advanced sleep inputs</span>
              {showAdvancedSleep ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </button>

            {showAdvancedSleep ? (
              <div className="grid md:grid-cols-4 gap-4">
                {[
                  ["recovery_score", "Recovery score"],
                  ["sleep_quality_score", "Sleep quality score"],
                  ["waso_min", "WASO (min)"],
                  ["routine_score", "Routine score"],
                  ["social_jetlag_min", "Social jetlag (min)"],
                  ["latency_min", "Sleep latency (min)"],
                  ["breathing_score", "Breathing score"],
                  ["spo2", "SpO2"],
                  ["snore_pct", "Snore %"],
                  ["sleep_debt_min", "Sleep debt (min)"],
                  ["airway_response_signal", "Airway response signal"],
                ].map(([key, label]) => (
                  <div className="space-y-2" key={key}>
                    <Label htmlFor={key}>{label}</Label>
                    <Input
                      id={key}
                      type="number"
                      step="0.1"
                      value={sleepInputs[key as keyof BaselineSleepInput] ?? ""}
                      onChange={(event) =>
                        updateSleep(
                          key as keyof BaselineSleepInput,
                          event.target.value === "" ? null : Number(event.target.value)
                        )
                      }
                    />
                  </div>
                ))}
              </div>
            ) : null}
          </CardContent>
        </Card>

        {error ? (
          <Card className="decision-card border-destructive/30">
            <CardContent className="p-6 text-sm text-destructive">{error}</CardContent>
          </Card>
        ) : null}

        {results ? (
          <>
            <div className="grid md:grid-cols-4 gap-4">
              <Card className="decision-card">
                <CardContent className="p-6 space-y-2">
                  <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                    Remaining life expectancy
                  </p>
                  <p className="text-4xl font-serif">
                    {results.point_estimate.remaining_life_expectancy.toFixed(1)}
                  </p>
                  <p className="text-sm text-muted-foreground">years</p>
                </CardContent>
              </Card>
              <Card className="decision-card">
                <CardContent className="p-6 space-y-2">
                  <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                    Expected death age
                  </p>
                  <p className="text-4xl font-serif">
                    {results.point_estimate.expected_death_age.toFixed(1)}
                  </p>
                  <p className="text-sm text-muted-foreground">years old</p>
                </CardContent>
              </Card>
              <Card className="decision-card">
                <CardContent className="p-6 space-y-2">
                  <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                    Remaining QALYs
                  </p>
                  <p className="text-4xl font-serif">
                    {results.point_estimate.remaining_qalys.toFixed(1)}
                  </p>
                  <p className="text-sm text-muted-foreground">0% discount</p>
                </CardContent>
              </Card>
              <Card className="decision-card">
                <CardContent className="p-6 space-y-2">
                  <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
                    Current quality weight
                  </p>
                  <p className="text-4xl font-serif">
                    {results.point_estimate.current_quality_weight.toFixed(3)}
                  </p>
                  <p className="text-sm text-muted-foreground">today</p>
                </CardContent>
              </Card>
            </div>

            <div className="grid lg:grid-cols-[0.95fr_1.05fr] gap-6">
              <Card className="decision-card">
                <CardContent className="p-6 space-y-4">
                  <div className="space-y-1">
                    <p className="text-xs uppercase tracking-[0.22em] text-primary">
                      Risk decomposition
                    </p>
                    <h2 className="font-serif text-2xl">Baseline hazard path</h2>
                  </div>
                  <div className="grid sm:grid-cols-2 gap-3">
                    {[
                      ["Lifestyle multiplier", results.risk.lifestyle_multiplier],
                      ["Condition multiplier", results.risk.condition_multiplier],
                      ["Sleep multiplier", results.risk.sleep_multiplier],
                      ["Raw multiplier", results.risk.raw_multiplier],
                      ["Calibration factor", results.risk.calibration_factor],
                      ["Calibrated multiplier", results.risk.calibrated_multiplier],
                    ].map(([label, value]) => (
                      <div key={label} className="surface-panel-soft rounded-2xl px-4 py-4">
                        <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                          {label}
                        </p>
                        <p className="mt-2 text-2xl font-serif">
                          {Number(value).toFixed(3)}
                        </p>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              <Card className="decision-card">
                <CardContent className="p-6 space-y-4">
                  <div className="space-y-1">
                    <p className="text-xs uppercase tracking-[0.22em] text-primary">
                      Survival curve
                    </p>
                    <h2 className="font-serif text-2xl">Expected path by age</h2>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="text-left text-muted-foreground">
                        <tr>
                          <th className="pb-3 font-medium">Age</th>
                          <th className="pb-3 font-medium">Survival</th>
                          <th className="pb-3 font-medium">Quality</th>
                          <th className="pb-3 font-medium">Expected QALY</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/30">
                        {curvePreview.map((point) => (
                          <tr key={point.age}>
                            <td className="py-3">{point.age}</td>
                            <td className="py-3">{formatProbability(point.survival_probability)}</td>
                            <td className="py-3">{point.quality_weight.toFixed(3)}</td>
                            <td className="py-3">{point.expected_qaly.toFixed(3)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            </div>

            {results.sleep_estimate ? (
              <Card className="decision-card">
                <CardContent className="p-6 space-y-4">
                  <div className="space-y-1">
                    <p className="text-xs uppercase tracking-[0.22em] text-primary">
                      Sleep state
                    </p>
                    <h2 className="font-serif text-2xl">Shared sleep model output</h2>
                  </div>
                  <div className="grid sm:grid-cols-3 gap-3">
                    <div className="surface-panel-soft rounded-2xl px-4 py-4">
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                        Annual QALY loss
                      </p>
                      <p className="mt-2 text-2xl font-serif">
                        {results.sleep_estimate.annual_qaly_loss.toFixed(4)}
                      </p>
                    </div>
                    <div className="surface-panel-soft rounded-2xl px-4 py-4">
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                        Mortality signal
                      </p>
                      <p className="mt-2 text-2xl font-serif">
                        {results.sleep_estimate.mortality_signal.toFixed(3)}
                      </p>
                    </div>
                    <div className="surface-panel-soft rounded-2xl px-4 py-4">
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                        Baseline hazard multiplier
                      </p>
                      <p className="mt-2 text-2xl font-serif">
                        {results.sleep_estimate.baseline_hazard_multiplier.toFixed(3)}
                      </p>
                    </div>
                  </div>
                  <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
                    {Object.entries(results.sleep_estimate.component_losses).map(([key, value]) => (
                      <div key={key} className="surface-panel-soft rounded-2xl px-4 py-3">
                        <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                          {humanizeKey(key)}
                        </p>
                        <p className="mt-2 text-lg font-medium">{value.toFixed(4)}</p>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            ) : null}
          </>
        ) : null}
      </main>
    </div>
  );
}
