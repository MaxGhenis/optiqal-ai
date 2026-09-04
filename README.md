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

`REBUILD.md` is the charter the current work follows: one open Python engine fed
by a fail-closed evidence table, emitting one content-hashed results file that
every surface reads. [PRODUCT_STRATEGY.md](PRODUCT_STRATEGY.md) carries the
product thesis, ICP and MVP scope.

## How it is put together

There is one engine. `python/optiqal/` computes every number.

- The served pages call it. `/predict` POSTs to `/api/baseline` and `/analyze`
  POSTs to `/api/frontier`; both routes go through `src/lib/python-bridge.ts`.
- Locally the bridge spawns `python/scripts/web_baseline.py` or
  `web_frontier.py` and exchanges JSON over stdin and stdout.
- In production it calls the `optiqal-model` service, the FastAPI wrapper in
  `backend/main.py`, which imports the same `optiqal.web_api` functions.
  `scripts/prepare-model-deploy.mjs` builds that deployment.
- The TypeScript under `src/` is the Next.js app: pages, components, the request
  and response contracts, and the bridge. It runs no simulation.

`REPRODUCIBILITY.md` documents the seeding actually enforced in code.
`docs/DATA_PROVENANCE.md` records where each committed data asset came from and
which claims are still unverified.

## Tech stack

- Next.js 16 + React 19 + TypeScript
- Tailwind CSS v4
- Vitest + Playwright
- Python 3.10+ with NumPy and SciPy for the QALY engine, managed by `uv`
- Evidence base: committed life-table and MEPS quality-weight snapshots, GBD-style
  disability weights, and hazard ratios from published meta-analyses, with Monte
  Carlo uncertainty and explicit confounding priors

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
