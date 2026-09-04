# Optiqal graph interface

The results file is not a monolithic regeneration. It is the manifest of a content-addressed
computation graph in which every card is a release node whose tier is derived from the gates
in its ancestry. This document is the frozen interface the graph lanes build against. It
borrows the identity regime of Microcosm's `microcosm-graph` shard (`docs/graph-acceptance.md`
there, and its `decl.py` and `kernel.py`) and leaves out everything that exists to manage a
shared population: versions, cell ownership, mass, weights. Optiqal's nodes exchange small
typed values, so the whole thing is a few hundred lines inside `optiqal.graph`, with no
dependency on Microcosm.

## What a node is

A node declares its kernel, the inputs it reads (other node ids, or source names), its
parameters, and its role. Its key is the hash of its normative declaration, the keys of its
inputs, and the kernel's implementation hash. Everything the executor, the store, the
manifest and the ledger page know comes from the compiled graph and the manifest; nothing is
typed twice.

Normative fields enter keys. Descriptive fields never do: `description`, `citation`, `notes`,
`extracted_by`, `source` strings on prior rows. Editing a citation regenerates nothing.

```python
# optiqal/graph/decl.py  (frozen; hash recorded in docs/rebuild/graph-interface.lock)

type Param = bool | int | float | str | None | tuple["Param", ...]

DESCRIPTIVE_FIELDS = frozenset({"description", "citation", "notes", "extracted_by", "source"})
ROLES = ("compute", "gate", "release")
GATE_OUTCOMES = ("pass", "fail", "evidence_absent", "not_applicable", "unreached")
TIERS = ("certified", "evidence", "unreached")

@dataclass(frozen=True)
class SourceRef:
    name: str            # "priors", "studies", "snapshot:cdc_life_table_2021", "catalog", "profile:<id>"
    loader: str          # registered loader that returns the source's normative content
    description: str = ""

@dataclass(frozen=True)
class Node:
    id: str
    kernel: str                        # "confound@1"
    inputs: tuple[str, ...] = ()       # node ids or source names, order is normative
    params: Mapping[str, Param] = {}
    role: str = "compute"
    description: str = ""
    citation: str = ""

@dataclass(frozen=True)
class Graph:
    name: str
    sources: tuple[SourceRef, ...]
    nodes: tuple[Node, ...]

def compile_graph(graph) -> CompiledGraph   # order (depth, id), predecessors, cycle and unknown-input errors,
                                            # a release node must have at least one gate ancestor
```

## Keys and seeds

```python
# optiqal/graph/keys.py
source_key(name, content)  = H("source", name, canonical_json(normative(content)))
node_key(node, input_keys, kernel)
                           = H("node", normative(node), input_keys, kernel.implementation_hash(),
                                 capabilities_projection(kernel.capabilities),
                                 platform_fingerprint() if kernel.capabilities.numeric == "platform_bitwise" else None)
artifact_key(node_key)     = H("artifact", node_key)
seed(node_key)             = int.from_bytes(sha256(b"seed\0" + node_key)[:8], "little")
```

`canonical_json` sorts keys, rejects NaN and infinity, writes floats in shortest round-trip
form, and encodes numpy arrays as `{"__ndarray__": dtype, shape, base64}`. The canonical form
is the only thing hashed; whitespace, key order and file names are inert.

A source's content is its loaded, validated object with descriptive fields dropped, not the
file's bytes: a reformatted `studies.yaml` with the same rows has the same key.

Seeds are pure functions of node keys. No kernel may take a seed parameter, read a global
generator, or consume randomness positionally; a static check in the acceptance suite fails
on `np.random.default_rng(` or `random_state=` anywhere under `optiqal/graph/` and in every
registered kernel module.

## Kernels

