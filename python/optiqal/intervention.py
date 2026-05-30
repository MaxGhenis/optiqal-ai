"""
Intervention Definition Module

Reads YAML intervention definitions (shared with TypeScript package).
"""

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union
import yaml
import numpy as np
from scipy import stats

from .confounding import ConfoundingPrior, get_confounding_prior


@dataclass
class Distribution:
    """Statistical distribution for uncertain parameters.

    For ``lognormal``, two parameterizations are supported:

    1. Raw: ``params={"log_mean": ..., "log_sd": ...}`` — stores parameters
       literally; ``sample()`` returns ``exp(Normal(log_mean, log_sd))``.
       In this mode the *median* of the sampled HR equals ``exp(log_mean)``
       and the *mean* is ``exp(log_mean + log_sd**2 / 2)``.
    2. HR-centered: ``params={"hr": h, "log_sd": s}`` — the safer option
       for catalog construction. Guarantees ``E[HR] == h`` by internally
       setting ``log_mean = log(h) - s**2 / 2``. This matches the CEA
       literature convention where reported point estimates are mean HRs.

    When both ``hr`` and ``log_mean`` are provided, ``hr`` takes precedence
    (the mean-centered form is always unambiguous). The raw form is kept so
    existing YAML files and direct ``log_mean`` callers aren't silently
    re-interpreted.
    """

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
            # hr-centered takes precedence when both are provided.
            if "hr" in data:
                params["hr"] = data["hr"]
            elif "log_mean" in data or "logMean" in data:
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

    def _lognormal_params(self) -> tuple[float, float]:
        """Resolve (log_mean, log_sd) for a lognormal Distribution.

        Handles both parameterizations: raw ``log_mean`` or hr-centered.
        """
        log_sd = float(self.params["log_sd"])
        if "hr" in self.params:
            hr = float(self.params["hr"])
            if hr <= 0:
                raise ValueError(f"hr must be positive, got {hr}")
            log_mean = float(np.log(hr) - (log_sd ** 2) / 2.0)
        else:
            log_mean = float(self.params["log_mean"])
        return log_mean, log_sd

    def sample(self, n: int = 1, random_state: Optional[int] = None) -> np.ndarray:
        """Sample from the distribution."""
        rng = np.random.default_rng(random_state)

        if self.type == "point":
            return np.full(n, self.params["value"])
        elif self.type == "normal":
            return rng.normal(self.params["mean"], self.params["sd"], size=n)
        elif self.type == "lognormal":
            log_mean, log_sd = self._lognormal_params()
            return np.exp(rng.normal(log_mean, log_sd, size=n))
        elif self.type == "beta":
            return rng.beta(self.params["alpha"], self.params["beta"], size=n)
        elif self.type == "uniform":
            return rng.uniform(self.params["min"], self.params["max"], size=n)

    @property
    def mean(self) -> float:
        """Expected value of the distribution.

        For hr-centered lognormals this returns ``hr`` exactly (not the
        distributional mean derived from ``log_mean + log_sd**2 / 2``). That
        is the same value either way because mean-centering constructs
        ``log_mean = log(hr) - log_sd**2 / 2``, but the short-circuit avoids
        floating-point drift.
        """
        if self.type == "point":
            return self.params["value"]
        elif self.type == "normal":
            return self.params["mean"]
        elif self.type == "lognormal":
            if "hr" in self.params:
                return float(self.params["hr"])
            mu, sigma = float(self.params["log_mean"]), float(self.params["log_sd"])
            return float(np.exp(mu + sigma ** 2 / 2))
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
class HarmEffect:
    """Direct harm from an intervention while active."""

    id: str
    description: Optional[str] = None
    annual_qaly_loss: Optional[Distribution] = None
    event_probability: Optional[Distribution] = None
    event_qaly_loss: Optional[Distribution] = None
    max_events: int = 1
    source: Optional[str] = None


@dataclass
class InteractionRule:
    """Stack-aware harm penalty triggered by overlapping intervention tags."""

    id: str
    requires_tags: List[str]
    minimum_matches: Optional[int] = None
    allocation: Literal["per_item", "split_across_matches"] = "per_item"
    description: Optional[str] = None
    annual_qaly_loss: Optional[Distribution] = None
    event_probability: Optional[Distribution] = None
    event_qaly_loss: Optional[Distribution] = None
    max_events: int = 1
    source: Optional[str] = None


def scale_distribution(
    distribution: Optional[Distribution],
    factor: float,
) -> Optional[Distribution]:
    """Scale a harm-magnitude or event-probability distribution."""
    if distribution is None or factor == 1.0:
        return distribution
    params = dict(distribution.params)
    if distribution.type == "point":
        params["value"] *= factor
    elif distribution.type == "normal":
        params["mean"] *= factor
        params["sd"] *= abs(factor)
    elif distribution.type == "uniform":
        low = params["min"] * factor
        high = params["max"] * factor
        params["min"], params["max"] = min(low, high), max(low, high)
    else:
        raise ValueError(f"Cannot scale {distribution.type} distribution")
    return Distribution(type=distribution.type, params=params)


