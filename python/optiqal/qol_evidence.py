"""Evidence guarding for quality-of-life (symptom) claims.

The mortality pathway has long had a calibrated guard stack: tiered
publication-bias shrinkage by study quality (``confounding.STUDY_QUALITY_SHRINKAGE``)
composed with a Beta causal-fraction prior calibrated to RCT-vs-observational
discrepancies. QoL overlays — which carry most of the modeled protocol value —
previously bypassed all of it: the ground-up pipeline took authored
``qol_annual`` means at face value, and sleep-relief fractions reached both the
QoL leg and the mortality hazard multiplier unguarded.

This module is the QoL analog. Every guarded claim composes two factors on the
claimed annual effect:

1. **Study-quality shrinkage** ``s`` — reporting/publication inflation for
   patient-reported endpoints, tiered like the mortality table but harsher at
   the weak end (subjective endpoints p-hack more easily than death).
2. **Transport prior** ``theta ~ Beta(a, b)`` — the fraction of the *claimed*
   benefit expected to survive placebo/expectancy stripping and transport from
   the trial population to an already-healthy, already-treated user.

``effective_annual = claimed_annual * (1 - s) * theta``

Two anchor modes keep the double-shrink problem honest:

- ``authored_shaded`` (default): the authored mean was already judgmentally
  shaded for personal severity (e.g. tadalafil's note says it models "a small
  fraction of the published TTO gain"). Re-stripping placebo from an
  already-shaded number would double-count skepticism, so these use a mild
  residual-optimism prior instead of the category prior. Re-anchoring such an
  item to a published delta requires a private severity input — the user's
  call, not the model's.
- ``published_delta``: the claimed value IS a published placebo-adjusted (or
  measured-burden-based) effect, so the full category transport prior applies.
  Sleep-relief fractions qualify: personal severity is measured (wearable +
  home sleep study burdens), so the relief fraction is a pure evidence claim.

Calibration anchors for the category priors (approximate figures, cited as
calibration judgments in the same spirit as ``confounding.CATEGORY_PRIORS``):

- Subjective insomnia outcomes: placebo response averages roughly two-thirds
  of drug response (Winkler & Rief 2015, meta-analysis of placebo groups in
  insomnia drug trials); objective gains are far smaller than felt gains
  (melatonin latency ~-7 min, Ferracioli-Oda 2013).
- ED / PDE5 inhibitors: pivotal placebo-controlled RCTs show large
  drug-minus-placebo IIEF deltas (Goldstein 1998), so the evidence base is
  strong and the placebo share comparatively small.
- Mood/stress supplements: commercial ashwagandha trials are small,
  unregistered, and shrink in better designs (Speers 2021 review).
- Joint pain: GAIT (Clegg 2006) found glucosamine no better than placebo on
  the primary endpoint with a large placebo response.
- Magnesium for sleep: low-to-very-low certainty, small biased trials
  (Mah & Pitre 2021 systematic review).
- OSA therapy: sham-CPAP-controlled trials show real but modest subjective
  gains (e.g. Jenkinson 1999), alongside objective AHI normalization.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional

import numpy as np

from .confounding import ConfoundingPrior


def stable_seed(*parts: str) -> int:
    """Deterministic cross-process seed from string parts (PYTHONHASHSEED-proof)."""
    digest = hashlib.sha256("|".join(parts).encode("utf8")).digest()
    return int.from_bytes(digest[:4], "big")


QolStudyQuality = Literal[
    "rct_objective_endpoint",
    "meta_analysis_placebo_rcts",
    "rct_placebo_patient_reported",
    "rct_open_label",
    "supplement_industry_rct",
    "observational_symptom",
    "mechanistic_or_self_experiment",
]

# Reporting/publication shrinkage for symptom endpoints. Same shape as the
# mortality table; the weak tiers are harsher because subjective endpoints are
# easier to p-hack and selectively report than hard endpoints.
QOL_STUDY_QUALITY_SHRINKAGE: Dict[QolStudyQuality, float] = {
    "rct_objective_endpoint": 0.10,
    "meta_analysis_placebo_rcts": 0.15,
    "rct_placebo_patient_reported": 0.20,
    "rct_open_label": 0.40,
    "supplement_industry_rct": 0.50,
    "observational_symptom": 0.55,
    "mechanistic_or_self_experiment": 0.70,
}

QolClaimCategory = Literal[
    "sleep_symptom",
    "respiratory_airway",
    "sexual_function",
    "mood_stress",
    "pain_joint",
    "gi_symptom",
    "cognitive",
    "hair_skin",
    "fitness_function",
    "metabolic_symptom",
    "general_vitality",
]

# Transport priors: fraction of a *published/claimed* effect expected to
# survive placebo stripping plus population transport. Reuses ConfoundingPrior
# purely for its Beta mechanics (mean/CI/sampling).
QOL_TRANSPORT_PRIORS: Dict[QolClaimCategory, ConfoundingPrior] = {
    "sleep_symptom": ConfoundingPrior(
        alpha=2.4,
        beta=5.6,
        rationale=(
            "Placebo response averages ~64% of drug response for subjective "
            "insomnia outcomes (Winkler & Rief 2015); objective deltas are far "
            "smaller than felt ones. Beta(2.4, 5.6) -> mean 30%."
        ),
        calibration_sources=[
            "Winkler & Rief 2015 (placebo response in insomnia trials)",
            "Ferracioli-Oda 2013 (melatonin objective latency)",
        ],
    ),
    "respiratory_airway": ConfoundingPrior(
        alpha=4.5,
        beta=4.5,
        rationale=(
            "Airway interventions mix objective mechanics (AHI, resistance) "
            "with subjective sleepiness; sham-controlled CPAP trials show real "
            "but roughly halved subjective gains vs open-label. "
            "Beta(4.5, 4.5) -> mean 50%."
        ),
        calibration_sources=[
            "Jenkinson 1999 (sham-controlled CPAP)",
            "Kiely 2004 (nasal steroid in snorers)",
        ],
    ),
    "sexual_function": ConfoundingPrior(
        alpha=5.5,
        beta=4.5,
        rationale=(
            "PDE5 pivotal RCTs show large placebo-adjusted IIEF deltas, and "
            "continued revealed use signals response; transport still shrinks "
            "toward a milder-severity user. Beta(5.5, 4.5) -> mean 55%."
        ),
        calibration_sources=["Goldstein 1998 (sildenafil RCT)"],
    ),
    "mood_stress": ConfoundingPrior(
        alpha=2.0,
        beta=7.0,
        rationale=(
            "Commercial adaptogen/mood trials are small, unregistered, and "
            "shrink in better designs; placebo share of subjective mood gains "
            "is large. Beta(2.0, 7.0) -> mean 22%."
        ),
        calibration_sources=[
            "Speers 2021 (ashwagandha review)",
            "Kirsch 2008 (placebo share, subjective mood endpoints)",
        ],
    ),
    "pain_joint": ConfoundingPrior(
        alpha=2.5,
        beta=6.0,
        rationale=(
            "OA/joint trials show very large placebo responses; GAIT found "
            "glucosamine no better than placebo on its primary endpoint. "
            "Beta(2.5, 6.0) -> mean 29%."
        ),
        calibration_sources=["Clegg 2006 (GAIT)"],
    ),
    "gi_symptom": ConfoundingPrior(
        alpha=2.8,
        beta=5.2,
        rationale=(
            "Fiber/probiotic RCTs exist but endpoints are subjective and "
            "strain/formulation-specific effects transport poorly. "
            "Beta(2.8, 5.2) -> mean 35%."
        ),
        calibration_sources=["Ford 2018 (probiotics in IBS, meta-analysis)"],
    ),
    "cognitive": ConfoundingPrior(
        alpha=1.8,
        beta=7.2,
        rationale=(
            "Cognitive-supplement effects in healthy adults rarely replicate "
            "outside industry trials; expectancy effects dominate. "
            "Beta(1.8, 7.2) -> mean 20%."
        ),
        calibration_sources=["Docherty 2023 (lion's mane pilot, n=41)"],
    ),
    "hair_skin": ConfoundingPrior(
        alpha=4.0,
        beta=4.0,
        rationale=(
            "Finasteride hair outcomes are objective (photographic RCTs), but "
            "mapping appearance change to utility leans on proxy TTO weights. "
            "Beta(4.0, 4.0) -> mean 50%."
        ),
        calibration_sources=["Kaufman 1998 (finasteride RCT)"],
    ),
    "fitness_function": ConfoundingPrior(
        alpha=5.0,
        beta=3.0,
        rationale=(
            "CRF/strength gains from structured training are objective and "
            "RCT-backed; the shrink covers the indirect CRF-to-utility "
            "mapping, not the training response. Beta(5.0, 3.0) -> mean 63%."
        ),
        calibration_sources=["Milanovic 2015 (HIIT VO2max meta-analysis)"],
    ),
    "metabolic_symptom": ConfoundingPrior(
        alpha=3.0,
        beta=5.0,
        rationale=(
            "Glycemic/metabolic symptom claims ride on objective markers but "
            "subjective wellbeing mapping is indirect. Beta(3.0, 5.0) -> mean 38%."
        ),
        calibration_sources=["SELECT 2023 (semaglutide, hard endpoints)"],
    ),
    "general_vitality": ConfoundingPrior(
        alpha=1.5,
        beta=8.5,
        rationale=(
            "Diffuse 'energy/vitality/longevity support' claims have the "
            "weakest evidence-to-feeling mapping. Beta(1.5, 8.5) -> mean 15%."
        ),
        calibration_sources=[],
    ),
}

# Residual-optimism prior for authored_shaded anchors: the authored mean
# already embeds a personal-severity judgment, so only residual author
# optimism is stripped, not the full placebo share.
AUTHORED_RESIDUAL_OPTIMISM_PRIOR = ConfoundingPrior(
    alpha=6.0,
    beta=2.0,
    rationale=(
        "Authored qol_annual values were hand-shaded for personal severity; "
        "this strips residual optimism only. Beta(6, 2) -> mean 75%."
    ),
)

QolAnchor = Literal["authored_shaded", "published_delta"]


@dataclass(frozen=True)
class QolEvidence:
    """Evidence annotation for one QoL (or sleep-relief) claim."""

    study_quality: QolStudyQuality
    category: QolClaimCategory
    anchor: QolAnchor = "authored_shaded"
    note: str = ""
    sources: tuple = field(default_factory=tuple)

    @property
    def shrinkage(self) -> float:
        return QOL_STUDY_QUALITY_SHRINKAGE[self.study_quality]

    @property
    def transport_prior(self) -> ConfoundingPrior:
        if self.anchor == "authored_shaded":
            return AUTHORED_RESIDUAL_OPTIMISM_PRIOR
        return QOL_TRANSPORT_PRIORS[self.category]

    @property
    def multiplier_mean(self) -> float:
        """Expected retained fraction of the claimed effect."""
        return (1.0 - self.shrinkage) * self.transport_prior.mean

    def sample_multiplier(
        self,
        n_simulations: int,
        random_state: Optional[int] = None,
    ) -> np.ndarray:
        """Per-draw retained fraction: (1 - s) * theta, theta ~ Beta."""
        theta = self.transport_prior.sample(n_simulations, random_state)
        return (1.0 - self.shrinkage) * theta

    def lineage(self, claimed_annual: float) -> Dict[str, Any]:
        """Transparency payload: raw -> after shrinkage -> after transport."""
        prior = self.transport_prior
        after_shrinkage = claimed_annual * (1.0 - self.shrinkage)
        return {
            "study_quality": self.study_quality,
            "category": self.category,
            "anchor": self.anchor,
            "claimed_annual_qaly": claimed_annual,
            "shrinkage": self.shrinkage,
            "after_shrinkage_annual_qaly": after_shrinkage,
            "transport_prior": {
                "alpha": prior.alpha,
                "beta": prior.beta,
                "mean": prior.mean,
                "ci95": list(prior.ci(0.95)),
            },
            "effective_annual_qaly": claimed_annual * self.multiplier_mean,
            "multiplier_mean": self.multiplier_mean,
            "note": self.note,
            "sources": list(self.sources),
        }


def effective_claimed_annual(
    claimed_annual: float,
    evidence: Optional[QolEvidence],
) -> float:
    """Mean effective annual effect after the evidence guard (legacy passthrough
    when unannotated)."""
    if evidence is None:
        return claimed_annual
    return claimed_annual * evidence.multiplier_mean


def guarded_component_relief(
    component_relief: Dict[str, float],
    evidence: Optional[QolEvidence],
) -> Dict[str, float]:
    """Apply the mean evidence multiplier to sleep-relief fractions.

    Relief fractions are pure evidence claims (personal severity is measured
    upstream from wearables and the home sleep study), so unlike authored
    general-QoL means they take the full guard. The guarded fractions feed
    BOTH the sleep-QoL leg and the sleep mortality hazard multiplier, closing
    the previous bypass where relief-derived mortality benefit skipped every
    evidence adjustment.
    """
    if evidence is None or not component_relief:
        return dict(component_relief)
    multiplier = evidence.multiplier_mean
    return {
        component: float(fraction) * multiplier
        for component, fraction in component_relief.items()
    }
