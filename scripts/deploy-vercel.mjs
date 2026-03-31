#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import path from "node:path";

const projectRoot = process.cwd();
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

function deployModel(modelCwd) {
  const deployArgs = ["deploy", "--yes", "--scope", scope];
  if (isProduction) {
    deployArgs.push("--prod");
  }
  return run("vercel", deployArgs, modelCwd)
    .split("\n")
    .map((line) => line.trim())
    .find((line) => line.startsWith("https://"));
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
  const bypassSecret = requireModelProtectionBypassSecret();
  const deployArgs = [
    "deploy",
    "--yes",
    "--scope",
    scope,
    "-b",
    `MODEL_URL=${runtimeModelUrl}`,
    "-e",
    `MODEL_URL=${runtimeModelUrl}`,
    "-b",
    `MODEL_PROTECTION_BYPASS_SECRET=${bypassSecret}`,
    "-e",
    `MODEL_PROTECTION_BYPASS_SECRET=${bypassSecret}`,
  ];
  if (isProduction) {
    deployArgs.push("--prod");
  }
  return run("vercel", deployArgs, projectRoot)
    .split("\n")
    .map((line) => line.trim())
    .find((line) => line.startsWith("https://"));
}

function main() {
  requireModelProtectionBypassSecret();

  const modelCwd = run("node", ["scripts/prepare-model-deploy.mjs"], projectRoot);

  ensureModelProjectExists();
  ensureModelProjectLinked(modelCwd);

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
