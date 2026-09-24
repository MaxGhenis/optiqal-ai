"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Check,
  ChevronDown,
  ExternalLink,
  Info,
  Loader2,
  Pencil,
  Pill,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { LogoLockup } from "@/components/brand/logo";
import { MedicalDisclaimer } from "@/components/medical-disclaimer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { useLatestRequest } from "@/hooks/use-latest-request";
import { parseStoredUserProfile } from "@/lib/profile-storage";
import { cn } from "@/lib/utils";
import type {
  FrontierDecisionState,
  FrontierItem,
  FrontierRequest,
  FrontierResponse,
  FrontierSleepInput,
  FrontierStep,
} from "@/lib/frontier-types";
import { DEFAULT_PROFILE, type UserProfile } from "@/types";

const PROFILE_STORAGE_KEY = "optiqal-frontier-profile-v1";
const SLEEP_STORAGE_KEY = "optiqal-frontier-sleep-v1";
const STACK_STORAGE_KEY = "optiqal-current-stack-v1";

const SLEEP_INPUT_BOUNDS: Array<{
  key: keyof FrontierSleepInput;
  min: number;
  max: number;
}> = [
  { key: "duration_hours", min: 0, max: 24 },
  { key: "recovery_score", min: 0, max: 100 },
  { key: "sleep_quality_score", min: 0, max: 100 },
  { key: "waso_min", min: 0, max: 1440 },
  { key: "routine_score", min: 0, max: 100 },
  { key: "social_jetlag_min", min: 0, max: 1440 },
  { key: "latency_min", min: 0, max: 1440 },
  { key: "breathing_score", min: 0, max: 1 },
  { key: "spo2", min: 0, max: 100 },
  { key: "snore_pct", min: 0, max: 100 },
  { key: "sleep_debt_min", min: 0, max: 1440 },
  { key: "airway_response_signal", min: 0, max: 1 },
];

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

const ADVANCED_SLEEP_FIELDS: Array<{
  key: keyof FrontierSleepInput;
  label: string;
  hint: string;
  min: number;
  max: number;
  step: number;
}> = [
  { key: "sleep_quality_score", label: "Sleep quality", hint: "0–100", min: 0, max: 100, step: 1 },
  { key: "waso_min", label: "Time awake", hint: "minutes", min: 0, max: 1440, step: 1 },
  { key: "routine_score", label: "Routine score", hint: "0–100", min: 0, max: 100, step: 1 },
  { key: "recovery_score", label: "Recovery score", hint: "0–100", min: 0, max: 100, step: 1 },
  { key: "breathing_score", label: "Breathing score", hint: "0–1", min: 0, max: 1, step: 0.01 },
  { key: "spo2", label: "Average SpO₂", hint: "%", min: 0, max: 100, step: 0.1 },
  { key: "snore_pct", label: "Time snoring", hint: "%", min: 0, max: 100, step: 0.1 },
  { key: "airway_response_signal", label: "Airway response", hint: "0–1", min: 0, max: 1, step: 0.01 },
];

function loadStoredJson<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

function parseStoredSleepInput(value: unknown): FrontierSleepInput {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return {};
  const stored = value as Record<string, unknown>;
  const sleep: FrontierSleepInput = {};

  for (const { key, min, max } of SLEEP_INPUT_BOUNDS) {
    let field = stored[key];
    if (
      (key === "breathing_score" || key === "airway_response_signal") &&
      typeof field === "number" &&
      field > 1 &&
      field <= 100
    ) {
      field /= 100;
    }
    if (typeof field === "number" && Number.isFinite(field) && field >= min && field <= max) {
      sleep[key] = field;
    }
  }

  return sleep;
}

function formatCurrency(value: number | null): string {
  if (value === null) return "Not priced";
  if (value === 0) return "$0";
  return currency.format(value);
}

function formatProbability(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function formatDuration(days: number): string {
  const absoluteDays = Math.abs(days);
  if (absoluteDays < 1) {
    const hours = days * 24;
    return `${hours.toFixed(hours < 10 ? 1 : 0)} hours`;
  }
  if (absoluteDays < 14) {
    return `${days.toFixed(1)} days`;
  }
  if (absoluteDays < 70) {
    return `${(days / 7).toFixed(1)} weeks`;
  }
  return `${Math.round(days)} days`;
}

function formatSignedDuration(days: number): string {
  return `${days >= 0 ? "+" : "−"}${formatDuration(Math.abs(days))}`;
}

function formatRange(item: FrontierItem): string | null {
  if (!item.net_days_ci) return null;
  const [low, high] = item.net_days_ci;
  if (Math.abs(high - low) < 0.1) {
    return "Uncertainty range unavailable for this action";
  }
  return `80% model interval ${formatDuration(low)}–${formatDuration(high)}`;
}

function formatCostPerQaly(item: FrontierItem): string {
  if (item.pricing_status === "unpriced") return "Not priced";
  if (item.cost_per_qaly === null) return "No added cost";
  return `${currency.format(item.cost_per_qaly)} / QALY`;
}

function humanize(value: string): string {
  return value.replaceAll("_", " ");
}

function accessLabel(item: FrontierItem): string {
  if (item.access.tier === "generic_rx") return "Generic prescription";
  if (item.access.tier === "brand_rx_prior_auth") return "Brand prescription";
  if (item.access.tier === "dme_rx") return "Prescription equipment";
  if (item.access.tier === "specialist_device") return "Specialist device";
  if (item.access.tier === "cash_pay") {
    return item.annual_cost === 0 ? "Self-directed" : "Cash pay";
  }
  if (item.access.tier === "otc") return "Over the counter";
  if (item.access.tier === "behavioral") return "Behavior change";
  return humanize(item.access.tier);
}

function isPrescription(item: FrontierItem): boolean {
  return item.display_category === "rx";
}

function PrescriptionBadge({ compact = false }: { compact?: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-highlight/35 bg-highlight/8 font-medium text-highlight",
        compact ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-xs"
      )}
    >
      <Pill aria-hidden="true" className="h-3 w-3" />
      Prescription — ask a clinician
    </span>
  );
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

