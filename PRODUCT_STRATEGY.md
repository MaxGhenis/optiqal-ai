# Optiqal Product Strategy

## Positioning

Optiqal is a health decision engine.

It does not primarily sell lab results, biological-age scores, or a branded protocol. It helps people answer a narrower and more valuable question:

`What is most worth doing next for my health, given what I already do?`

## Problem

People can find endless health advice, but they cannot compare unlike interventions on one consistent scale.

Examples:
- Sleep 45 more minutes
- Lower ApoB
- Quit alcohol
- Add creatine
- Wear sunscreen daily
- Copy a supplement from Bryan Johnson

The market mostly offers:
- Dashboards and biomarker interpretation
- Protocols and supplement stacks
- Narrow vertical apps for nutrition, sleep, or longevity

It still lacks a strong consumer tool that ranks interventions across domains with explicit uncertainty and stack effects.

## Product thesis

The winning object is not a single number. It is a decision card for each intervention with:
- Expected benefit
- Probability of net benefit
- Downside risk
- Sensitivity to priors
- Burden
- Cost
- Reversibility
- Incremental effect versus current stack

The main insight is comparative, not absolute. Users do not need a poetic estimate of life expectancy as much as they need a defensible next action.

## Market gap

Adjacent products exist, but they cluster into three buckets:
- `scores`: biological age, pace-of-aging, risk, readiness
- `dashboards`: labs, wearables, clinical summaries
- `protocols`: guided stacks, supplements, and coaching

Optiqal should occupy the `decision engine` slot.

Suggested one-line positioning:

`Optiqal tells you what is most worth doing next.`

## ICP

Initial ideal customer profile:
- Quantified-self users
- Longevity enthusiasts
- High-agency professionals already spending on supplements, labs, or wearables
- People comparing a crowded personal stack and trying to cut noise

Why this segment first:
- They already feel the ranking problem
- They are willing to tolerate uncertainty if it is explicit
- They already spend money on adjacent products

## Wedge

Start with cross-intervention ranking where the posterior is most decision-useful.

V1 question:

`Given my current profile, what are the top 5 additions, removals, or swaps most likely to improve my healthspan?`

This is stronger than:
- another longevity score
- another supplement tracker
- another lab report explainer

## MVP scope

Include in v1:
- Baseline profile estimation
- Intervention ranking on a common QALY scale
- Bayesian posterior over net QALY impact
- Stack-aware marginal ranking
- Clear uncertainty display
- Bias, confounding, and publication-shrinkage priors
- Explicit harm distributions
- Burden and cost inputs
- Add, remove, and swap analysis

High-value early categories for v1:
- Sleep
- Exercise
- Smoking and nicotine
- Alcohol reduction
- Blood pressure
- ApoB or LDL lowering
- Weight loss where clinically relevant
- Sunscreen and skin cancer prevention
- Vaccination and core preventive care where modelable

## What to exclude from v1

Do not lead with:
- Large supplement catalogs
- Weak mechanism-only interventions
- Consumer-grade biomarker overfitting
- Fully automated protocol generation
- Claims of medical-grade personalization

Do not market the long tail before the core posterior engine feels trustworthy.

## Evidence model

Optiqal should be Bayesian and continuous, not a hand-authored evidence-bucket system.

Core model components:
- Prior on causal effect size by intervention family
- Prior on bias, confounding, and publication distortion
- Prior on external validity to the user profile
- Harm distribution, not just benefit distribution
- Posterior over net QALY delta

Weak evidence should not be marked with a binary label. It should shrink harder toward zero, widen uncertainty, and show more downside sensitivity.

That means “speculative” emerges from the posterior rather than from a manually assigned tier.

Recommended outputs:
- `E[net QALY delta]`
- `P(net benefit > 0)`
- `P(net benefit > threshold)`
- Downside tail risk
- Burden-adjusted expected utility
- Sensitivity to prior choice

This avoids false precision without introducing a brittle strong-versus-speculative boundary.

## UX principles

- Default to ranking, not raw prediction
- Show marginal effect over current stack
- Make source evidence inspectable
- Prefer ranges to point estimates
- Penalize burden and cost explicitly
- Make it easy to remove low-value habits or supplements, not just add more

## Monetization

Free:
- Basic profile
- Limited intervention comparisons
- Public methodology and citations

Paid individual:
- Saved profile and stack
- Lab and wearable imports
- More interventions and swap analysis
- Personalized rankings over time
- Scenario planning and portfolio optimization

Paid pro:
- Coaching or clinician view
- Shared plans
- Client reports
- White-label decision support

## Go-to-market

Phase 1:
- Ship a credible, opinionated consumer tool
- Win quantified-self and longevity users
- Publish transparent methodology and case studies

Phase 2:
- Add imports from labs and wearables
- Add recurring “what changed in my ranking?” workflows
- Expand into practitioner or coach workflows

Phase 3:
- Add team plans, clinician tooling, and enterprise distribution if the consumer layer proves sticky

## Success criteria

The product is working if users say:
- “This helped me stop wasting effort on low-value interventions.”
- “This gave me a clearer next step than my lab dashboard did.”
- “This helped me remove things from my stack, not just add more.”

## Near-term product changes

- Position the homepage around intervention ranking, not just life expectancy
- Route primary CTAs to the analysis flow
- Standardize branding on `Optiqal`
- Make posterior outputs and prior sensitivity first-class fields in every result
- Keep the strongest interventions front and center before expanding the catalog
