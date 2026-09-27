// @vitest-environment node
import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { assertDeployableCheckout } from "./deploy-guard.mjs";

// Real git repositories in a temp directory: a bare "origin", a checkout that
// deploys, and a second clone standing in for someone else pushing to main.

const gitEnv = {
  ...process.env,
  GIT_CONFIG_GLOBAL: "/dev/null",
  GIT_CONFIG_NOSYSTEM: "1",
  GIT_AUTHOR_NAME: "Deploy Guard Test",
  GIT_AUTHOR_EMAIL: "deploy-guard@example.invalid",
  GIT_COMMITTER_NAME: "Deploy Guard Test",
  GIT_COMMITTER_EMAIL: "deploy-guard@example.invalid",
};

function git(cwd, ...args) {
  return execFileSync("git", args, {
    cwd,
    env: gitEnv,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  }).trim();
}

function commitFile(cwd, name, contents) {
  writeFileSync(path.join(cwd, name), contents);
  git(cwd, "add", name);
  git(cwd, "commit", "--quiet", "--no-gpg-sign", "-m", `Write ${name}`);
  return git(cwd, "rev-parse", "HEAD");
}

let root;
let origin;
let checkout;

beforeEach(() => {
  root = mkdtempSync(path.join(tmpdir(), "deploy-guard-"));
  origin = path.join(root, "origin.git");
  checkout = path.join(root, "checkout");
  git(root, "init", "--quiet", "--bare", "--initial-branch=main", origin);
  git(root, "clone", "--quiet", origin, checkout);
  git(checkout, "symbolic-ref", "HEAD", "refs/heads/main");
  writeFileSync(path.join(checkout, ".gitignore"), ".vercel/\n");
  git(checkout, "add", ".gitignore");
  git(checkout, "commit", "--quiet", "--no-gpg-sign", "-m", "Ignore .vercel");
  commitFile(checkout, "app.txt", "one\n");
  git(checkout, "push", "--quiet", "origin", "main");
});

afterEach(() => {
  rmSync(root, { recursive: true, force: true });
});

// Each case spawns a dozen git processes; allow for a slow CI runner.
describe("assertDeployableCheckout", { timeout: 30_000 }, () => {
  it("returns the SHA of a clean checkout at origin/main", () => {
    expect(assertDeployableCheckout(checkout)).toBe(git(checkout, "rev-parse", "HEAD"));
  });

  it("accepts an older commit that origin/main contains", () => {
    const older = git(checkout, "rev-parse", "HEAD~1");
    git(checkout, "checkout", "--quiet", "--detach", older);
    expect(assertDeployableCheckout(checkout)).toBe(older);
  });

  it("ignores gitignored files such as .vercel/", () => {
    mkdirSync(path.join(checkout, ".vercel"));
    writeFileSync(path.join(checkout, ".vercel", "project.json"), "{}\n");
    expect(() => assertDeployableCheckout(checkout)).not.toThrow();
  });

  it("refuses a modified tracked file", () => {
    writeFileSync(path.join(checkout, "app.txt"), "edited\n");
    expect(() => assertDeployableCheckout(checkout)).toThrow(/working tree is dirty[\s\S]*app\.txt/);
  });

  it("refuses a staged change", () => {
    writeFileSync(path.join(checkout, "app.txt"), "staged\n");
    git(checkout, "add", "app.txt");
    expect(() => assertDeployableCheckout(checkout)).toThrow(/working tree is dirty/);
  });

  it("refuses an untracked file", () => {
    mkdirSync(path.join(checkout, "src"));
    writeFileSync(path.join(checkout, "src", "new.ts"), "export {};\n");
    expect(() => assertDeployableCheckout(checkout)).toThrow(/working tree is dirty[\s\S]*src\/new\.ts/);
  });

  it("refuses a local commit that origin/main does not contain", () => {
    const local = commitFile(checkout, "app.txt", "unpushed\n");
    expect(() => assertDeployableCheckout(checkout)).toThrow(
      new RegExp(`HEAD ${local} is not on origin/main`)
    );
  });

  it("refuses a commit on another pushed branch", () => {
    git(checkout, "checkout", "--quiet", "-b", "feature");
    commitFile(checkout, "app.txt", "feature\n");
    git(checkout, "push", "--quiet", "origin", "feature");
    expect(() => assertDeployableCheckout(checkout)).toThrow(/is not on origin\/main/);
  });

  it("fetches main, so a commit pushed from elsewhere is accepted", () => {
    const other = path.join(root, "other");
    git(root, "clone", "--quiet", "--branch", "main", origin, other);
    const pushed = commitFile(other, "app.txt", "from another clone\n");
    git(other, "push", "--quiet", "origin", "main");

    // The deploying checkout has the commit, but its origin/main ref is stale
    // until the guard fetches.
    git(checkout, "fetch", "--quiet", "origin", "+refs/heads/main:refs/heads/incoming");
    git(checkout, "update-ref", "refs/remotes/origin/main", git(checkout, "rev-parse", "HEAD"));
    expect(git(checkout, "rev-parse", "refs/remotes/origin/main")).not.toBe(pushed);
    git(checkout, "checkout", "--quiet", "--detach", pushed);

    expect(assertDeployableCheckout(checkout)).toBe(pushed);
    expect(git(checkout, "rev-parse", "refs/remotes/origin/main")).toBe(pushed);
  });

  it("refuses when origin cannot be fetched", () => {
    git(checkout, "remote", "set-url", "origin", path.join(root, "missing.git"));
    expect(() => assertDeployableCheckout(checkout)).toThrow(/could not fetch origin\/main/);
  });
});
