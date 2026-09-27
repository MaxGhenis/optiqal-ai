# Sleep Model V1

This document defines how sleep should enter Optiqal as a first-class health state.

It is intentionally narrower than [canonical-model-v1.md](/Users/maxghenis/optiqal-ai/docs/canonical-model-v1.md): the point is to make sleep the first fully specified vertical slice of the canonical model.

## Goal

The target estimand is:

`E[net lifetime QALY delta from intervention d via sleep pathways | user sleep state, evidence, harms, current stack]`

This should replace the older pattern of:

- one scalar `sleep_benefit_fraction`
- hand-authored protocol-only sleep bonuses
- opaque overlap penalties that treat all sleep aids as the same

## Design Principles

1. Sleep is a latent state, not one metric.
2. Consumer wearables are observations, not endpoints.
3. Direct quality-of-life burden is the main pathway.
4. Hard-outcome credit should be modest and concentrated in better-supported components.
5. Interventions should only get credit for the sleep components they plausibly improve.
6. Sleep overlap should happen at the component level, not the “sleep supplement” level.

## Causal Structure

The intended graph is:

`Sleep observations`
-> `latent sleep phenotype`
-> `direct quality burden`
-> `selected mortality / morbidity pathways`
-> `lifetime QALY burden`

and:

`intervention`
-> `component-level sleep relief`
-> `reduced sleep burden`
-> `net QALY gain`

## Observation Layer

The sleep observation layer should accept rolling summaries from multiple sources:

- duration
- latency
- WASO / fragmentation
- routine / regularity
- social jetlag
- subjective quality
- recovery / daytime impairment proxy
- SpO2
- breathing / snoring proxies
- later: home-study or PSG outputs such as REI/AHI, ODI, mean/min SpO2, positional dependence

These are inputs to inference about the phenotype. They are not themselves the causal quantities of interest.

## Latent Sleep Phenotype

Sleep Model V1 decomposes sleep into six components:

- `duration`
- `continuity`
- `quality`
- `regularity`
- `daytime`
- `breathing`

This is now represented in [sleep.py](/Users/maxghenis/optiqal-ai/python/optiqal/sleep.py).

The phenotype posterior should eventually carry uncertainty. The current implementation uses deterministic burden scores from rolling summaries as an intermediate step.

## Burden Layer

The annual sleep burden has two outputs:

- `annual_qaly_loss`
- `mortality_signal`

The annual QALY loss should mostly represent direct quality burden:

- poor function
- poor alertness
- poor sleep satisfaction
- burden from fragmentation or breathing disturbance

The mortality signal should stay modest and should only lean materially on:

- duration
- regularity
- breathing

Insomnia-style symptoms without stronger airway evidence should mostly remain in the quality layer.

## Intervention Layer

Each intervention can declare a `sleep_component_relief` map.

Examples:

- magnesium: duration, quality, daytime
- melatonin: duration, continuity, regularity
- trazodone: duration, continuity, quality, daytime
- CPAP: breathing, daytime, continuity
- nasal steroid: breathing
- head elevation: breathing
- schedule / light therapy: regularity

The intervention should get no sleep credit outside those declared components.

This is now represented in the Python catalog for sleep-relevant interventions in [catalog.py](/Users/maxghenis/optiqal-ai/python/optiqal/catalog.py).

## Overlap Layer

Sleep overlap should be component-specific.

Two interventions should only meaningfully overlap where they both target the same sleep component:

- `sleep_duration_support`
- `sleep_continuity_support`
- `sleep_quality_support`
- `sleep_regularity_support`
- `sleep_daytime_support`

This is already the direction of [stack_interactions.py](/Users/maxghenis/optiqal-ai/python/optiqal/stack_interactions.py).

The overlap multiplier should be informed by unmet burden:

- more unmet burden -> less overlap penalty
- less unmet burden -> more overlap penalty

## Current Integration

The current core integration now supports:

- `AnalysisConfig.sleep_metrics`
- `AnalysisConfig.sleep_estimate`
- automatic derivation of a sleep estimate from metrics
- personalized `sleep_qol_qaly` in catalog and analyzer outputs
- a modest baseline sleep-hazard multiplier derived from the latent sleep phenotype
- component-level sleep mortality relief for sleep-targeted interventions
- sleep-informed overlap multipliers in portfolio construction

The protocol script can still layer additional customization on top, but sleep is no longer protocol-only.

