# Optiqal.ai

**Rank the health interventions most worth doing next.**

Optiqal is a personalized health decision tool. It compares interventions on a common QALY-informed scale, then shows posterior expected benefit, uncertainty, and likely marginal value given your current profile.

## What it does

Enter a health intervention you're considering, and Optiqal will:

1. **Build your baseline**: Start from age, sex, risk factors, and current behaviors
2. **Estimate intervention impact**: Model the expected effect on longevity and quality of life
3. **Show what is incremental**: Compare additions, removals, or swaps against your current state
4. **Expose uncertainty**: Present intervals and evidence limitations instead of false precision

Results are expressed in human-readable units: hours, days, or weeks of quality-adjusted life rather than abstract QALY fractions.

See [PRODUCT_STRATEGY.md](/Users/maxghenis/optiqal-ai/PRODUCT_STRATEGY.md) for the current product thesis, ICP, MVP scope, and monetization plan.

## Tech stack

- Next.js 15 + React 19 + TypeScript
- Tailwind CSS v4
- Vitest + Playwright
- Python package for the QALY simulation engine and precomputation
- Evidence base: CDC life tables, GBD 2019 disability weights, and hazard
  ratios from peer-reviewed meta-analyses, with Monte Carlo uncertainty

## Development

```bash
bun install
bun run dev
```

Checks (all enforced in CI):

```bash
bun run typecheck && bun run lint && bun run test   # web
bun run test:e2e                                    # Playwright, needs browsers
cd python && uv run --all-extras pytest -q && uv run ruff check && uv run ruff format --check
```

## Usage

1. Fill in your profile (age, sex, and basic health markers)
2. Use **Predict** to see your baseline longevity/QALY projection, or
   **Analyze** to rank interventions by expected marginal QALY gain
3. Review expected benefit, prediction intervals, and supporting evidence

Your profile is sent to the server to run the analysis engine and is processed
only to return your results, not stored long-term. See the in-app Privacy
Policy for details.

## Disclaimer

Optiqal provides statistical estimates based on published research and should not be considered medical advice. Estimates involve significant uncertainty, incomplete causal knowledge, and potential unmodeled interactions. Always consult healthcare professionals for medical decisions.
