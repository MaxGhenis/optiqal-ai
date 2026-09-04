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
from .priors import load_priors


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

_QOL_PRIOR_DATA = load_priors()["qol_transport"]

QOL_STUDY_QUALITY_SHRINKAGE: Dict[QolStudyQuality, float] = {
    key: round(1.0 - row["retention"], 12)
    for key, row in _QOL_PRIOR_DATA["study_quality_shrinkage"].items()
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


def _prior_from_row(row: dict) -> ConfoundingPrior:
    return ConfoundingPrior(
        alpha=row["alpha"],
        beta=row["beta"],
        rationale=row["rationale"],
        calibration_sources=list(row["calibration_sources"]),
    )


QOL_TRANSPORT_PRIORS: Dict[QolClaimCategory, ConfoundingPrior] = {
    key: _prior_from_row(row) for key, row in _QOL_PRIOR_DATA["categories"].items()
}

AUTHORED_RESIDUAL_OPTIMISM_PRIOR = _prior_from_row(
    _QOL_PRIOR_DATA["authored_residual_optimism"]
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
