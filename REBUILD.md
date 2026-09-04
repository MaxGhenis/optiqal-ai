# Optiqal rebuild charter

Optiqal becomes one open Python engine fed by a fail-closed evidence table, emitting one
content-hashed results file that every surface reads, with a scoreboard whose first rows count
what is still unsourced. Everything that does not serve that object is deleted. This file is
the charter for the `rebuild/*` branches; the review memo it comes from is in
`~/Downloads/optiqal-whatnut-from-scratch.html` (v4, 2026-09-03).

## The object

A decision card for a (profile, intervention) pair: the posterior of the net discounted
lifetime QALY delta versus not doing it, as mean, 95% interval, P(delta > 0), and a
decomposition into mortality, quality-of-life and harm legs, plus a causal-fraction
sensitivity row. A card is admissible only when its chain terminates in ground truth:

    card <- study rows (evidence/studies.yaml, DOI or PMID that resolves)
         <- one prior (data/priors.yaml, one global skeptical prior for observational rows,
            none for trial rows, per-item override only where a paired row exists)
         <- inputs loaded from committed snapshots (CDC life table, MEPS weights), never typed

Cards are materialized per commit into `results/cards.json` with a committed sha256. The
site, the methods note and maxghenis.com/protocol read that file and nothing else; a drift
test loads all three and fails on disagreement.

## Facts the design rests on (verified 2026-09-03, see the memo)

- The TypeScript engine (`src/lib/qaly`, 12,817 non-test lines) has no importers from any
  page or component; it and `src/lib/evidence` import each other and nothing else. The app's
  two routes run the Python engine (locally through `python/scripts/web_*.py`, in production
  through the FastAPI wrapper in `backend/`).
- `simulate.py` seeds the quality-offset draws and the hazard-ratio draws from the same
  `random_state`, so their standardized draws are identical (correlation 1.000) and seeded
  means run 6 to 8% low. The `_sample_distribution` helper already derives independent
  child seeds; only the harm draws use it.
- The confounding prior drifts across artifacts: exercise 17% in `confounding.py` and the
  paper, 33% in `walking_30min_daily.yaml` and the methodology; diet 25/50/62/71% across four
  files. 45 distinct hand-set (alpha, beta) pairs exist across 92 catalog items. The only
  calibration table in the repo is three rows whose ratio column matches no convention.
- Of 92 catalog items, 51 have no sources; 50 of the 61 that claim a mortality effect are
  unsourced; 7 carry a PMID or DOI anywhere. No intervention YAML has the `lineage:` block
  the canonical-model note says exists.
- The prior is inert for 31 of 92 catalog items and for all six items the public frontier
  ranks (hazard ratio 1.0, valued by an authored `qol_annual`). QoL overlays are 84% of the
  gross positive value of Max's current stack. So the ledger shows two legs, never summed.
- `lifecycle.py` hand-transcribes the CDC 2021 life table and the MEPS quality weights;
  `docs/DATA_PROVENANCE.md` records that they drift from the calibration artifacts, that 50 MB
  of raw MEPS parquet is committed without LFS and read only by the orphaned
  `population.py`, and that `condition_joint_distribution.json` has no recorded source.
- `docs/index.md` states the exercise prior's 95% interval as 7 to 30% (line 554) and 2 to
  45% (line 251); Beta(1.2, 6.0) spans 0.8 to 49%. Line 265 applies an E-value formula that is
  complex-valued for HR < 1 (correct values: 2.21 for HR 0.70, 5.04 for HR 2.80).
- The deployed paper is built from a December 2025 branch and shows a third set of numbers.

## Branches and order

Base: `rebuild/one-engine`, stacked on `qol-evidence-stack` (which stacks on
`insurance-aware-costing`), both local-only on 2026-09-04. Each PR below is a branch
`rebuild/<letter>-<slug>` off `rebuild/one-engine`, built in its own worktree, reviewed, then
merged into `rebuild/one-engine`. Nothing is pushed until Max says so.

| PR | Branch | Scope | Depends on |
|----|--------|-------|------------|
| A | `rebuild/a-rng-priors` | independent RNG streams; `data/priors.yaml` as the single source for every Beta prior, shrinkage schedule and transport prior; drift test that parses the docs; paper interval and E-value prose corrected; goldens rebaselined once | none |
| E | `rebuild/e-load-snapshots` | `lifecycle.py` loads the CDC life table and MEPS weights from committed, provenance-stamped JSON; fail closed on mismatch; DATA_PROVENANCE updated | none |
| D | `rebuild/d-evidence-table` | `data/evidence/studies.yaml` schema and fail-closed loader; DOI fixture; seed rows from the intervention YAMLs and the hard-endpoint catalog items; three ratchet files with CI tests; `optiqal lint` | none |
| B | `rebuild/b-deletion` | delete `src/lib/qaly`, `src/lib/evidence`, `public/precomputed`, `bayesian.py`, `markov.py`, `population.py`, their tests and scripts, `docs/optiqal_results.py`, `paper-results.ts`, the MEPS parquet and the unsourced condition JSON; move intervention YAMLs under `python/optiqal/data/interventions/`; strip precompute's PyMC branch; retire the paid tiers from PRODUCT_STRATEGY; README and REPRODUCIBILITY rewritten | A |
| C | `rebuild/c-results-file` | rewrite `precompute.py` over `profile.generate_all_profiles` into `results/cards.json` with sha256; frontier route reads the file; baseline route stays dynamic; cross-artifact drift test | B, D, E |
| G | `rebuild/g-global-prior` | one global skeptical prior for observational rows, none for trial rows, per-item overrides only where a paired row exists; 45 hand-set priors become one plus overrides; cards regenerated | C |
| F | `rebuild/f-scoreboard` | scoreboard page (ratchet counts, drift status, reproduce-versus-published rows); methods note filled from cards.json with no kernel at render; retraction banner on the deployed paper; LICENSE; pyproject URL | C |
| H | site repo | maxghenis.com/protocol shows the mortality leg and the QoL leg separately with commit hash; retire the +1.2-year portfolio stat; read cards.json | C |
| P | private package | `optiqal-protocol` consumes the engine and reads a redacted profile; the personal catalog moves with it | Max's call on where it lives |

