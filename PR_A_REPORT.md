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

QoL-only `hiit_2x_week` remains `0.014792646571` total QALY and `strength_maintenance` remains `0.002015135813`; both now have exactly `0.0` mortality QALY. Those are catalog-path figures, and the catalog path already gated on `has_direct_mortality_effect` before PR A, so `0.0` there is not what changed. The change is on the decisions path; see "Decision-path mortality for a QoL-only item" below.

## Why the shift is larger than the brief expected

The charter's reading of `simulate.py` predicted that seeded means ran 6 to 8% low. Walking's net mean moved +6.23%, inside that band. The three mortality-bearing personal items did not: their mortality legs moved +22.10% to +25.86%, and statin's total QALY moved +40.52%.

| Item | Leg | Before | After | Absolute | Relative |
| --- | --- | ---: | ---: | ---: | ---: |
| walking_30min_daily | net | 0.191573422864 | 0.203502549408 | +0.011929 | +6.23% |
| finasteride_1.25mg | mortality | 0.111285351332 | 0.137994815642 | +0.026709 | +24.00% |
| finasteride_1.25mg | total | 0.282027340208 | 0.308851301752 | +0.026824 | +9.51% |
| statin_5mg | mortality | 0.104691626716 | 0.131761542229 | +0.027070 | +25.86% |
| statin_5mg | total | 0.066800365657 | 0.093868791877 | +0.027068 | +40.52% |
| tadalafil_2.5mg | mortality | 0.098460016335 | 0.120221341127 | +0.021761 | +22.10% |
| tadalafil_2.5mg | total | 0.336333670569 | 0.358027437699 | +0.021694 | +6.45% |

Two separate things drive the gap between +6% and +40%.

The shift itself is a covariance term. Under the old code the quality offset and the standardized log-hazard-ratio draw were the same number, so every draw that received the larger survival gain also received the lower quality weight, and the mean carried a negative covariance between life-years gained and the quality weight they are valued at. Independent streams remove it, which is why every item's mean rose rather than moving in both directions. Relative to the mean, that term scales with how dispersed the draws are: under coupling walking's net-QALY draws have a coefficient of variation of 0.89 and its mean moves +5.3% at the current prior, while the three items' draws have coefficients of variation of 1.82 to 1.85 and their mortality legs move 22 to 26%.

Then a difference of larger legs amplifies whatever lands in one of them. Statin's total is a small net of a positive mortality leg against a negative quality-of-life leg (+0.104692 against -0.037891 before). The mortality leg moved +0.027070 in absolute terms, which is 25.86% of that leg but 40.52% of the 0.066800 net. Finasteride and tadalafil run the other way: their totals are dominated by a large positive QoL leg (+0.201805 and +0.239128), so the same size of absolute shift is under 10% of the total. The absolute move is confined to the mortality leg in all three cases; only the denominator differs.

## Decision-path mortality for a QoL-only item

The `0.0` figures above were measured on the catalog path (`item_results_by_id`), which gated on `has_direct_mortality_effect` before PR A as well, so it read `0.0` on the base commit too. What PR A changed is the decisions path, where `_simulate_one` formerly always built a mortality arm.

Measured on `hiit_2x_week` at n=1,000, seed 42, the 45-year-old male never-smoker profile:

| Decision | Base `009acd90` | PR A, review round 1 | Catalog leg (all three) |
| --- | ---: | ---: | ---: |
| ADD, no override | -0.004055991723 | 0.0 | 0.0 |
| ADJUST, `override_hr=0.85` | 0.105118835077 | 0.104778860915 | 0.0 |
| ADJUST, `override_hr=1.0` | -0.004055991723 | 0.0 | 0.0 |

The base's `-0.004056` on a QoL-only item is the coupled RNG's residual on an arm that should not have existed; independent streams plus the flag make it exactly `0.0`. The middle row is the review's finding: between the first PR A pass and this round the overridden hazard ratio was computed and then discarded, so the decision returned exactly `0.0` where the base returned a real effect. `_decision_has_mortality_arm` restores it.

## Null-item residual

The stochastic mean-null regression in `tests/test_simulate.py` (log_sd 0.12, diet prior Beta(3.0, 3.0), seed 1, n=100,000) moved from `-0.013928386234` to `+0.009530169552` QALY. The docstring on the base commit claimed "around -0.035 QALY" for that case; re-running it on `009acd90` gives `-0.013928`, so the -0.035 was already stale before PR A. The current docstring's "around +0.01" is correct.

## Protocol optimizer verdict flip

`ef1e2221` rebased two optimizer sign cases, and one of them is a changed verdict rather than a changed magnitude. On the base commit the protocol optimizer dropped `vitamin_d_2000`; under independent streams it keeps it.

| Item | Base `009acd90` | PR A | Verdict before | Verdict after |
| --- | ---: | ---: | --- | --- |
| vitamin_d_2000 | -0.0013 | +0.0018 | drop | keep |
| aspirin_81mg | -0.0064 | -0.0048 | drop | drop |

Aspirin keeps its sign and its verdict, which is why the negative-item drop case was moved onto aspirin instead of being weakened to a list literal. Vitamin D's deterministic estimate crosses zero, so `test_protocol_optimizer_keeps_positive_current_item` now asserts the keep. This is a recommendation change on a personal-protocol item, not only a test rebase.

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
