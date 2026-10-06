import { EventEmitter } from "node:events";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { spawnMock } = vi.hoisted(() => ({
  spawnMock: vi.fn(),
}));

vi.mock("node:child_process", () => ({
  spawn: spawnMock,
  default: {
    spawn: spawnMock,
  },
}));

import {
  clearPythonBridgeCaches,
  PythonBridgeClientError,
  runPythonJson,
} from "@/lib/python-bridge";

interface FakeChildProcess extends EventEmitter {
  stdout: EventEmitter;
  stderr: EventEmitter;
  stdin: {
    write: ReturnType<typeof vi.fn>;
    end: ReturnType<typeof vi.fn>;
  };
  kill: ReturnType<typeof vi.fn>;
}

function createFakeChildProcess(): FakeChildProcess {
  const child = new EventEmitter() as FakeChildProcess;
  child.stdout = new EventEmitter();
  child.stderr = new EventEmitter();
  child.stdin = {
    write: vi.fn(),
    end: vi.fn(),
  };
  child.kill = vi.fn();
  return child;
}

describe("python bridge", () => {
  beforeEach(() => {
    clearPythonBridgeCaches();
    spawnMock.mockReset();
    vi.useRealTimers();
    vi.unstubAllGlobals();
    delete process.env.MODEL_URL;
    delete process.env.OPTIQAL_MODEL_URL;
    delete process.env.VERCEL;
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("dedupes in-flight requests and serves cached responses", async () => {
    const child = createFakeChildProcess();
    spawnMock.mockReturnValue(child);

    const options = {
      payload: { profile: { age: 39 } },
      scriptPath: "scripts/web_frontier.py",
      label: "frontier",
      parseResponse: (value: unknown) =>
        typeof value === "object" && value !== null ? (value as { ok: boolean }) : null,
      cacheTtlMs: 1_000,
      cacheKey: "frontier-age-39",
      timeoutMs: 1_000,
    };

    const first = runPythonJson(options);
    const second = runPythonJson(options);

    expect(spawnMock).toHaveBeenCalledTimes(1);

    child.stdout.emit("data", Buffer.from('{"ok":true}'));
    child.emit("close", 0);

    await expect(Promise.all([first, second])).resolves.toEqual([
      { ok: true },
      { ok: true },
    ]);

    const third = await runPythonJson(options);
    expect(third).toEqual({ ok: true });
    expect(spawnMock).toHaveBeenCalledTimes(1);
  });

  it("evicts the oldest entry once the cache cap is exceeded", async () => {
    // The cap is 500 (MAX_CACHE_ENTRIES). Fill it with 501 distinct payloads,
    // which evicts the very first; then re-request the first and confirm it
    // re-fetches (was evicted), while the newest is still served from cache.
    process.env.MODEL_URL = "https://model.example/svc/model";
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      text: vi.fn().mockResolvedValue('{"ok":true}'),
    });
    vi.stubGlobal("fetch", fetchMock);

    const run = (n: number) =>
      runPythonJson({
        payload: { n },
        scriptPath: "scripts/web_frontier.py",
        remotePath: "/frontier",
        label: "frontier",
        parseResponse: (value: unknown) =>
          typeof value === "object" && value !== null
            ? (value as { ok: boolean })
            : null,
        cacheTtlMs: 10_000,
        cacheKey: `fixture-${n}`,
        timeoutMs: 1_000,
      });

    // 0 is the oldest; 1..500 fill the cache to the cap and evict 0.
    for (let n = 0; n <= 500; n++) {
      await run(n);
    }
    expect(fetchMock).toHaveBeenCalledTimes(501);

    // 0 was evicted -> re-fetch.
    await run(0);
    expect(fetchMock).toHaveBeenCalledTimes(502);

    // 500 is the newest -> still cached, no re-fetch.
    await run(500);
    expect(fetchMock).toHaveBeenCalledTimes(502);
  });

  it("does not retain personalized responses without an explicit cache key", async () => {
    process.env.MODEL_URL = "https://model.example/svc/model";
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: vi.fn().mockResolvedValue('{"ok":true}'),
    });
    vi.stubGlobal("fetch", fetchMock);

    const options = {
      payload: { profile: { age: 39, has_diabetes: true } },
      scriptPath: "scripts/web_frontier.py",
      remotePath: "/frontier",
      label: "frontier",
      parseResponse: (value: unknown) =>
        typeof value === "object" && value !== null ? (value as { ok: boolean }) : null,
      cacheTtlMs: 10_000,
      timeoutMs: 1_000,
    };

    await runPythonJson(options);
    await runPythonJson(options);

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("classifies current-stack ValueErrors from the local bridge as client errors", async () => {
    const child = createFakeChildProcess();
    spawnMock.mockReturnValue(child);

    const request = runPythonJson({
      payload: { profile: { age: 39 }, current_stack_ids: ["removed-item"] },
      scriptPath: "scripts/web_frontier.py",
      label: "frontier",
      parseResponse: (value: unknown) =>
        typeof value === "object" && value !== null ? (value as { ok: boolean }) : null,
      timeoutMs: 1_000,
    });

    child.stderr.emit(
      "data",
      Buffer.from(
        'Traceback (most recent call last):\n  File "web_frontier.py", line 14\nValueError: current_stack_ids contains an unknown catalog ID\n'
      )
    );
    child.emit("close", 1);

    await expect(request).rejects.toBeInstanceOf(PythonBridgeClientError);
  });

  it("does not misclassify unrelated backend ValueErrors as client errors", async () => {
    const child = createFakeChildProcess();
    spawnMock.mockReturnValue(child);

    const request = runPythonJson({
      payload: { profile: { age: 39 } },
      scriptPath: "scripts/web_frontier.py",
      label: "frontier",
      parseResponse: (value: unknown) =>
        typeof value === "object" && value !== null ? (value as { ok: boolean }) : null,
      timeoutMs: 1_000,
    }).catch((error: unknown) => error);

    child.stderr.emit(
      "data",
      Buffer.from("Traceback (most recent call last):\nValueError: internal model invariant\n")
    );
    child.emit("close", 1);

    const error = await request;
    expect(error).toBeInstanceOf(Error);
    expect(error).not.toBeInstanceOf(PythonBridgeClientError);
  });

  it("classifies remote validation responses as client errors", async () => {
    process.env.MODEL_URL = "https://model.example/svc/model";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        text: vi.fn().mockResolvedValue('{"detail":"invalid request"}'),
      })
    );

    const request = runPythonJson({
      payload: { profile: { age: 39 } },
      scriptPath: "scripts/web_frontier.py",
      remotePath: "/frontier",
      label: "frontier",
      parseResponse: (value: unknown) =>
        typeof value === "object" && value !== null ? (value as { ok: boolean }) : null,
      timeoutMs: 1_000,
    });

    await expect(request).rejects.toBeInstanceOf(PythonBridgeClientError);
  });

  it("times out long-running processes and kills them", async () => {
    vi.useFakeTimers();

    const child = createFakeChildProcess();
    spawnMock.mockReturnValue(child);

    const request = runPythonJson({
      payload: { profile: { age: 39 } },
      scriptPath: "scripts/web_frontier.py",
      label: "frontier",
      parseResponse: (value: unknown) =>
        typeof value === "object" && value !== null ? (value as { ok: boolean }) : null,
      timeoutMs: 100,
    });
    const handledRequest = request.catch((error: unknown) => error);

    await vi.advanceTimersByTimeAsync(100);

    const error = await handledRequest;
    expect(error).toBeInstanceOf(Error);
    expect((error as Error).message).toBe("Python frontier request timed out after 100ms");
    expect(child.kill).toHaveBeenCalledWith("SIGTERM");
  });

  it("uses the remote model service when MODEL_URL is configured", async () => {
    process.env.MODEL_URL = "https://model.example/svc/model";

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      text: vi.fn().mockResolvedValue('{"ok":true}'),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await runPythonJson({
      payload: { profile: { age: 39 } },
      scriptPath: "scripts/web_frontier.py",
      remotePath: "/frontier",
      label: "frontier",
      parseResponse: (value: unknown) =>
        typeof value === "object" && value !== null ? (value as { ok: boolean }) : null,
      remoteHeaders: {
        "x-vercel-protection-bypass": "bypass-secret",
      },
      timeoutMs: 1_000,
    });

    expect(result).toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledWith(
      "https://model.example/svc/model/frontier",
      expect.objectContaining({
        headers: expect.any(Headers),
        method: "POST",
      })
    );
    const requestHeaders = fetchMock.mock.calls[0]?.[1]?.headers;
    expect(requestHeaders).toBeInstanceOf(Headers);
    expect(requestHeaders.get("x-vercel-protection-bypass")).toBe("bypass-secret");
    expect(spawnMock).not.toHaveBeenCalled();
  });

  it("preserves MODEL_URL query params for shareable preview backends", async () => {
    process.env.MODEL_URL = "https://model.example/svc/model?_vercel_share=preview-token";

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      text: vi.fn().mockResolvedValue('{"ok":true}'),
    });
    vi.stubGlobal("fetch", fetchMock);

    await runPythonJson({
      payload: { profile: { age: 39 } },
      scriptPath: "scripts/web_frontier.py",
      remotePath: "/frontier",
      label: "frontier",
      parseResponse: (value: unknown) =>
        typeof value === "object" && value !== null ? (value as { ok: boolean }) : null,
      timeoutMs: 1_000,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "https://model.example/svc/model/frontier?_vercel_share=preview-token",
      expect.objectContaining({
        headers: expect.any(Headers),
        method: "POST",
      })
    );
  });

  it("fails fast on Vercel runtimes without a configured Python service", async () => {
    process.env.VERCEL = "1";

    const request = runPythonJson({
      payload: { profile: { age: 39 } },
      scriptPath: "scripts/web_frontier.py",
      label: "frontier",
      parseResponse: (value: unknown) =>
        typeof value === "object" && value !== null ? (value as { ok: boolean }) : null,
      timeoutMs: 1_000,
    });

    await expect(request).rejects.toThrow(
      "Python frontier bridge is not configured for the Vercel Node runtime"
    );
    expect(spawnMock).not.toHaveBeenCalled();
  });

  it("fails clearly when the remote service returns a Vercel auth page", async () => {
    process.env.MODEL_URL = "https://model.example/svc/model";

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      text: vi.fn().mockResolvedValue(
        "<!doctype html><title>Authentication Required</title><body>Vercel Authentication</body>"
      ),
    });
    vi.stubGlobal("fetch", fetchMock);

    const request = runPythonJson({
      payload: { profile: { age: 39 } },
      scriptPath: "scripts/web_frontier.py",
      remotePath: "/frontier",
      label: "frontier",
      parseResponse: (value: unknown) =>
        typeof value === "object" && value !== null ? (value as { ok: boolean }) : null,
      timeoutMs: 1_000,
    });

    await expect(request).rejects.toThrow("MODEL_PROTECTION_BYPASS_SECRET");
  });
});