## Rules for every lane

- Read this file, then `docs/DATA_PROVENANCE.md`, `docs/canonical-model-v1.md`, and the
  module you are changing, before writing.
- Every number that reaches a public surface traces to a study row, a prior row, or a
  committed snapshot. A number that cannot be traced is nulled, listed in a ratchet file,
  and never softened.
- No fabricated mechanisms. Describe code you read this session, or say you inferred.
- Behavior-preserving refactors carry a test proving it (old value equals new value to
  1e-9). Behavior changes state the shift in the commit message with the numbers.
- `uv run pytest` and `uv run ruff check` green before the final commit. `bun run typecheck`
  and `bun run lint` green when TypeScript is touched.
- Never touch `~/clawd/data/health.db`, other worktrees, or `origin`. Never push.
- Commit messages: imperative subject, a body with what moved and why, and the trailer
  `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Sentence case in headings. No emoji. `uv`, `bun`.

## Schemas

### `python/optiqal/data/priors.yaml` (PR A)

    version: 1
    confounding:
      categories:
        exercise: {alpha: 1.2, beta: 6.0, source: "..."}
        ...
      interventions:            # per-item overrides, keyed by catalog id
        moderate_alcohol: {alpha: ..., beta: ..., source: "..."}
    study_quality_shrinkage:
      rct_preregistered_hard_endpoint: {retention: 1.0, source: "..."}
      ...
    evidence_adjustments:       # the alpha multipliers in confounding.py, until PR G removes them
      rct: {alpha_multiplier: 1.5, source: "..."}
    qol_transport:              # the tiers in qol_evidence.py
      ...

Values are copied verbatim from the code on the day of the move; `source` strings carry the
existing comments. The code loads this file at import and holds no literal Beta parameters.

### `python/optiqal/data/evidence/studies.yaml` (PR D)

    - id: aune2016_nuts_allcause
      doi: 10.1186/s12916-016-0730-3      # or pmid:
      design: cohort_meta_analysis         # one of the STUDY_QUALITY_SHRINKAGE labels
      population: "20 cohorts, 819,448 adults"
      exposure: "nut consumption, 28 g/day"
      comparator: "none"
      endpoint: all_cause_mortality
      estimate: {type: RR, value: 0.78, ci_low: 0.72, ci_high: 0.84}
      role: direct                         # direct | mechanism | transport | harm | baseline_risk | calibration
      extracted_by: "claude-opus-5 lane 2026-09-04"
      verified: 2026-09-04                 # date the DOI was resolved against the fixture
      notes: ""

The loader rejects a row whose CI does not bracket the point, whose DOI or PMID is absent
from `doi_fixture.json`, or whose design is not in the vocabulary. The fixture is refreshed
by `scripts/verify_evidence.py --refresh` (network); CI reads the fixture only.

### Ratchets (PR D), `python/optiqal/data/ratchets/*.yaml`

    known_unsourced_claims.yaml     # catalog ids with no study row behind a claimed effect
    known_unverified_atoms.yaml     # study rows whose identifier has not resolved
    known_judgment_atoms.yaml       # hand-set numbers: per-item priors, OVERLAP_MATRIX, retention

Each file is a list of `{id, reason, since}`. `tests/test_ratchets.py` fails when the
generated list contains an id not in the file (a new debt) and when the file contains an id
the generated list no longer has (a fixed debt that must be removed).

### `results/cards.json` (PR C)

    {"engine_commit": "...", "generated_from": "...", "sha256_of_inputs": "...",
     "profiles": [...], "cards": [{"profile_id": ..., "intervention_id": ...,
       "mortality_qaly": {"mean":..,"ci_low":..,"ci_high":..}, "qol_qaly": {...},
       "harm_qaly": {...}, "p_positive": .., "causal_fraction_ladder": {"0.10":..,"declared":..,"0.50":..},
       "verification_state": "sourced|authored|heuristic", "study_ids": [...]}]}

A card with `verification_state: heuristic` never reaches the public site.

## PR E notes (2026-09-04)

- `lifecycle.py` now loads its five public data blocks from three committed,
  provenance-stamped JSON snapshots through a fail-closed loader. The dated
  fixture proves every numeric value stayed unchanged to `1e-12`.
- The MEPS snapshot regenerates from the committed calibration artifact, and
  `fetch_meps.py` refreshes it after recalibration. The age-95 quality weight is
  labeled as an authored extrapolation rather than attributed to MEPS.
- The production life-table anchors are transcribed legacy data. A committed
  comparison against NVSR 72-12 Tables 2–3 finds zero matches across 44 anchors;
  production is not using the CDC 2021 table the earlier docs cited. Correcting
  those values requires a later behavior-changing PR.
- Cause fractions remain a transcribed approximation because no saved CDC WONDER
  query or export exists. Their pinned validator prints the raw evidence a
  future replacement must record instead of inventing a regeneration path.
- `condition_joint_distribution.json` and the committed MEPS parquet remain in
  place for PR B, as required by the lane boundaries.
