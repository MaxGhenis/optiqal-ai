# PR I progress

## State

In progress on `rebuild/i-graph`. The graph contract, identity/store/manifest runtime,
registered normative source loaders, executor, and one-screen view are implemented. The toy
graph and HTML explorer are next.

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
- Implemented registered prior, study, snapshot, catalog, and profile loaders, including
  optional-PR fallbacks, granular study/catalog source aliases, and explicit removal of
  descriptive content before source identity is computed.
- Implemented the executor's full resume contract, artifact-keyed storage, immutable input
  projection, identity-derived generators, gate exception semantics, transitive numeric
  scopes, derived release tiers, and portable run receipts.
- Implemented deterministic one-screen node descriptions from the embedded graph and
  manifest; all 117 graph-focused tests pass.

## Next

- Implement the toy graph and the explorer CLI.
- Run all requested verification and record the three toy-run outputs.
