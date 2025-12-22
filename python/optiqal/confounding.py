"""
Confounding Adjustment Module

Evidence-calibrated priors for causal fraction estimation.
Based on whatnut methodology.
"""

from dataclasses import dataclass
from typing import Literal, Optional
import numpy as np
from scipy import stats


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

    def sample(self, n: int = 1, random_state: Optional[int] = None) -> np.ndarray:
        """Sample from the prior."""
        rng = np.random.default_rng(random_state)
        return rng.beta(self.alpha, self.beta, size=n)


# Category-specific confounding priors
#
# CALIBRATED against actual RCT vs observational discrepancies:
# - Exercise: Ballin 2021 RCT review shows ~0 causal effect, Finnish Twin Cohort confirms
# - Diet: PREDIMED RCT confirms substantial causal effect (~70% of observational)
# - Medical: Statin studies show ~28% causal fraction (HR 0.54 obs vs 0.84 RCT)
CATEGORY_PRIORS = {
    # Exercise: VERY skeptical - RCTs and twin studies show ~0 causal effect
    "exercise": ConfoundingPrior(
        alpha=1.2,
        beta=6.0,
        rationale=(
            "CALIBRATED: RCTs show exercise does not reduce mortality (Ballin 2021, n=50k). "
            "Finnish Twin Cohort 2024: identical twins discordant for PA show no mortality difference. "
            "Beta(1.2, 6.0) → mean 17%, 95% CI: 2-45%"
        ),
        calibration_sources=[
            "Ballin et al. 2021 (RCT critical review, n=50k)",
            "Finnish Twin Cohort 2024 (twin discordance)",
            "Mendelian randomization studies (null for mortality)",
        ],
    ),
    # Diet: Less skeptical - PREDIMED RCT confirms substantial causal effect
    "diet": ConfoundingPrior(
        alpha=3.0,
        beta=3.0,
        rationale=(
            "CALIBRATED: PREDIMED RCT confirms 30% CVD reduction, consistent with observational. "
            "Nuts, olive oil have RCT backing. Diet has higher causal fraction than exercise. "
            "Beta(3.0, 3.0) → mean 50%, 95% CI: 15-85%"
        ),
        calibration_sources=[
            "PREDIMED Trial 2018 (RCT, n=7447, 30% CVD reduction)",
            "Aune et al. 2016 (nut meta-analysis)",
        ],
    ),
    # Sleep: Skeptical - no RCT evidence for mortality
    "sleep": ConfoundingPrior(
        alpha=1.5,
        beta=4.5,
        rationale=(
            "No RCTs for sleep duration and mortality. High reverse causation risk: "
            "illness affects sleep patterns. CBT-I shows causal quality-of-life effects. "
            "Beta(1.5, 4.5) → mean 25%, 95% CI: 3-58%"
        ),
        calibration_sources=[
            "Cappuccio et al. 2010 (observational only)",
            "No mortality RCTs available",
        ],
    ),
    # Stress: Very skeptical
    "stress": ConfoundingPrior(
        alpha=1.2,
        beta=5.0,
        rationale=(
            "Meditation/mindfulness RCTs show much smaller effects than observational. "
            "Stress levels heavily confounded with SES, health behaviors. "
            "Beta(1.2, 5.0) → mean 19%, 95% CI: 2-50%"
        ),
        calibration_sources=[
            "Goyal et al. 2014 (meditation RCT meta-analysis)",
            "Khoury et al. 2015",
        ],
    ),
    # Substance: Mixed - smoking has RCT backing, alcohol J-curve is confounded
    "substance": ConfoundingPrior(
        alpha=2.0,
        beta=4.0,
        rationale=(
            "CALIBRATED: Smoking cessation has strong RCT backing (causal fraction ~56%). "
            "Alcohol J-curve is entirely confounded (MR shows no benefit). "
            "Beta(2.0, 4.0) → mean 33%, 95% CI: 6-68%"
        ),
        calibration_sources=[
            "Taylor et al. 2014 (smoking cessation RCTs, ~56% causal)",
            "Stockwell et al. 2016 (alcohol J-curve is bias)",
        ],
    ),
    # Medical: Moderate skepticism - even RCT-based drugs show observational inflation
    "medical": ConfoundingPrior(
        alpha=2.5,
        beta=4.0,
        rationale=(
            "CALIBRATED: Even RCT-based drugs show observational inflation. "
            "Statins: HR 0.54 observational vs 0.84 RCT (causal fraction ~28%). "
            "Beta(2.5, 4.0) → mean 38%, 95% CI: 8-73%"
        ),
        calibration_sources=[
            "Danaei et al. 2012 (statin RCT vs observational)",
            "ARRIVE/ASPREE trials (aspirin less effective)",
        ],
    ),
    # Social: Very skeptical - no RCT possible
    "social": ConfoundingPrior(
        alpha=1.0,
        beta=5.5,
        rationale=(
            "Social relationships heavily confounded with SES, mental health, physical health. "
            "No RCT evidence possible for mortality endpoints. "
            "Beta(1.0, 5.5) → mean 15%, 95% CI: 1-42%"
        ),
        calibration_sources=[
            "Holt-Lunstad et al. 2010 (observational only)",
        ],
    ),
    # Other: Conservative prior
    "other": ConfoundingPrior(
        alpha=1.2,
        beta=4.8,
        rationale=(
            "Unknown intervention type; using conservative prior "
            "reflecting general observational bias from calibration data. "
            "Beta(1.2, 4.8) → mean 20%, 95% CI: 2-50%"
        ),
    ),
}

# Evidence type adjustments (multipliers on alpha)
EVIDENCE_ADJUSTMENTS = {
    "meta-analysis": 1.1,
    "rct": 1.5,
    "cohort": 0.8,
    "case-control": 0.7,
    "review": 1.0,
    "other": 0.9,
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
