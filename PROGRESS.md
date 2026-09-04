# PR I progress

## State

In progress on `rebuild/i-graph`. The frozen declaration and kernel interfaces are
implemented, tested, formatted, and locked. Runtime identity and storage are next.

## Done

- Confirmed the requested worktree is clean and checked out on `rebuild/i-graph`.
- Read `REBUILD.md`, the graph interface and acceptance charters, and the existing
  simulation, lifecycle, confounding, and optional source modules in the required order.
- Located the Microcosm graph reference implementation in its read-only graph integration
  worktree because the path named in the brief is not present in its main worktree.
- Synced as far as the network-restricted environment permits; dependency download was
  unavailable, so verification uses an existing local Python 3.14 toolchain with this
  worktree on `PYTHONPATH`.
- Implemented frozen source, node, graph, compiled-graph, capability, tolerance, numeric
  scope, context, result, protocol, registry, and source-hash contracts.
- Added deliberate interface validation/error tests (24 passing) and recorded the canonical
  interface hash in `docs/rebuild/graph-interface.lock`.

## Next

- Implement canonical encoding, keys, and the atomic content store with corruption tests.
- Implement the manifest and executor with gates, tiers, numerics, and resume policies.
- Implement source loaders, the toy graph, views, and the explorer CLI.
- Run all requested verification and record the three toy-run outputs.