function toRequest(
  profile: UserProfile,
  sleep: FrontierSleepInput,
  currentStackIds: string[]
): FrontierRequest {
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
    current_stack_ids: currentStackIds,
    n_simulations: 5000,
  };
}

function isProfileValid(profile: UserProfile): boolean {
  return (
    profile.age >= 18 &&
    profile.age <= 100 &&
    profile.height >= 100 &&
    profile.height <= 250 &&
    profile.weight >= 20 &&
    profile.weight <= 500 &&
    profile.sleepHoursPerNight >= 0 &&
    profile.sleepHoursPerNight <= 24
  );
}

function isSleepInputValid(sleepInputs: FrontierSleepInput): boolean {
  return SLEEP_INPUT_BOUNDS.every(({ key, min, max }) => {
    const value = sleepInputs[key];
    return value === null || value === undefined || (value >= min && value <= max);
  });
}

interface ProfileEditorProps {
  profile: UserProfile;
  sleepInputs: FrontierSleepInput;
  showAdvancedSleep: boolean;
  loading: boolean;
  error: string | null;
  hasResults: boolean;
  savedStackCount: number;
  onProfileChange: (key: keyof UserProfile, value: UserProfile[keyof UserProfile]) => void;
  onSleepChange: (key: keyof FrontierSleepInput, value: number | null) => void;
  onToggleAdvancedSleep: () => void;
  onCancel: () => void;
  onClearSavedRoutine: () => void;
  onSubmit: () => void;
}

