# Canonical Model V1

This document defines the first-principles target model for Optiqal.

It is intentionally separate from the current implementation. The point is to make one canonical statistical object that future Monte Carlo, MCMC, precompute, and UI layers can all agree on.

## Why This Exists

Optiqal currently has multiple overlapping estimation paths:

- TypeScript lifecycle Monte Carlo for product-serving estimates
- Python Monte Carlo for catalog and stack analysis
- Python PyMC MCMC for a narrower posterior workflow

Those paths share ideas, but they do not yet share one explicit generative specification. Canonical Model V1 defines that specification.

## Design Principles

1. One estimand per decision
2. Study-level evidence as the primitive input
3. Continuous Bayesian uncertainty, not evidence buckets
4. Explicit separation of evidence, transport, harm, and decision layers
5. Provenance for every important parameter
6. Fast serving can differ from canonical inference, but must be traceable back to it

## Core Estimand

For a user `u` and intervention decision `d`, the primary estimand is:

`E[net lifetime QALY delta | evidence, priors, user state, current stack, decision d]`

where `net lifetime QALY delta` includes:

- mortality effects
- morbidity / quality-of-life effects
- harms
- adherence / persistence
- burden and financial cost only if the decision surface chooses to convert them into utility space

The model should also produce:

- `P(net benefit > 0)`
- `P(net harm < 0)`
- expected upside
- expected downside
- conditional upside / downside
- value of information

## Canonical Causal Graph

The canonical graph is:

`User state at baseline`
-> `intervention assignment`
-> `adherence / dose / persistence`
-> `proximal mediators`
-> `clinical states over time`
-> `cause-specific mortality and quality trajectories`
-> `discounted lifetime QALYs`

with additional latent layers:

- measurement error
- study bias / confounding / publication distortion
- transportability from study population to user
- interaction with current stack

## Model Layers

### 1. User State

The user state should be explicit and versioned. It includes:

- demographics
- current conditions
- biomarkers
- habits / exposures
- current intervention stack
- preferences relevant to burden and reversibility

This layer determines baseline hazards, baseline quality weights, and effect modification.

### 2. Intervention Representation

An intervention is not fundamentally “an HR.” It is a bundle of causal changes:

- adherence / persistence assumptions
- mediator effects
- direct benefit effects if justified
- direct harm effects if justified
- time profile of onset / ramp / decay

Interventions should be represented in a way that allows both:

- direct study-level evidence on hard outcomes
- mechanism-mediated extrapolation when hard outcomes are unavailable

### 3. Evidence Layer

The primitive evidence unit is a study estimate, not an intervention summary.

Each study object should carry:

- citation / year / design
- population
- exposure / comparator definition
- endpoint
- effect measure
- uncertainty
- bias notes
- role in the model

Roles include:

- direct-effect
- mechanism-link
- prior-calibration
- transport
- harm-model
- baseline-risk
- heuristic

### 4. Bias and Confounding Layer

Bias should not be hidden inside one scalar confidence label.

Canonical Model V1 separates:

- parameter uncertainty
- causal uncertainty
- publication / selection distortion
- transport uncertainty

For many lifestyle interventions, the canonical direct-effect parameter is:

`causal log-effect = causal_fraction * observed log-effect`

But this should be treated as one special case, not the whole model.

Eventually the canonical bias layer should support:

- category-level priors
- intervention-specific calibration
- study-design-specific likelihood adjustments
- optional negative-control / MR / twin / RCT anchoring

### 5. Transport Layer

Population evidence is not the target. Personalized evidence is.

Transport should be modeled explicitly via:

- baseline-risk scaling
- mediator responsiveness
- contraindications / ceiling effects
- stack overlap
- demographic and comorbidity modifiers

Transport belongs in the posterior, not as an afterthought in UI copy.

### 6. Outcome Layer

The outcome layer maps causes and states into:

- cause-specific mortality
- disease incidence / remission
- quality weights over time
- harms over time

This layer should remain lifecycle-based. That is still the right abstraction.

### 7. Decision Layer

The final decision object is not just a QALY interval.

It should contain:

- posterior over net QALY delta
- burden-adjusted utility if enabled
- downside tail risk
- reversibility
- stack incrementality
- value of information

## When To Use Direct Outcome Evidence vs Mechanism Mediation

Use direct hard-outcome evidence when it exists and is credible.

Use mechanism mediation when:

- no direct hard-outcome evidence exists
- the intervention is too novel or too specific
- the relevant endpoint is quality rather than mortality

If both exist, the canonical model should combine them rather than forcing one to replace the other.

## Provenance Schema

Canonical Model V1 requires every intervention definition to support a lineage object with:

- `estimand`
- `model_version`
- `studies`
- `parameter_lineage`
- optional `prior_lineage`
- optional notes

The lineage object answers:

- which empirical studies were used
- what parameter each study informs
- how the parameter was derived
- what prior was imposed and why

This is now represented in the shared intervention schema and parser layer.

## Example Parameter Lineage

For `mortality.hazard_ratio`:

- study: meta-analysis of walking and mortality
- derivation: pooled log-HR mapped into a lognormal uncertainty distribution
- assumptions:
  - comparator approximates “not doing intervention”
  - study population is transportable after shrinkage
  - residual healthy-user bias handled by confounding prior

For `confounding.causal_fraction`:

- prior family: beta
- sources: twin, MR, RCT, or calibration papers
- rationale: observational effect likely inflated for this intervention class

## Canonical Inference Strategy

The target backend should be study-level Bayesian inference for curated interventions.

That means:

1. study-level likelihoods
2. parameter pooling / shrinkage
3. explicit bias priors
4. explicit transport priors
5. posterior simulation through lifecycle outcomes

This is where MCMC is justified.

## Serving Strategy

Canonical inference and product serving do not need to be identical.

Recommended architecture:

1. Canonical Python backend performs study-level posterior inference for curated interventions
2. Posterior summaries and lineage are precomputed
3. The web app serves those posterior summaries instantly
4. Free-text or speculative interventions can continue to use the lighter structured Monte Carlo path, clearly labeled as such

## What Current Heuristics Should Be Retired

Over time, retire or reduce:

- single-summary “evidence quality implies uncertainty multiplier” as the main evidence model
- intervention-level HRs with no study decomposition
- hidden transport assumptions
- untracked heuristic pathway splits
- any UI summary that cannot point back to provenance

## Migration Plan

### Phase 1

- define canonical schema
- attach lineage to intervention definitions
- expose lineage in result objects
- document current heuristics explicitly

### Phase 2

- create curated study tables for a small set of interventions
- fit study-level posteriors in Python
- compare posterior summaries against current Monte Carlo outputs

### Phase 3

- make curated posterior outputs the source of truth for precomputed interventions
- keep free-text interventions on the lighter path

### Phase 4

- add lineage and posterior trace views to the app
- add value-of-information and transport sensitivity surfaces

## Non-Goals

Canonical Model V1 is not trying to:

- fully solve every intervention class immediately
- force all interventions into hard-outcome evidence only
- make the interactive app run full MCMC on-demand
- eliminate heuristic approximations everywhere on day one

## Current Interpretation

The current TypeScript rigorous simulation remains the best serving path for interactive use.

The current Python MCMC path is a promising backend research path, but it is not yet the canonical product model because it is not yet study-level, lineage-complete, or broad enough to replace the serving pipeline.
