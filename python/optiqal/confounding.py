"""
Confounding Adjustment Module

Evidence-calibrated priors for causal fraction estimation.
Based on whatnut methodology.
"""

from dataclasses import dataclass
from typing import Literal, Optional, Union

import numpy as np
from scipy import stats

from .priors import load_priors


@dataclass
class ConfoundingPrior:
    """
    Beta prior for causal fraction.

    The causal fraction represents what proportion of the observed
    association is actually causal (vs. due to confounding).

    For example, if we observe HR = 0.78 and causal_fraction = 0.25,
    then the causal HR = exp(0.25 * log(0.78)) ≈ 0.94.
    """

    alpha: float
    beta: float
    rationale: str = ""
    calibration_sources: list = None

    def __post_init__(self):
        if self.calibration_sources is None:
            self.calibration_sources = []

    @property
    def mean(self) -> float:
        """Expected causal fraction."""
        return self.alpha / (self.alpha + self.beta)

    @property
    def variance(self) -> float:
        """Variance of causal fraction."""
        a, b = self.alpha, self.beta
        return (a * b) / ((a + b) ** 2 * (a + b + 1))

    @property
    def std(self) -> float:
        """Standard deviation of causal fraction."""
        return np.sqrt(self.variance)

    def ci(self, level: float = 0.95) -> tuple:
        """Credible interval for causal fraction."""
        tail = (1 - level) / 2
        dist = stats.beta(self.alpha, self.beta)
        return (dist.ppf(tail), dist.ppf(1 - tail))

    def sample(
        self,
        n: int = 1,
        random_state: Optional[Union[int, np.random.Generator]] = None,
    ) -> np.ndarray:
        """Sample from the prior."""
        rng = np.random.default_rng(random_state)
        return rng.beta(self.alpha, self.beta, size=n)


def _prior_from_row(row: dict) -> ConfoundingPrior:
    """Build the runtime object while keeping the YAML as the value source."""
    return ConfoundingPrior(
        alpha=row["alpha"],
        beta=row["beta"],
        rationale=row.get("rationale", ""),
        calibration_sources=list(row.get("calibration_sources", [])),
    )


_PRIOR_DATA = load_priors()
_CONFOUNDING_DATA = _PRIOR_DATA["confounding"]

CATEGORY_PRIORS = {
    key: _prior_from_row(row) for key, row in _CONFOUNDING_DATA["categories"].items()
}
INTERVENTION_PRIORS = {
    key: _prior_from_row(row) for key, row in _CONFOUNDING_DATA["interventions"].items()
}
PROTOCOL_INTERVENTION_PRIORS = {
    key: _prior_from_row(row)
    for key, row in _CONFOUNDING_DATA["protocol_interventions"].items()
}
EVIDENCE_ADJUSTMENTS = {
    key: row["alpha_multiplier"]
    for key, row in _PRIOR_DATA["evidence_adjustments"].items()
}


def get_confounding_prior(
    category: str,
    evidence_type: Optional[str] = None,
) -> ConfoundingPrior:
    """
    Get confounding prior for an intervention category.

    Args:
        category: Intervention category (exercise, diet, etc.)
        evidence_type: Primary study type (rct, cohort, etc.)

    Returns:
        ConfoundingPrior with adjusted alpha if evidence_type provided.
    """
    base = CATEGORY_PRIORS.get(category, CATEGORY_PRIORS["other"])

    if evidence_type is None:
        return base

    multiplier = EVIDENCE_ADJUSTMENTS.get(evidence_type, 1.0)
    return ConfoundingPrior(
        alpha=base.alpha * multiplier,
        beta=base.beta,
        rationale=f"{base.rationale} Adjusted for {evidence_type}.",
        calibration_sources=base.calibration_sources,
    )


StudyQuality = Literal[
    "rct_preregistered_hard_endpoint",
    "rct_standard",
    "meta_analysis_rcts",
    "cohort_large",
    "cohort_small",
    "case_control",
    "supplement_industry_rct",
    "observational_speculative",
    "animal_or_mechanistic",
]

STUDY_QUALITY_SHRINKAGE: dict[StudyQuality, float] = {
    key: round(1.0 - row["retention"], 12)
    for key, row in _PRIOR_DATA["study_quality_shrinkage"].items()
}


def shrinkage_for_study_quality(
    study_quality: Optional[str],
    fallback: float = 0.30,
) -> float:
    """Look up publication-bias shrinkage for a study-quality tier."""
    if study_quality is None:
        return fallback
    return STUDY_QUALITY_SHRINKAGE.get(study_quality, fallback)


