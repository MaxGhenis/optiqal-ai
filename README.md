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
- Python package for simulation and precomputation
- Claude API (Anthropic) for evidence synthesis

## Development

```bash
pnpm install   # Use pnpm (Vercel uses pnpm for this project)
pnpm dev
```

### Before pushing

Run these checks to avoid failed Vercel deployments:

```bash
pnpm install          # Ensure lockfile is in sync
npx tsc --noEmit      # Check for TypeScript errors
pnpm build            # Verify production build works
```

**Common issues:**
- **Lockfile out of sync**: If you add dependencies, commit `pnpm-lock.yaml`
- **Type errors**: Fix all TypeScript errors before pushing (Vercel runs `tsc`)
- **Stale `.next` cache**: Run `rm -rf .next` if you see phantom type errors

## Usage

1. Enter your Anthropic API key (stored locally, never sent to our servers)
2. Fill in your profile for personalized estimates
3. Enter an intervention to analyze or compare
4. Review expected benefit, uncertainty, and supporting evidence

## Disclaimer

Optiqal provides statistical estimates based on published research and should not be considered medical advice. Estimates involve significant uncertainty, incomplete causal knowledge, and potential unmodeled interactions. Always consult healthcare professionals for medical decisions.
