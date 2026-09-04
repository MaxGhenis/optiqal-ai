# PR S: the graph acceptance suite (red)

You are writing the acceptance suite for `optiqal.graph`. Worktree:
`/Users/maxghenis/optiqal-ai-rebuild-s`, branch `rebuild/s-acceptance`, branched from
`rebuild/one-engine` after PR I (the graph interface and runtime) landed. Read, in order:
`REBUILD.md`, `docs/rebuild/graph-acceptance.md` (every property you will encode),
`docs/rebuild/graph-interface.md` and `docs/rebuild/graph-interface.lock`,
`python/optiqal/graph/decl.py`, `kernel.py`, `keys.py`, `store.py`, `executor.py`,
`manifest.py`, `view.py`, `toy.py`, and `python/tests/test_graph_*.py` (the runtime lane's
unit tests, which you must not duplicate). For the shape, Microcosm's suite under
`/Users/maxghenis/PolicyEngine/microcosm/packages/microcosm-graph/tests/test_acceptance_*.py`
and its `tools/graph_acceptance_burndown.py` (read-only reference).

Setup: `cd /Users/maxghenis/optiqal-ai-rebuild-s/python && uv sync` (fallback:
`PYTHONPATH=. uv run pytest`).

## HEADLESS EXECUTION

You run as a single headless turn. There are no later turns. Never use background jobs,
sleep-and-poll, "I'll wait for", or "standing by" patterns; run every command synchronously
to completion. Keep `PROGRESS.md` updated and committed with each step. Your final message is
the deliverable.

## The rule you work under

You are the author, never the implementer. You write one test per charter property in
`python/tests/test_graph_acceptance_<group>.py` (`identity`, `seeds`, `gates`, `store`,
`numerics`, `parity`, `legibility`). Each test carries
`@pytest.mark.xfail(strict=True, reason="<Id>: <property title>")` and a docstring quoting
the property. You do not change anything under `python/optiqal/`. If a property is already
satisfied by the runtime as landed, its test will fail CI under strict xfail; that is the
signal, so run the suite and, for each property that passes today, remove the marker and say
so in the final message (those are green on arrival, not skipped). Everything else stays red
for the implementation lanes to flip.

## Deliverables

1. The seven test files, one test per property, 28 properties (A1-A7, C1-C3, F1-F6, E1-E5,
   N1-N4, H1-H3, G1-G4). Tests for A, C, E, F, N and G run against `optiqal.graph.toy`
   and a temporary store under `tmp_path`; tests for H run against pinned fixtures you
   create under `python/tests/fixtures/graph_parity/` from the engine as it stands on this
   branch (record the commands that made them in a README beside them; the platform
   fingerprint goes in the fixture name).
2. `python/scripts/graph_acceptance_burndown.py --verify`: counts `xfail` markers across the
   seven files, compares to the count on `rebuild/one-engine` (fall back to a committed
   `docs/rebuild/graph-acceptance-burndown.json` when the ref is absent), fails when the
   count rose, and prints the per-property table. Wire it into the ruff CI job.
3. `python/scripts/graph_acceptance_flip.py`: given a pytest JUnit report, removes the
   marker from tests that passed (the tool implementation lanes use).
4. Static-check tests for C2 (no positional randomness) and G2 (no personal imports) must
   scan real files with `ast`, not grep strings, and must be green or red on their own
   merits today.

## Verification before your final commit

    cd /Users/maxghenis/optiqal-ai-rebuild-s/python
    uv run ruff check . && uv run ruff format --check .
    PYTHONPATH=. uv run pytest -q tests/test_graph_acceptance_*.py
    PYTHONPATH=. uv run python scripts/graph_acceptance_burndown.py --verify

The suite must pass under strict xfail: every red test fails for the property's reason,
not for an import error or a typo. Paste the burndown table in the final message.

## Rules

Commit in steps on `rebuild/s-acceptance`; imperative subjects; explanatory bodies;
`Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` on every message. Never push.
Never touch other worktrees, `origin`, or `~/clawd/data/health.db`. Never edit
`python/optiqal/`. If a property cannot be expressed against the frozen interface, do not
bend the interface: write the test against the spec as written, mark it, and list it in
the final message as an interface finding for an amendment.

## Final message

1. Commits (hash, subject).
2. The burndown table: property, file, state (red / green on arrival).
3. Interface findings, if any.
4. Tails of `pytest`, `ruff`, and the burndown check.
5. Anything not done, and why.
