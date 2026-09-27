#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import path from "node:path";
import { assertDeployableCheckout } from "./deploy-guard.mjs";

const projectRoot = process.cwd();
const frontendProjectName = "optiqal-ai";
const modelProjectName = "optiqal-model";
const scope = "max-ghenis-projects";
const mode = process.argv[2] === "production" ? "production" : "preview";
const isProduction = mode === "production";
const modelProtectionBypassSecret =
  process.env.OPTIQAL_MODEL_BYPASS_SECRET ?? process.env.MODEL_PROTECTION_BYPASS_SECRET ?? "";

function run(command, args, cwd = projectRoot) {
  return execFileSync(command, args, {
    cwd,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  }).trim();
}

function requireModelProtectionBypassSecret() {
  if (!modelProtectionBypassSecret) {
    throw new Error(
      "Missing MODEL_PROTECTION_BYPASS_SECRET (or OPTIQAL_MODEL_BYPASS_SECRET). " +
        "Cross-project Vercel model deployments require an explicit protection bypass secret."
    );
  }
  return modelProtectionBypassSecret;
}

function ensureModelProjectExists() {
  try {
    run("vercel", ["project", "inspect", modelProjectName, "--scope", scope]);
  } catch {
    run("vercel", ["project", "add", modelProjectName, "--scope", scope]);
  }
}

function ensureModelProjectLinked(modelCwd) {
  run("vercel", ["link", "--yes", "--project", modelProjectName, "--scope", scope], modelCwd);
}

function ensureFrontendProjectLinked() {
  run("vercel", ["link", "--yes", "--project", frontendProjectName, "--scope", scope]);
}

function deploymentUrlFromOutput(output) {
  try {
    const parsed = JSON.parse(output);
    const candidate = parsed.url ?? parsed.deployment?.url ?? parsed.deploymentUrl;
    if (typeof candidate === "string" && candidate.length > 0) {
      return candidate.startsWith("http") ? candidate : `https://${candidate}`;
    }
  } catch {
    // Fall through to support CLI versions that emit JSON progress lines.
  }

  const absoluteUrl = output.match(/https:\/\/[^\s"']+\.vercel\.app/);
  if (absoluteUrl) return absoluteUrl[0];
  const hostname = output.match(/[a-z0-9-]+\.vercel\.app/i);
  return hostname ? `https://${hostname[0]}` : undefined;
}

function deployModel(modelCwd) {
  const deployArgs = ["deploy", "--yes", "--scope", scope, "--format", "json"];
  if (isProduction) {
    deployArgs.push("--prod");
  }
  return deploymentUrlFromOutput(run("vercel", deployArgs, modelCwd));
}

function inspectDeploymentJson(url, cwd = projectRoot) {
  return JSON.parse(run("vercel", ["inspect", url, "--scope", scope, "--json"], cwd));
}

function getProductionModelAlias(modelUrl, modelCwd) {
  const deployment = inspectDeploymentJson(modelUrl, modelCwd);
  const aliases = Array.isArray(deployment.aliases) ? deployment.aliases : [];
  const preferredAlias =
    aliases.find((alias) => alias === `${modelProjectName}.vercel.app`) ?? aliases[0];

  return preferredAlias ? `https://${preferredAlias}` : modelUrl;
}

function deployFrontend(modelUrl, runtimeModelUrl = modelUrl) {
  const deployArgs = [
    "deploy",
    "--yes",
    "--scope",
    scope,
    "--format",
    "json",
    "-b",
    `MODEL_URL=${runtimeModelUrl}`,
    "-e",
    `MODEL_URL=${runtimeModelUrl}`,
  ];
  if (modelProtectionBypassSecret) {
    // Runtime-only: the bridge reads this when calling the protected model
    // service. Never pass it as a build var (-b) — build env is echoed in
    // build logs and baked into the build cache.
    deployArgs.push(
      "-e",
      `MODEL_PROTECTION_BYPASS_SECRET=${modelProtectionBypassSecret}`
    );
  }
  if (isProduction) {
    deployArgs.push("--prod");
  }
  return deploymentUrlFromOutput(run("vercel", deployArgs, projectRoot));
}

function main() {
  // Refuse before building or uploading anything: a deployment must come from a
  // clean checkout of a commit already on origin/main.
  const commit = assertDeployableCheckout(projectRoot);

  if (!isProduction) {
    requireModelProtectionBypassSecret();
  }

  const modelCwd = run("node", ["scripts/prepare-model-deploy.mjs"], projectRoot);

  ensureModelProjectExists();
  ensureModelProjectLinked(modelCwd);
  ensureFrontendProjectLinked();

  const modelUrl = deployModel(modelCwd);
  if (!modelUrl) {
    throw new Error("Failed to determine model deployment URL");
  }

  const runtimeModelUrl = isProduction ? getProductionModelAlias(modelUrl, modelCwd) : modelUrl;

  const frontendUrl = deployFrontend(modelUrl, runtimeModelUrl);
  if (!frontendUrl) {
    throw new Error("Failed to determine frontend deployment URL");
  }

  run(
    "node",
    ["scripts/verify-vercel-preview.mjs", frontendUrl, modelUrl, path.resolve(modelCwd)],
    projectRoot
  );

  console.log(
    JSON.stringify(
      {
        mode,
        commit,
        modelUrl,
        runtimeModelUrl,
        frontendUrl,
      },
      null,
      2
    )
  );
}

main();
