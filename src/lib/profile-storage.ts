import { DEFAULT_PROFILE, type UserProfile } from "@/types";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function boundedNumber(value: unknown, low: number, high: number): number | null {
  return typeof value === "number" && Number.isFinite(value) && value >= low && value <= high
    ? value
    : null;
}

/**
 * Migrate untrusted browser storage into the current profile schema.
 * Invalid or missing fields fall back independently so one stale value does
 * not make the whole saved profile unusable.
 */
export function parseStoredUserProfile(value: unknown): UserProfile | null {
  if (!isRecord(value)) return null;

  const profile: UserProfile = {
    ...DEFAULT_PROFILE,
    existingConditions: [...DEFAULT_PROFILE.existingConditions],
  };

  const age = boundedNumber(value.age, 18, 100);
  const weight = boundedNumber(value.weight, 20, 500);
  const height = boundedNumber(value.height, 100, 250);
  const exerciseHours = boundedNumber(value.exerciseHoursPerWeek, 0, 168);
  const sleepHours = boundedNumber(value.sleepHoursPerNight, 0, 24);
  if (age !== null) profile.age = age;
  if (weight !== null) profile.weight = weight;
  if (height !== null) profile.height = height;
  if (exerciseHours !== null) profile.exerciseHoursPerWeek = exerciseHours;
  if (sleepHours !== null) profile.sleepHoursPerNight = sleepHours;

  if (value.sex === "male" || value.sex === "female" || value.sex === "other") {
    profile.sex = value.sex;
  }
  if (
    value.activityLevel === "sedentary" ||
    value.activityLevel === "light" ||
    value.activityLevel === "moderate" ||
    value.activityLevel === "active"
  ) {
    profile.activityLevel = value.activityLevel;
  }
  if (
    value.diet === "omnivore" ||
    value.diet === "vegetarian" ||
    value.diet === "vegan" ||
    value.diet === "pescatarian" ||
    value.diet === "keto" ||
    value.diet === "other"
  ) {
    profile.diet = value.diet;
  }

  if (typeof value.smoker === "boolean") profile.smoker = value.smoker;
  if (typeof value.hasDiabetes === "boolean") profile.hasDiabetes = value.hasDiabetes;
  if (typeof value.hasHypertension === "boolean") {
    profile.hasHypertension = value.hasHypertension;
  }
  if (Array.isArray(value.existingConditions)) {
    profile.existingConditions = value.existingConditions
      .filter((condition): condition is string => typeof condition === "string")
      .slice(0, 100);
  }

  return profile;
}
