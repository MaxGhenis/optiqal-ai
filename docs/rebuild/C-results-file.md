# PR C: kernels and the results file

You are building PR C of the Optiqal rebuild. Worktree: `/Users/maxghenis/optiqal-ai-rebuild-c`,
branch `rebuild/c-results-file`, branched from `rebuild/one-engine` after PRs A, E, D, B, I
and S landed. Read, in order: `REBUILD.md`, `docs/rebuild/graph-interface.md` and its lock,
`docs/rebuild/graph-acceptance.md`, the notes sections PRs A, B, D, E and I appended to
`REBUILD.md`, `python/optiqal/graph/` (all of it), `python/tests/test_graph_acceptance_*.py`
(the red properties you are flipping; you never edit them), `python/optiqal/simulate.py`,
`lifecycle.py`, `confounding.py`, `priors.py`, `qol_evidence.py`, `evidence.py`,
`ratchets.py`, `snapshots.py`, `precompute.py`, `profile.py`, `web_api.py`
(`build_frontier_response_with_policy` and the lanes it applies), `data/public_policy_lanes.json`,
`data/predeclared_ranges_v1.json`, `public_frontier_benchmark.py`,
`src/app/api/frontier/route.ts`, `src/lib/frontier-types.ts`, `src/lib/frontier-contract.ts`,
`src/components/analyze/frontier-workbench.tsx`, and `/Users/maxghenis/whatnut/src/whatnut/lifecycle.py`
(read-only; for H3).

Setup: `cd /Users/maxghenis/optiqal-ai-rebuild-c/python && uv sync` (fallback `PYTHONPATH=.`);
at the root `bun install`.

## HEADLESS EXECUTION

You run as a single headless turn. There are no later turns. Never use background jobs,
sleep-and-poll, "I'll wait for", or "standing by" patterns; run every command synchronously
to completion (the full card grid takes minutes). Keep `PROGRESS.md` updated and committed
with each step. Your final message is the deliverable.

## What this PR makes true

`results/cards.json` is a projection of a run manifest of the Optiqal graph. Every card is a
release node; its tier and verification state are derived; the store under `results/store/`
makes an unchanged graph execute zero kernels in CI and a changed prior or study row
execute exactly its descendants. The public frontier route reads the projection. The graph
acceptance properties A1-A7, C1-C3, F1-F6, E1-E5, N1-N4, H1-H3 and G1-G4 that PR S left red
go green in this PR (flip them with `scripts/graph_acceptance_flip.py`; never edit the
suite by hand).

## Do

1. **Kernels** under `python/optiqal/kernels/`, registered in one `registry()`:
   `confound@1`, `lifecycle@1`, `qol_guard@1`, `qol_leg@1`, `harm@1`, `stack@1`,
   `evidence_gate@1`, `range_gate@1`, `canary_gate@1`, `platform_parity_gate@1`, `card@1`,
   with the inputs, values and numerics the interface spec's table declares. Each wraps the
   existing module without duplicating its math: the kernel projects `context.inputs` into
   the module's function arguments, passes `context.rng`, and returns the arrays. Kernels
   read no files, no environment, no module-level tables: the life table, quality weights,
   priors and study rows arrive as inputs. H1 parity tests (pinned fixtures from PR S) prove
   each kernel reproduces the direct call byte for byte on this platform.
2. **Graph builder** `python/optiqal/cards.py`: `build_graph(profiles, interventions)` emits
   the nodes for the default `generate_all_profiles()` grid and the public-lane items
   (`consumer_public` and `conditional_public`; `personal_only` is excluded from the public
   graph), with `confound/<item>` and `qol_guard/<item>` shared across profiles. `python -m
   optiqal.cards` compiles, runs (`resume=auto`) against `results/store/`, saves the manifest
   to `results/manifest.json`, and writes the projection `results/cards.json` (schema in
   `REBUILD.md`, plus `manifest_key`, `platform`, per-card `node_key`, `tier`,
   `verification_state`, `study_ids`, `gate_outcomes`). `--check` runs in `require` mode and
   compares the projection to the committed file. Commit the store, the manifest and the
   projection; report the wall time cold and warm and the file sizes. If the store is too
   large to commit (say the number), commit the manifest and projection and store the
   artifacts under `results/store/` with a `.gitignore` plus a CI job that rebuilds cold and
   asserts the manifest key.
3. **Frontier route.** `src/app/api/frontier/route.ts` loads `results/cards.json` at build
   time, snaps the request profile to the nearest grid point (document the rule; nearest age
   bin, exact categorical match, activity folded to the grid's value), applies the same lane
   rules the Python policy applied, filters to certified cards, and returns the response shape
   the workbench expects with `meta.source = "cards.json@<manifest key prefix>"` and
   `meta.snapped_profile`. The public-frontier benchmark harness must pass against the route.
   `/api/baseline` and `backend/main.py` stay untouched.
4. **Drift test.** `tests/test_artifact_drift.py`: `cards --check` passes; the projection's
   `manifest_key` equals the manifest's; when `OPTIQAL_PROTOCOL_JSON` names a file (the site
   repo's protocol JSON), its recorded engine commit and manifest key agree, else skip with a
   message. `load_certified` refuses a projection with an edited `tier` (F3).
5. **What Nut parity (H3).** `lifecycle@1` fed What Nut's pathway RRs, annual cost and start
   age reproduces `whatnut.lifecycle.run_lifecycle` on the pinned fixture to 1e-9. If the two
   integrators differ in a way that is not a bug (a different discounting convention, say),
   do not paper over it: record the exact difference in the final message and leave H3 red
   with the reason in the marker.
6. Delete `precompute.py` and its test once `cards.py` covers them, or keep it as a thin
   alias; say which.

## Verification before your final commit

    cd /Users/maxghenis/optiqal-ai-rebuild-c/python
    uv run ruff check . && uv run ruff format --check .
    PYTHONPATH=. uv run pytest -q
    PYTHONPATH=. uv run python -m optiqal.cards --check
    PYTHONPATH=. uv run python scripts/graph_acceptance_burndown.py --verify
    cd .. && bun run typecheck && bun run lint && bun run test && bun run build

Then run `python -m optiqal.cards` a second time and show zero misses; change one study
row's estimate in a temporary copy and show the exact miss set (A3). Compare the frontier
top six from the route against the dynamic response PR B captured; QoL-only items agree to
the third decimal.

## Rules

Commit in steps on `rebuild/c-results-file`; imperative subjects; explanatory bodies;
`Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` on every message. Never push.
Never touch other worktrees, `origin`, or `~/clawd/data/health.db`. Never edit the
acceptance suite; flip markers with the tool. Interface changes are dated amendments in
`graph-interface.md`, re-locked in the same commit, with the reason.

## Final message

1. Commits (hash, subject).
2. Card counts by tier and verification state; store size; cold and warm wall time;
   manifest key.
3. The A3 miss set for one study-row change.
4. The burndown table after flipping; any property left red and why.
5. The snapping rule and the frontier top six against the dynamic response.
6. Tails of every verification command.
7. Anything not done, and why.
