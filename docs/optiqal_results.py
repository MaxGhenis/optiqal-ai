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
    """Confounding calibration parameters.

    Note: The framework uses category-specific priors (see paper Table).
    Values here represent the exercise category prior, which is the
    primary reference intervention.
    """

    alpha: float
    beta: float
    mean: float
    ci_lower: float
    ci_upper: float
    category: str = "exercise"  # Reference category


@dataclass
class ReferenceCase:
    """Reference person for estimates."""

    age: int
    sex: str
    bmi: float
    systolic_bp: int
    smoking: str
    exercise_min: int
    diet_adherence: float
    drinks_per_week: int
    sleep_hours: float
    social_connections: int

    @property
    def description(self) -> str:
        return (
            f"{self.age}-year-old {self.sex}, BMI {self.bmi}, "
            f"BP {self.systolic_bp}, {self.smoking} smoker, "
            f"{self.exercise_min} min/week exercise"
        )


class PaperResults:
    """Container for all paper results."""

    def __init__(self):
        # Reference person: average American adult (less healthy than default)
        self.reference = ReferenceCase(
            age=40,
            sex="male",
            bmi=28.5,           # US average (overweight)
            systolic_bp=128,    # Elevated
            smoking="never",
            exercise_min=50,    # Below guideline (sedentary-ish)
            diet_adherence=0.35,  # Below average
            drinks_per_week=5,
            sleep_hours=6.5,    # Below optimal
            social_connections=3,
        )

        # Target population
        self.target_age = self.reference.age
        self.baseline_qalys = 33.8  # Lower due to less healthy baseline

        # Confounding calibration (exercise category - primary reference)
        # See paper for category-specific priors table
        self.confounding = ConfoundingParams(
            alpha=1.2,
            beta=6.0,
            mean=0.17,  # 1.2 / (1.2 + 6.0) = 0.167
            ci_lower=0.02,
            ci_upper=0.45,
            category="exercise",
        )

        # Key intervention results (from precomputed profiles, 40yo male overweight reference)
        self.quit_smoking = InterventionResult(
            id="quit_smoking",
            name="Quit Smoking (vs current smoker)",
            category="substance",
            qaly_mean=1.15,
            qaly_ci_lower=0.61,
            qaly_ci_upper=1.66,
            life_years=4.4,
            life_years_ci_lower=2.4,
            life_years_ci_upper=6.5,
            evidence_quality="high",
            sources=["Jha 2013", "Doll 2004"],
        )

        self.exercise = InterventionResult(
            id="exercise_150min",
            name="Exercise 150 min/week (vs light activity)",
            category="exercise",
            qaly_mean=0.33,
            qaly_ci_lower=0.08,
            qaly_ci_upper=0.78,
            life_years=1.2,
            life_years_ci_lower=0.3,
            life_years_ci_upper=2.9,
            evidence_quality="high",
            sources=["Arem 2015", "Moore 2012"],
        )

        self.mediterranean_diet = InterventionResult(
            id="mediterranean_diet",
            name="Mediterranean Diet (vs typical Western)",
            category="diet",
            qaly_mean=0.45,
            qaly_ci_lower=0.10,
            qaly_ci_upper=0.90,
            life_years=1.7,
            life_years_ci_lower=0.4,
            life_years_ci_upper=3.4,
            evidence_quality="high",
            sources=["PREDIMED 2018", "Estruch 2013"],
        )

        self.daily_nuts = InterventionResult(
            id="daily_nut_consumption",
            name="Daily Nuts 28g (vs none)",
            category="diet",
            qaly_mean=0.25,  # Estimated based on diet fraction
            qaly_ci_lower=0.05,
            qaly_ci_upper=0.50,
            life_years=0.9,
            life_years_ci_lower=0.2,
            life_years_ci_upper=1.9,
            evidence_quality="moderate",
            sources=["Aune 2016", "Bao 2013"],
        )

        self.reduce_alcohol = InterventionResult(
            id="reduce_alcohol_moderate",
            name="Moderate Alcohol (vs heavy >14/week)",
            category="substance",
            qaly_mean=0.08,
            qaly_ci_lower=-0.05,
            qaly_ci_upper=0.39,
            life_years=0.3,
            life_years_ci_lower=-0.2,
            life_years_ci_upper=1.5,
            evidence_quality="moderate",
            sources=["Wood 2018", "GBD 2016"],
        )

        self.sleep = InterventionResult(
            id="consistent_bedtime",
            name="Sleep 7-8h (vs <7h)",
            category="sleep",
            qaly_mean=0.07,
            qaly_ci_lower=-0.05,
            qaly_ci_upper=0.33,
            life_years=0.2,
            life_years_ci_lower=-0.2,
            life_years_ci_upper=1.2,
            evidence_quality="moderate",
            sources=["Cappuccio 2010", "Yin 2017"],
        )

        self.social = InterventionResult(
            id="regular_social_interaction",
            name="Social Connection (vs isolated)",
            category="stress",
            qaly_mean=0.35,  # Estimated based on meditation/stress category
            qaly_ci_lower=0.08,
            qaly_ci_upper=0.75,
            life_years=1.3,
            life_years_ci_lower=0.3,
            life_years_ci_upper=2.8,
            evidence_quality="moderate",
            sources=["Holt-Lunstad 2010", "House 1988"],
        )

        self.meditation = InterventionResult(
            id="meditation_daily",
            name="Daily Meditation 10-20min (vs none)",
            category="stress",
            qaly_mean=0.10,
            qaly_ci_lower=-0.22,
            qaly_ci_upper=0.48,
            life_years=0.4,
            life_years_ci_lower=-0.8,
            life_years_ci_upper=1.8,
            evidence_quality="low",
            sources=["Goyal 2014", "Black 2015"],
        )

        self.walking = InterventionResult(
            id="walking_30min",
            name="Walk 30 min/day (vs sedentary)",
            category="exercise",
            qaly_mean=0.14,
            qaly_ci_lower=0.01,
            qaly_ci_upper=0.42,
            life_years=0.5,
            life_years_ci_lower=0.04,
            life_years_ci_upper=1.6,
            evidence_quality="high",
            sources=["Kelly 2014", "Murtagh 2015"],
        )

        self.strength_training = InterventionResult(
            id="strength_training",
            name="Strength Training 2x/week",
            category="exercise",
            qaly_mean=0.10,
            qaly_ci_lower=-0.06,
            qaly_ci_upper=0.42,
            life_years=0.4,
            life_years_ci_lower=-0.2,
            life_years_ci_upper=1.6,
            evidence_quality="moderate",
            sources=["Stamatakis 2018", "Liu 2019"],
        )

        # Alternative reference cases for sensitivity
        self.smoker_reference = ReferenceCase(
            age=40,
            sex="male",
            bmi=27.0,
            systolic_bp=130,
            smoking="current",  # 20 pack-years
            exercise_min=30,
            diet_adherence=0.30,
            drinks_per_week=8,
            sleep_hours=6.0,
            social_connections=2,
        )

        self.healthy_reference = ReferenceCase(
            age=40,
            sex="female",
            bmi=23.0,
            systolic_bp=115,
            smoking="never",
            exercise_min=180,  # Already active
            diet_adherence=0.65,
            drinks_per_week=2,
            sleep_hours=7.5,
            social_connections=6,
        )

        self.elderly_reference = ReferenceCase(
            age=65,
            sex="male",
            bmi=27.0,
            systolic_bp=135,
            smoking="former",
            exercise_min=60,
            diet_adherence=0.45,
            drinks_per_week=4,
            sleep_hours=6.5,
            social_connections=4,
        )

        # Sensitivity: QALY gains by age (for exercise intervention, from precomputed)
        self.exercise_by_age = {
            30: 0.28,
            40: 0.33,
            50: 0.38,
            60: 0.40,
            70: 0.38,
            80: 0.28,
        }

        # Sensitivity: QALY gains by baseline BMI (for diet intervention, from precomputed)
        self.diet_by_bmi = {
            22: 0.44,   # normal BMI
            25: 0.45,   # overweight
            30: 0.58,   # obese
            35: 0.63,   # severely obese
        }

        # Summary statistics
        self.intervention_count = 10
        self.category_count = 5

        # Key findings (from precomputed, 40yo male overweight reference)
        self.qaly_range = "0.05-1.15"
        self.life_years_range = "0.2-4.4"
        self.months_range = "2-53"

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
            self.social,
            self.daily_nuts,
            self.walking,
            self.strength_training,
            self.meditation,
            self.reduce_alcohol,
            self.sleep,
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
