import { execFileSync } from "node:child_process";

// Every served number must be a function of a pushed commit on main. The
// deploy script calls this before building or uploading anything, so a
// deployment can only come from a clean checkout of a commit that
// origin/main already contains.

function git(args, cwd) {
  return execFileSync("git", args, {
    cwd,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  }).trimEnd();
}

function stderrOf(error) {
  const stderr = error?.stderr;
  return typeof stderr === "string" ? stderr.trim() : String(stderr ?? "").trim();
}

/**
 * Throw unless `cwd` is a clean checkout of a commit on `<remote>/<branch>`.
 *
 * Clean means `git status --porcelain --untracked-files=all` prints nothing:
 * no staged, modified, deleted or untracked files. Ignored files (.vercel/,
 * node_modules/, .model-service/) do not count.
 *
 * On `<remote>/<branch>` means HEAD is that branch's tip or one of its
 * ancestors, after fetching the branch so a stale remote-tracking ref cannot
 * decide the answer.
 *
 * @returns {string} the full SHA being deployed
 */
export function assertDeployableCheckout(cwd, { remote = "origin", branch = "main" } = {}) {
  const status = git(["status", "--porcelain", "--untracked-files=all"], cwd);
  if (status) {
    throw new Error(
      "Refusing to deploy: the working tree is dirty. Commit and merge these " +
        `changes to ${remote}/${branch} first:\n${status}`
    );
  }

  const trackingRef = `refs/remotes/${remote}/${branch}`;
  try {
    git(["fetch", "--quiet", remote, `+refs/heads/${branch}:${trackingRef}`], cwd);
  } catch (error) {
    throw new Error(
      `Refusing to deploy: could not fetch ${remote}/${branch} to confirm the ` +
        `commit is on it.\n${stderrOf(error)}`
    );
  }

  const head = git(["rev-parse", "--verify", "HEAD^{commit}"], cwd);
  try {
    git(["merge-base", "--is-ancestor", head, trackingRef], cwd);
  } catch (error) {
    if (error?.status === 1) {
      throw new Error(
        `Refusing to deploy: HEAD ${head} is not on ${remote}/${branch}. ` +
          `Merge it to ${branch} and deploy from there.`
      );
    }
    throw new Error(
      `Refusing to deploy: could not compare HEAD with ${remote}/${branch}.\n` +
        stderrOf(error)
    );
  }

  return head;
}
