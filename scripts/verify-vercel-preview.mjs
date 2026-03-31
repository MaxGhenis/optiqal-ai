#!/usr/bin/env node

import { execFileSync } from "node:child_process";

const modelProtectionBypassSecret =
  process.env.OPTIQAL_MODEL_BYPASS_SECRET ?? process.env.MODEL_PROTECTION_BYPASS_SECRET ?? "";

function runVercelCurl(
  path,
  deployment,
  extraArgs = [],
  cwd = process.cwd(),
  options = {}
) {
  const args = ["curl", path, "--deployment", deployment];
  if (options.protectionBypass) {
    args.push("--protection-bypass", options.protectionBypass);
  }
  args.push("--", "--silent", "--show-error", ...extraArgs);
  return execFileSync(
    "vercel",
    args,
    {
      cwd,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    }
  );
}

function assertIncludes(haystack, needle, label) {
  if (!haystack.includes(needle)) {
    throw new Error(`Expected ${label} to include "${needle}"`);
  }
}

function extractJson(output) {
  const start = output.indexOf("{");
  if (start === -1) {
    throw new Error("Expected JSON response body in vercel curl output");
  }
  return JSON.parse(output.slice(start));
}

function parseVerifiedJson(output, label) {
  const parsed = extractJson(output);
  if (
    parsed &&
    typeof parsed === "object" &&
    "error" in parsed &&
    typeof parsed.error === "string"
  ) {
    throw new Error(`${label} returned error: ${parsed.error}`);
  }
  return parsed;
}

function main() {
  const deployment = process.argv[2];
  const modelDeployment = process.argv[3];
  const modelCwd = process.argv[4] ?? process.cwd();
  if (!deployment) {
    console.error(
      "Usage: node scripts/verify-vercel-preview.mjs <frontend-deployment-url> [model-deployment-url] [model-cwd]"
    );
    process.exit(1);
  }

  const predictHtml = runVercelCurl("/predict", deployment);
  assertIncludes(
    predictHtml,
    "Project remaining life years and QALYs",
    "/predict HTML"
  );
  assertIncludes(predictHtml, "Activity level", "/predict HTML");

  if (modelDeployment) {
    if (!modelProtectionBypassSecret) {
      throw new Error(
        "Missing MODEL_PROTECTION_BYPASS_SECRET (or OPTIQAL_MODEL_BYPASS_SECRET) for preview verification"
      );
    }

    const modelHealthResponse = parseVerifiedJson(
      runVercelCurl("/health", modelDeployment, [], modelCwd, {
        protectionBypass: modelProtectionBypassSecret,
      }),
      "Model /health"
    );
    if (modelHealthResponse.status !== "ok") {
      throw new Error("Model service health check failed");
    }

    const modelBaselineResponse = parseVerifiedJson(
      runVercelCurl(
        "/baseline",
        modelDeployment,
        [
          "--request",
          "POST",
          "--header",
          "Content-Type: application/json",
          "--data",
          JSON.stringify({
            profile: {
              age: 35,
              sex: "female",
              weight_kg: 65,
              height_cm: 165,
              smoker: false,
              has_diabetes: false,
              has_hypertension: false,
              activity_level: "light",
              sleep_hours_per_night: 7,
            },
          }),
        ],
        modelCwd,
        {
          protectionBypass: modelProtectionBypassSecret,
        }
      ),
      "Model /baseline"
    );
    if (
      typeof modelBaselineResponse.point_estimate?.expected_death_age !== "number" ||
      modelBaselineResponse.point_estimate.expected_death_age < 88 ||
      modelBaselineResponse.point_estimate.expected_death_age > 96
    ) {
      throw new Error(
        `Model baseline returned unexpected expected_death_age=${modelBaselineResponse.point_estimate?.expected_death_age}`
      );
    }
  }

  const baselineResponse = parseVerifiedJson(
    runVercelCurl("/api/baseline", deployment, [
      "--request",
      "POST",
      "--header",
      "Content-Type: application/json",
      "--data",
      JSON.stringify({
        profile: {
          age: 35,
          sex: "female",
          weight_kg: 65,
          height_cm: 165,
          smoker: false,
          has_diabetes: false,
          has_hypertension: false,
          activity_level: "light",
          sleep_hours_per_night: 7,
        },
      }),
    ]),
    "Frontend /api/baseline"
  );

  if (
    typeof baselineResponse.point_estimate?.expected_death_age !== "number" ||
    baselineResponse.point_estimate.expected_death_age < 88 ||
    baselineResponse.point_estimate.expected_death_age > 96
  ) {
    throw new Error(
      `Baseline preview response returned unexpected expected_death_age=${baselineResponse.point_estimate?.expected_death_age}`
    );
  }

  const frontierResponse = parseVerifiedJson(
    runVercelCurl("/api/frontier", deployment, [
      "--request",
      "POST",
      "--header",
      "Content-Type: application/json",
      "--data",
      JSON.stringify({
        profile: {
          age: 39,
          sex: "male",
          weight_kg: 74.8,
          height_cm: 178,
          smoker: false,
          has_diabetes: false,
          has_hypertension: false,
          activity_level: "active",
          sleep_hours_per_night: 7,
        },
        sleep_metrics: {
          duration_hours: 6.8,
          breathing_score: 0.78,
          spo2: 95.1,
          snore_pct: 3.2,
        },
        n_simulations: 500,
      }),
    ]),
    "Frontend /api/frontier"
  );

  if (
    frontierResponse.meta?.selection_mode !== "ordered_by_marginal_cost_per_qaly" ||
    !Array.isArray(frontierResponse.items) ||
    frontierResponse.items.length === 0 ||
    !Array.isArray(frontierResponse.frontier)
  ) {
    throw new Error("Frontier preview response did not match the expected contract");
  }

  console.log(`Preview verification passed for ${deployment}`);
}

main();