```python
# optiqal/graph/kernel.py  (frozen)

class Determinism(StrEnum): DETERMINISTIC, SEEDED
class Numeric(StrEnum):     BITWISE, PLATFORM_BITWISE, TOLERANCE_BOUND

@dataclass(frozen=True)
class Tolerance: rtol: float = 0.0; atol: float = 0.0   # required iff TOLERANCE_BOUND

@dataclass(frozen=True)
class Capabilities:
    determinism: Determinism
    numeric: Numeric = Numeric.BITWISE
    role: str = "compute"
    dependencies: tuple[str, ...] = ()   # distributions whose versions enter the implementation hash
    tolerance: Tolerance | None = None

@dataclass(frozen=True)
class KernelContext:
    node: Node
    inputs: Mapping[str, object]        # input id -> the loaded artifact or source content (read-only)
    params: Mapping[str, Param]
    rng: np.random.Generator            # seeded from the node key; the only randomness allowed
    numerics: Mapping[str, NumericScope]  # per input: loosest numeric class among its writers

@dataclass(frozen=True)
class KernelResult:
    value: object                        # JSON-canonicalizable, numpy arrays allowed
    receipt: Mapping[str, object] = {}   # deterministic facts; a gate puts "outcome" and "evidence" here
    artifacts: Mapping[str, bytes] = {}  # opaque bytes stored beside the value

class Kernel(Protocol):
    ref: str                              # "lifecycle@1"; the suffix is the contract version
    capabilities: Capabilities
    def implementation_hash(self) -> str  # sha256 over the defining module's bytes + dependency versions
    def run(self, context: KernelContext) -> KernelResult

class KernelRegistry: register / get / refs / implementation_hash
```

A kernel never reads a file, an environment variable, a clock, or a module-level table; it
reads `context.inputs` and `context.params`. The lifecycle table, the quality weights and the
priors reach a kernel as inputs whose keys are source keys, which is how a snapshot edit
invalidates exactly its consumers.

The kernels the rebuild registers, and what they wrap:

| ref | wraps | inputs | value |
|---|---|---|---|
| `confound@1` | `confounding.py` shrinkage of an observed HR under a prior | `priors`, study rows or the catalog entry, params: intervention id | posterior log-HR draws (n×1) |
| `lifecycle@1` | `lifecycle.py` + the vectorized simulator's mortality arm | `snapshot:cdc_life_table`, `snapshot:cause_fractions`, `snapshot:quality_weights`, `confound/<item>`, `profile:<id>` | mortality-leg QALY draws |
| `qol_guard@1` | `qol_evidence.py` tiered transport shrinkage of an authored `qol_annual` | `priors`, catalog entry | guarded annual QoL draws |
| `qol_leg@1` | survival-weighted integration of the guarded QoL | `qol_guard/<item>`, `lifecycle/<profile>/<item>` survival, snapshots | QoL-leg QALY draws |
| `harm@1` | the harm draws of `simulate.py` | catalog entry, `profile:<id>` | harm-leg QALY draws |
| `stack@1` | `stack_interactions.py` / `combination.py` | a tuple of card nodes | stack card |
| `evidence_gate@1` | PR D's loader and ratchets | `studies`, `catalog`, params: intervention id | outcome + `verification_state` in evidence |
| `range_gate@1` | `predeclared_ranges_v1.json` | a card's legs, the ranges | outcome |
| `canary_gate@1` | the public-policy lanes and benchmark canaries | catalog entry, lanes | outcome |
| `card@1` | assembles a card | the three legs, the gates | the card (release) |

`confound@1` and `qol_guard@1` depend on the intervention only, so they run once and are hits
for every one of the 1,152 profiles. That is the payoff the monolithic regeneration cannot
have.

## Gates, tiers and the public loader

A gate is a node whose kernel role is `gate`. Its receipt carries `outcome` from
`GATE_OUTCOMES` and `evidence`; an exception inside a gate kernel is a `fail` with the
exception as evidence, and the run continues. A compute kernel that raises aborts the run.

A release node (`card@1`) owns a `tier` the executor derives from its ancestry: `certified`
when every ancestral gate is `pass` or `not_applicable`; `unreached` when any ancestral gate
is `unreached`; `evidence` otherwise. No kernel and no file may set `tier`. The evidence gate's
receipt also carries `verification_state` in `{sourced, authored, heuristic}`: `sourced` when
every claimed effect has a verified study row; `authored` when the item claims no mortality
effect and its value is an authored `qol_annual` (outcome `pass`, so an authored card can be
certified, and the label travels with it); `heuristic` when a claimed effect has no row
(outcome `fail`, so the card is evidence-tier and never public).