def allocate_interaction_rule(
    rule: InteractionRule,
    matches: int,
) -> InteractionRule:
    """Allocate shared stack-level harm across matched contributors."""
    if rule.allocation != "split_across_matches" or matches <= 1:
        return rule
    share = 1.0 / matches
    return replace(
        rule,
        annual_qaly_loss=scale_distribution(rule.annual_qaly_loss, share),
        event_probability=scale_distribution(rule.event_probability, share),
    )


@dataclass
class InterventionLineage:
    """Study- and prior-level provenance for an intervention estimate."""

    estimand: str
    model_version: Optional[str] = None
    studies: List[Dict[str, Any]] = field(default_factory=list)
    parameter_lineage: List[Dict[str, Any]] = field(default_factory=list)
    prior_lineage: List[Dict[str, Any]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


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
    harm_model: List[HarmEffect] = field(default_factory=list)
    interaction_tags: List[str] = field(default_factory=list)
    interaction_rules: List[InteractionRule] = field(default_factory=list)

    # Evidence
    evidence_quality: Literal["high", "moderate", "low", "very-low"] = "moderate"
    primary_study_type: Optional[str] = None
    sources: List[Dict[str, Any]] = field(default_factory=list)

    # Confounding
    confounding_prior: Optional[ConfoundingPrior] = None

    # Caveats
    caveats: List[str] = field(default_factory=list)

    # Provenance
    lineage: Optional[InterventionLineage] = None

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

        harm_model = []
        if "harm_model" in data:
            for harm_data in data["harm_model"]:
                harm_model.append(
                    HarmEffect(
                        id=harm_data["id"],
                        description=harm_data.get("description"),
                        annual_qaly_loss=(
                            Distribution.from_dict(harm_data["annual_qaly_loss"])
                            if harm_data.get("annual_qaly_loss") is not None
                            else None
                        ),
                        event_probability=(
                            Distribution.from_dict(harm_data["event_probability"])
                            if harm_data.get("event_probability") is not None
                            else None
                        ),
                        event_qaly_loss=(
                            Distribution.from_dict(harm_data["event_qaly_loss"])
                            if harm_data.get("event_qaly_loss") is not None
                            else None
                        ),
                        max_events=harm_data.get("max_events", 1),
                        source=harm_data.get("source"),
                    )
                )

        interaction_rules = []
        if "interaction_rules" in data:
            for rule_data in data["interaction_rules"]:
                interaction_rules.append(
                    InteractionRule(
                        id=rule_data["id"],
                        requires_tags=rule_data["requires_tags"],
                        minimum_matches=rule_data.get("minimum_matches"),
                        allocation=rule_data.get("allocation", "per_item"),
                        description=rule_data.get("description"),
                        annual_qaly_loss=(
                            Distribution.from_dict(rule_data["annual_qaly_loss"])
                            if rule_data.get("annual_qaly_loss") is not None
                            else None
                        ),
                        event_probability=(
                            Distribution.from_dict(rule_data["event_probability"])
                            if rule_data.get("event_probability") is not None
                            else None
                        ),
                        event_qaly_loss=(
                            Distribution.from_dict(rule_data["event_qaly_loss"])
                            if rule_data.get("event_qaly_loss") is not None
                            else None
                        ),
                        max_events=rule_data.get("max_events", 1),
                        source=rule_data.get("source"),
                    )
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

        lineage = None
        if "lineage" in data:
            lineage_data = data["lineage"]
            lineage = InterventionLineage(
                estimand=lineage_data["estimand"],
                model_version=lineage_data.get("model_version"),
                studies=lineage_data.get("studies", []),
                parameter_lineage=lineage_data.get("parameter_lineage", []),
                prior_lineage=lineage_data.get("prior_lineage", []),
                notes=lineage_data.get("notes", []),
            )

        return cls(
            id=data["id"],
            name=data["name"],
            category=data["category"],
            description=data.get("description"),
            keywords=data.get("keywords", []),
            mechanisms=mechanisms,
            mortality=mortality,
            harm_model=harm_model,
            interaction_tags=data.get("interaction_tags", []),
            interaction_rules=interaction_rules,
            evidence_quality=data.get("evidence", {}).get("quality", "moderate"),
            primary_study_type=data.get("evidence", {}).get("primary_study_type"),
            sources=data.get("evidence", {}).get("sources", []),
            confounding_prior=confounding_prior,
            caveats=data.get("caveats", []),
            lineage=lineage,
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
