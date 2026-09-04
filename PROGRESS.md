# PR I progress

## State

In progress on `rebuild/i-graph`. Every PR I deliverable is implemented and the resumed
independent audit is addressing one fallback-source semantic defect before final verification.

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
- Implemented a 28-node toy graph over two interventions and four profiles, with deterministic
  and seeded computation, all five gate outcomes, cached failed and raising gates, release
  tiers, selection independence, source overrides, and exact descendant invalidation.
- Verified the toy's focused suite passes in under two seconds with the local Python toolchain.
- Hardened direct source handling so every descriptive field and snapshot provenance block
  is removed before both identity and kernel execution, matching registered-loader behavior.
- Made tier derivation an invariant of every manifest construction/load and prohibited kernels
  or serialized receipts from authoring tiers or non-gate verification states.
- Aligned the frozen `Tolerance()` zero defaults with the authority and refreshed the interface
  lock; all 137 graph-focused tests and the lock verification pass.
- Added the zero-dependency HTML explorer with an inline SVG DAG, cache/gate/tier facts,
  fragment-driven `describe` details, strict escaping, and a tested manifest CLI.
- Documented nodes, kernels, gates, tiers, and manifests in the Python README using the
  required kernel definition; all 138 graph-focused tests pass.
- Verified all 616 project tests pass after repairing only the ignored, incomplete `.venv`
  left by the network-blocked sync; Ruff reports all 95 files formatted and lint-clean.
- Verified the frozen interface lock at
  `cfc039d2f15cc034a1422af363d8460c71e6f147dc11a98a6aa1da04d9131fa8`.
- Recorded cold, fully warm, and one-parameter-changed toy runs, including the exact 13-node
  descendant miss set, in `FINAL_REPORT.md`.
- Corrected the pre-PR-A study-quality fallback to convert the legacy shrinkage fraction to
  PR A's normative retention value, preserving its meaning across the optional-module boundary.

## Next

- Complete the independent reference/spec audit.
- Repeat whole-project verification and commit the final report.
