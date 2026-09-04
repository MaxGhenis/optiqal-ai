# PR I: the graph interface and runtime

You are building PR I of the Optiqal rebuild. Worktree: `/Users/maxghenis/optiqal-ai-rebuild-i`,
branch `rebuild/i-graph`, branched from `rebuild/one-engine`. Read, in order:
`REBUILD.md`, `docs/rebuild/graph-interface.md` (the spec you are implementing; it is the
authority), `docs/rebuild/graph-acceptance.md` (the properties an acceptance lane will test
against your interface), `python/optiqal/simulate.py`, `python/optiqal/lifecycle.py`,
`python/optiqal/confounding.py`, `python/optiqal/snapshots.py`, `python/optiqal/priors.py`
(if PR A has landed; otherwise `confounding.py`'s tables), and, for the shape you are
borrowing, Microcosm's `decl.py`, `kernel.py`, `keys.py`, `canonical.py`, `store.py`,
`executor.py`, `manifest.py`, `view.py` under
`/Users/maxghenis/PolicyEngine/microcosm/packages/microcosm-graph/src/microcosm/graph/`
(read-only; do not import it; Optiqal has no shared population, so ownership, versions,
mass, weights and entrants do not come along).

Setup: `cd /Users/maxghenis/optiqal-ai-rebuild-i/python && uv sync` (if the dev extra fails
to install, run tests with `PYTHONPATH=. uv run pytest`).

## HEADLESS EXECUTION

You run as a single headless turn. There are no later turns. Never use background jobs,
sleep-and-poll, "I'll wait for", or "standing by" patterns; run every command synchronously
to completion. Your final message is the deliverable. Keep `PROGRESS.md` at the worktree
root updated and committed with each step. If you cannot finish, say exactly what is done
and what is not.

## Deliverables

1. `python/optiqal/graph/decl.py` and `python/optiqal/graph/kernel.py` exactly as specified
   (frozen dataclasses, validation in `__post_init__`, `compile_graph`, the `Kernel`
   protocol, `Capabilities`, `Tolerance`, `NumericScope`, `KernelContext`, `KernelResult`,
   `KernelRegistry`, `source_hash`). Record their canonical hash in
   `docs/rebuild/graph-interface.lock` with the command that recomputes it
   (`python -m optiqal.graph.lock --verify`). Where the spec is silent, follow Microcosm's
   choice and say so in a docstring.
2. `canonical.py` (canonical JSON, domain-separated sha256, numpy encoding, NaN and infinity
   refused), `keys.py` (`source_key`, `node_key`, `artifact_key`, `seed`,
   `platform_fingerprint`), `store.py` (`ContentStore` under `results/store/`, atomic writes,
   checksum on load, `StoreMissError` / `StoreCorruptError`), `executor.py` (`run_graph` with
   `resume` in `auto` / `require` / `forbid`, gate semantics, tier derivation, the
   `KernelContext` projection with `numerics`), `manifest.py` (`RunManifest`, `NodeReceipt`,
   `Decision`, `manifest.key`, `save` / `load` / `load_certified`), `view.py` (`describe`),
   `errors.py`.
3. Source loaders registered by name: `priors` (from `priors.yaml` via `optiqal.priors` if
   present, else from `confounding.py`'s tables), `studies` (from `evidence.py` if PR D has
   landed, else an empty table), `snapshot:<name>` (via `optiqal.snapshots`), `catalog`
   (the `CatalogEntry` normative projection: every numeric field, `study_ids`, lanes; `notes`
   and `sources` strings descriptive), `profile:<id>` (a `Profile` from
   `profile.generate_all_profiles`, keyed by its fields). Each loader returns the normative
   content the key is computed from.
4. A toy graph and a toy kernel set in `python/optiqal/graph/toy.py` (two synthetic
   interventions, four profiles, a deterministic compute kernel, a seeded compute kernel, a
   gate that passes, a gate that fails, a release kernel) that exercises every executor path
   in under ten seconds. This is what the acceptance suite's G3 and most A, C, E, F, N
   properties run against; the real kernels come in PR C.
5. Tests in `python/tests/test_graph_*.py` for everything above (not the acceptance suite;
   that lane writes its own). Target: every public function exercised, every error path
   raised on purpose.
6. `python/optiqal/graph/explain.py` (`python -m optiqal.graph.explain <manifest>`): one
   self-contained HTML page (inline CSS and SVG, zero external references) with the DAG,
   hit or miss per node, gate outcomes, tier per release node, and `describe` on click.
   Sentence case, no emoji.
7. README section in `python/README.md`: what a node, a kernel, a gate, a tier and a
   manifest are, one sentence each; a kernel is "a pure function from declared inputs and a
   seed to declared outputs, hashed by its source".

## Verification before your final commit

    cd /Users/maxghenis/optiqal-ai-rebuild-i/python
    uv run ruff check . && uv run ruff format --check .
    PYTHONPATH=. uv run pytest -q
    PYTHONPATH=. uv run python -m optiqal.graph.lock --verify
    PYTHONPATH=. uv run python -c "from optiqal.graph.toy import run_toy; m = run_toy(); print(m.key, sum(r.hit for r in m.nodes.values()))"

Run the toy graph twice against the same store and show that the second run has zero
misses and the same manifest key. Run it once more with one toy parameter changed and show
the exact miss set. Put all three outputs in the final message.

## Rules

Commit in steps on `rebuild/i-graph`; imperative subjects; bodies that say what moved and
why; `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` on every message. Never push.
Never touch other worktrees, `origin`, or `~/clawd/data/health.db`. Do not change
`graph-interface.md` except to append a dated amendment if the spec is inconsistent with
itself; say what you amended and why in the final message.

## Final message

1. Commits (hash, subject).
2. The three toy runs' outputs (keys, hit counts, miss set).
3. The lock hash and the command.
4. Any spec amendment and its reason.
5. Tails of `pytest`, `ruff`, and the lock check.
6. Anything not done, and why.
