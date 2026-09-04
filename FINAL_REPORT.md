# PR I final report

Completed on 2026-09-04 on branch `rebuild/i-graph`. This report's own documentation commit
necessarily follows the implementation commits listed below; its hash is available as `HEAD`.

## Commits

- `c7aad9950303738d882a73eaf6d4c0b2349423e0` — Start the graph implementation ledger
- `9b3647a6c84170530deaf10381bac82b823c3293` — Freeze the graph declaration and kernel contracts
- `12a3b6f549384d976ade68dbc83869ffac0e0ee7` — Add content identity and atomic graph storage
- `ffdeeb705ec9e3aff87b36738b1fc5a6380b2df9` — Authenticate portable graph manifests
- `d52f9fb442f6b1e4019226236af2b17f8614a221` — Execute content-addressed graphs
- `2146fb1d8c4c60e3a853215ca54df1da668e3d97` — Exercise every graph runtime path
- `daf017a83f5e914cd859ae2a93f8634a6c4f4f0c` — Harden source and release authority
- `8a802bb19c7e0bfaed457fb026d39563df690105` — Explain graph runs in one page
- `5205c5c73c73bc8e81f1b3bc42f7d5a584c2fa15` — Preserve fallback prior semantics
- `e7eb02d25ace0e7c39c2f69b4839c4181b08bf78` — Reserve derived provenance recursively
- `d323897fdc55fe52feab2666247ce4cf2804be58` — Exercise remaining graph contracts

Every commit has an imperative subject, an explanatory body, and the required
`Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` trailer.

## Toy runs

All three runs used one fresh `ContentStore`; run 3 changed only `alpha_shrinkage` from `0.75`
to `0.5`.

```text
run1 key=85a57753bd68e1d4b001fa8b9baa1da3392c3373d868fe039788930e7ecaf2ae hits=0 misses=28
miss_set=['card/p1/alpha', 'card/p1/beta', 'card/p2/alpha', 'card/p2/beta', 'card/p3/alpha', 'card/p3/beta', 'card/p4/alpha', 'card/p4/beta', 'confound/alpha', 'confound/beta', 'gate/fail/detached', 'gate/p1/alpha', 'gate/p1/beta', 'gate/p2/alpha', 'gate/p2/beta', 'gate/p3/alpha', 'gate/p3/beta', 'gate/p4/alpha', 'gate/p4/beta', 'gate/raise/detached', 'lifecycle/p1/alpha', 'lifecycle/p1/beta', 'lifecycle/p2/alpha', 'lifecycle/p2/beta', 'lifecycle/p3/alpha', 'lifecycle/p3/beta', 'lifecycle/p4/alpha', 'lifecycle/p4/beta']

run2 key=85a57753bd68e1d4b001fa8b9baa1da3392c3373d868fe039788930e7ecaf2ae hits=28 misses=0
miss_set=[]

run3 key=f9e6ccb7c82647636830715c3a007eececa21ca94bd5e4b684c9b4a675ffe0f7 hits=15 misses=13
miss_set=['card/p1/alpha', 'card/p2/alpha', 'card/p3/alpha', 'card/p4/alpha', 'confound/alpha', 'gate/p1/alpha', 'gate/p2/alpha', 'gate/p3/alpha', 'gate/p4/alpha', 'lifecycle/p1/alpha', 'lifecycle/p2/alpha', 'lifecycle/p3/alpha', 'lifecycle/p4/alpha']
```

The warm run has the same manifest key as the cold run and zero misses. The changed run misses
exactly `confound/alpha` and its lifecycle, gate, and card descendants for the four profiles.

## Interface lock

```text
cfc039d2f15cc034a1422af363d8460c71e6f147dc11a98a6aa1da04d9131fa8
```

The recorded recomputation command is:

```sh
python -m optiqal.graph.lock --verify
```

## Specification amendment

None. `docs/rebuild/graph-interface.md` is unchanged. The final lock refresh aligned
`Tolerance()` with the authority's existing zero defaults, so no amendment was necessary.

## Verification tails

Ruff:

```text
All checks passed!
96 files already formatted
```

Pytest:

```text
.....................................................                    [100%]
629 passed in 985.98s (0:16:25)
```

Lock:

```text
Graph interface lock verified: cfc039d2f15cc034a1422af363d8460c71e6f147dc11a98a6aa1da04d9131fa8
```

The successful commands used `UV_NO_SYNC=1` with the already-installed local toolchain and
`UV_CACHE_DIR="$PWD/.uv-cache"` to keep uv's cache in the writable worktree. Unqualified
`uv sync` could not resolve `pandas==3.0.1` because this sandbox has no DNS/network access;
uv's default cache location was also outside the writable sandbox. No product code or tracked
environment configuration was changed to work around those infrastructure limits.

## Not done

Nothing in PR I is outstanding. Network dependency synchronization was unavailable for the
reason above, but the requested lint, format, test, lock, and toy checks all completed locally.
