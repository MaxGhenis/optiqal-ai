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
