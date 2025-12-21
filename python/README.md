# OptiqAL Python

Bayesian QALY estimation for lifestyle interventions.

## Installation

```bash
# Basic installation
pip install optiqal

# With Bayesian (MCMC) support
pip install optiqal[bayesian]

# Full development install
pip install optiqal[all]
```

## Quick Start

```python
from optiqal import Intervention, simulate_qaly

# Load intervention from YAML
intervention = Intervention.from_yaml("walking_30min_daily.yaml")

# Run Monte Carlo simulation
result = simulate_qaly(
    intervention,
    age=40,
    sex="male",
    n_simulations=10000,
)

print(f"QALY gain: {result.median:.2f} [{result.ci95[0]:.2f}, {result.ci95[1]:.2f}]")
```

## Bayesian Inference

For full posterior distributions, install with MCMC support:

```python
from optiqal.bayesian import run_mcmc, summarize_posterior

trace = run_mcmc(
    intervention,
    age=40,
    sex="male",
    n_samples=2000,
    chains=4,
)

print(summarize_posterior(trace))
```

## Precomputation

Generate precomputed results for TypeScript web app:

```python
from optiqal.precompute import precompute_all_interventions

precompute_all_interventions(
    intervention_dir="interventions/",
    output_dir="precomputed/",
    use_mcmc=True,
)
```

## Key Features

- **CDC Life Tables**: Uses official CDC National Vital Statistics mortality rates
- **Pathway Decomposition**: Separates effects into CVD, cancer, and other mortality
- **Confounding Adjustment**: Beta priors based on intervention category and evidence type
- **E-Value Calculation**: Robustness assessment per VanderWeele & Ding (2017)
- **Discounting**: Standard 3% annual rate per ICER/NICE guidelines
- **YAML DSL**: Shared intervention format with TypeScript package

## License

MIT
