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
# These reflect expected healthy user bias for each intervention type
CATEGORY_PRIORS = {
    # Exercise: Strong healthy user bias
    # RCT vs observational discrepancy suggests ~30-40% causal
    "exercise": ConfoundingPrior(
        alpha=2.5,
        beta=5.0,
        rationale=(
            "Exercise studies show strong healthy user bias. "
            "RCT effects typically 30-50% of observational estimates. "
            "Beta(2.5, 5.0) → mean 33%, 95% CI: 8-65%"
        ),
        calibration_sources=[
            "Hamer & Stamatakis 2012 (sibling comparison)",
            "Arem et al 2015 (dose-response modeling)",
            "Ekelund et al 2019 (device-measured PA)",
        ],
    ),
    # Diet: Moderate healthy user bias
    "diet": ConfoundingPrior(
        alpha=2.0,
        beta=4.0,
        rationale=(
            "Dietary studies have moderate confounding. "
            "PREDIMED and other RCTs suggest ~35% causal effect. "
            "Beta(2.0, 4.0) → mean 33%, 95% CI: 6-70%"
        ),
        calibration_sources=[
            "PREDIMED-Plus (RCT)",
            "Aune et al 2016 (nut meta-analysis)",
            "Golestan Cohort (cross-cultural validation)",
        ],
    ),
    # Sleep: Less healthy user bias than exercise
    "sleep": ConfoundingPrior(
        alpha=2.5,
        beta=4.5,
        rationale=(
            "Sleep interventions have moderate confounding. "
            "CBT-I RCTs show robust effects, but observational sleep studies "
            "confounded by comorbidities. Beta(2.5, 4.5) → mean 36%, 95% CI: 10-68%"
        ),
        calibration_sources=[
            "Trauer et al 2015 (CBT-I meta-analysis)",
            "Cappuccio et al 2010 (sleep duration cohort)",
        ],
    ),
    # Stress: Difficult to separate from confounders
    "stress": ConfoundingPrior(
        alpha=1.5,
        beta=4.5,
        rationale=(
            "Stress reduction studies have high confounding. "
            "Meditation/mindfulness RCTs show smaller effects than observational. "
            "Beta(1.5, 4.5) → mean 25%, 95% CI: 3-60%"
        ),
        calibration_sources=[
            "Goyal et al 2014 (meditation meta-analysis)",
            "Khoury et al 2015 (mindfulness-based therapy)",
        ],
    ),
    # Substance: Strong confounding from selection effects
    "substance": ConfoundingPrior(
        alpha=2.0,
        beta=4.5,
        rationale=(
            "Substance use studies have selection confounding. "
            "Smoking cessation RCTs vs observational show ~30-40% causal. "
            "Alcohol J-curve likely confounded. Beta(2.0, 4.5) → mean 31%, 95% CI: 6-64%"
        ),
        calibration_sources=[
            "Taylor et al 2014 (smoking cessation RCT meta)",
            "Stockwell et al 2016 (alcohol J-curve bias)",
        ],
    ),
    # Medical: Generally RCT-based, less confounding
    "medical": ConfoundingPrior(
        alpha=4.0,
        beta=3.0,
        rationale=(
            "Medical interventions usually have RCT evidence. "
            "Less healthy user bias; randomization controls confounding. "
            "Beta(4.0, 3.0) → mean 57%, 95% CI: 22-88%"
        ),
        calibration_sources=[
            "Cochrane systematic reviews",
            "FDA approval trials",
        ],
    ),
    # Social: Strong confounding from social selection
    "social": ConfoundingPrior(
        alpha=1.5,
        beta=5.0,
        rationale=(
            "Social interventions have strong selection effects. "
            "People with more social connections differ systematically. "
            "Beta(1.5, 5.0) → mean 23%, 95% CI: 3-55%"
        ),
        calibration_sources=[
            "Holt-Lunstad et al 2010 (social relationships meta)",
        ],
    ),
    # Other: Conservative prior
    "other": ConfoundingPrior(
        alpha=1.5,
        beta=4.5,
        rationale=(
            "Unknown intervention type; using conservative prior. "
            "Beta(1.5, 4.5) → mean 25%, 95% CI: 3-60%"
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