def publication_bias_correct(
    observed_hr: float,
    shrinkage: float = 0.30,
    study_quality: Optional[str] = None,
) -> float:
    """
    Correct hazard ratio for publication bias by shrinking toward null.

    Published effect sizes are systematically inflated due to:
    - Selective reporting (significant results more likely published)
    - P-hacking and researcher degrees of freedom
    - Winner's curse (largest estimates most likely to cross threshold)

    Shrinks log(HR) toward 0 (null) by the specified fraction.

    Args:
        observed_hr: Published/observed hazard ratio.
        shrinkage: Fraction to shrink toward null. Used as a fallback when
            ``study_quality`` is not supplied. 0.30 matches Ioannidis 2008
            average inflation in cohort studies.
        study_quality: Optional study-quality tier. When provided, overrides
            ``shrinkage`` with the tier-specific value from
            :data:`STUDY_QUALITY_SHRINKAGE`.

    Returns:
        Bias-corrected hazard ratio (closer to 1.0 than observed).

    Example:
        >>> publication_bias_correct(0.80, shrinkage=0.30)
        0.854  # log(0.80) * 0.70 → less protective after correction
        >>> publication_bias_correct(0.80, study_quality="supplement_industry_rct")
        0.894  # 50% shrinkage → much weaker effect after correction
    """
    effective_shrinkage = shrinkage_for_study_quality(study_quality, fallback=shrinkage)
    log_hr = np.log(observed_hr)
    corrected = log_hr * (1 - effective_shrinkage)
    return float(np.exp(corrected))


def hr_to_lognormal_params(hr: float, log_sd: float) -> dict:
    """Return mean-centered lognormal parameters for a hazard ratio.

    The naive parameterization ``log_mean = log(hr)`` makes ``hr`` the
    *median* of the sampled distribution, not the mean. Because the
    lognormal's mean is ``exp(log_mean + log_sd**2 / 2)``, any ``log_sd > 0``
    produces Monte Carlo draws whose mean is ``hr * exp(log_sd**2 / 2) > hr``
    for protective effects (or < hr when hr > 1). For a genuinely null
    intervention (hr = 1.0), this yields an average draw of
    ``exp(log_sd**2 / 2)`` ≈ 1.007 at log_sd = 0.12 — a spurious harm signal
    in the life-table integration.

    This helper returns parameters such that ``E[HR] == hr`` exactly:
    ``log_mean = log(hr) - log_sd**2 / 2``. Under this convention the
    *median* is ``hr * exp(-log_sd**2 / 2)`` (slightly more protective), and
    the mean is what the user typed.

    This matches the cost-effectiveness literature convention where the
    reported point estimate is the expected value, not the median draw.
    """
    if hr <= 0:
        raise ValueError(f"hr must be positive, got {hr}")
    if log_sd < 0:
        raise ValueError(f"log_sd must be non-negative, got {log_sd}")
    return {
        "log_mean": float(np.log(hr) - (log_sd**2) / 2.0),
        "log_sd": float(log_sd),
    }


def adjust_hr(observed_hr: float, causal_fraction: float) -> float:
    """
    Adjust hazard ratio by causal fraction.

    For protective effects (HR < 1):
    log(HR_causal) = causal_fraction × log(HR_observed)

    This shrinks the effect toward null (HR = 1).
    """
    log_hr = np.log(observed_hr)
    adjusted_log_hr = causal_fraction * log_hr
    return np.exp(adjusted_log_hr)


def calculate_e_value(observed_hr: float) -> tuple:
    """
    Calculate E-value for robustness to unmeasured confounding.

    The E-value quantifies the minimum strength of association an
    unmeasured confounder would need with both exposure and outcome
    to fully explain an observed association.

    Reference: VanderWeele & Ding (2017)

    Args:
        observed_hr: Observed hazard ratio

    Returns:
        (e_value, interpretation)
    """
    # Convert protective effects to RR > 1
    rr = 1 / observed_hr if observed_hr < 1 else observed_hr

    # E-value formula
    e_value = rr + np.sqrt(rr * (rr - 1))

    # Interpretation
    if e_value < 1.5:
        interpretation = "Very susceptible to confounding"
    elif e_value < 2.0:
        interpretation = "Moderately robust (RR ~2 confounder could explain)"
    elif e_value < 3.0:
        interpretation = "Reasonably robust (RR ~2-3 confounder needed)"
    else:
        interpretation = "Robust to confounding (RR >3 needed)"

    return e_value, interpretation