The public site loads `results/cards.json` through `load_certified`, which refuses a manifest
whose content key does not match, whose ancestry carries a failed or unreached gate, or whose
schema is older than the current one. Editing `tier` or `verification_state` in the file is
detected because the manifest is keyed by content.

Human decisions (a publication sign-off, a label like "reviewed by Max") are signed records
in the manifest and never enter a key (Microcosm's A7 and F5).

## Store, executor, manifest

```python
# optiqal/graph/store.py
class ContentStore:  # results/store/<key[:2]>/<key>.json (+ .bin artifacts), atomic writes, sha256 checked on load
    get(key) -> value | StoreMissError | StoreCorruptError
    put(key, value, artifacts, receipt)

# optiqal/graph/executor.py
run_graph(compiled, registry, store, sources, resume="auto" | "require" | "forbid") -> RunManifest

# optiqal/graph/manifest.py
RunManifest: graph name, engine commit, platform fingerprint, run-level fields (wall time, hit counts),
             per node: key, kernel ref, implementation hash, hit, receipt, seed, tier for release nodes,
             decisions: tuple[Decision, ...]
manifest.key      # hashes every node key and receipt less run-level fields (Microcosm amendment 18)
save / load / load_certified
```

`resume="require"` refuses to execute any node without a store hit; `forbid` never reads the
store; `auto` memoizes. CI runs `auto` against the committed store: an unchanged graph
executes zero kernels, and a changed prior or study row executes exactly its descendants.

`results/cards.json` is a projection of the manifest: the release nodes' values with their
tiers, verification states, study ids, keys and receipts, plus the manifest key and the
platform fingerprint. It is regenerated by `python -m optiqal.cards` and checked by
`python -m optiqal.cards --check`, which compiles the graph, runs it in `require` mode, and
compares the projection to the committed file.

## Numerics and platforms

Monte Carlo kernels (`confound@1`, `lifecycle@1`, `qol_leg@1`, `harm@1`) declare
`platform_bitwise`: identical bytes on one platform and locked dependencies, no bound across
platforms, and the platform fingerprint (architecture, OS, Python minor) enters their keys so
a store never serves another platform's output. `evidence_gate@1`, `range_gate@1`,
`canary_gate@1` and `card@1` are `bitwise`. A cross-platform check (CI on Linux against a
store written on macOS) is a gate, `platform_parity_gate@1`, that regenerates a declared
sample and compares every leg's mean within three Monte Carlo standard errors, recording the
deltas as evidence; it never asserts bytes across platforms. Nothing machine-specific beyond
the fingerprint enters a key: no interpreter bytes, no hostnames, no paths, no clocks.

## Legibility

`describe(node, manifest)` renders, from the compiled graph and the manifest alone, one
screen: the kernel and its implementation hash, every input with its key and (for a study
row or prior) its identifier, the parameters, the seed derivation, the gate outcomes on the
path to this node, and the tier. `explain(manifest)` renders the whole run as one HTML page:
the DAG, hit or miss per node, the gates, and `describe` on click. The ledger page on
maxghenis.com/protocol and the per-card view on the public site are `describe` output, never
hand-drawn, so they stay true as the code moves. A kernel is defined in one sentence in the
README: a pure function from declared inputs and a seed to declared outputs, hashed by its
source.

## What stays outside the graph

The private protocol package and anything that reads `health.db` are not nodes in the public
graph; they are a separate graph in the private package whose sources include a redacted
profile. The public engine imports nothing personal, and a static check proves it (Microcosm
G2, "the executor knows no country").

## Freeze

`optiqal/graph/decl.py` and `optiqal/graph/kernel.py` are frozen once the interface lane
lands them; their canonical hash is recorded in `docs/rebuild/graph-interface.lock`. Changing
either needs a dated amendment in this file and a re-lock in the same commit. Everything else
moves freely.
