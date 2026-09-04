# Graph acceptance charter

`optiqal.graph` is done when every property below is a green test in
`python/tests/test_graph_acceptance_*.py`. Each property is committed red first, as
`pytest.mark.xfail(strict=True)`, by the acceptance lane, against the frozen interface in
`docs/rebuild/graph-interface.md`; the implementation lanes flip them and never edit the
suite. `python/scripts/graph_acceptance_burndown.py --verify` fails CI when the count of
`xfail` markers rises. This mirrors Microcosm's `docs/graph-acceptance.md`, cut down to what
a graph of independent cards needs.

## A. Identity and reuse

| Id | Property |
|---|---|
| A1 | **Determinism.** Two runs of the same graph over the same sources with the same kernels produce identical node keys and byte-identical artifacts across process restarts and a reloaded store. Keys never depend on paths, hostnames, clocks, or the order nodes are declared. |
| A2 | **Memoization.** The second run of an unchanged graph executes zero kernels; the manifest records a store hit for every node. |
| A3 | **Descendant-exact invalidation.** Changing one study row's estimate re-executes exactly the nodes downstream of that row (the item's `confound` node, its lifecycle and QoL legs for every profile, its gates and cards) and nothing else; changing one profile re-executes only that profile's nodes; the test asserts the exact miss set. |
| A4 | **Inert-field invariance.** Editing `description`, `citation`, `notes`, `extracted_by`, or a prior row's `source` string changes no key. Reformatting `studies.yaml` or `priors.yaml` without changing a normative value changes no key. |
| A5 | **Code identity.** Changing a kernel module's bytes, or the installed version of a distribution it declares, invalidates exactly the nodes bound to that kernel and their descendants. |
| A6 | **Source content identity.** Changing a snapshot's `data` invalidates exactly its consumers; changing only its `provenance` block invalidates nothing. |
| A7 | **Decisions are not identity.** Adding a signed human decision or a label to the manifest changes no node key. |

## C. Seeds

| Id | Property |
|---|---|
| C1 | **Seed from identity.** A node's generator is seeded from its key alone; two nodes with identical declarations, inputs, and kernels in different graphs draw identical values. |
| C2 | **No positional randomness.** A static check over `optiqal/graph/` and every registered kernel module finds no `default_rng(`, `np.random.seed`, `random_state=`, or module-level generator. |
| C3 | **Card independence.** Removing an intervention or a profile from the graph changes no other card's bytes; adding one changes none. |

## F. Gates and tiers

| Id | Property |
|---|---|
| F1 | **A gate is a node.** Its outcome is an artifact keyed like any other; identical inputs hit the store; changed inputs re-evaluate. |
| F2 | **Tier is derived.** A card whose ancestry carries a failed gate is `evidence`-tier by construction; one whose ancestry carries an `unreached` gate is `unreached`; a card is `certified` only when every ancestral gate is `pass` or `not_applicable`. No kernel result and no file sets `tier`. |
| F3 | **The one-field flip is impossible.** Editing `tier` or `verification_state` in a serialized `cards.json` is detected by `load_certified`, because the manifest is keyed by content. |
| F4 | **Five outcomes, no accidental pass.** Gate outcomes are exactly `pass`, `fail`, `evidence_absent`, `not_applicable`, `unreached`; a raising gate kernel yields `fail` with the exception as evidence and the run continues; a raising compute kernel aborts the run. |
| F5 | **Verification state is a gate receipt.** `sourced`, `authored`, `heuristic` come from the evidence gate's receipt; a `heuristic` card cannot be certified; an `authored` card can, and carries the label. |
| F6 | **Nothing heuristic reaches the public loader.** `load_certified` on a manifest containing an evidence-tier card raises; the site's frontier reader never returns one. |

## E. Store, manifest, projection

| Id | Property |
|---|---|
| E1 | **Content validation on load.** An artifact whose bytes were altered is rejected with `StoreCorruptError`; it is never used. |
| E2 | **Resume policy is real.** `require` refuses to execute any node without a hit; `forbid` never reads the store; `auto` memoizes. All three are tested on one graph. |
| E3 | **Atomic writes.** An interruption mid-write leaves no partial artifact visible; the next run treats the node as a miss. |
| E4 | **Manifest completeness and determinism.** The manifest lists every node key, hit or miss, kernel implementation hash, receipt, seed, and tier; two runs of the same graph produce manifests that differ only in run-level fields, and `manifest.key` is identical. |
| E5 | **`cards.json` is a projection.** `python -m optiqal.cards --check` compiles the graph, runs it in `require` mode, and the projection equals the committed file byte for byte on the committing platform. |

## N. Numerics and platforms

| Id | Property |
|---|---|
| N1 | **Declared numerics.** A kernel claiming `tolerance_bound` without a `Tolerance` is refused at registration; a `bitwise` or `platform_bitwise` kernel may not carry one. |
| N2 | **Platform partition.** A `platform_bitwise` node's key carries the platform fingerprint; a store written on one platform serves nothing to another, and the manifest names the platform. |
| N3 | **Nothing machine-bound beyond the fingerprint.** Keys are identical across two checkouts on the same platform with different paths, hostnames, interpreter binaries, and CPU counts. |
| N4 | **Cross-platform parity is a gate.** `platform_parity_gate@1` compares a declared sample of cards against a manifest from another platform within three Monte Carlo standard errors per leg and records the deltas as evidence; it never asserts bytes. |

## H. Parity with the engine as it stands

| Id | Property |
|---|---|
| H1 | **Kernel parity.** `confound@1`, `lifecycle@1`, `qol_guard@1`, `qol_leg@1`, `harm@1` each reproduce the direct call into the module they wrap on a pinned fixture and seed, byte for byte on the pinned platform. |
| H2 | **Card parity.** For six pinned (profile, intervention) pairs the card's legs equal `simulate_qaly_profile_vectorized` run with the same derived seeds, to 1e-9. |
| H3 | **What Nut parity.** `lifecycle@1` fed What Nut's pathway RRs, cost and start age reproduces `whatnut.lifecycle.run_lifecycle` on What Nut's fixture to 1e-9 (the shared kernel the memo asked for). |

## G. Legibility and separation

| Id | Property |
|---|---|
| G1 | **One-screen view.** `describe(node, manifest)` renders kernel and implementation hash, every input with its key and identifier, parameters, seed derivation, gate outcomes on the path, and tier, under 40 lines, from the compiled graph and manifest alone. |
| G2 | **The engine knows no person.** `optiqal.graph` and every registered public kernel import nothing from the private protocol package and contain no reference to `health.db` (static check). |
| G3 | **Toy graph in CI.** A synthetic graph of two interventions and four profiles runs sources → confound → lifecycle → gates → cards → `load_certified` end to end in under 30 seconds on the fast lane. |
| G4 | **Explorer.** `python -m optiqal.graph.explain <manifest>` renders one HTML page with the DAG, hit or miss per node, gate outcomes, and `describe` on click, with zero external references. |

## Process

- Strict xfail; monotone burndown verified in lint; implementer never edits the suite.
- The suite lane branches from `rebuild/one-engine` after the interface lane's
  `decl.py` and `kernel.py` land with `docs/rebuild/graph-interface.lock`; its tests import
  the frozen interface and nothing else from `optiqal.graph`.
- Amendments to the interface are dated entries in `graph-interface.md`, re-locked in the
  same commit, reviewed by the Fable main.
