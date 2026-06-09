import { spawn } from "node:child_process";
import path from "node:path";

interface PythonJsonRunnerOptions<T> {
  payload: unknown;
  scriptPath: string;
  label: string;
  parseResponse: (value: unknown) => T | null;
  remotePath?: string;
  remoteBaseUrl?: string;
  remoteHeaders?: Record<string, string | undefined>;
  timeoutMs?: number;
  cacheTtlMs?: number;
  cacheKey?: string;
}

interface CacheEntry {
  expiresAt: number;
  value: unknown;
}

// Bound the cache so a flood of distinct (attacker-controlled) payloads cannot
// grow it without limit. Map preserves insertion order, so deleting the first
// key evicts approximately the oldest entry.
const MAX_CACHE_ENTRIES = 500;
const responseCache = new Map<string, CacheEntry>();
const inflightRequests = new Map<string, Promise<unknown>>();

function buildDefaultCacheKey(scriptPath: string, payload: unknown): string {
  return JSON.stringify({ scriptPath, payload });
}

function getCachedValue<T>(cacheKey: string, now: number): T | null {
  const cached = responseCache.get(cacheKey);
  if (!cached) {
    return null;
  }
  if (cached.expiresAt <= now) {
    responseCache.delete(cacheKey);
    return null;
  }
  return cached.value as T;
}

function setCachedValue(cacheKey: string, entry: CacheEntry): void {
  // Refresh recency by re-inserting at the end.
  responseCache.delete(cacheKey);
  responseCache.set(cacheKey, entry);
  while (responseCache.size > MAX_CACHE_ENTRIES) {
    const oldest = responseCache.keys().next().value;
    if (oldest === undefined) {
      break;
    }
    responseCache.delete(oldest);
  }
}

function formatProcessFailure(label: string, stderr: string, code: number | null): Error {
  const trimmedStderr = stderr.trim();
  if (!trimmedStderr) {
    return new Error(`Python ${label} process exited with code ${code}`);
  }

  const summary =
    trimmedStderr.length > 600
      ? `${trimmedStderr.slice(0, 600).trimEnd()}...`
      : trimmedStderr;
  return new Error(summary);
}

function buildTimeoutError(label: string, timeoutMs: number): Error {
  return new Error(`Python ${label} request timed out after ${timeoutMs}ms`);
}

function buildRemotePathError(label: string): Error {
  return new Error(`Python ${label} bridge is missing a remote service path`);
}

function buildUnsupportedRuntimeError(label: string): Error {
  if (process.env.VERCEL) {
    return new Error(
      `Python ${label} bridge is not configured for the Vercel Node runtime. ` +
        "Configure an external Python service before deploying these routes."
    );
  }

  return new Error(`Python ${label} bridge is unavailable in this runtime`);
}

function getPythonServiceBaseUrl(explicitBaseUrl?: string): string | null {
  return explicitBaseUrl ?? process.env.OPTIQAL_MODEL_URL ?? process.env.MODEL_URL ?? null;
}

function joinServiceUrl(baseUrl: string, remotePath: string): string {
  const normalizedPath = remotePath.replace(/^\/+/, "");
  const base = new URL(baseUrl);
  const baseWithSlash = new URL(base.toString());
  if (!baseWithSlash.pathname.endsWith("/")) {
    baseWithSlash.pathname = `${baseWithSlash.pathname}/`;
  }
  const resolved = new URL(normalizedPath, baseWithSlash);
  resolved.search = base.search;
  return resolved.toString();
}

function isVercelProtectionPage(rawText: string): boolean {
  return (
    rawText.includes("<title>Authentication Required</title>") ||
    rawText.includes("Vercel Authentication") ||
    rawText.includes("x-vercel-protection-bypass")
  );
}