function ProfileEditor({
  profile,
  sleepInputs,
  showAdvancedSleep,
  loading,
  error,
  hasResults,
  savedStackCount,
  onProfileChange,
  onSleepChange,
  onToggleAdvancedSleep,
  onCancel,
  onClearSavedRoutine,
  onSubmit,
}: ProfileEditorProps) {
  const valid = isProfileValid(profile) && isSleepInputValid(sleepInputs);

  return (
    <form
      className="rounded-[1.75rem] border border-border/70 bg-surface-panel/92 p-5 shadow-[0_30px_80px_-54px_hsl(var(--text-strong)/0.35)] sm:p-7"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">
            About you
          </p>
          <h2 className="mt-2 text-xl font-semibold">Build a useful baseline</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Six quick inputs help the model filter and rank the public catalog.
          </p>
        </div>
        {hasResults ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={loading}
            onClick={onCancel}
          >
            <X className="mr-1.5 h-4 w-4" />
            Close
          </Button>
        ) : null}
      </div>

      <fieldset disabled={loading} className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="age">Age</Label>
            <Input
              id="age"
              type="number"
              min={18}
              max={100}
              inputMode="numeric"
              value={profile.age}
              aria-invalid={profile.age < 18 || profile.age > 100}
              onChange={(event) =>
                onProfileChange("age", Number.parseInt(event.target.value || "0", 10))
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="sex">Sex used in life tables</Label>
            <Select
              id="sex"
              value={profile.sex}
              onChange={(event) =>
                onProfileChange("sex", event.target.value as UserProfile["sex"])
              }
            >
              <option value="male">Male</option>
              <option value="female">Female</option>
              <option value="other">Other (uses male life table)</option>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="height">Height (cm)</Label>
            <Input
              id="height"
              type="number"
              min={100}
              max={250}
              inputMode="decimal"
              value={Math.round(profile.height)}
              aria-invalid={profile.height < 100 || profile.height > 250}
              onChange={(event) =>
                onProfileChange("height", Number.parseFloat(event.target.value || "0"))
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="weight">Weight (kg)</Label>
            <Input
              id="weight"
              type="number"
              min={20}
              max={500}
              inputMode="decimal"
              value={Math.round(profile.weight)}
              aria-invalid={profile.weight < 20 || profile.weight > 500}
              onChange={(event) =>
                onProfileChange("weight", Number.parseFloat(event.target.value || "0"))
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="activity">Current activity</Label>
            <Select
              id="activity"
              value={profile.activityLevel}
              onChange={(event) =>
                onProfileChange(
                  "activityLevel",
                  event.target.value as UserProfile["activityLevel"]
                )
              }
            >
              <option value="sedentary">Mostly sedentary</option>
              <option value="light">Lightly active</option>
              <option value="moderate">Moderately active</option>
              <option value="active">Very active</option>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="sleepHours">Sleep per night</Label>
            <div className="relative">
              <Input
                id="sleepHours"
                type="number"
                min={0}
                max={24}
                step="0.1"
                inputMode="decimal"
                className="pr-14"
                value={profile.sleepHoursPerNight}
                aria-invalid={
                  profile.sleepHoursPerNight < 0 || profile.sleepHoursPerNight > 24
                }
                onChange={(event) =>
                  onProfileChange(
                    "sleepHoursPerNight",
                    Number.parseFloat(event.target.value || "0")
                  )
                }
              />
              <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">
                hours
              </span>
            </div>
          </div>
        </div>

        <div className="grid gap-2 sm:grid-cols-3">
          {[
            ["smoker", "Current smoker", profile.smoker],
            ["hasDiabetes", "Diabetes", profile.hasDiabetes],
            ["hasHypertension", "Hypertension", profile.hasHypertension],
          ].map(([key, label, checked]) => (
            <label
              key={String(key)}
              className="flex min-h-12 cursor-pointer items-center gap-3 rounded-xl border border-border/70 px-3.5 py-2.5 text-sm transition-colors hover:bg-muted/20"
            >
              <input
                id={String(key)}
                type="checkbox"
                checked={Boolean(checked)}
                onChange={(event) =>
                  onProfileChange(key as keyof UserProfile, event.target.checked)
                }
                className="h-4 w-4 rounded border-input bg-card text-primary focus:ring-primary"
              />
              {label}
            </label>
          ))}
        </div>

        <div className="border-t border-border/60 pt-4">
          <button
            type="button"
            aria-expanded={showAdvancedSleep}
            aria-controls="advanced-sleep-fields"
            onClick={onToggleAdvancedSleep}
            className="flex w-full items-center justify-between rounded-xl px-1 py-2 text-left text-sm font-medium text-foreground transition-colors hover:text-primary"
          >
            <span>
              Add wearable sleep details
              <span className="ml-2 font-normal text-muted-foreground">Optional</span>
            </span>
            <ChevronDown
              aria-hidden="true"
              className={cn(
                "h-4 w-4 transition-transform",
                showAdvancedSleep && "rotate-180"
              )}
            />
          </button>

          {showAdvancedSleep ? (
            <div id="advanced-sleep-fields" className="mt-3 grid gap-4 sm:grid-cols-2">
              {ADVANCED_SLEEP_FIELDS.map(({ key, label, hint, min, max, step }) => (
                <div key={key} className="space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <Label htmlFor={key}>{label}</Label>
                    <span className="text-[11px] text-muted-foreground">{hint}</span>
                  </div>
                  <Input
                    id={key}
                    type="number"
                    min={min}
                    max={max}
                    step={step}
                    value={sleepInputs[key] ?? ""}
                    aria-invalid={
                      sleepInputs[key] !== null &&
                      sleepInputs[key] !== undefined &&
                      (sleepInputs[key]! < min || sleepInputs[key]! > max)
                    }
                    onChange={(event) =>
                      onSleepChange(
                        key,
                        event.target.value === ""
                          ? null
                          : Number.parseFloat(event.target.value)
                      )
                    }
                  />
                </div>
              ))}
            </div>
          ) : null}
        </div>
      </fieldset>

      {!valid ? (
        <p className="mt-4 flex items-start gap-2 text-sm text-destructive" role="alert">
          <Info className="mt-0.5 h-4 w-4 shrink-0" />
          Check the highlighted values before running your analysis.
        </p>
      ) : null}

      {error ? (
        <p
          className="mt-4 rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive"
          role="alert"
        >
          {error}
        </p>
      ) : null}

      {!hasResults && savedStackCount > 0 ? (
        <div className="mt-4 flex items-center justify-between gap-4 rounded-xl border border-border/70 bg-muted/10 px-4 py-3 text-sm">
          <span className="text-muted-foreground">
            {savedStackCount} saved routine action{savedStackCount === 1 ? "" : "s"} will be included.
          </span>
          <button
            type="button"
            className="shrink-0 font-medium text-primary hover:underline"
            onClick={onClearSavedRoutine}
          >
            Clear routine
          </button>
        </div>
      ) : null}

      <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
        <Button
          type="submit"
          size="lg"
          disabled={!valid || loading}
          className="h-12 px-6 sm:min-w-48"
        >
          {loading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Ranking options
            </>
          ) : hasResults ? (
            <>
              <RefreshCw className="mr-2 h-4 w-4" />
              Update my ranking
            </>
          ) : (
            <>
              Rank my options
              <Sparkles className="ml-2 h-4 w-4" />
            </>
          )}
        </Button>
        <p className="flex items-start gap-2 text-xs leading-relaxed text-muted-foreground">
          <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
          Your profile is processed to produce this result and saved only in this browser.
        </p>
      </div>

    </form>
  );
}

interface RecommendationListProps {
  steps: FrontierStep[];
  itemsById: Map<string, FrontierItem>;
  selectedItemId: string | null;
  onSelect: (itemId: string) => void;
}

function RecommendationList({
  steps,
  itemsById,
  selectedItemId,
  onSelect,
}: RecommendationListProps) {
  if (steps.length === 0) {
    return (
      <div className="border-y border-border/60 py-10 text-center">
        <p className="font-medium">No positive next move was identified.</p>
        <p className="mt-2 text-sm text-muted-foreground">
          Review all analyzed options or adjust your profile and routine.
        </p>
      </div>
    );
  }

  return (
    <ol className="border-t border-border/70">
      {steps.slice(0, 6).map((step, index) => {
        const item = itemsById.get(step.added_intervention);
        const selected = selectedItemId === step.added_intervention;
        return (
          <li key={step.added_intervention} className="border-b border-border/70">
            <button
              type="button"
              aria-pressed={selected}
              onClick={() => onSelect(step.added_intervention)}
              className={cn(
                "group grid w-full grid-cols-[2.25rem_1fr_auto] gap-3 px-2 py-5 text-left transition-colors sm:grid-cols-[2.75rem_1fr_auto] sm:px-3",
                selected ? "bg-primary/7" : "hover:bg-surface-panel/65"
              )}
            >
              <span
                className={cn(
                  "flex h-7 w-7 items-center justify-center rounded-full border text-xs font-semibold sm:h-8 sm:w-8",
                  index === 0
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border-strong/50 text-muted-foreground"
                )}
              >
                {index + 1}
              </span>
              <span className="min-w-0">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold text-foreground">{step.added_name}</span>
                  {item && isPrescription(item) ? <PrescriptionBadge compact /> : null}
                </span>
                <span className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground sm:text-sm">
                  <span>{item ? formatProbability(item.p_benefit) : "—"} standalone net benefit</span>
                  <span>{item ? `${formatCurrency(item.annual_cost)} / year` : "—"}</span>
                </span>
              </span>
              <span className="whitespace-nowrap pt-0.5 text-right">
                <span className="block font-mono text-sm font-semibold text-primary sm:text-base">
                  {formatSignedDuration(step.marginal_days)}
                </span>
                <span className="mt-1 block text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                  marginal gain
                </span>
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}

interface InterventionDetailProps {
  item: FrontierItem | null;
  step: FrontierStep | null;
  rank: number | null;
  isCurrent: boolean;
  loading: boolean;
  onToggleCurrent: (itemId: string, next: boolean) => void;
}

function InterventionDetail({
  item,
  step,
  rank,
  isCurrent,
  loading,
  onToggleCurrent,
}: InterventionDetailProps) {
  if (!item) {
    return (
      <aside
        id="intervention-detail"
        tabIndex={-1}
        className="scroll-mt-24 rounded-[1.5rem] border border-border/70 bg-surface-panel/80 p-6 outline-none focus-visible:ring-2 focus-visible:ring-primary"
      >
        <p className="text-sm text-muted-foreground">Select an option to inspect it.</p>
      </aside>
    );
  }

  const expectedDays = step?.marginal_days ?? item.days;
  const marginalDiffersFromStandalone = Boolean(
    step && Math.abs(step.marginal_days - item.days) >= 0.1
  );
  const range = marginalDiffersFromStandalone
    ? "Marginal uncertainty range unavailable"
    : formatRange(item);
  const costEffectiveness = step
    ? step.marginal_cost_per_qaly === null
      ? "No added cost"
      : `${currency.format(step.marginal_cost_per_qaly)} / QALY`
    : formatCostPerQaly(item);

  return (
    <aside
      id="intervention-detail"
      tabIndex={-1}
      className="scroll-mt-24 rounded-[1.5rem] border border-primary/18 bg-surface-panel p-6 outline-none shadow-[0_28px_70px_-50px_hsl(var(--text-strong)/0.42)] focus-visible:ring-2 focus-visible:ring-primary lg:sticky lg:top-24"
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">
            {rank ? `Why it ranks #${rank}` : isCurrent ? "In your routine" : "Option detail"}
          </p>
          <h2 className="mt-2 font-serif text-3xl font-semibold leading-tight tracking-[-0.03em]">
            {item.name}
          </h2>
        </div>
        {isCurrent ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">
            <Check className="h-3 w-3" /> Current
          </span>
        ) : null}
      </div>

      {isPrescription(item) ? <div className="mt-4"><PrescriptionBadge /></div> : null}

      <div className="mt-7 border-y border-border/70 py-6">
        <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
          {step ? "Expected marginal benefit" : "Expected standalone benefit"}
        </p>
        <p className="mt-2 font-mono text-4xl font-semibold tracking-[-0.04em] text-primary">
          {formatSignedDuration(expectedDays)}
        </p>
        {range ? <p className="mt-2 text-sm text-muted-foreground">{range}</p> : null}
      </div>

      <dl className="grid grid-cols-2 gap-x-5 gap-y-5 py-6 text-sm">
        <div>
          <dt className="text-muted-foreground">Standalone net-benefit probability</dt>
          <dd className="mt-1 text-lg font-semibold">{formatProbability(item.p_benefit)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Chance of standalone net loss</dt>
          <dd className="mt-1 text-lg font-semibold">{formatProbability(item.p_harm)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Listed annual cost</dt>
          <dd className="mt-1 font-medium">{formatCurrency(item.annual_cost)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Access</dt>
          <dd className="mt-1 font-medium capitalize">{accessLabel(item)}</dd>
        </div>
        <div className="col-span-2">
          <dt className="text-muted-foreground">Cost-effectiveness</dt>
          <dd className="mt-1 font-medium">{costEffectiveness}</dd>
        </div>
      </dl>

      {step ? (
        <p className="mb-5 border-l-2 border-primary/20 pl-3 text-xs leading-relaxed text-muted-foreground">
          The marginal point estimate accounts for your routine. Benefit and harm probabilities describe this action on its own.
        </p>
      ) : null}

      <div className="border-t border-border/70 pt-5">
        <h3 className="text-sm font-semibold">Evidence and assumptions</h3>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          {item.notes || "No additional evidence note is attached to this option."}
        </p>
        {item.rankability_reason ? (
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            {item.rankability_reason}
          </p>
        ) : null}
      </div>

      <Button
        type="button"
        variant={isCurrent ? "outline" : "default"}
        className="mt-6 w-full"
        disabled={loading}
        onClick={() => onToggleCurrent(item.id, !isCurrent)}
      >
        {loading ? (
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        ) : isCurrent ? (
          <X className="mr-2 h-4 w-4" />
        ) : (
          <Check className="mr-2 h-4 w-4" />
        )}
        {isCurrent ? "Mark as not current — rerank" : "Already in my routine — rerank"}
      </Button>
      <p className="mt-2 text-center text-xs leading-relaxed text-muted-foreground">
        {isPrescription(item)
          ? "This only updates the model baseline. Do not start or stop medication without your clinician."
          : "This only updates the model baseline; it does not tell you to start or stop the action."}
      </p>

      {item.sources.length > 0 ? (
        <details className="mt-5 border-t border-border/70 pt-4">
          <summary className="cursor-pointer text-sm font-medium text-primary">
            View {item.sources.length} source{item.sources.length === 1 ? "" : "s"}
          </summary>
          <ul className="mt-3 space-y-2">
            {item.sources.map((source, index) => (
              <li key={source}>
                <a
                  href={source}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-start gap-2 text-sm text-primary hover:underline"
                >
                  <span>Source {index + 1}</span>
                  <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                </a>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </aside>
  );
}

function SleepPathways({ states }: { states: FrontierDecisionState[] }) {
  if (states.length === 0) return null;

  return (
    <details className="group border-b border-border/70 py-5">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-medium">
        <span>Sleep-specific pathways</span>
        <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" />
      </summary>
      <div className="mt-5 space-y-6">
        {states.map((state) => (
          <section key={state.id} className="border-l-2 border-primary/20 pl-4">
            <h3 className="font-semibold">{state.label}</h3>
            <p className="mt-1 text-sm text-muted-foreground">{state.description}</p>
            {state.kind === "choice" ? (
              <ul className="mt-3 space-y-2 text-sm">
                {state.options.map((option) => (
                  <li key={option.id} className="flex justify-between gap-4 border-t border-border/50 pt-2">
                    <span>{option.label}</span>
                    <span className="font-mono text-primary">
                      {formatSignedDuration(option.marginal_days)}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <ol className="mt-3 space-y-2 text-sm">
                {state.steps.map((step) => (
                  <li key={step.id} className="flex justify-between gap-4 border-t border-border/50 pt-2">
                    <span>{step.step}. {step.name}</span>
                    <span className="font-mono text-primary">
                      {formatSignedDuration(step.marginal_days)}
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </section>
        ))}
      </div>
    </details>
  );
}

export function FrontierWorkbench() {
  const [profile, setProfile] = useState<UserProfile>(DEFAULT_PROFILE);
  const [analyzedProfile, setAnalyzedProfile] = useState<UserProfile | null>(null);
  const [sleepInputs, setSleepInputs] = useState<FrontierSleepInput>({});
  const [analyzedSleepInputs, setAnalyzedSleepInputs] =
    useState<FrontierSleepInput | null>(null);
  const [currentStackIds, setCurrentStackIds] = useState<string[]>([]);
  const [results, setResults] = useState<FrontierResponse | null>(null);
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingProfile, setEditingProfile] = useState(true);
  const [showAdvancedSleep, setShowAdvancedSleep] = useState(false);
  const [showNegatives, setShowNegatives] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");
  const [hydrated, setHydrated] = useState(false);
  const latestRequest = useLatestRequest();

  useEffect(() => {
    const storedProfile = parseStoredUserProfile(loadStoredJson<unknown>(PROFILE_STORAGE_KEY));
    const storedSleep = parseStoredSleepInput(loadStoredJson<unknown>(SLEEP_STORAGE_KEY));
    const storedStack = loadStoredJson<string[]>(STACK_STORAGE_KEY);
    if (storedProfile) setProfile(storedProfile);
    setSleepInputs(storedSleep);
    if (storedStack && Array.isArray(storedStack)) {
      setCurrentStackIds(
        Array.from(
          new Set(
            storedStack
              .filter((itemId): itemId is string => typeof itemId === "string")
              .map((itemId) => itemId.trim())
              .filter(Boolean)
          )
        ).slice(0, 50)
      );
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(profile));
  }, [hydrated, profile]);

  useEffect(() => {
    if (!hydrated) return;
    localStorage.setItem(SLEEP_STORAGE_KEY, JSON.stringify(sleepInputs));
  }, [hydrated, sleepInputs]);

  useEffect(() => {
    if (!hydrated) return;
    localStorage.setItem(STACK_STORAGE_KEY, JSON.stringify(currentStackIds));
  }, [currentStackIds, hydrated]);

  const itemsById = useMemo(() => {
    return new Map((results?.items ?? []).map((item) => [item.id, item]));
  }, [results]);

  const publicItems = useMemo(() => {
    if (!results) return [];
    return results.items.filter((item) => item.pricing_status !== "unpriced");
  }, [results]);

  const visibleItems = useMemo(() => {
    return showNegatives ? publicItems : publicItems.filter((item) => item.total_qaly > 0);
  }, [publicItems, showNegatives]);

  const selectedItem = selectedItemId ? itemsById.get(selectedItemId) ?? null : null;
  const selectedStep =
    results?.frontier.find((step) => step.added_intervention === selectedItemId) ?? null;
  const selectedRank = selectedStep ? results!.frontier.indexOf(selectedStep) + 1 : null;
  const currentStackItems = currentStackIds
    .map((itemId) => itemsById.get(itemId))
    .filter((item): item is FrontierItem => Boolean(item));

  const updateProfile = (key: keyof UserProfile, value: UserProfile[keyof UserProfile]) => {
    setProfile((previous) => ({ ...previous, [key]: value }));
  };

  const updateSleep = (key: keyof FrontierSleepInput, value: number | null) => {
    setSleepInputs((previous) => ({ ...previous, [key]: value }));
  };

  const runAnalysis = async (
    stackIds: string[] = currentStackIds
  ): Promise<boolean> => {
    if (!isProfileValid(profile) || !isSleepInputValid(sleepInputs)) return false;

    const { requestId, controller } = latestRequest.beginRequest();
    setLoading(true);
    setError(null);
    setStatusMessage("Ranking your options.");

    try {
      const response = await fetch("/api/frontier", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(toRequest(profile, sleepInputs, stackIds)),
        signal: controller.signal,
      });
      const data = (await response.json()) as FrontierResponse | { error: string };
      if (!response.ok || "error" in data) {
        throw new Error("error" in data ? data.error : "Unable to rank your options");
      }
      if (!latestRequest.isCurrentRequest(requestId)) return false;

      setResults(data);
      setAnalyzedProfile({ ...profile });
      setAnalyzedSleepInputs({ ...sleepInputs });
      setCurrentStackIds(stackIds);
      setEditingProfile(false);
      setSelectedItemId(
        data.frontier[0]?.added_intervention ??
          data.items.find((item) => item.pricing_status !== "unpriced")?.id ??
          null
      );
      document.documentElement.scrollTop = 0;
      document.body.scrollTop = 0;
      setStatusMessage(
        data.frontier[0]
          ? `Ranking complete. Top-ranked addition: ${data.frontier[0].added_name}.`
          : "Ranking complete. No positive addition was identified."
      );
      return true;
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") return false;
      if (!latestRequest.isCurrentRequest(requestId)) return false;
      setError(caught instanceof Error ? caught.message : "Unable to rank your options");
      setStatusMessage("Ranking failed. Review the error and try again.");
      return false;
    } finally {
      if (latestRequest.finishRequest(requestId)) setLoading(false);
    }
  };

  const toggleCurrentItem = (itemId: string, next: boolean) => {
    const nextItem = itemsById.get(itemId);
    const conflictingIds = nextItem?.exclusive_group
      ? new Set(
          currentStackIds.filter(
            (currentId) =>
              itemsById.get(currentId)?.exclusive_group === nextItem.exclusive_group
          )
        )
      : new Set<string>();
    const nextStack = next
      ? Array.from(
          new Set([
            ...currentStackIds.filter((currentId) => !conflictingIds.has(currentId)),
            itemId,
          ])
        )
      : currentStackIds.filter((currentId) => currentId !== itemId);
    void runAnalysis(nextStack);
  };

  const selectCatalogItem = (item: FrontierItem) => {
    setSelectedItemId(item.id);
    setStatusMessage(`${item.name} details selected.`);
    const detail = document.getElementById("intervention-detail");
    detail?.focus({ preventScroll: true });
    detail?.scrollIntoView?.({
      behavior: window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
        ? "auto"
        : "smooth",
      block: "start",
    });
  };

  const topStep = results?.frontier[0] ?? null;
  const resultProfile = analyzedProfile ?? profile;

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,hsl(var(--surface-canvas))_0%,hsl(var(--surface-panel-soft))_70%,hsl(var(--surface-canvas))_100%)]">
      <header className="sticky top-0 z-50 border-b border-border/50 bg-surface-overlay/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3.5 sm:px-6">
          <Link href="/" className="group">
            <LogoLockup
              size="sm"
              showDescriptor={false}
              markClassName="transition-transform group-hover:scale-[1.04]"
            />
          </Link>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/">
              <ArrowLeft className="mr-1.5 h-4 w-4" />
              Home
            </Link>
          </Button>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-12">
        <p className="sr-only" role="status" aria-live="polite">
          {statusMessage}
        </p>
        {editingProfile ? (
          <div className="grid items-start gap-10 lg:grid-cols-[0.78fr_1.22fr] lg:gap-14">
            <section className="pt-2 lg:sticky lg:top-28 lg:pt-6">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-primary">
                Personalized decision engine
              </p>
              <h1 className="mt-4 max-w-xl font-serif text-4xl font-semibold leading-[0.98] tracking-[-0.045em] sm:text-6xl">
                Rank the next health addition.
              </h1>
              <p className="mt-4 max-w-lg text-base leading-relaxed text-muted-foreground sm:mt-5 sm:text-lg">
                Compare unlike health actions on one scale, then see which option adds the most value beyond what you already do.
              </p>

              <ol className="mt-9 hidden max-w-lg border-t border-border/70 lg:block">
                {[
                  ["01", "Build your baseline", "Age, health markers, activity, and sleep."],
                  ["02", "Account for your routine", "Mark an action current and the ranking recalculates around it."],
                  ["03", "Choose the next move", "Compare benefit, uncertainty, cost, harm, and access."],
                ].map(([number, title, body]) => (
                  <li key={number} className="grid grid-cols-[2.5rem_1fr] gap-3 border-b border-border/70 py-4">
                    <span className="pt-0.5 font-mono text-xs text-primary">{number}</span>
                    <div>
                      <p className="font-medium">{title}</p>
                      <p className="mt-1 text-sm text-muted-foreground">{body}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </section>

            <ProfileEditor
              profile={profile}
              sleepInputs={sleepInputs}
              showAdvancedSleep={showAdvancedSleep}
              loading={loading}
              error={error}
              hasResults={Boolean(results)}
              savedStackCount={currentStackIds.length}
              onProfileChange={updateProfile}
              onSleepChange={updateSleep}
              onToggleAdvancedSleep={() => setShowAdvancedSleep((value) => !value)}
              onCancel={() => {
                if (analyzedProfile) setProfile(analyzedProfile);
                if (analyzedSleepInputs) setSleepInputs(analyzedSleepInputs);
                setEditingProfile(false);
              }}
              onClearSavedRoutine={() => setCurrentStackIds([])}
              onSubmit={() => void runAnalysis()}
            />
          </div>
        ) : results ? (
          <div className="animate-fade-in">
            <section className="grid gap-6 border-b border-border/70 pb-8 md:grid-cols-[1fr_auto] md:items-end">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-primary">
                  Your next move
                </p>
                <h1 className="mt-3 max-w-4xl font-serif text-4xl font-semibold leading-[1.02] tracking-[-0.04em] sm:text-5xl">
                  {topStep ? `Top-ranked addition: ${topStep.added_name}` : "Review your options"}
                </h1>
                <p className="mt-4 max-w-2xl text-base leading-relaxed text-muted-foreground sm:text-lg">
                  Ranked for a {resultProfile.age}-year-old with {humanize(resultProfile.activityLevel)} activity
                  {currentStackIds.length > 0
                    ? `, after accounting for ${currentStackIds.length} current action${currentStackIds.length === 1 ? "" : "s"}`
                    : ". Add what you already do to reveal the next best move"}.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" onClick={() => setEditingProfile(true)}>
                  <Pencil className="mr-2 h-4 w-4" />
                  Edit profile
                </Button>
                <Button variant="outline" disabled={loading} onClick={() => void runAnalysis()}>
                  {loading ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCw className="mr-2 h-4 w-4" />
                  )}
                  Recalculate
                </Button>
              </div>
            </section>

            {currentStackIds.length > 0 ? (
              <section className="flex flex-col gap-3 border-b border-border/70 py-5 sm:flex-row sm:items-center">
                <p className="shrink-0 text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  Already in your routine
                </p>
                <div className="flex flex-wrap gap-2">
                  {currentStackItems.map((item) => (
                    <span
                      key={item.id}
                      className="inline-flex items-center overflow-hidden rounded-full border border-primary/20 bg-primary/6 text-sm"
                    >
                      <button
                        type="button"
                        className="px-3 py-1.5 font-medium text-primary hover:bg-primary/8"
                        onClick={() => setSelectedItemId(item.id)}
                      >
                        {item.name}
                      </button>
                      <button
                        type="button"
                        aria-label={`Mark ${item.name} as not current in the model and rerank`}
                        title={`Mark ${item.name} as not current in the model and rerank`}
                        className="border-l border-primary/15 px-2 py-2 text-primary hover:bg-primary/10"
                        disabled={loading}
                        onClick={() => toggleCurrentItem(item.id, false)}
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </span>
                  ))}
                </div>
              </section>
            ) : null}

            {error ? (
              <p className="mt-5 rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive" role="alert">
                {error}
              </p>
            ) : null}

            <div className="mt-8 grid items-start gap-8 lg:grid-cols-[1.05fr_0.95fr] xl:gap-12">
              <section aria-labelledby="ranked-options-heading">
                <div className="mb-5 flex items-end justify-between gap-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">
                      Ranked action plan
                    </p>
                    <h2 id="ranked-options-heading" className="mt-1 text-2xl font-semibold">
                      Marginal cost-effectiveness order
                    </h2>
                  </div>
                  <p className="hidden text-right text-xs text-muted-foreground sm:block">
                    Select an action to inspect it
                  </p>
                </div>
                <RecommendationList
                  steps={results.frontier}
                  itemsById={itemsById}
                  selectedItemId={selectedItemId}
                  onSelect={setSelectedItemId}
                />
              </section>

              <InterventionDetail
                item={selectedItem}
                step={selectedStep}
                rank={selectedRank}
                isCurrent={selectedItem ? currentStackIds.includes(selectedItem.id) : false}
                loading={loading}
                onToggleCurrent={toggleCurrentItem}
              />
            </div>

            <MedicalDisclaimer className="mt-8" />

            <section className="mt-10 border-t border-border/70" aria-label="Further analysis">
              <details className="group border-b border-border/70 py-5">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-medium">
                  <span>
                    Explore {visibleItems.length}{" "}
                    {showNegatives ? "priced public options" : "positive, priced public options"}
                  </span>
                  <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" />
                </summary>
                <div className="mt-5">
                  <label className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
                    <input
                      type="checkbox"
                      checked={showNegatives}
                      onChange={(event) => setShowNegatives(event.target.checked)}
                      className="h-4 w-4 rounded border-input bg-card text-primary focus:ring-primary"
                    />
                    Include options with a non-positive estimate
                  </label>
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[640px] text-sm">
                      <thead className="border-b border-border/70 text-left text-xs uppercase tracking-[0.12em] text-muted-foreground">
                        <tr>
                          <th className="py-3 pr-4 font-medium">Intervention</th>
                          <th className="py-3 pr-4 font-medium">Expected benefit</th>
                          <th className="py-3 pr-4 font-medium">Standalone net benefit</th>
                          <th className="py-3 font-medium">Annual cost</th>
                        </tr>
                      </thead>
                      <tbody>
                        {visibleItems.map((item) => (
                          <tr key={item.id} className="border-b border-border/50">
                            <td className="py-3 pr-4">
                              <button
                                type="button"
                                className="flex flex-wrap items-center gap-2 text-left font-medium hover:text-primary"
                                onClick={() => selectCatalogItem(item)}
                              >
                                <span>{item.name}</span>
                                {isPrescription(item) ? <PrescriptionBadge compact /> : null}
                              </button>
                            </td>
                            <td className="py-3 pr-4 font-mono text-primary">
                              {formatSignedDuration(item.days)}
                            </td>
                            <td className="py-3 pr-4">{formatProbability(item.p_benefit)}</td>
                            <td className="py-3">{formatCurrency(item.annual_cost)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </details>

              <SleepPathways states={results.decision_states} />

              <details className="group border-b border-border/70 py-5">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-medium">
                  <span>How this ranking works</span>
                  <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" />
                </summary>
                <div className="mt-5 grid gap-8 md:grid-cols-[1fr_1.1fr]">
                  <div>
                    <p className="text-sm leading-relaxed text-muted-foreground">
                      Optiqal compares the incremental value of each eligible option against your current routine. It combines expected quality-adjusted benefit, interaction effects, and cost, then reveals uncertainty and access separately so you can judge the tradeoff.
                    </p>
                    <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                      Public recommendations are curated for broad relevance. Condition-specific and clinician-mediated options only appear when the supplied profile qualifies them.
                    </p>
                  </div>
                  <dl className="grid grid-cols-2 gap-x-6 gap-y-5 text-sm">
                    <div>
                      <dt className="text-muted-foreground">Simulations</dt>
                      <dd className="mt-1 font-mono font-medium">
                        {results.meta.n_simulations.toLocaleString()}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">QALY discount rate</dt>
                      <dd className="mt-1 font-mono font-medium">
                        {(results.meta.qaly_discount_rate * 100).toFixed(0)}%
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Eligible now</dt>
                      <dd className="mt-1 font-mono font-medium">{results.meta.rankable_count}</dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Full catalog</dt>
                      <dd className="mt-1 font-mono font-medium">{results.meta.analyzed_count}</dd>
                    </div>
                  </dl>
                </div>
              </details>
            </section>

            <p className="mx-auto mt-8 max-w-3xl text-center text-xs leading-relaxed text-muted-foreground">
              Estimates combine published population evidence with the profile you supplied. They are decision aids, not diagnoses or guarantees.
            </p>
          </div>
        ) : null}
      </main>
    </div>
  );
}
