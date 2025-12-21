"""
Intervention Definition Module

Reads YAML intervention definitions (shared with TypeScript package).
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union
import yaml
import numpy as np
from scipy import stats

from .confounding import ConfoundingPrior, get_confounding_prior


@dataclass
class Distribution:
    """Statistical distribution for uncertain parameters."""

    type: Literal["point", "normal", "lognormal", "beta", "uniform"]
    params: Dict[str, float]

    @classmethod
    def from_dict(cls, data: Union[str, dict]) -> "Distribution":
        """Parse from YAML format (object or shorthand string)."""
        if isinstance(data, str):
            return cls._parse_shorthand(data)

        dist_type = data["type"]
        params = {}

        if dist_type == "point":
            params["value"] = data["value"]
        elif dist_type == "normal":
            params["mean"] = data["mean"]
            params["sd"] = data["sd"]
        elif dist_type == "lognormal":
            params["log_mean"] = data.get("log_mean", data.get("logMean"))
            params["log_sd"] = data.get("log_sd", data.get("logSd"))
        elif dist_type == "beta":
            params["alpha"] = data["alpha"]
            params["beta"] = data["beta"]
        elif dist_type == "uniform":
            params["min"] = data["min"]
            params["max"] = data["max"]

        return cls(type=dist_type, params=params)

    @classmethod
    def _parse_shorthand(cls, s: str) -> "Distribution":
        """Parse shorthand like 'Normal(-4, 2)' or 'LogNormal(-0.18, 0.08)'."""
        import re

        match = re.match(r"(\w+)\(([^)]+)\)", s)
        if not match:
            raise ValueError(f"Invalid distribution shorthand: {s}")

        dist_type = match.group(1).lower()
        args = [float(x.strip()) for x in match.group(2).split(",")]

        if dist_type == "normal":
            return cls(type="normal", params={"mean": args[0], "sd": args[1]})
        elif dist_type == "lognormal":
            return cls(type="lognormal", params={"log_mean": args[0], "log_sd": args[1]})
        elif dist_type == "beta":
            return cls(type="beta", params={"alpha": args[0], "beta": args[1]})
        elif dist_type == "uniform":
            return cls(type="uniform", params={"min": args[0], "max": args[1]})
        elif dist_type == "point":
            return cls(type="point", params={"value": args[0]})
        else:
            raise ValueError(f"Unknown distribution type: {dist_type}")

    def sample(self, n: int = 1, random_state: Optional[int] = None) -> np.ndarray:
        """Sample from the distribution."""
        rng = np.random.default_rng(random_state)

        if self.type == "point":
            return np.full(n, self.params["value"])
        elif self.type == "normal":
            return rng.normal(self.params["mean"], self.params["sd"], size=n)
        elif self.type == "lognormal":
            return np.exp(
                rng.normal(self.params["log_mean"], self.params["log_sd"], size=n)
            )
        elif self.type == "beta":
            return rng.beta(self.params["alpha"], self.params["beta"], size=n)
        elif self.type == "uniform":
            return rng.uniform(self.params["min"], self.params["max"], size=n)

    @property
    def mean(self) -> float:
        """Expected value of the distribution."""
        if self.type == "point":
            return self.params["value"]
        elif self.type == "normal":
            return self.params["mean"]
        elif self.type == "lognormal":
            mu, sigma = self.params["log_mean"], self.params["log_sd"]
            return np.exp(mu + sigma**2 / 2)
        elif self.type == "beta":
            a, b = self.params["alpha"], self.params["beta"]
            return a / (a + b)
        elif self.type == "uniform":
            return (self.params["min"] + self.params["max"]) / 2


@dataclass
class MechanismEffect:
    """Effect on a biological mechanism."""

    mechanism: str
    effect_size: Distribution
    direction: Literal["increase", "decrease"]
    units: Optional[str] = None
    evidence: Literal["strong", "moderate", "weak"] = "moderate"
    source: Optional[str] = None


@dataclass
class MortalityEffect:
    """Mortality effect of an intervention."""

    hazard_ratio: Distribution
    onset_delay: float = 0
    ramp_up: float = 0.5
    decay_rate: float = 0


@dataclass
class Intervention:
    """
    Complete intervention specification.

    Can be loaded from YAML files (shared format with TypeScript).
    """

    id: str
    name: str
    category: Literal[
        "exercise", "diet", "sleep", "stress", "substance", "medical", "social", "other"
    ]
    description: Optional[str] = None
    keywords: List[str] = field(default_factory=list)

    # Effects
    mechanisms: List[MechanismEffect] = field(default_factory=list)
    mortality: Optional[MortalityEffect] = None

    # Evidence
    evidence_quality: Literal["high", "moderate", "low", "very-low"] = "moderate"
    primary_study_type: Optional[str] = None
    sources: List[Dict[str, Any]] = field(default_factory=list)

    # Confounding
    confounding_prior: Optional[ConfoundingPrior] = None

    # Caveats
    caveats: List[str] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "Intervention":
        """Load intervention from YAML file."""
        path = Path(path)
        with open(path) as f:
            data = yaml.safe_load(f)

        return cls._from_dict(data)

    @classmethod
    def from_yaml_string(cls, yaml_str: str) -> "Intervention":
        """Load intervention from YAML string."""
        data = yaml.safe_load(yaml_str)
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict) -> "Intervention":
        """Parse from dictionary."""
        # Parse mechanisms
        mechanisms = []
        if "mechanisms" in data:
            for mech_name, mech_data in data["mechanisms"].items():
                mechanisms.append(
                    MechanismEffect(
                        mechanism=mech_name,
                        effect_size=Distribution.from_dict(mech_data["effect"]),
                        direction=mech_data["direction"],
                        units=mech_data.get("units"),
                        evidence=mech_data.get("evidence", "moderate"),
                        source=mech_data.get("source"),
                    )
                )

        # Parse mortality
        mortality = None
        if "mortality" in data:
            mort = data["mortality"]
            mortality = MortalityEffect(
                hazard_ratio=Distribution.from_dict(mort["hazard_ratio"]),
                onset_delay=mort.get("onset_delay", 0),
                ramp_up=mort.get("ramp_up", 0.5),
                decay_rate=mort.get("decay_rate", 0),
            )

        # Parse confounding prior
        confounding_prior = None
        if "confounding" in data and "prior" in data["confounding"]:
            prior_data = data["confounding"]["prior"]
            prior_dist = Distribution.from_dict(prior_data)
            if prior_dist.type != "beta":
                raise ValueError("Confounding prior must be Beta distribution")
            confounding_prior = ConfoundingPrior(
                alpha=prior_dist.params["alpha"],
                beta=prior_dist.params["beta"],
                rationale=data["confounding"].get("rationale", ""),
                calibration_sources=data["confounding"].get("calibration_sources", []),
            )
        elif "category" in data:
            # Use default prior for category
            confounding_prior = get_confounding_prior(
                data["category"],
                data.get("evidence", {}).get("primary_study_type"),
            )

        return cls(
            id=data["id"],
            name=data["name"],
            category=data["category"],
            description=data.get("description"),
            keywords=data.get("keywords", []),
            mechanisms=mechanisms,
            mortality=mortality,
            evidence_quality=data.get("evidence", {}).get("quality", "moderate"),
            primary_study_type=data.get("evidence", {}).get("primary_study_type"),
            sources=data.get("evidence", {}).get("sources", []),
            confounding_prior=confounding_prior,
            caveats=data.get("caveats", []),
        )

    def to_pathway_hrs(
        self,
        causal_fraction: float = 1.0,
        pathway_weights: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        """
        Convert mortality HR to pathway-specific HRs.

        Args:
            causal_fraction: Fraction of effect that is causal (0-1)
            pathway_weights: Weights for distributing effect across pathways

        Returns:
            Dict with cvd, cancer, other HRs
        """
        if self.mortality is None:
            return {"cvd": 1.0, "cancer": 1.0, "other": 1.0}

        base_hr = self.mortality.hazard_ratio.mean

        # Default pathway weights from Aune et al. meta-analysis
        if pathway_weights is None:
            pathway_weights = {"cvd": 0.50, "cancer": 0.30, "other": 0.20}

        # Apply confounding adjustment
        from .confounding import adjust_hr

        adjusted_hr = adjust_hr(base_hr, causal_fraction)

        # Distribute across pathways
        log_hr = np.log(adjusted_hr)
        return {
            "cvd": np.exp(log_hr * pathway_weights["cvd"] * 2),
            "cancer": np.exp(log_hr * pathway_weights["cancer"] * 2),
            "other": np.exp(log_hr * pathway_weights["other"] * 2),
        }
