# PR A: independent RNG streams and one priors file

You are building PR A of the Optiqal rebuild. Worktree: `/Users/maxghenis/optiqal-ai-rebuild-a`,
branch `rebuild/a-rng-priors` (already created, checked out, clean). Read `REBUILD.md` at the
worktree root first; it is the charter and carries the schemas and rules. Then read
`python/optiqal/simulate.py`, `python/optiqal/confounding.py`, `python/optiqal/analyzer.py`,
`python/optiqal/qol_evidence.py`, `python/optiqal/intervention.py`, and
`python/scripts/rebaseline_model_regression.py` before editing anything.

Setup: `cd /Users/maxghenis/optiqal-ai-rebuild-a/python && uv sync` (creates the venv). All
Python commands run from that directory with `uv run`. Node is not needed for this PR.

## HEADLESS EXECUTION

You run as a single headless turn. There are no later turns. Never use background jobs,
sleep-and-poll, "I'll wait for", or "standing by" patterns; run every command synchronously
to completion (the full pytest suite takes several minutes; that is fine). Your final message
is the deliverable. If you cannot finish, say exactly what is done and what is not.

## Task 1: independent RNG streams (behavior change, stated)

Verified facts (2026-09-03, refuters with repo access):

- `simulate.py` `simulate_qaly_profile_vectorized` (def near line 528) builds
  `rng = np.random.default_rng(random_state)` near line 560, draws
  `quality_offsets = rng.normal(0, QUALITY_WEIGHT_STD, n)` near 606-608, then calls
  `intervention.mortality.hazard_ratio.sample(n, random_state)` near 614-616 and
  `intervention.confounding_prior.sample(n, random_state)` near 622-624. `Distribution.sample`
  (`intervention.py` ~113-122) and `ConfoundingPrior.sample` (`confounding.py` ~58-61) each build
  a fresh `default_rng(random_state)`, so the standardized quality-offset draws and the
  standardized log-HR draws are identical (correlation 1.0 at every integer seed). Seeded means
  run 6 to 8% below the unseeded mean (a 45-year-old man walking daily: 0.192 seeded, 0.205
  independent). The Beta draw is not coupled (corr 0.007).
- The file already has `_sample_distribution(dist, n, rng)` near line 432, which derives a
  child seed from the local generator; only the harm draws (~486, 497, 502) use it.
- The loop simulators `simulate_qaly` (~846) and `simulate_qaly_profile` (~939) pass the same
  raw seed to both `sample()` calls.
- `analyzer._simulate_one` (~126-160) builds a mortality arm and a ConfoundingPrior even when
  the entry has `has_direct_mortality_effect=False` and `hr_observed=1.0`, so those items pick
  up a seed-dependent mortality term (hiit_2x_week: mortality QALY -0.0053 at seed 42 against
  a true value of 0). `web_api` never calls that path; the analyzer API does.
- Seeded callers: `web_api.py` ~645 (`random_state=42`), `analyzer.py` ~55/161/377,
  `precompute.py` ~121/387, `protocol_ground_up.py` ~3878
  (`random_state=stable_random_seed(item_id, "structured_qaly")`; the `SEED = 42` constant at
  line 54 is dead).

Do:

1. Derive every stream in the vectorized simulator from one
   `np.random.SeedSequence(random_state).spawn(k)` (or route each draw through
   `_sample_distribution`); make `Distribution.sample` and `ConfoundingPrior.sample` accept a
   `np.random.Generator` as well as an int (`np.random.default_rng` passes a Generator
   through). Fix the two loop simulators the same way.
2. Make an item with no mortality arm (`has_direct_mortality_effect=False` or a point hazard
   ratio of exactly 1.0) produce a mortality QALY of exactly 0.0 on every path, including
   `analyzer._simulate_one`.
3. Tests, in `python/tests/test_simulate_streams.py`:
   - correlation between standardized quality offsets and standardized log-HR draws is below
     0.05 at seeds 42, 1 and 7 (today it is 1.0; assert the old coupling is gone by
     reconstructing the draws the way the simulator does);
   - a seeded run is bit-reproducible across two calls;
   - an HR-1.0 catalog entry yields mortality QALY 0.0 on the vectorized path and through
     the analyzer;
   - for `walking_30min_daily` and a 45-year-old male never-smoker, the seeded mean is
     within Monte Carlo error (three standard errors at n=20,000) of the mean of ten unseeded
     runs.

## Task 2: `python/optiqal/data/priors.yaml` as the single source (behavior-preserving)

Move every hand-set prior parameter into one file, values copied verbatim, and load it:

- `confounding.py`: `CATEGORY_PRIORS` (line ~70, every category), `EVIDENCE_ADJUSTMENTS`
  (~182), `STUDY_QUALITY_SHRINKAGE` (~246), and any intervention-specific prior table.
