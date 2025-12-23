/**
 * Result caching layer to reduce API costs
 *
 * Uses localStorage for browser-side caching with:
 * - TTL: 7 days (configurable)
 * - Max entries: 100 (LRU eviction)
 * - Normalized intervention strings for matching
 */

import type { StructuredAnalysisResult } from "./analyze-structured";
import type { UserProfile } from "@/types";

// Cache configuration
const CACHE_KEY_PREFIX = "optiqal-cache-";
const CACHE_TTL_MS = 7 * 24 * 60 * 60 * 1000; // 7 days
const MAX_CACHE_ENTRIES = 100;
const PRUNE_TO_ENTRIES = 80; // Prune to 80% of max when exceeded

/**
 * Cache entry with metadata
 */
interface CacheEntry {
  intervention: string;
  profile: UserProfile;
  result: StructuredAnalysisResult;
  timestamp: number;
  normalizedKey: string;
}

/**
 * Cache statistics
 */
export interface CacheStats {
  totalEntries: number;
  totalSize: number; // In bytes
  oldestEntry: number | null; // Timestamp
}

/**
 * Normalize an intervention string for cache matching
 *
 * Handles:
 * - Case normalization
 * - Whitespace trimming
 * - Common time unit variations (min/mins/minutes, hr/hrs/hour/hours)
 * - Number word conversion (one -> 1, two -> 2, etc.)
 * - Common synonyms (jogging -> running, bicycling -> cycling)
 */
export function normalizeIntervention(intervention: string): string {
  let normalized = intervention.toLowerCase().trim();

  // Normalize time units
  normalized = normalized.replace(/\b(\d+)\s*mins?\b/g, "$1 minutes");
  normalized = normalized.replace(/\b(\d+)\s*hrs?\b/g, "$1 hours");

  // Convert number words to digits
  const numberWords: Record<string, string> = {
    one: "1",
    two: "2",
    three: "3",
    four: "4",
    five: "5",
    six: "6",
    seven: "7",
    eight: "8",
    nine: "9",
    ten: "10",
  };
  for (const [word, digit] of Object.entries(numberWords)) {
    normalized = normalized.replace(new RegExp(`\\b${word}\\b`, "g"), digit);
  }

  // Normalize common synonyms
  const synonyms: Record<string, string> = {
    jogging: "running",
    strolling: "walking",
    bicycling: "cycling",
  };
  for (const [synonym, canonical] of Object.entries(synonyms)) {
    normalized = normalized.replace(new RegExp(`\\b${synonym}\\b`, "g"), canonical);
  }

  // Collapse multiple spaces
  normalized = normalized.replace(/\s+/g, " ");

  return normalized;
}

/**
 * Generate a profile hash for cache key uniqueness
 */
function hashProfile(profile: UserProfile): string {
  // Include key profile attributes that affect results
  const key = `${profile.age}_${profile.sex}_${profile.height}_${profile.weight}_${profile.exerciseHoursPerWeek}_${profile.sleepHoursPerNight}_${profile.diet}_${profile.smoker}`;

  // Simple hash function
  let hash = 0;
  for (let i = 0; i < key.length; i++) {
    const char = key.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash = hash & hash; // Convert to 32-bit integer
  }
  return Math.abs(hash).toString(36);
}

/**
 * Generate cache key from intervention and profile
 */
export function getCacheKey(intervention: string, profile: UserProfile): string {
  const normalized = normalizeIntervention(intervention);
  const profileHash = hashProfile(profile);
  return `${normalized}|${profileHash}`;
}

/**
 * Get all cache entries from localStorage
 */
function getAllCacheEntries(): CacheEntry[] {
  const entries: CacheEntry[] = [];

  if (typeof localStorage === "undefined") {
    return entries;
  }

  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key?.startsWith(CACHE_KEY_PREFIX)) {
      try {
        const value = localStorage.getItem(key);
        if (value) {
          const entry = JSON.parse(value) as CacheEntry;
          entries.push(entry);
        }
      } catch {
        // Ignore parse errors
      }
    }
  }

  return entries;
}