async function runRemotePythonJson<T>({
  payload,
  label,
  parseResponse,
  timeoutMs,
  remotePath,
  remoteBaseUrl,
  remoteHeaders,
}: {
  payload: unknown;
  label: string;
  parseResponse: (value: unknown) => T | null;
  timeoutMs: number;
  remotePath?: string;
  remoteBaseUrl?: string;
  remoteHeaders?: Record<string, string | undefined>;
}): Promise<T> {
  const baseUrl = getPythonServiceBaseUrl(remoteBaseUrl);
  if (!baseUrl) {
    throw buildUnsupportedRuntimeError(label);
  }
  if (!remotePath) {
    throw buildRemotePathError(label);
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => {
    controller.abort();
  }, timeoutMs);

  try {
    const headers = new Headers({
      "Content-Type": "application/json",
    });
    for (const [key, value] of Object.entries(remoteHeaders ?? {})) {
      if (value) {
        headers.set(key, value);
      }
    }

    const response = await fetch(joinServiceUrl(baseUrl, remotePath), {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    const rawText = await response.text();
    if (isVercelProtectionPage(rawText)) {
      throw new Error(
        "Remote Python service is behind Vercel Deployment Protection. " +
          "Configure MODEL_PROTECTION_BYPASS_SECRET for cross-project model access."
      );
    }

    let parsedJson: unknown;
    try {
      parsedJson = JSON.parse(rawText);
    } catch {
      if (!response.ok) {
        throw new Error(
          rawText.trim() || `Python ${label} remote request failed with status ${response.status}`
        );
      }
      throw new Error(`Failed to parse ${label} JSON from remote Python service`);
    }

    if (!response.ok) {
      if (
        typeof parsedJson === "object" &&
        parsedJson !== null &&
        "error" in parsedJson &&
        typeof parsedJson.error === "string"
      ) {
        throw new Error(parsedJson.error);
      }
      if (
        typeof parsedJson === "object" &&
        parsedJson !== null &&
        "detail" in parsedJson &&
        typeof parsedJson.detail === "string"
      ) {
        throw new Error(parsedJson.detail);
      }
      throw new Error(`Python ${label} remote request failed with status ${response.status}`);
    }

    const parsedResponse = parseResponse(parsedJson);
    if (parsedResponse === null) {
      throw new Error(`Invalid ${label} response from Python service`);
    }

    return parsedResponse;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw buildTimeoutError(label, timeoutMs);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

export function clearPythonBridgeCaches(): void {
  responseCache.clear();
  inflightRequests.clear();
}

export async function runPythonJson<T>({
  payload,
  scriptPath,
  label,
  parseResponse,
  remotePath,
  remoteBaseUrl,
  remoteHeaders,
  timeoutMs = 30_000,
  cacheTtlMs = 0,
  cacheKey,
}: PythonJsonRunnerOptions<T>): Promise<T> {
  const resolvedCacheKey =
    cacheTtlMs > 0 ? (cacheKey ?? buildDefaultCacheKey(scriptPath, payload)) : null;
  const now = Date.now();

  if (resolvedCacheKey) {
    const cached = getCachedValue<T>(resolvedCacheKey, now);
    if (cached !== null) {
      return cached;
    }

    const inflight = inflightRequests.get(resolvedCacheKey);
    if (inflight) {
      return inflight as Promise<T>;
    }
  }

  const repoRoot = process.cwd();
  const pythonDir = path.join(repoRoot, "python");

  if (getPythonServiceBaseUrl(remoteBaseUrl)) {
    const requestPromise = runRemotePythonJson({
      payload,
      label,
      parseResponse,
      timeoutMs,
      remotePath,
      remoteBaseUrl,
      remoteHeaders,
    });

    if (!resolvedCacheKey) {
      return requestPromise;
    }

    inflightRequests.set(resolvedCacheKey, requestPromise);
    try {
      const result = await requestPromise;
      setCachedValue(resolvedCacheKey, {
        expiresAt: Date.now() + cacheTtlMs,
        value: result,
      });
      return result;
    } finally {
      inflightRequests.delete(resolvedCacheKey);
    }
  }

  const requestPromise = new Promise<T>((resolve, reject) => {
    if (process.env.VERCEL) {
      reject(buildUnsupportedRuntimeError(label));
      return;
    }

    const child = spawn("uv", ["run", "python", scriptPath], {
      cwd: pythonDir,
      stdio: ["pipe", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";
    let settled = false;

    const timeoutId = setTimeout(() => {
      child.kill("SIGTERM");
      setTimeout(() => {
        child.kill("SIGKILL");
      }, 1_000).unref();
      finish(() => {
        reject(buildTimeoutError(label, timeoutMs));
      });
    }, timeoutMs);
    timeoutId.unref();

    function finish(callback: () => void): void {
      if (settled) {
        return;
      }
      settled = true;
      clearTimeout(timeoutId);
      callback();
    }

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });

    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });

    child.on("error", (error) => {
      finish(() => {
        reject(error);
      });
    });

    child.on("close", (code) => {
      finish(() => {
        if (code !== 0) {
          reject(formatProcessFailure(label, stderr, code));
          return;
        }

        let parsedJson: unknown;
        try {
          parsedJson = JSON.parse(stdout);
        } catch (error) {
          reject(
            new Error(
              `Failed to parse ${label} JSON: ${
                error instanceof Error ? error.message : "unknown error"
              }`
            )
          );
          return;
        }

        const parsedResponse = parseResponse(parsedJson);
        if (parsedResponse === null) {
          reject(new Error(`Invalid ${label} response from Python bridge`));
          return;
        }

        resolve(parsedResponse);
      });
    });

    child.stdin.write(JSON.stringify(payload));
    child.stdin.end();
  });

  if (!resolvedCacheKey) {
    return requestPromise;
  }

  inflightRequests.set(resolvedCacheKey, requestPromise);

  try {
    const result = await requestPromise;
    setCachedValue(resolvedCacheKey, {
      expiresAt: Date.now() + cacheTtlMs,
      value: result,
    });
    return result;
  } finally {
    inflightRequests.delete(resolvedCacheKey);
  }
}