- `qol_evidence.py`: `AUTHORED_RESIDUAL_OPTIMISM_PRIOR` (~238) and the tier retention tables.
- `catalog.py`: `EVIDENCE_EFFECT_MULTIPLIERS`.
- Carry the existing code comments into `source:` strings. Do not change any value.

Write `python/optiqal/priors.py` with `load_priors()` (cached, validates alpha and beta
positive, retentions in [0, 1], multipliers positive, unknown keys rejected). The modules build
their dicts from it at import; no literal Beta parameters remain in `.py` files (a test greps
for `ConfoundingPrior(` with numeric literals outside tests and fails on hits). Commit a
frozen fixture `python/tests/fixtures/priors_2026-09-04.json` containing today's literal
values and a test asserting the loaded dicts equal it exactly, so the move is provably
behavior-preserving.

## Task 3: drift test across artifacts (values change, stated)

Write `python/tests/test_priors_drift.py` that parses the confounding prior tables out of
`docs/methodology.md` and `docs/index.md` (find the tables; `docs/index.md` lines ~244-246
list exercise 17%, diet 25%, smoking 38%) and the `confounding:` blocks of
`src/lib/qaly/interventions/*.yaml` (`walking_30min_daily.yaml` line ~47 says Beta(2.5, 5.0);
`mediterranean_diet.yaml` says Beta(6, 2.5)) and asserts they equal `priors.yaml`. Today they
disagree: exercise 17% in code and paper against 33% in the YAML and methodology; diet 50% in
code, 71% in YAML and methodology, 25% in the paper table. Resolution rule for this PR: the
served code value wins. Edit the YAMLs and both docs to match `priors.yaml`, and list every
changed number (artifact, old, new) in the commit body. The test must fail if any of them
drifts again.

## Task 4: correct the paper's stated numbers (prose, computed by the code)

In `docs/index.md`:

- line ~554: "95% CI: 7%-30%" for the exercise prior; Beta(1.2, 6.0) spans 0.8% to 49.0%;
- line ~251 (and the matching comment in `confounding.py` ~78): "95% CI [2%, 45%]" and
  "P(f > 0.45) < 0.025"; the true tail probability is 0.039;
- line ~265: the E-value formula HR + sqrt(HR(HR-1)) is complex-valued for HR < 1; the
  repo's own `calculate_e_value` (confounding.py ~369-372) uses 1/HR correctly and gives 2.21
  for HR 0.70 (paper says ~1.9) and 5.04 for HR 2.80 (paper says ~5.2);
- the "+/-1 SD" sensitivity table (10%/17%/30%): the true +/-1 SD of Beta(1.2, 6) is
  3.7%/29.7%; fix the numbers or the label.

Prefer rendering these through the existing `{eval}` mechanism (`docs/optiqal_results.py`
exposes `r.*`) so they come from code; if a value must stay typed, compute it with scipy in
the commit body and cite the line. Do not touch `src/lib/qaly/paper-results.ts`; PR B deletes
it.

## Task 5: rebaseline goldens once

The RNG fix moves every seeded number with a mortality arm by roughly +6 to +8%. Read
`python/scripts/rebaseline_model_regression.py`, run it once, and commit the rebaseline as
its own commit whose body lists before and after for `walking_30min_daily` and three catalog
items with a mortality arm, plus the statement that QoL-only items are unchanged. If the sleep
goldens (`test_sleep.py`, rebaselined in commit 3fb4e660) move, include them.

## Verification before your final commit

    cd /Users/maxghenis/optiqal-ai-rebuild-a/python
    uv run ruff check .
    uv run pytest -q

Both must be green. Also run the public frontier for the default profile before and after
(`uv run python scripts/web_frontier.py` reads a JSON request on stdin; the canonical
scenarios are in `optiqal/data/public_frontier_benchmark_scenarios.json` and
`optiqal/web_api.py` has `CANONICAL_PUBLIC_FRONTIER_SCENARIOS`) and put the top-six ranking
with numbers, before and after, in the final message. Expect the QoL-only exercise items to
be unchanged and mortality items to shift.

## Rules

Commit in small steps on `rebuild/a-rng-priors`; imperative subjects; bodies that say what
moved and why; every message ends with the trailer
`Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Never push. Never touch other
worktrees, `origin`, or `~/clawd/data/health.db`. Do not edit `REBUILD.md` except to append a
dated "PR A notes" section if the priors schema needed to change. Never invent a source or a
number; if something cannot be traced, say so in the final message.

## Final message

1. Commits (hash, subject).
2. Drift table: artifact, old value, new value, for every prior you changed.
3. RNG results: the correlation before and after; walking seeded mean before and after.
4. Frontier top six before and after.
5. Last lines of `pytest` and `ruff`.
6. Anything not done, and why.