## Ground-up protocol composition

The ground-up protocol and exhaustive sleep-stack search share
[`ProtocolInteractionEvaluator`](../python/optiqal/protocol_overlap.py). Their
default `ProtocolContext.overlap_mode = "component"` uses each item's
full-precision, evidence-guarded relief after airway personalization. The
serialized `sleep_overlap` payload records these fractions, component annual
losses, and each component's standalone discounted QoL benefit.

For component c, let L_c be its annual QoL loss and r_ic the guarded fraction
relieved by item i. Split time at every item's `qol_years` horizon. In each
window w, A_w is the set of active items and D_w its discounted duration:

```text
state_sleep_qol = Σ_c L_c · Σ_w D_w · (1 − Π_{i∈A_w}(1 − r_ic))
sleep_qol_interaction = state_sleep_qol − Σ_i standalone_sleep_qol_i
```

Discounting follows the standalone QoL stream: year t has weight
`(1 + discount_rate)^(-t)`, and a window's fractional year contributes exactly
its fraction of that weight. Composition therefore preserves every standalone
value, handles unequal and fractional treatment windows exactly, and gives zero
interaction between items targeting disjoint components. Shared-component
interactions are nonpositive. Implementation and invariant tests are in
[`sleep_overlap.py`](../python/optiqal/sleep_overlap.py) and
[`test_sleep_overlap.py`](../python/tests/test_sleep_overlap.py).

Sleep-derived mortality is isolated by paired simulations with and without
sleep relief, using the same seed and direct HR. The mortality interaction uses
the same component composition, allocating each window's combined relief among
its active contributors in proportion to their relief fractions. Each item's
retained exposure scales its standalone sleep-derived mortality QALY. Exposure
weights are life-table derivatives for a temporary log-hazard change: treatment
ends at `qol_years`, while downstream survival gains accrue through the modeled
age-100 horizon. This is a first-order mortality approximation.
`mortality_approximation_bound` compares it with exact expected-quality survival
integration for composed sleep HRs on the common baseline and gives a
conservative absolute-error bound for every subset of the supplied items. The
bound includes the spread in paired-simulation slopes; it does not assert an
exact joint model of direct HR effects.

The isolated `ab-stageB` check on 2026-09-23, with the profile's age fallback,
bounded mortality error across every subset of all 19 sleep-relief items at
`1.994e-8 QALY`. The all-items absolute difference was `1.244e-9 QALY`:
`0.000130986525` under proportional allocation versus `0.000130985281` under
exact expected-quality integration. The repaired inputs leave only one item
with positive sleep-derived mortality benefit, so this run has no overlapping
mortality relief. Synthetic tests additionally check shared mortality
components with different horizons and the bound across their subsets.

Non-sleep tags retain their existing schedules, applied only to positive
general QoL and direct-HR mortality benefit. Each item receives only its largest
non-sleep-tag penalty. `overlap_mode = "legacy_rank_retention"` restores the
historical retention arithmetic and the benefit-tag changes associated with
this component-overlap repair. It operates on the supplied baseline and item
estimates; input repairs and sedation-tag changes remain separate.

`ProtocolContext.residual_mode = "evidence_rule"` applies the shared
[`sleep residual rule`](../python/optiqal/sleep_residual.py): the reviewed bedtime
items receive no extra general-QoL credit for their sleep outcomes. Ashwagandha
retains its separately guarded stress/anxiety term. New sleep interventions
default to no general residual. `residual_mode = "authored"` restores authored
values for sensitivity analysis. Integration tests check both overlap modes
against full protocol-state evaluation to `1e-9` in
[`test_protocol_overlap.py`](../python/tests/test_protocol_overlap.py).

## Known Gaps

Sleep Model V1 is not finished. Remaining gaps include:

- explicit uncertainty on the sleep phenotype posterior
- direct ingestion from the health DB into Optiqal core
- stronger evidence mapping for the burden weights
- explicit airway intervention entries
- sleep-study / HSAT posterior updates
- n-of-1 learning from intervention experiments
- stronger source attribution for the mortality transport shrinkage

## Next Steps

1. Add sleep-study observations as first-class inputs.
2. Add airway interventions to the core catalog.
3. Make sleep burden weights traceable to explicit lineage entries.
4. Add experiment-driven personalization for sleep interventions.
5. Migrate protocol-side sleep logic onto the core analyzer completely.