/**
 * Get cached result for an intervention and profile
 *
 * Returns null if:
 * - No cache entry found
 * - Entry expired (> TTL)
 */
export function getCachedResult(
  intervention: string,
  profile: UserProfile
): StructuredAnalysisResult | null {
  if (typeof localStorage === "undefined") {
    return null;
  }

  const cacheKey = getCacheKey(intervention, profile);
  const storageKey = CACHE_KEY_PREFIX + cacheKey;

  try {
    const cached = localStorage.getItem(storageKey);
    if (!cached) {
      return null;
    }

    const entry = JSON.parse(cached) as CacheEntry;

    // Check if expired
    const now = Date.now();
    if (now - entry.timestamp > CACHE_TTL_MS) {
      localStorage.removeItem(storageKey);
      return null;
    }

    return entry.result;
  } catch {
    return null;
  }
}

/**
 * Store result in cache
 */
export function setCachedResult(
  intervention: string,
  profile: UserProfile,
  result: StructuredAnalysisResult
): void {
  if (typeof localStorage === "undefined") {
    return;
  }

  const cacheKey = getCacheKey(intervention, profile);
  const storageKey = CACHE_KEY_PREFIX + cacheKey;

  const entry: CacheEntry = {
    intervention,
    profile,
    result,
    timestamp: Date.now(),
    normalizedKey: cacheKey,
  };

  try {
    localStorage.setItem(storageKey, JSON.stringify(entry));
    pruneCacheIfNeeded();
  } catch (error) {
    // localStorage might be full, try pruning and retry
    console.warn("Cache storage failed, pruning old entries:", error);
    pruneCacheIfNeeded();
    try {
      localStorage.setItem(storageKey, JSON.stringify(entry));
    } catch {
      // If still fails, give up silently
      console.error("Cache storage failed after pruning");
    }
  }
}

/**
 * Clear all cache entries
 */
export function clearCache(): void {
  if (typeof localStorage === "undefined") {
    return;
  }

  const keysToRemove: string[] = [];
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key?.startsWith(CACHE_KEY_PREFIX)) {
      keysToRemove.push(key);
    }
  }

  for (const key of keysToRemove) {
    localStorage.removeItem(key);
  }
}

/**
 * Get cache statistics
 */
export function getCacheStats(): CacheStats {
  const entries = getAllCacheEntries();

  let totalSize = 0;
  let oldestEntry: number | null = null;

  for (const entry of entries) {
    // Estimate size
    totalSize += JSON.stringify(entry).length;

    // Track oldest
    if (oldestEntry === null || entry.timestamp < oldestEntry) {
      oldestEntry = entry.timestamp;
    }
  }

  return {
    totalEntries: entries.length,
    totalSize,
    oldestEntry,
  };
}

/**
 * Prune cache using LRU strategy if over max entries
 *
 * Removes oldest 20% when max is exceeded
 */
export function pruneCacheIfNeeded(): void {
  if (typeof localStorage === "undefined") {
    return;
  }

  const entries = getAllCacheEntries();

  if (entries.length <= MAX_CACHE_ENTRIES) {
    return;
  }

  // Sort by timestamp (oldest first)
  entries.sort((a, b) => a.timestamp - b.timestamp);

  // Remove oldest entries until we reach PRUNE_TO_ENTRIES
  const toRemove = entries.length - PRUNE_TO_ENTRIES;
  for (let i = 0; i < toRemove; i++) {
    const entry = entries[i];
    const storageKey = CACHE_KEY_PREFIX + entry.normalizedKey;
    localStorage.removeItem(storageKey);
  }

  console.log(`[Cache] Pruned ${toRemove} old entries (${entries.length} -> ${PRUNE_TO_ENTRIES})`);
}
