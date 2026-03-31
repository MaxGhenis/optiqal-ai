import { NextRequest, NextResponse } from "next/server";
import type { BaselineRequest, BaselineResponse } from "@/lib/baseline-types";
import { parseBaselineRequest, parseBaselineResponse } from "@/lib/baseline-contract";
import { getRemoteModelBaseUrl, getRemoteModelHeaders } from "@/lib/model-service";
import { runPythonJson } from "@/lib/python-bridge";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BASELINE_TIMEOUT_MS = 20_000;
const BASELINE_CACHE_TTL_MS = process.env.NODE_ENV === "production" ? 60_000 : 5_000;

async function runPythonBaseline(
  payload: BaselineRequest,
  request: NextRequest
): Promise<BaselineResponse> {
  const remoteBaseUrl = getRemoteModelBaseUrl(request.nextUrl.origin);
  return runPythonJson({
    payload,
    scriptPath: "scripts/web_baseline.py",
    label: "baseline",
    parseResponse: parseBaselineResponse,
    remotePath: "/baseline",
    remoteBaseUrl,
    remoteHeaders: getRemoteModelHeaders(request.headers, {
      remoteBaseUrl,
      requestOrigin: request.nextUrl.origin,
    }),
    timeoutMs: BASELINE_TIMEOUT_MS,
    cacheTtlMs: BASELINE_CACHE_TTL_MS,
  });
}

export async function POST(request: NextRequest) {
  try {
    const body: unknown = await request.json();
    const payload = parseBaselineRequest(body);

    if (!payload) {
      return NextResponse.json(
        { error: "Invalid request body for baseline analysis" },
        { status: 400 }
      );
    }

    const result = await runPythonBaseline(payload, request);
    return NextResponse.json(result);
  } catch (error) {
    console.error("Error in /api/baseline:", error);
    return NextResponse.json(
      {
        error:
          error instanceof Error
            ? error.message
            : "Failed to run baseline analysis",
      },
      { status: 500 }
    );
  }
}
