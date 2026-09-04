# PR I progress

## State

In progress on `rebuild/i-graph`. The authoritative graph specification and acceptance
charter have been read. The optional `optiqal.snapshots` and `optiqal.priors` modules are
not present on this branch, so their documented fallbacks will be implemented.

## Done

- Confirmed the requested worktree is clean and checked out on `rebuild/i-graph`.
- Read `REBUILD.md`, the graph interface and acceptance charters, and the existing
  simulation, lifecycle, confounding, and optional source modules in the required order.
- Located the Microcosm graph reference implementation in its read-only graph integration
  worktree because the path named in the brief is not present in its main worktree.

## Next

- Read the Microcosm reference modules in the requested order.
- Sync the Python environment and inventory the Optiqal catalog/profile/snapshot shapes.
- Implement and test the frozen declarations and kernel interface, then lock them.
- Implement identity, store, manifest, executor, source loaders, toy graph, views, and CLI.
- Run all requested verification and record the three toy-run outputs.
