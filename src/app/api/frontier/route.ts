import { NextRequest, NextResponse } from "next/server";
import type { FrontierRequest, FrontierResponse } from "@/lib/frontier-types";
import { parseFrontierRequest, parseFrontierResponse } from "@/lib/frontier-contract";
import { getRemoteModelBaseUrl, getRemoteModelHeaders } from "@/lib/model-service";
import { runPythonJson } from "@/lib/python-bridge";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const FRONTIER_TIMEOUT_MS = 45_000;
const FRONTIER_CACHE_TTL_MS = process.env.NODE_ENV === "production" ? 60_000 : 5_000;

async function runPythonFrontier(
  payload: FrontierRequest,
  request: NextRequest
): Promise<FrontierResponse> {
  const remoteBaseUrl = getRemoteModelBaseUrl(request.nextUrl.origin);
  return runPythonJson({
    payload,
    scriptPath: "scripts/web_frontier.py",
    label: "frontier",
    parseResponse: parseFrontierResponse,
    remotePath: "/frontier",
    remoteBaseUrl,
    remoteHeaders: getRemoteModelHeaders(request.headers, {
      remoteBaseUrl,
      requestOrigin: request.nextUrl.origin,
    }),
    timeoutMs: FRONTIER_TIMEOUT_MS,
    cacheTtlMs: FRONTIER_CACHE_TTL_MS,
  });
}

export async function POST(request: NextRequest) {
  try {
    const body: unknown = await request.json();
    const payload = parseFrontierRequest(body);

    if (!payload) {
      return NextResponse.json(
        { error: "Invalid request body for frontier analysis" },
        { status: 400 }
      );
    }

    const result = await runPythonFrontier(payload, request);
    return NextResponse.json(result);
  } catch (error) {
    console.error("Error in /api/frontier:", error);
    return NextResponse.json(
      {
        error:
          error instanceof Error
            ? error.message
            : "Failed to run frontier analysis",
      },
      { status: 500 }
    );
  }
}
