#!/usr/bin/env node

import { cpSync, existsSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";

const projectRoot = process.cwd();
const deployRoot = path.join(projectRoot, ".model-service");

function resetDirectory(dir) {
  rmSync(dir, { force: true, recursive: true });
  mkdirSync(dir, { recursive: true });
}

function copyIntoDeployRoot(relativeSourcePath, relativeDestPath = relativeSourcePath) {
  cpSync(
    path.join(projectRoot, relativeSourcePath),
    path.join(deployRoot, relativeDestPath),
    {
      dereference: true,
      recursive: true,
    }
  );
}

function removePath(relativePath) {
  const targetPath = path.join(deployRoot, relativePath);
  if (existsSync(targetPath)) {
    rmSync(targetPath, { force: true, recursive: true });
  }
}

function main() {
  resetDirectory(deployRoot);

  mkdirSync(path.join(deployRoot, "api"), { recursive: true });
  copyIntoDeployRoot("backend/index.py", "api/index.py");
  copyIntoDeployRoot("backend/main.py", "main.py");
  copyIntoDeployRoot("backend/requirements.txt", "requirements.txt");
  copyIntoDeployRoot("python/optiqal", "optiqal");
  writeFileSync(
    path.join(deployRoot, "vercel.json"),
    JSON.stringify(
      {
        $schema: "https://openapi.vercel.sh/vercel.json",
        rewrites: [
          { source: "/health", destination: "/api/index.py" },
          { source: "/baseline", destination: "/api/index.py" },
          { source: "/frontier", destination: "/api/index.py" },
        ],
      },
      null,
      2
    )
  );

  removePath("optiqal/__pycache__");
  removePath("optiqal/tests");

  console.log(deployRoot);
}

main();
