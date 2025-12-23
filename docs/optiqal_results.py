"""Paper results wrapper for MyST {eval} directives.

This Python module wraps the TypeScript paper-results.ts values for use
in the JupyterBook documentation. Values are kept in sync manually.

Usage in paper:
    Inline: The QALY for exercise is {eval}`r.exercise.qaly`.
    Code cell:
        ```{code-cell} python
        :tags: [remove-cell]
        from optiqal_results import r
        ```
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class InterventionResult:
    """Results for a single intervention."""

    id: str
    name: str
    category: str
    qaly_mean: float
    qaly_ci_lower: float
    qaly_ci_upper: float
    life_years: float
    life_years_ci_lower: float
    life_years_ci_upper: float
    evidence_quality: str
    sources: list[str]

    @property
    def qaly(self) -> str:
        """Format QALY for inline use."""
        return f"{self.qaly_mean:.2f}"

    @property
    def qaly_ci(self) -> str:
        """Format QALY CI for inline use."""
        return f"[{self.qaly_ci_lower:.2f}, {self.qaly_ci_upper:.2f}]"

    @property
    def life_years_fmt(self) -> str:
        """Format life years for inline use."""
        return f"{self.life_years:.1f}"

    @property
    def months(self) -> float:
        """Life years in months."""
        return self.life_years * 12

    @property
    def months_fmt(self) -> str:
        """Format months for inline use."""
        return f"{self.months:.0f}"


@dataclass
class ConfoundingParams:
    """Confounding calibration parameters."""

    alpha: float
    beta: float
    mean: float
    ci_lower: float
    ci_upper: float


class PaperResults:
    """Container for all paper results."""

    def __init__(self):
        # Target population
        self.target_age = 40
        self.baseline_qalys = 35.2

        # Confounding calibration
        self.confounding = ConfoundingParams(
            alpha=2.5,
            beta=5.0,
            mean=0.33,
            ci_lower=0.10,
            ci_upper=0.60,
        )

        # Key intervention results
        self.quit_smoking = InterventionResult(
            id="quit_smoking",
            name="Quit Smoking (vs 20 pack-years)",
            category="substance",
            qaly_mean=1.55,
            qaly_ci_lower=0.82,
            qaly_ci_upper=2.41,
            life_years=2.1,
            life_years_ci_lower=1.1,
            life_years_ci_upper=3.2,
            evidence_quality="high",
            sources=["Jha 2013", "Doll 2004"],
        )

        self.exercise = InterventionResult(
            id="exercise_150min",
            name="Exercise 150 min/week (vs sedentary)",
            category="exercise",
            qaly_mean=1.03,
            qaly_ci_lower=0.51,
            qaly_ci_upper=1.62,
            life_years=1.4,
            life_years_ci_lower=0.7,
            life_years_ci_upper=2.2,
            evidence_quality="high",
            sources=["Arem 2015", "Moore 2012"],
        )

        self.mediterranean_diet = InterventionResult(
            id="mediterranean_diet",
            name="Mediterranean Diet (vs typical Western)",
            category="diet",
            qaly_mean=0.75,
            qaly_ci_lower=0.32,
            qaly_ci_upper=1.24,
            life_years=1.0,
            life_years_ci_lower=0.4,
            life_years_ci_upper=1.7,
            evidence_quality="high",
            sources=["PREDIMED 2018", "Estruch 2013"],
        )

        self.daily_nuts = InterventionResult(
            id="daily_nut_consumption",
            name="Daily Nuts 28g (vs none)",
            category="diet",
            qaly_mean=0.45,
            qaly_ci_lower=0.18,
            qaly_ci_upper=0.78,
            life_years=0.6,
            life_years_ci_lower=0.2,
            life_years_ci_upper=1.0,
            evidence_quality="moderate",
            sources=["Aune 2016", "Bao 2013"],
        )

        self.reduce_alcohol = InterventionResult(
            id="reduce_alcohol_moderate",
            name="Moderate Alcohol (vs heavy >14/week)",
            category="substance",
            qaly_mean=0.38,
            qaly_ci_lower=0.12,
            qaly_ci_upper=0.71,
            life_years=0.5,
            life_years_ci_lower=0.2,
            life_years_ci_upper=0.9,
            evidence_quality="moderate",
            sources=["Wood 2018", "GBD 2016"],
        )

        self.sleep = InterventionResult(
            id="consistent_bedtime",
            name="Sleep 7-8h (vs <6h)",
            category="sleep",
            qaly_mean=0.52,
            qaly_ci_lower=0.21,
            qaly_ci_upper=0.89,
            life_years=0.7,
            life_years_ci_lower=0.3,
            life_years_ci_upper=1.2,
            evidence_quality="moderate",
            sources=["Cappuccio 2010", "Yin 2017"],
        )

        self.social = InterventionResult(
            id="regular_social_interaction",
            name="Social Connection (vs isolated)",
            category="stress",
            qaly_mean=0.68,
            qaly_ci_lower=0.28,
            qaly_ci_upper=1.15,
            life_years=0.9,
            life_years_ci_lower=0.4,
            life_years_ci_upper=1.5,
            evidence_quality="moderate",
            sources=["Holt-Lunstad 2010", "House 1988"],
        )

        self.meditation = InterventionResult(
            id="meditation_daily",
            name="Daily Meditation 10-20min (vs none)",
            category="stress",
            qaly_mean=0.22,
            qaly_ci_lower=0.05,
            qaly_ci_upper=0.45,
            life_years=0.3,
            life_years_ci_lower=0.1,
            life_years_ci_upper=0.6,
            evidence_quality="low",
            sources=["Goyal 2014", "Black 2015"],
        )

        # Summary statistics
        self.intervention_count = 44
        self.category_count = 6

        # Key findings
        self.qaly_range = "0.22-1.55"
        self.life_years_range = "0.3-2.1"
        self.months_range = "4-25"

    @property
    def confounding_mean(self) -> str:
        return f"{self.confounding.mean:.0%}"

    @property
    def confounding_ci(self) -> str:
        return f"{self.confounding.ci_lower:.0%}-{self.confounding.ci_upper:.0%}"

    def all_interventions(self) -> list[InterventionResult]:
        """Return all intervention results sorted by QALY impact."""
        return sorted([
            self.quit_smoking,
            self.exercise,
            self.mediterranean_diet,
            self.daily_nuts,
            self.reduce_alcohol,
            self.sleep,
            self.social,
            self.meditation,
        ], key=lambda x: x.qaly_mean, reverse=True)

    def intervention_table(self) -> str:
        """Generate markdown table of interventions."""
        header = "| Intervention | Category | QALYs | 95% CI | Life Years | Evidence |\n"
        header += "|--------------|----------|-------|--------|------------|----------|\n"

        rows = []
        for i in self.all_interventions():
            row = f"| {i.name} | {i.category} | {i.qaly} | {i.qaly_ci} | {i.life_years_fmt} | {i.evidence_quality} |"
            rows.append(row)

        return header + "\n".join(rows)


# Global instance for {eval} access
r = PaperResults()


if __name__ == "__main__":
    # Verify values
    print(f"Target age: {r.target_age}")
    print(f"Quit smoking: {r.quit_smoking.qaly} QALYs ({r.quit_smoking.months_fmt} months)")
    print(f"Exercise: {r.exercise.qaly} QALYs ({r.exercise.months_fmt} months)")
    print(f"QALY range: {r.qaly_range}")
    print()
    print(r.intervention_table())
