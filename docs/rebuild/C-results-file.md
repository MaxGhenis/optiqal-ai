# PR C: the results file

You are building PR C of the Optiqal rebuild. Worktree: `/Users/maxghenis/optiqal-ai-rebuild-c`,
branch `rebuild/c-results-file`, branched from `rebuild/one-engine` after PRs A, E, D and B
landed. Read `REBUILD.md` first (the `cards.json` schema is there), then
`docs/rebuild/{A,B,D,E}-*.md` and their "notes" sections in `REBUILD.md`, then
`python/optiqal/precompute.py`, `python/optiqal/profile.py` (`generate_all_profiles`, the
1,152-profile grid), `python/optiqal/web_api.py` (`build_frontier_response_with_policy` and
the policy lanes it applies), `python/optiqal/data/public_policy_lanes.json`,
`python/optiqal/evidence.py`, `python/optiqal/ratchets.py`, `python/optiqal/priors.py`,
`python/optiqal/snapshots.py`, `src/app/api/frontier/route.ts`, `src/lib/frontier-types.ts`,
`src/lib/frontier-contract.ts`, `src/components/analyze/frontier-workbench.tsx`, and
`backend/main.py`.

Setup: `cd /Users/maxghenis/optiqal-ai-rebuild-c/python && uv sync`; at the root `bun install`.

## HEADLESS EXECUTION

You run as a single headless turn. There are no later turns. Never use background jobs,
sleep-and-poll, "I'll wait for", or "standing by" patterns; run every command synchronously
to completion (the full card grid takes minutes; that is fine). Your final message is the
deliverable. If you cannot finish, say exactly what is done and what is not.

## The object

`results/cards.json` at the repository root: one decision card per (profile, intervention)
pair over the default `generate_all_profiles()` grid (1,152 profiles) and the public-lane
catalog items (the `consumer_public` and `conditional_public` lanes from
`public_policy_lanes.json`; the `personal_only` items are excluded from the public file).
Each card carries the mortality, quality-of-life and harm legs separately with mean, 95%
interval and P(delta > 0); the causal-fraction sensitivity row at prior means 0.10, the
declared prior, and 0.50; `verification_state` (`sourced` when the item has a verified study
row behind its claimed effect, `authored` when its value is an authored `qol_annual` with no
mortality claim, `heuristic` otherwise, all derived from PR D's ratchets, never typed); and
the `study_ids`. The file header records the engine commit, the sha256 over every input
(`priors.yaml`, `studies.yaml`, the snapshots, the catalog module source, the intervention
YAMLs), the seed, the simulation count, and the generation timestamp.

## Do

1. `python/optiqal/cards.py`: rewrite `precompute.py`'s profile path into a card builder over
   `generate_all_profiles()` and the public-lane items, using `simulate_qaly_profile_vectorized`
   with the seeding PR A established (one `SeedSequence` per card, derived from the seed and
   the card key, so cards are independent and reproducible). Emit the schema in `REBUILD.md`;
   add a `--profiles N` sampling flag and a `--check` mode that regenerates a fixed random
   sample of 24 cards and compares them to the committed file (exit non-zero on any
   difference beyond 1e-9). Delete `precompute.py` and `test_precompute.py` once `cards.py`
   covers them, or keep `precompute.py` only as a thin alias; say which.
2. Generate the file: `uv run python -m optiqal.cards --out ../results/cards.json` with
   n_simulations 2,000 and seed 42. Commit it with its sha256 in `results/cards.sha256`.
   Record the wall time in the final message.
3. `/api/frontier` reads the file. Change `src/app/api/frontier/route.ts` to load
   `results/cards.json` at build time (a JSON import or a small loader under `src/lib/`),
   snap the request profile to the nearest grid point (document the snapping rule: nearest
   age bin, exact match on the categorical fields, `activity_level` folded to the grid's
   value), and return the same response shape the workbench expects
   (`src/lib/frontier-types.ts`, `frontier-contract.ts`) with `meta.source` set to
   `cards.json@<sha256 prefix>` and `meta.snapped_profile`. Keep the policy lanes' behavior
   (banned and required items) by applying the same lane rules to the cards; the
   public-frontier benchmark harness must still pass. Leave `/api/baseline` and
   `backend/main.py` untouched: the baseline route stays dynamic.
4. `tests/test_artifact_drift.py`: loads `results/cards.json`, verifies `cards.sha256`
   matches, verifies the recorded input hash matches the current inputs (so a prior or
   evidence change without regeneration fails CI), and, when the environment variable
   `OPTIQAL_PROTOCOL_JSON` points at a file (maxghenis.com's `protocol-ground-up.json`),
   asserts its engine commit and input hash agree with the cards file; skip with a message
   when the variable is unset. Add a CI job that runs `cards --check`.
5. Nothing served may carry a `heuristic` card: the route filters them out and a test proves
   it.

## Verification before your final commit

    cd /Users/maxghenis/optiqal-ai-rebuild-c/python
    uv run ruff check . && uv run pytest -q
    uv run python -m optiqal.cards --check
    cd .. && bun run typecheck && bun run lint && bun run test && bun run build

Then run the frontier route for the default profile through the bridge (`bun run dev` is
not available headless; call the route's loader from a vitest test or a small script) and
compare the top-six ranking and numbers against the dynamic response captured in PR B's
final message: the QoL-only items must agree to the third decimal.

## Rules

Commit in steps on `rebuild/c-results-file`; imperative subjects; bodies that say what moved
and why; `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` on every message. Never
push. Never touch other worktrees, `origin`, or `~/clawd/data/health.db`. Append a dated
"PR C notes" section to `REBUILD.md` if the card schema changed.

## Final message

1. Commits (hash, subject).
2. Card counts by `verification_state`; the file size; generation wall time; the sha256.
3. The snapping rule and the frontier top six from the file against the dynamic response.
4. Tails of every verification command.
5. Anything not done, and why.
