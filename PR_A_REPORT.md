# PR A final report

Date: 2026-09-04  
Branch: `rebuild/a-rng-priors`

## Commits

| Commit | Subject |
| --- | --- |
| `4a06ef2d` | Track PR A progress |
| `8d108d77` | Separate simulation random streams |
| `a23d4d7d` | Centralize hand-set priors |
| `e5f41dc7` | Align prior artifacts with served values |
| `96de9f2e` | Correct paper confounding statistics |
| `0cd390b0` | Rebaseline seeded model goldens |
| `ef1e2221` | Rebase protocol optimizer sign cases |
| `af3b11a7` | Bound protocol smoke-test runtime |
| `07b107a1` | Record PR A completion |

## Prior drift resolved

| Artifact | Old value | New value |
| --- | --- | --- |
| `python/optiqal/data/priors.yaml` — walking | Beta(2.5, 5.0), mean 33%, CI 8–65% | Beta(1.2, 6.0), mean 17%, CI 0.8–49.0% |
| Frozen priors fixture — walking | Beta(2.5, 5.0), mean 33%, CI 8–65% | Beta(1.2, 6.0), mean 17%, CI 0.8–49.0% |
| `walking_30min_daily.yaml` | Beta(2.5, 5.0), mean 33%, CI 8–65% | Beta(1.2, 6.0), mean 17%, CI 0.8–49.0% |
| `docs/methodology.md` walking example | Beta(2.5, 5.0), mean 33% | Beta(1.2, 6.0), mean 17% |
| `python/optiqal/data/priors.yaml` — Mediterranean diet | Beta(6.0, 2.5), mean 71%, CI 42–90% | Beta(3.0, 3.0), mean 50%, CI 15–85% |
| Frozen priors fixture — Mediterranean diet | Beta(6.0, 2.5), mean 71%, CI 42–90% | Beta(3.0, 3.0), mean 50%, CI 15–85% |
| `mediterranean_diet.yaml` | Beta(6.0, 2.5), mean 71%, CI 42–90% | Beta(3.0, 3.0), mean 50%, CI 15–85% |
| `docs/methodology.md` Mediterranean example | Beta(6.0, 2.5), mean 71% | Beta(3.0, 3.0), mean 50% |
| `docs/index.md` Diet row | Beta(1.5, 4.5), mean 25% | Beta(3.0, 3.0), mean 50% |
| `docs/index.md` Smoking/Substance row | Beta(2.5, 4.0), mean 38% | Beta(2.0, 4.0), mean 33%, relabeled Substance |
| `docs/index.md` Sleep row | Beta(1.0, 5.5), mean 15% | Beta(1.5, 4.5), mean 25% |
| `docs/index.md` Social row | Beta(2.0, 4.0), mean 33% | Beta(1.0, 5.5), mean 15% |
| `docs/index.md` Supplements/Stress row | Beta(1.2, 5.0), mean 19% | Same values, relabeled Stress |
| `docs/index.md` Medical row | Absent | Beta(2.5, 4.0), mean 38% |
| `docs/index.md` Other row | Absent | Beta(1.2, 4.8), mean 20% |
| `docs/methodology.md` Other block | Absent | Beta(1.2, 4.8), mean 20%, CI 2–50% |

The drift test now parses all eight category entries in both documents and every shipped intervention YAML.

## Paper number corrections

| Artifact | Old | New |
| --- | --- | --- |
| Exercise prior 95% interval | 2%–45% (and elsewhere 7%–30%) | 0.8%–49.0% |
| Exercise prior upper tail | `P(f > 0.45) < 0.025` | `P(f > 0.45) = 0.039` |
| Exercise E-value, HR 0.70 | Invalid protective-HR formula; approximately 1.9 | Reciprocal-RR formula; 2.21 |
| Smoking E-value, HR 2.80 | Approximately 5.2 (2.22 for exercise in the appendix) | 5.04 (2.21 for exercise in the appendix) |
| Sensitivity description | 10%/17%/30% labeled ±1 SD | Actual mean ±1 SD is 3.7%–29.7%; 10%/17%/30% are labeled scenario points |

The interval and tail are frozen SciPy results and tested against SciPy; E-values are tested against `calculate_e_value`.

## RNG results

| Seed | Quality/log-HR correlation before | Correlation after |
| ---: | ---: | ---: |
| 42 | 1.000000000000 | 0.002378031509 |
| 1 | 1.000000000000 | 0.007807690665 |
| 7 | 1.000000000000 | -0.000487198714 |

For a 45-year-old male never-smoker at 20,000 draws, walking's seeded mean moved from `0.191573422864` to `0.203502549408` from stream separation alone (+6.23%). The ten-run unseeded reference was `0.203690149787`, within the test's three-standard-error bound. After the separate served-prior correction from Beta(2.5, 5.0) to Beta(1.2, 6.0), the final walking mean is `0.101699260674`.

Mortality-bearing catalog comparisons for the same profile and seed:

| Item | Before mortality / total QALY | After mortality / total QALY |
| --- | ---: | ---: |
| finasteride_1.25mg | 0.111285351332 / 0.282027340208 | 0.137994815642 / 0.308851301752 |
| statin_5mg | 0.104691626716 / 0.066800365657 | 0.131761542229 / 0.093868791877 |
| tadalafil_2.5mg | 0.098460016335 / 0.336333670569 | 0.120221341127 / 0.358027437699 |

QoL-only `hiit_2x_week` remains `0.014792646571` total QALY and `strength_maintenance` remains `0.002015135813`; both now have exactly `0.0` mortality QALY.

## Default public frontier, top six

Request: age 35, male, 75 kg, 175 cm, never-smoker, no diabetes or hypertension, light activity, seven hours of sleep, 5,000 draws.

| Rank | Item | Before QALY / days | After QALY / days |
| ---: | --- | ---: | ---: |
| 1 | hiit_2x_week | 0.0150 / 5.5 | 0.0150 / 5.5 |
| 2 | hiit_3x_week | 0.0130 / 4.7 | 0.0130 / 4.7 |
| 3 | tempo_run_1x_week | 0.0109 / 4.0 | 0.0109 / 4.0 |
| 4 | hiit_1x_week | 0.0095 / 3.5 | 0.0095 / 3.5 |
| 5 | zone2_cardio_2x_week | 0.0068 / 2.5 | 0.0068 / 2.5 |
| 6 | strength_maintenance | 0.0020 / 0.7 | 0.0020 / 0.7 |

All six are QoL-only and unchanged, with exactly zero mortality contribution. Mortality-bearing items moved as shown in the preceding comparison.

## Verification

`uv run ruff check .`:

```text
All checks passed!
```

`uv run pytest -q`:

```text
........................................................................ [ 98%]
........                                                                 [100%]
512 passed in 1071.86s (0:17:51)
```

The sandbox could not download SciPy during the initial network-backed `uv sync`; verification therefore used the worktree `.venv` with the already-installed system packages and `uv run --no-sync` semantics. No requested implementation, test, drift correction, rebaseline, or verification work is omitted. Nothing was pushed.
