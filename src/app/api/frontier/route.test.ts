import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const { runPythonJsonMock } = vi.hoisted(() => ({
  runPythonJsonMock: vi.fn(),
}));

vi.mock("@/lib/python-bridge", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/python-bridge")>();
  return {
    ...actual,
    runPythonJson: runPythonJsonMock,
  };
});

import { POST } from "@/app/api/frontier/route";
import { PythonBridgeClientError } from "@/lib/python-bridge";

const validRequest = {
  profile: {
    age: 39,
    sex: "male",
    weight_kg: 75,
    height_cm: 175,
    smoker: false,
    has_diabetes: false,
    has_hypertension: false,
    activity_level: "light",
  },
  current_stack_ids: ["removed_catalog_item"],
};

function requestFor(body: unknown): NextRequest {
  return new NextRequest("http://localhost/api/frontier", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

describe("POST /api/frontier", () => {
  beforeEach(() => {
    runPythonJsonMock.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns 400 for a semantic current-stack validation error", async () => {
    runPythonJsonMock.mockRejectedValueOnce(
      new PythonBridgeClientError("current_stack_ids contains an unknown catalog ID")
    );

    const response = await POST(requestFor(validRequest));

    expect(response.status).toBe(400);
    expect(runPythonJsonMock.mock.calls[0]?.[0]).not.toHaveProperty("cacheTtlMs");
    await expect(response.json()).resolves.toEqual({
      error: "Current routine is invalid. Clear or update it and try again.",
    });
  });

  it("keeps unexpected bridge failures as sanitized server errors", async () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    runPythonJsonMock.mockRejectedValueOnce(
      new Error("Traceback: /private/server/path and implementation detail")
    );

    const response = await POST(requestFor(validRequest));

    expect(response.status).toBe(500);
    await expect(response.json()).resolves.toEqual({
      error: "Failed to run frontier analysis",
    });
  });

  it("rejects malformed request bodies before invoking the model", async () => {
    const response = await POST(requestFor({ profile: { age: 39 } }));

    expect(response.status).toBe(400);
    expect(runPythonJsonMock).not.toHaveBeenCalled();
  });
});
