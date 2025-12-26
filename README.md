# OptiqAL.ai

**Quantify the impact of your choices on quality-adjusted life.**

OptiqAL uses AI to estimate the QALY (Quality-Adjusted Life Year) impact of lifestyle choices based on the best available causal evidence from medical research.

## What it does

Enter a lifestyle change you're considering—like switching to a plant-based diet, adding daily meditation, or upgrading your sleep setup—and OptiqAL will:

1. **Search the evidence**: Pull relevant meta-analyses, RCTs, and cohort studies
2. **Estimate the impact**: Calculate the effect on both longevity and quality of life
3. **Personalize to you**: Adjust estimates based on your age, health, and baseline behaviors
4. **Quantify uncertainty**: Provide confidence intervals reflecting the strength of evidence

Results are expressed in human-readable units: hours, days, or weeks of quality-adjusted life rather than abstract QALY fractions.

## Tech stack

- React + TypeScript + Vite
- Tailwind CSS v4
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
3. Enter a lifestyle choice to analyze
4. Review the estimated QALY impact with supporting evidence

## Disclaimer

OptiqAL provides estimates based on published research and should not be considered medical advice. Estimates involve significant uncertainty. Always consult healthcare professionals for medical decisions.
