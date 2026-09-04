# PR I progress

## State

In progress on `rebuild/i-graph`. The frozen interface, canonical identity, atomic content
storage, and fail-closed portable manifest are implemented. The executor and source loaders
are next.

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
- Implemented canonical JSON with domain-separated hashing, NumPy dtype/shape/base64
  encoding, and strict rejection of non-finite or unsupported values.
- Implemented source, node, artifact, seed, and platform identities with declared-input-only
  factorization.
- Implemented `ContentStore` at the required sharded path with JSON and artifact checksums,
  atomic visibility, corruption/miss separation, and NumPy restoration (17 focused tests
  passing).
- Implemented immutable decisions, node receipts, and run manifests with canonical atomic
  save/load, stable run-independent manifest keys, graph/input/key/seed authentication, and
  strict schema parsing.
- Implemented certified loading that re-derives every release tier, requires complete gate
  evidence, permits authored evidence, and refuses failed, unreached, heuristic, empty, or
  tampered releases (52 graph-focused tests passing).

## Next

- Implement source loaders and the executor with gates, tiers, numerics, and resume policies.
- Implement the toy graph, views, and the explorer CLI.
- Run all requested verification and record the three toy-run outputs.
