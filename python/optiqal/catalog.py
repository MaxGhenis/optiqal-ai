"""
Intervention Catalog — structured database of supplements and interventions.

Each entry contains literature-derived hazard ratios, confounding priors,
costs, QoL modifiers, and source notes. All HRs are pre-publication-bias-
correction (raw observed values from studies).

Use with `publication_bias_correct()` from `confounding.py` before simulation.
"""

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, List, Literal, Mapping, Optional

import numpy as np

from .confounding import (
    ConfoundingPrior,
    publication_bias_correct,
    shrinkage_for_study_quality,
)
from .defaults import (
    DEFAULT_COST_DISCOUNT_RATE,
    DEFAULT_QALY_DISCOUNT_RATE,
    validate_qaly_discount_rate,
)
from .intervention import (
    Distribution,
    HarmEffect,
    InteractionRule,
    Intervention,
    MortalityEffect,
)
from .profile import Profile
from .sleep import (
    SleepBurdenEstimate,
    effective_sleep_component_relief,
    estimate_airway_target_multiplier,
    estimate_sleep_mortality_relief_fraction,
    estimate_sleep_relief_annual_qaly,
    sleep_baseline_mortality_multiplier,
    sleep_intervention_mortality_hr_multiplier,
)


@dataclass(frozen=True)
class ProfileEffectRule:
    """Profile-conditioned transport multiplier for an intervention effect."""

    multiplier: float
    bmi_categories: Optional[tuple[str, ...]] = None
    has_diabetes: Optional[bool] = None
    has_hypertension: Optional[bool] = None
    activity_levels: Optional[tuple[str, ...]] = None
    min_age: Optional[int] = None
    max_age: Optional[int] = None

    def matches(self, profile: Profile) -> bool:
        if self.bmi_categories is not None and profile.bmi_category not in self.bmi_categories:
            return False
        if self.has_diabetes is not None and profile.has_diabetes != self.has_diabetes:
            return False
        if self.has_hypertension is not None and profile.has_hypertension != self.has_hypertension:
            return False
        if self.activity_levels is not None and profile.activity_level not in self.activity_levels:
            return False
        if self.min_age is not None and profile.age < self.min_age:
            return False
        if self.max_age is not None and profile.age > self.max_age:
            return False
        return True


@dataclass(frozen=True)
class AccessProfile:
    """Public-facing access and coverage friction metadata."""

    tier: Literal[
        "behavioral",
        "otc",
        "generic_rx",
        "brand_rx_prior_auth",
        "dme_rx",
        "specialist_device",
        "cash_pay",
    ] = "cash_pay"
    coverage_outlook: Literal["na", "likely", "mixed", "unlikely"] = "na"
    friction: Literal["low", "medium", "high"] = "medium"
    notes: str = ""


@dataclass(frozen=True)
class QolEffect:
    """Named non-mortality QALY effect with explicit uncertainty."""

    id: str
    label: str
    annual_qaly: Distribution
    description: str = ""
    source: Optional[str] = None


EVIDENCE_EFFECT_MULTIPLIERS: Dict[Literal["high", "moderate", "low", "very-low"], float] = {
    "high": 1.0,
    "moderate": 0.95,
    "low": 0.75,
    "very-low": 0.5,
}

EVIDENCE_CONFIDENCE_LABELS: Dict[Literal["high", "moderate", "low", "very-low"], Literal["high", "medium", "low"]] = {
    "high": "high",
    "moderate": "medium",
    "low": "low",
    "very-low": "low",
}

PublicRecommendationLane = Literal["consumer_public", "conditional_public", "personal_only"]
PublicCondition = Literal[
    "airway_signal",
    "osa_therapy_signal",
    "nasal_dryness_signal",
    "cardiometabolic_signal",
    "metabolic_signal",
    "glp1_signal",
]
PublicDisplayCategory = Literal["exercise", "sleep", "service", "rx", "supplement"]

PublicThresholdSignal = Literal[
    "sleep_breathing_burden",
    "sleep_airway_response_signal",
    "sleep_upper_airway_probability",
    "sleep_nasal_inflammation_probability",
    "sleep_mucus_probability",
]
PublicProfileRuleField = Literal[
    "age",
    "bmi_category",
    "smoking_status",
    "has_diabetes",
    "has_hypertension",
]
PublicProfileRuleOperator = Literal["gte", "eq", "in"]
PublicConditionEvaluationKind = Literal["sleep_any_threshold", "profile_score"]
PUBLIC_RECOMMENDATION_LANE_VALUES: tuple[PublicRecommendationLane, ...] = (
    "consumer_public",
    "conditional_public",
    "personal_only",
)
PUBLIC_DISPLAY_CATEGORY_VALUES: tuple[PublicDisplayCategory, ...] = (
    "exercise",
    "sleep",
    "service",
    "rx",
    "supplement",
)

PUBLIC_CONDITION_VALUES: tuple[PublicCondition, ...] = (
    "airway_signal",
    "osa_therapy_signal",
    "nasal_dryness_signal",
    "cardiometabolic_signal",
    "metabolic_signal",
    "glp1_signal",
)
PUBLIC_THRESHOLD_SIGNAL_VALUES: tuple[PublicThresholdSignal, ...] = (
    "sleep_breathing_burden",
    "sleep_airway_response_signal",
    "sleep_upper_airway_probability",
    "sleep_nasal_inflammation_probability",
    "sleep_mucus_probability",
)
PUBLIC_PROFILE_RULE_FIELDS: tuple[PublicProfileRuleField, ...] = (
    "age",
    "bmi_category",
    "smoking_status",
    "has_diabetes",
    "has_hypertension",
)
PUBLIC_PROFILE_RULE_OPERATORS: tuple[PublicProfileRuleOperator, ...] = ("gte", "eq", "in")
PUBLIC_CONDITION_EVALUATION_KINDS: tuple[PublicConditionEvaluationKind, ...] = (
    "sleep_any_threshold",
    "profile_score",
)
PUBLIC_LANE_DATA_PATH = Path(__file__).parent / "data" / "public_policy_lanes.json"
PUBLIC_CONDITION_DATA_PATH = Path(__file__).parent / "data" / "public_policy_conditions.json"
PUBLIC_ITEM_POLICY_DATA_PATH = Path(__file__).parent / "data" / "public_policy_items.json"


@dataclass(frozen=True)
class PublicThresholdRule:
    """Threshold rule for a public condition trigger."""

    signal: PublicThresholdSignal
    threshold: float
    label: str


@dataclass(frozen=True)
class PublicProfileScoreRule:
    """Score contribution rule for a profile-based public condition."""

    field: PublicProfileRuleField
    operator: PublicProfileRuleOperator
    value: object
    points: int
    label: str

    def matches(self, profile: Profile) -> bool:
        field_value = getattr(profile, self.field)
        if self.operator == "gte":
            return bool(field_value >= self.value)
        if self.operator == "eq":
            return bool(field_value == self.value)
        if self.operator == "in":
            return bool(field_value in self.value)
        return False


@dataclass(frozen=True)
class PublicConditionSpec:
    """Declarative public condition definition used for gating and UI."""

    id: PublicCondition
    label: str
    description: str
    evaluation_kind: PublicConditionEvaluationKind
    hidden_reason: str
    threshold_rules: tuple[PublicThresholdRule, ...] = ()
    profile_rules: tuple[PublicProfileScoreRule, ...] = ()
    profile_score_threshold: Optional[int] = None

@dataclass(frozen=True)
class PublicLaneSpec:
    """Declarative public lane definition used for export and UI."""

    id: PublicRecommendationLane
    label: str
    description: str


@dataclass(frozen=True)
class PublicItemPolicySpec:
    """Declarative per-item public policy metadata."""

    item_id: str
    public_lane: Optional[PublicRecommendationLane] = None
    public_condition: Optional[PublicCondition] = None
    public_display_category_override: Optional[PublicDisplayCategory] = None


@dataclass(frozen=True)
class PublicPolicy:
    """Resolved public-frontier policy that can be overridden without editing the model."""

    lane_specs: Mapping[PublicRecommendationLane, PublicLaneSpec]
    condition_specs: Mapping[PublicCondition, PublicConditionSpec]
    item_policy_specs: Mapping[str, PublicItemPolicySpec]
    excluded_reasons: Mapping[str, str]


def _load_public_lane_specs() -> Dict[PublicRecommendationLane, PublicLaneSpec]:
    """Load declarative public lane definitions from packaged JSON."""
    raw_specs = json.loads(PUBLIC_LANE_DATA_PATH.read_text())
    loaded_specs: Dict[PublicRecommendationLane, PublicLaneSpec] = {}

    if set(raw_specs) != set(PUBLIC_RECOMMENDATION_LANE_VALUES):
        raise ValueError(
            "public_policy_lanes.json must define exactly "
            f"{sorted(PUBLIC_RECOMMENDATION_LANE_VALUES)}, got {sorted(raw_specs)}"
        )

    for lane_id, raw_spec in raw_specs.items():
        if lane_id not in PUBLIC_RECOMMENDATION_LANE_VALUES:
            raise ValueError(f"Unexpected public lane id: {lane_id}")
        loaded_specs[lane_id] = PublicLaneSpec(
            id=lane_id,
            label=str(raw_spec["label"]),
            description=str(raw_spec["description"]),
        )

    return loaded_specs


def _load_public_item_policy_specs() -> Dict[str, PublicItemPolicySpec]:
    """Load declarative per-item public metadata from packaged JSON."""
    raw_specs = json.loads(PUBLIC_ITEM_POLICY_DATA_PATH.read_text())
    loaded_specs: Dict[str, PublicItemPolicySpec] = {}

    for item_id, raw_spec in raw_specs.items():
        public_lane = raw_spec.get("public_lane")
        public_condition = raw_spec.get("public_condition")
        display_category = raw_spec.get("public_display_category_override")

        if public_lane is not None and public_lane not in PUBLIC_RECOMMENDATION_LANE_VALUES:
            raise ValueError(f"Unexpected public lane for {item_id}: {public_lane}")
        if public_condition is not None and public_condition not in PUBLIC_CONDITION_VALUES:
            raise ValueError(f"Unexpected public condition for {item_id}: {public_condition}")
        if display_category is not None and display_category not in PUBLIC_DISPLAY_CATEGORY_VALUES:
            raise ValueError(
                f"Unexpected public display category override for {item_id}: {display_category}"
            )

        loaded_specs[item_id] = PublicItemPolicySpec(
            item_id=item_id,
            public_lane=public_lane,
            public_condition=public_condition,
            public_display_category_override=display_category,
        )

    return loaded_specs

def _load_public_condition_specs() -> Dict[PublicCondition, PublicConditionSpec]:
    """Load declarative public condition definitions from packaged JSON."""
    raw_specs = json.loads(PUBLIC_CONDITION_DATA_PATH.read_text())
    loaded_specs: Dict[PublicCondition, PublicConditionSpec] = {}

    if set(raw_specs) != set(PUBLIC_CONDITION_VALUES):
        raise ValueError(
            "public_policy_conditions.json must define exactly "
            f"{sorted(PUBLIC_CONDITION_VALUES)}, got {sorted(raw_specs)}"
        )

    for condition_id, raw_spec in raw_specs.items():
        if condition_id not in PUBLIC_CONDITION_VALUES:
            raise ValueError(f"Unexpected public condition id: {condition_id}")

        evaluation_kind = raw_spec["evaluation_kind"]
        if evaluation_kind not in PUBLIC_CONDITION_EVALUATION_KINDS:
            raise ValueError(f"Unexpected evaluation kind for {condition_id}: {evaluation_kind}")

        threshold_rules = []
        for rule in raw_spec.get("threshold_rules", []):
            signal = rule["signal"]
            if signal not in PUBLIC_THRESHOLD_SIGNAL_VALUES:
                raise ValueError(f"Unexpected threshold signal for {condition_id}: {signal}")
            threshold_rules.append(
                PublicThresholdRule(
                    signal=signal,
                    threshold=float(rule["threshold"]),
                    label=str(rule["label"]),
                )
            )

        profile_rules = []
        for rule in raw_spec.get("profile_rules", []):
            field_name = rule["field"]
            operator = rule["operator"]
            value = rule["value"]
            if field_name not in PUBLIC_PROFILE_RULE_FIELDS:
                raise ValueError(f"Unexpected profile field for {condition_id}: {field_name}")
            if operator not in PUBLIC_PROFILE_RULE_OPERATORS:
                raise ValueError(f"Unexpected profile operator for {condition_id}: {operator}")
            if operator == "in" and isinstance(value, list):
                value = tuple(value)
            profile_rules.append(
                PublicProfileScoreRule(
                    field=field_name,
                    operator=operator,
                    value=value,
                    points=int(rule["points"]),
                    label=str(rule["label"]),
                )
            )

        profile_score_threshold = raw_spec.get("profile_score_threshold")
        if evaluation_kind == "profile_score" and profile_score_threshold is None:
            raise ValueError(f"profile_score condition {condition_id} requires profile_score_threshold")

        loaded_specs[condition_id] = PublicConditionSpec(
            id=condition_id,
            label=str(raw_spec["label"]),
            description=str(raw_spec["description"]),
            evaluation_kind=evaluation_kind,
            hidden_reason=str(raw_spec["hidden_reason"]),
            threshold_rules=tuple(threshold_rules),
            profile_rules=tuple(profile_rules),
            profile_score_threshold=(
                int(profile_score_threshold) if profile_score_threshold is not None else None
            ),
        )

    return loaded_specs


PUBLIC_CONDITION_SPECS: Dict[PublicCondition, PublicConditionSpec] = _load_public_condition_specs()
PUBLIC_LANE_SPECS: Dict[PublicRecommendationLane, PublicLaneSpec] = _load_public_lane_specs()
PUBLIC_ITEM_POLICY_SPECS: Dict[str, PublicItemPolicySpec] = _load_public_item_policy_specs()


def _profile_adjusted_hr(hr: float, multiplier: float) -> float:
    if multiplier == 1.0:
        return hr
    return float(np.exp(np.log(hr) * multiplier))


def _sleep_component_relief_effect(
    sleep_estimate: SleepBurdenEstimate,
    sleep_component_relief: Dict[str, float],
    airway_target_weights: Dict[str, float],
) -> Dict[str, float]:
    return effective_sleep_component_relief(
        sleep_estimate,
        sleep_component_relief,
        airway_target_weights,
    )


@dataclass(frozen=True)
class CatalogEntry:
    """A single intervention in the catalog."""

    id: str
    name: str
    category: Literal[
        "rx_current", "rx_candidate", "supplement_current",
        "supplement_bought", "supplement_candidate",
        "sleep_current", "sleep_candidate",
    ]
    hr_observed: float  # Raw observed HR from literature (before pub bias correction)
    log_sd: float  # Uncertainty in log(HR)
    conf_alpha: float  # Beta prior alpha for causal fraction
    conf_beta: float  # Beta prior beta for causal fraction
    annual_cost: float  # Annual cost in USD
    qol_annual: float = 0.0  # Annual QoL effect in QALYs (non-mortality)
    qol_effects: List[QolEffect] = field(default_factory=list)
    qol_years: float = 40.0
    has_direct_mortality_effect: bool = True
    harm_effects: List[HarmEffect] = field(default_factory=list)
    interaction_tags: List[str] = field(default_factory=list)
    interaction_rules: List[InteractionRule] = field(default_factory=list)
    benefit_tags: List[str] = field(default_factory=list)
    exclusive_group: Optional[str] = None
    sleep_component_relief: Dict[str, float] = field(default_factory=dict)
    airway_target_weights: Dict[str, float] = field(default_factory=dict)
    profile_effect_rules: List[ProfileEffectRule] = field(default_factory=list)
    # Optional genotype-conditioned HR multipliers. Typed as ``List`` of a
    # late-imported ``GeneticEffectRule`` so the core catalog doesn't
    # force the optional genetics module into public builds. Rules fire
    # only when ``profile.genetic_profile`` is set and a matching
    # phenotype is present.
    genetic_effect_rules: List["Any"] = field(default_factory=list)
    access_profile: AccessProfile = field(default_factory=AccessProfile)
    notes: str = ""
    sources: List[str] = field(default_factory=list)
    evidence_quality: Literal["high", "moderate", "low", "very-low"] = "moderate"
    # Per-item publication-bias tier. When unset, the catalog falls back to the
    # caller's (AnalysisConfig) ``pub_bias_shrinkage`` value — preserving prior
    # behavior. Tiered shrinkage lets a PCPT-scale RCT keep most of its effect
    # while a small supplement-industry trial loses half of it.
    study_quality: Optional[str] = None
    # Optional allocation of bundled cost. When this item is packaged inside a
    # larger bundle (e.g. Blueprint Essential Capsules), ``bundle_cost_share``
    # is the dollar amount attributed to this item per year. The sim uses
    # ``effective_annual_cost()`` so $0 bundled items no longer free-ride.
    bundle_cost_share: float = 0.0
    bundle_id: Optional[str] = None
    public_lane: PublicRecommendationLane = "personal_only"
    public_condition: Optional[PublicCondition] = None
    public_display_category_override: Optional[PublicDisplayCategory] = None

    def profile_effect_multiplier(self, profile: Optional[Profile]) -> float:
        """Transport-study effects into the user profile with explicit shrinkage rules.

        Includes genotype-derived multipliers when ``profile.genetic_profile``
        is populated (optional genetics module; private builds only). Each
        matching rule's multiplier is composed multiplicatively, same as
        demographic rules.
        """
        if profile is None:
            return 1.0
        multiplier = 1.0
        for rule in self.profile_effect_rules:
            if rule.matches(profile):
                multiplier *= rule.multiplier
        genetic_profile = getattr(profile, "genetic_profile", None)
        if genetic_profile is not None:
            for rule in self.genetic_effect_rules:
                # Late-bound call via duck typing keeps the core catalog
                # decoupled from optiqal.genetics.
                if getattr(rule, "matches", lambda _: False)(genetic_profile):
                    multiplier *= float(getattr(rule, "multiplier", 1.0))
        return multiplier

    def evidence_effect_multiplier(self) -> float:
        """Shrink benefit claims when the evidence base is weak or very indirect."""
        return EVIDENCE_EFFECT_MULTIPLIERS[self.evidence_quality]

    def evidence_confidence(self) -> Literal["high", "medium", "low"]:
        return EVIDENCE_CONFIDENCE_LABELS[self.evidence_quality]

    def raw_qol_annual(self) -> float:
        """Expected annual non-mortality QALY before evidence shrinkage."""
        return self.qol_annual + sum(effect.annual_qaly.mean for effect in self.qol_effects)

    def effective_qol_annual(self) -> float:
        return self.raw_qol_annual() * self.evidence_effect_multiplier()

    def raw_sleep_qol_annual(
        self,
        sleep_estimate: Optional[SleepBurdenEstimate],
    ) -> float:
        if sleep_estimate is None or not self.sleep_component_relief:
            return 0.0
        return estimate_sleep_relief_annual_qaly(
            sleep_estimate,
            _sleep_component_relief_effect(
                sleep_estimate,
                self.sleep_component_relief,
                self.airway_target_weights,
            ),
        )

    def effective_pub_bias_shrinkage(self, fallback: float = 0.30) -> float:
        """Resolve the publication-bias shrinkage used for this entry."""
        return shrinkage_for_study_quality(self.study_quality, fallback=fallback)

    def corrected_hr_observed(
        self,
        pub_bias_shrinkage: float = 0.30,
        profile: Optional[Profile] = None,
    ) -> float:
        """Observed HR after publication-bias, evidence, and profile transport shrinkage.

        ``pub_bias_shrinkage`` is the fallback when ``self.study_quality`` is
        not set. When the entry declares a ``study_quality``, that tier wins.
        """
        shrinkage = self.effective_pub_bias_shrinkage(fallback=pub_bias_shrinkage)
        hr = publication_bias_correct(self.hr_observed, shrinkage=shrinkage)
        combined_multiplier = self.profile_effect_multiplier(profile) * self.evidence_effect_multiplier()
        return _profile_adjusted_hr(hr, combined_multiplier)

    def effective_annual_cost(self) -> float:
        """Dollar cost attributed to this item, including any bundle allocation.

        Bundled catalog items historically declared ``annual_cost=0`` because
        their price was absorbed by the bundle (e.g. Blueprint Essentials).
        That understated true cost. When ``bundle_cost_share`` is set, it is
        added to ``annual_cost`` so $/QALY reflects the real marginal spend.
        """
        return float(self.annual_cost) + float(self.bundle_cost_share)

    def _effective_sleep_component_relief(
        self,
        sleep_estimate: SleepBurdenEstimate,
    ) -> Dict[str, float]:
        relief = _sleep_component_relief_effect(
            sleep_estimate,
            self.sleep_component_relief,
            self.airway_target_weights,
        )
        multiplier = self.evidence_effect_multiplier()
        if multiplier == 1.0:
            return relief
        return {component: value * multiplier for component, value in relief.items()}

    def sleep_qol_annual(
        self,
        sleep_estimate: Optional[SleepBurdenEstimate],
    ) -> float:
        """Map a personalized sleep phenotype into intervention-specific annual QALY relief."""
        if sleep_estimate is None or not self.sleep_component_relief:
            return 0.0
        return estimate_sleep_relief_annual_qaly(
            sleep_estimate,
            self._effective_sleep_component_relief(sleep_estimate),
        )

    def airway_effect_multiplier(
        self,
        sleep_estimate: Optional[SleepBurdenEstimate],
    ) -> float:
        if not self.airway_target_weights:
            return 1.0
        return estimate_airway_target_multiplier(
            sleep_estimate,
            self.airway_target_weights,
        )

    def sleep_mortality_relief_fraction(
        self,
        sleep_estimate: Optional[SleepBurdenEstimate],
    ) -> float:
        """Fraction of current sleep-related mortality burden relieved by this intervention."""
        if sleep_estimate is None or not self.sleep_component_relief:
            return 0.0
        return estimate_sleep_mortality_relief_fraction(
            sleep_estimate,
            self._effective_sleep_component_relief(sleep_estimate),
        )

    def sleep_mortality_hr_multiplier(
        self,
        sleep_estimate: Optional[SleepBurdenEstimate],
    ) -> float:
        """Relative HR improvement from reducing the user's sleep-related mortality burden."""
        if sleep_estimate is None or not self.sleep_component_relief:
            return 1.0
        return sleep_intervention_mortality_hr_multiplier(
            sleep_estimate,
            self._effective_sleep_component_relief(sleep_estimate),
        )

    def to_intervention(
        self,
        pub_bias_shrinkage: float = 0.30,
        profile: Optional[Profile] = None,
    ) -> Intervention:
        """Convert to an Intervention object with publication bias correction."""
        hr = self.corrected_hr_observed(pub_bias_shrinkage, profile)
        mortality = None
        confounding_prior = None
        if self.has_direct_mortality_effect:
            # Use hr-centered lognormal so E[HR] == hr exactly and downstream
            # Distribution.mean returns hr without floating-point drift.
            mortality = MortalityEffect(
                hazard_ratio=Distribution(
                    type="lognormal",
                    params={"hr": hr, "log_sd": self.log_sd},
                ),
            )
            confounding_prior = ConfoundingPrior(
                alpha=self.conf_alpha, beta=self.conf_beta,
            )
        return Intervention(
            id=self.id,
            name=self.name,
            category="diet",  # Generic; actual confounding prior is explicit
            mortality=mortality,
            harm_model=list(self.harm_effects),
            interaction_tags=list(self.interaction_tags),
            interaction_rules=list(self.interaction_rules),
            confounding_prior=confounding_prior,
            evidence_quality=self.evidence_quality,
        )


# =============================================================================
# CATALOG
# =============================================================================

CATALOG: Dict[str, CatalogEntry] = {}

SEDATION_STACK_RULE = InteractionRule(
    id="sedation_stack",
    requires_tags=["sedating"],
    minimum_matches=2,
    allocation="split_across_matches",
    description="Extra grogginess and coordination cost from stacking sedating agents.",
    annual_qaly_loss=Distribution(type="point", params={"value": 0.0015}),
)

BLEEDING_STACK_RULE = InteractionRule(
    id="bleeding_stack",
    requires_tags=["bleeding_stack"],
    minimum_matches=3,
    allocation="split_across_matches",
    description="Small but non-zero additive bleeding risk from combining several blood-thinning agents.",
    event_probability=Distribution(type="point", params={"value": 0.0008}),
    event_qaly_loss=Distribution(type="point", params={"value": 0.05}),
)

DUPLICATE_VITAMIN_D_RULE = InteractionRule(
    id="duplicate_vitamin_d",
    requires_tags=["vitamin_d"],
    minimum_matches=2,
    allocation="split_across_matches",
    description="Redundant vitamin D dosing in an already replete user adds nuisance and modest downside.",
    annual_qaly_loss=Distribution(type="point", params={"value": 0.0002}),
)


def _add(entry: CatalogEntry) -> None:
    policy = PUBLIC_ITEM_POLICY_SPECS.get(entry.id)
    if policy is not None:
        entry = replace(
            entry,
            public_lane=policy.public_lane or entry.public_lane,
            public_condition=policy.public_condition,
            public_display_category_override=(
                policy.public_display_category_override or entry.public_display_category_override
            ),
        )
    CATALOG[entry.id] = entry


# ---------------------------------------------------------------------------
# Prescriptions — current
# ---------------------------------------------------------------------------
_add(CatalogEntry(
    "finasteride_1.25mg", "Finasteride 1.25mg", "rx_current",
    hr_observed=0.93, log_sd=0.10, conf_alpha=4.0, conf_beta=2.5,
    annual_cost=171,  # $14.99 / (8*4 doses) * 365 = $171/yr
    qol_annual=0.015,
    harm_effects=[
        HarmEffect(
            id="sexual_or_mood_side_effects",
            description="Persistent sexual or mood side effects in a minority of users.",
            annual_qaly_loss=Distribution(type="normal", params={"mean": 0.0015, "sd": 0.0007}),
        ),
    ],
    notes="PCPT RCT n=18882. Hair preservation.",
))
_add(CatalogEntry(
    "tadalafil_2.5mg", "Tadalafil 2.5mg", "rx_current",
    hr_observed=0.88, log_sd=0.15, conf_alpha=2.0, conf_beta=4.0,
    annual_cost=252,  # $20.72 / 30 * 365 = $252/yr
    qol_annual=0.020,
    harm_effects=[
        HarmEffect(
            id="headache_or_hypotension",
            description="Rare symptomatic hypotension or other PDE5 adverse effects.",
            event_probability=Distribution(type="point", params={"value": 0.002}),
            event_qaly_loss=Distribution(type="point", params={"value": 0.02}),
        ),
    ],
    interaction_tags=["vasodilator"],
    notes="Anderson 2016 obs HR 0.67. Endothelial RCTs.",
))
_add(CatalogEntry(
    "trazodone_50mg", "Trazodone 50mg", "rx_current",
    hr_observed=1.00, log_sd=0.05, conf_alpha=3.0, conf_beta=3.0,
    annual_cost=223,  # $18.34 / 30 * 365 = $223/yr
    qol_annual=0.0005,
    has_direct_mortality_effect=False,
    exclusive_group="insomnia_rx",
    harm_effects=[
        HarmEffect(
            id="daytime_sedation",
            description="Residual morning grogginess or orthostatic effects.",
            annual_qaly_loss=Distribution(type="normal", params={"mean": 0.0012, "sd": 0.0005}),
        ),
    ],
    interaction_tags=["sedating"],
    interaction_rules=[SEDATION_STACK_RULE],
    sleep_component_relief={
        "duration": 0.22,
        "continuity": 0.20,
        "quality": 0.25,
        "daytime": 0.12,
    },
    benefit_tags=[
        "sleep_duration_support",
        "sleep_continuity_support",
        "sleep_quality_support",
        "sleep_daytime_support",
    ],
    access_profile=AccessProfile(
        tier="generic_rx",
        coverage_outlook="likely",
        friction="low",
        notes="Generic prescription. Usually lower-friction than branded insomnia agents if a clinician is willing to prescribe it.",
    ),
    notes="Sleep maintenance. No mortality data.",
    evidence_quality="moderate",
))
_add(CatalogEntry(
    "doxepin_3mg", "Doxepin 3mg", "sleep_candidate",
    hr_observed=1.0, log_sd=0.05, conf_alpha=2.0, conf_beta=4.5,
    annual_cost=60, qol_annual=0.0002,
    has_direct_mortality_effect=False,
    exclusive_group="insomnia_rx",
    harm_effects=[
        HarmEffect(
            id="antihistamine_hangover",
            description="Possible morning grogginess, dry mouth, or anticholinergic nuisance.",
            annual_qaly_loss=Distribution(type="normal", params={"mean": 0.00035, "sd": 0.00018}),
        ),
    ],
    interaction_tags=["sedating"],
    interaction_rules=[SEDATION_STACK_RULE],
    sleep_component_relief={
        "duration": 0.08,
        "continuity": 0.22,
        "quality": 0.10,
        "daytime": 0.06,
    },
    benefit_tags=[
        "sleep_duration_support",
        "sleep_continuity_support",
        "sleep_quality_support",
        "sleep_daytime_support",
    ],
    access_profile=AccessProfile(
        tier="generic_rx",
        coverage_outlook="likely",
        friction="low",
        notes="Generic prescription. Often easier to cover than branded DORAs.",
    ),
    notes=(
        "Low-dose doxepin is guideline-supported for sleep-maintenance insomnia. "
        "Respiratory caution exists in severe sleep apnea, but it is not clearly contraindicated in mild OSA."
    ),
    sources=[
        "https://aasm.org/resources/pdf/pharmacologictreatmentofinsomnia.pdf",
        "https://www.accessdata.fda.gov/drugsatfda_docs/label/2010/022036lbl.pdf",
    ],
    evidence_quality="moderate",
))
_add(CatalogEntry(
    "daridorexant_25mg", "Daridorexant 25mg", "sleep_candidate",
    hr_observed=1.0, log_sd=0.05, conf_alpha=2.4, conf_beta=4.2,
    annual_cost=6156, qol_annual=0.0002,
    has_direct_mortality_effect=False,
    exclusive_group="insomnia_rx",
    harm_effects=[
        HarmEffect(
            id="next_day_somnolence",
            description="Residual somnolence or dizziness in a minority of users.",
            annual_qaly_loss=Distribution(type="normal", params={"mean": 0.00022, "sd": 0.00012}),
        ),
    ],
    interaction_tags=["sedating"],
    interaction_rules=[SEDATION_STACK_RULE],
    sleep_component_relief={
        "duration": 0.12,
        "continuity": 0.24,
        "quality": 0.12,
        "daytime": 0.10,
    },
    benefit_tags=[
        "sleep_duration_support",
        "sleep_continuity_support",
        "sleep_quality_support",
        "sleep_daytime_support",
    ],
    access_profile=AccessProfile(
        tier="brand_rx_prior_auth",
        coverage_outlook="mixed",
        friction="high",
        notes="Brand-only DORA. Coverage often depends on prior authorization and plan-specific insomnia criteria.",
    ),
    notes=(
        "Dual orexin receptor antagonist with direct mild-to-moderate OSA respiratory-safety data. "
        "Modeled as a cleaner maintenance-insomnia option than trazodone, but very expensive."
    ),
    sources=[
        "https://pubmed.ncbi.nlm.nih.gov/35065036/",
        "https://pubmed.ncbi.nlm.nih.gov/33305817/",
        "https://pubmed.ncbi.nlm.nih.gov/39543812/",
    ],
    evidence_quality="high",
))
_add(CatalogEntry(
    "lemborexant_5mg", "Lemborexant 5mg", "sleep_candidate",
    hr_observed=1.0, log_sd=0.05, conf_alpha=2.5, conf_beta=4.1,
    annual_cost=4350, qol_annual=0.0002,
    has_direct_mortality_effect=False,
    exclusive_group="insomnia_rx",
    harm_effects=[
        HarmEffect(
            id="next_day_somnolence",
            description="Residual somnolence, balance impairment, or orexin-class parasomnia burden.",
            annual_qaly_loss=Distribution(type="normal", params={"mean": 0.00028, "sd": 0.00014}),
        ),
    ],
    interaction_tags=["sedating"],
    interaction_rules=[SEDATION_STACK_RULE],
    sleep_component_relief={
        "duration": 0.13,
        "continuity": 0.28,
        "quality": 0.13,
        "daytime": 0.09,
    },
    benefit_tags=[
        "sleep_duration_support",
        "sleep_continuity_support",
        "sleep_quality_support",
        "sleep_daytime_support",
    ],
    access_profile=AccessProfile(
        tier="brand_rx_prior_auth",
        coverage_outlook="mixed",
        friction="high",
        notes="Brand-only DORA. Coverage often depends on prior authorization and prior step-therapy failures.",
    ),
    notes=(
        "Dual orexin receptor antagonist with direct respiratory-safety data in mild through severe OSA. "
        "Modeled as slightly more efficacious than daridorexant for maintenance insomnia, but with a bit more next-day drag."
    ),
    sources=[
        "https://pubmed.ncbi.nlm.nih.gov/32585700/",
        "https://pubmed.ncbi.nlm.nih.gov/32187781/",
        "https://pubmed.ncbi.nlm.nih.gov/37677076/",
        "https://pubmed.ncbi.nlm.nih.gov/40848323/",
    ],
    evidence_quality="high",
))
_add(CatalogEntry(
    "suvorexant_10mg", "Suvorexant 10mg", "sleep_candidate",
    hr_observed=1.0, log_sd=0.05, conf_alpha=2.2, conf_beta=4.8,
    annual_cost=5686, qol_annual=0.0002,
    has_direct_mortality_effect=False,
    exclusive_group="insomnia_rx",
    harm_effects=[
        HarmEffect(
            id="next_day_somnolence",
            description="Residual somnolence plus orexin-class complex sleep behavior and cataplexy-like burden.",
            annual_qaly_loss=Distribution(type="normal", params={"mean": 0.00045, "sd": 0.0002}),
        ),
    ],
    interaction_tags=["sedating"],
    interaction_rules=[SEDATION_STACK_RULE],
    sleep_component_relief={
        "duration": 0.11,
        "continuity": 0.22,
        "quality": 0.11,
        "daytime": 0.08,
    },
    benefit_tags=[
        "sleep_duration_support",
        "sleep_continuity_support",
        "sleep_quality_support",
        "sleep_daytime_support",
    ],
    access_profile=AccessProfile(
        tier="brand_rx_prior_auth",
        coverage_outlook="mixed",
        friction="high",
        notes="Brand-only DORA. May be covered, but often with prior authorization and more respiratory caution than newer peers.",
    ),
    notes=(
        "Dual orexin receptor antagonist with clear insomnia efficacy, but the label keeps more respiratory caution in OSA "
        "than daridorexant or lemborexant. Modeled as a middling trazodone alternative for mild OSA."
    ),
    sources=[
        "https://pubmed.ncbi.nlm.nih.gov/27397664/",
        "https://pubmed.ncbi.nlm.nih.gov/26194728/",
        "https://pubmed.ncbi.nlm.nih.gov/39543812/",
        "https://www.drugs.com/pro/belsomra.html",
    ],
    evidence_quality="low",
))
_add(CatalogEntry(
    "nasacort_nightly", "Nasacort nightly", "sleep_current",
    hr_observed=1.0, log_sd=0.05, conf_alpha=2.0, conf_beta=4.5,
    annual_cost=120, qol_annual=0.0002,
    has_direct_mortality_effect=False,
    sleep_component_relief={
        "breathing": 0.24,
        "continuity": 0.05,
        "quality": 0.06,
    },
    airway_target_weights={
        "upper_airway": 0.4,
        "nasal_inflammation": 0.6,
    },
    benefit_tags=[
        "sleep_breathing_support",
        "sleep_continuity_support",
        "sleep_quality_support",
    ],
    access_profile=AccessProfile(
        tier="otc",
        coverage_outlook="na",
        friction="low",
        notes="Over-the-counter nasal steroid. Easy to trial without specialist access.",
    ),
    notes=(
        "Best-supported for congestion-mediated sleep disturbance and as an adjunct "
        "in nasal-obstruction OSA phenotypes. Main benefit is upper-airway, not "
        "general prevention."
    ),
    sources=[
        "https://pubmed.ncbi.nlm.nih.gov/9042068/",
        "https://pubmed.ncbi.nlm.nih.gov/30154874/",
        "https://pubmed.ncbi.nlm.nih.gov/15124166/",
    ],
    evidence_quality="high",
))
_add(CatalogEntry(
    "nasal_strips_nightly", "Nasal strips nightly", "sleep_current",
    hr_observed=1.0, log_sd=0.05, conf_alpha=1.8, conf_beta=4.8,
    annual_cost=180, qol_annual=0.0001,
    has_direct_mortality_effect=False,
    sleep_component_relief={
        "breathing": 0.14,
        "quality": 0.05,
    },
    airway_target_weights={
        "upper_airway": 0.8,
        "nasal_inflammation": 0.2,
    },
    benefit_tags=[
        "sleep_breathing_support",
        "sleep_quality_support",
    ],
    access_profile=AccessProfile(
        tier="otc",
        coverage_outlook="na",
        friction="low",
        notes="Over-the-counter and easy to test immediately, but usually only a modest airway aid.",
    ),
    notes=(
        "Primarily a subjective nasal-congestion and snoring aid. Helps when the "
        "problem is upper-airway narrowing, but usually not a large standalone OSA treatment."
    ),
    sources=[
        "https://pubmed.ncbi.nlm.nih.gov/30154874/",
    ],
    evidence_quality="moderate",
))
_add(CatalogEntry(
    "humidifier_nightly", "Humidifier nightly", "sleep_candidate",
    hr_observed=1.0, log_sd=0.06, conf_alpha=1.2, conf_beta=6.2,
    annual_cost=80, qol_annual=0.00005,
    has_direct_mortality_effect=False,
    sleep_component_relief={
        "breathing": 0.05,
        "continuity": 0.03,
        "quality": 0.05,
    },
    airway_target_weights={
        "upper_airway": 0.25,
        "nasal_inflammation": 0.65,
        "mucus": 0.10,
    },
    benefit_tags=[
        "sleep_breathing_support",
        "sleep_continuity_support",
        "sleep_quality_support",
    ],
    access_profile=AccessProfile(
        tier="cash_pay",
        coverage_outlook="na",
        friction="low",
        notes="Low-friction bedroom hardware, but only attractive if the room is actually dry and you keep humidity in a safe range.",
    ),
    notes=(
        "Modeled as a small dryness / nasal-comfort intervention, not a meaningful standalone OSA treatment. "
        "Best case is low ambient humidity or waking with dry irritated nasal passages."
    ),
    sources=[
        "https://www.aaaai.org/tools-for-the-public/conditions-library/allergies/humidifiers-and-indoor-allergies",
        "https://www.epa.gov/mold/mold-course-chapter-2",
        "https://pubmed.ncbi.nlm.nih.gov/3348500/",
    ],
    evidence_quality="low",
))
_add(CatalogEntry(
    "mouth_tape_nightly", "Mouth tape nightly", "sleep_candidate",
    hr_observed=1.0, log_sd=0.06, conf_alpha=1.3, conf_beta=6.0,
    annual_cost=220, qol_annual=0.00008,
    has_direct_mortality_effect=False,
    harm_effects=[
        HarmEffect(
            id="mouth_tape_irritation_or_fragmentation",
            description="Skin irritation, discomfort, or fragmented sleep if it feels intolerable.",
            annual_qaly_loss=Distribution(type="normal", params={"mean": 0.00018, "sd": 0.0001}),
        ),
    ],
    sleep_component_relief={
        "breathing": 0.10,
        "quality": 0.04,
        "continuity": 0.02,
    },
    airway_target_weights={
        "upper_airway": 1.0,
    },
    benefit_tags=[
        "sleep_breathing_support",
        "sleep_quality_support",
        "sleep_continuity_support",
    ],
    access_profile=AccessProfile(
        tier="cash_pay",
        coverage_outlook="na",
        friction="low",
        notes="Low-friction cash-pay adjunct. Best case is a clear mouth-breathing phenotype with decent nasal patency.",
    ),
    notes=(
        "Modeled as a phenotype-specific mouth-breathing intervention, not a generic OSA fix. "
        "The evidence suggests some benefit in mild OSA or snoring when habitual open-mouth breathing is part of the problem, "
        "but the literature is still thin."
    ),
    sources=[
        "https://pubmed.ncbi.nlm.nih.gov/25450408/",
        "https://pubmed.ncbi.nlm.nih.gov/38780959/",
        "https://pubmed.ncbi.nlm.nih.gov/39662104/",
        "https://pubmed.ncbi.nlm.nih.gov/25766699/",
    ],
    evidence_quality="low",
))
_add(CatalogEntry(
    "head_elevation_nightly", "Head elevation nightly", "sleep_current",
    hr_observed=1.0, log_sd=0.05, conf_alpha=2.2, conf_beta=4.2,
    annual_cost=0, qol_annual=0.0001,
    has_direct_mortality_effect=False,
    sleep_component_relief={
        "breathing": 0.18,
        "continuity": 0.05,
    },
    airway_target_weights={
        "upper_airway": 1.0,
    },
    benefit_tags=[
        "sleep_breathing_support",
        "sleep_continuity_support",
    ],
    access_profile=AccessProfile(
        tier="behavioral",
        coverage_outlook="na",
        friction="low",
        notes="Behavioral setup change. No prescription or purchase barrier if you already have the hardware.",
    ),
    notes=(
        "Behavioral airway aid. Most plausible in positional or upper-airway-predominant sleep-disordered breathing."
    ),
    sources=[
        "https://pubmed.ncbi.nlm.nih.gov/39347559/",
    ],
    evidence_quality="moderate",
))
_add(CatalogEntry(
    "apap_nightly", "APAP nightly", "sleep_candidate",
    hr_observed=1.0, log_sd=0.05, conf_alpha=3.0, conf_beta=3.8,
    annual_cost=400, qol_annual=0.0002,
    has_direct_mortality_effect=False,
    exclusive_group="osa_primary_therapy",
    sleep_component_relief={
        "breathing": 0.65,
        "continuity": 0.25,
        "quality": 0.18,
        "daytime": 0.28,
    },
    airway_target_weights={
        "upper_airway": 0.6,
        "nasal_inflammation": 0.25,
        "mucus": 0.15,
    },
    benefit_tags=[
        "sleep_breathing_support",
        "sleep_continuity_support",
        "sleep_quality_support",
        "sleep_daytime_support",
    ],
    access_profile=AccessProfile(
        tier="dme_rx",
        coverage_outlook="likely",
        friction="medium",
        notes="Usually requires a prescription plus a DME supplier, but often has better coverage than branded insomnia drugs.",
    ),
    notes=(
        "Modeled as the strongest pre-diagnosis airway intervention candidate. "
        "No direct mortality term; benefit comes through sleep-burden and sleep-mortality relief."
    ),
    sources=[
        "https://aasm.org/wp-content/uploads/2019/11/Treatment-OSA-with-PAP-Patient-Guide.pdf",
        "https://pubmed.ncbi.nlm.nih.gov/30736887/",
    ],
    evidence_quality="high",
))
_add(CatalogEntry(
    "oral_appliance_custom", "Custom oral appliance", "sleep_candidate",
    hr_observed=1.0, log_sd=0.05, conf_alpha=2.6, conf_beta=4.2,
    annual_cost=500, qol_annual=0.0002,
    has_direct_mortality_effect=False,
    exclusive_group="osa_primary_therapy",
    sleep_component_relief={
        "breathing": 0.45,
        "continuity": 0.16,
        "quality": 0.12,
        "daytime": 0.18,
    },
    airway_target_weights={
        "upper_airway": 0.7,
        "nasal_inflammation": 0.2,
        "mucus": 0.1,
    },
    benefit_tags=[
        "sleep_breathing_support",
        "sleep_continuity_support",
        "sleep_quality_support",
        "sleep_daytime_support",
    ],
    access_profile=AccessProfile(
        tier="specialist_device",
        coverage_outlook="mixed",
        friction="medium",
        notes="Usually needs a dentist or sleep specialist plus custom fabrication. Coverage is more variable than PAP.",
    ),
    notes=(
        "Custom mandibular advancement device, annualized over replacement and follow-up. "
        "Typically less effective than PAP but often easier to tolerate."
    ),
    sources=[
        "https://aasm.org/aasm-and-aadsm-issue-new-joint-clinical-practice-guideline-for-oral-appliance-therapy/",
        "https://pubmed.ncbi.nlm.nih.gov/26094920/",
    ],
    evidence_quality="high",
))
_add(CatalogEntry(
    "hiit_1x_week", "HIIT 1x/week", "supplement_candidate",
    hr_observed=1.0, log_sd=0.06, conf_alpha=2.0, conf_beta=4.8,
    annual_cost=0, qol_annual=0.0014, qol_years=12,
    has_direct_mortality_effect=False,
    exclusive_group="cardio_mode",
    notes=(
        "Structured interval training once weekly, assumed to replace an easier cardio session rather than add volume. "
        "Modeled through modest CRF/VO2max utility, not a direct mortality claim."
    ),
    sources=[
        "https://pubmed.ncbi.nlm.nih.gov/26243014/",
        "https://pubmed.ncbi.nlm.nih.gov/38599681/",
    ],
))
_add(CatalogEntry(
    "hiit_2x_week", "HIIT 2x/week", "supplement_candidate",
    hr_observed=1.0, log_sd=0.07, conf_alpha=1.9, conf_beta=5.0,
    annual_cost=0, qol_annual=0.0022, qol_years=12,
    has_direct_mortality_effect=False,
    exclusive_group="cardio_mode",
    notes=(
        "Structured interval training twice weekly, assumed to replace easier cardio. "
        "Modeled as a somewhat larger CRF stimulus with diminishing marginal return."
    ),
    sources=[
        "https://pubmed.ncbi.nlm.nih.gov/26243014/",
        "https://pubmed.ncbi.nlm.nih.gov/38599681/",
        "https://pubmed.ncbi.nlm.nih.gov/40976973/",
    ],
))
_add(CatalogEntry(
    "hiit_3x_week", "HIIT 3x/week", "supplement_candidate",
    hr_observed=1.0, log_sd=0.08, conf_alpha=1.7, conf_beta=5.4,
    annual_cost=0, qol_annual=0.0019, qol_years=12,
    has_direct_mortality_effect=False,
    exclusive_group="cardio_mode",
    notes=(
        "Three structured interval sessions weekly, assumed to replace easier cardio. "
        "Modeled with extra recovery uncertainty and a small recurring downside because current frequency evidence suggests no clear added benefit over 2x/week in recreational runners."
    ),
    sources=[
        "https://pubmed.ncbi.nlm.nih.gov/26243014/",
        "https://pubmed.ncbi.nlm.nih.gov/38599681/",
        "https://pubmed.ncbi.nlm.nih.gov/40976973/",
    ],
))
_add(CatalogEntry(
    "zone2_cardio_2x_week", "Zone 2 cardio 2x/week", "supplement_candidate",
    hr_observed=1.0, log_sd=0.05, conf_alpha=1.8, conf_beta=5.0,
    annual_cost=0, qol_annual=0.0010, qol_years=12,
    has_direct_mortality_effect=False,
    exclusive_group="cardio_mode",
    notes=(
        "Two structured low-to-moderate intensity cardio sessions weekly, assumed to replace unstructured easier running. "
        "Modeled as a small CRF and recovery-positive intervention."
    ),
    sources=[
        "https://pubmed.ncbi.nlm.nih.gov/38599681/",
    ],
))
_add(CatalogEntry(
    "tempo_run_1x_week", "Tempo run 1x/week", "supplement_candidate",
    hr_observed=1.0, log_sd=0.06, conf_alpha=1.9, conf_beta=4.9,
    annual_cost=0, qol_annual=0.0016, qol_years=12,
    has_direct_mortality_effect=False,
    exclusive_group="cardio_mode",
    notes=(
        "One threshold/tempo-style run weekly, assumed to replace easier cardio. "
        "Modeled as intermediate between easy cardio and HIIT for CRF benefit."
    ),
    sources=[
        "https://pubmed.ncbi.nlm.nih.gov/26243014/",
        "https://pubmed.ncbi.nlm.nih.gov/38599681/",
    ],
))
_add(CatalogEntry(
    "strength_maintenance", "Strength maintenance", "supplement_candidate",
    hr_observed=1.0, log_sd=0.04, conf_alpha=1.4, conf_beta=5.6,
    annual_cost=0, qol_annual=0.0003, qol_years=12,
    has_direct_mortality_effect=False,
    exclusive_group="strength_mode",
    notes=(
        "Structured maintenance lifting. Kept near flat because you already do strength work daily."
    ),
    sources=[
        "https://pubmed.ncbi.nlm.nih.gov/38599681/",
    ],
))

# ---------------------------------------------------------------------------
# Prescriptions — candidates (off-label longevity)
# ---------------------------------------------------------------------------
_add(CatalogEntry(
    "rapamycin_5mg_wk", "Rapamycin 5mg/wk", "rx_candidate",
    hr_observed=0.85, log_sd=0.20, conf_alpha=2.0, conf_beta=3.0,
    annual_cost=600, qol_annual=-0.003,
    notes="ITP mice: +26% median lifespan. Mannick 2014. Immunosuppression risk.",
))
_add(CatalogEntry(
    "metformin_500mg", "Metformin 500mg", "rx_candidate",
    hr_observed=0.90, log_sd=0.12, conf_alpha=2.5, conf_beta=3.5,
    annual_cost=48, qol_annual=0.000,
    benefit_tags=["cardiometabolic_support"],
    notes="Bannister 2014: diabetics on metformin outlived controls. TAME pending.",
))
_add(CatalogEntry(
    "acarbose_50mg", "Acarbose 50mg", "rx_candidate",
    hr_observed=0.88, log_sd=0.18, conf_alpha=2.0, conf_beta=4.0,
    annual_cost=120, qol_annual=-0.005,
    notes="ITP mice: +22% median lifespan (males). GI side effects.",
))
_add(CatalogEntry(
    "aspirin_81mg", "Low-dose aspirin 81mg", "rx_candidate",
    hr_observed=0.94, log_sd=0.06, conf_alpha=4.0, conf_beta=2.0,
    annual_cost=15, qol_annual=-0.001,
    harm_effects=[
        HarmEffect(
            id="bleeding",
            description="Clinically meaningful bleeding risk.",
            event_probability=Distribution(type="point", params={"value": 0.004}),
            event_qaly_loss=Distribution(type="point", params={"value": 0.05}),
        ),
    ],
    interaction_tags=["bleeding_stack"],
    interaction_rules=[BLEEDING_STACK_RULE],
    benefit_tags=["cardiometabolic_support"],
    notes="ASPREE (>70yr): no benefit, more bleeding. USPSTF equivocal at 39.",
))
_add(CatalogEntry(
    "semaglutide", "GLP-1 RA (semaglutide)", "rx_candidate",
    hr_observed=0.80, log_sd=0.12, conf_alpha=3.5, conf_beta=2.0,
    annual_cost=6000, qol_annual=0.004,
    harm_effects=[
        HarmEffect(
            id="ongoing_gi_side_effects",
            description="Nausea, vomiting, or GI intolerance during treatment.",
            annual_qaly_loss=Distribution(type="normal", params={"mean": 0.004, "sd": 0.0015}),
        ),
        HarmEffect(
            id="gallbladder_or_pancreatitis",
            description="Rare but meaningful biliary or pancreatic adverse event.",
            event_probability=Distribution(type="point", params={"value": 0.002}),
            event_qaly_loss=Distribution(type="point", params={"value": 0.05}),
        ),
    ],
    profile_effect_rules=[
        ProfileEffectRule(
            multiplier=0.20,
            bmi_categories=("normal",),
        ),
        ProfileEffectRule(
            multiplier=0.75,
            has_diabetes=False,
            has_hypertension=False,
        ),
    ],
    benefit_tags=["cardiometabolic_support"],
    notes=(
        "SELECT trial: HR 0.80 MACE in overweight/obesity with established CVD. "
        "Strong transport shrinkage applied for lean, low-risk profiles plus GI/gallbladder harms."
    ),
))
_add(CatalogEntry(
    "lithium_5mg", "Low-dose lithium 5mg", "rx_candidate",
    hr_observed=0.92, log_sd=0.18, conf_alpha=1.5, conf_beta=4.5,
    annual_cost=60, qol_annual=0.001,
    notes="Ecological: municipal Li → lower suicide/dementia. No RCTs at low dose.",
))
_add(CatalogEntry(
    "17a_estradiol", "17α-estradiol (topical)", "rx_candidate",
    hr_observed=0.88, log_sd=0.20, conf_alpha=1.5, conf_beta=4.5,
    annual_cost=360, qol_annual=-0.002,
    notes="ITP mice: +19% median lifespan (males only). No human data.",
))
_add(CatalogEntry(
    "empagliflozin", "SGLT2i (empagliflozin)", "rx_candidate",
    hr_observed=0.86, log_sd=0.10, conf_alpha=3.5, conf_beta=2.5,
    annual_cost=3600, qol_annual=0.002,
    benefit_tags=["cardiometabolic_support"],
    notes="EMPA-REG: HR 0.68 CV death (diabetics). Off-label in healthy unclear.",
))
_add(CatalogEntry(
    "statin_5mg", "Statin (rosuvastatin 5mg)", "rx_candidate",
    hr_observed=0.88, log_sd=0.08, conf_alpha=4.5, conf_beta=1.5,
    annual_cost=120, qol_annual=-0.002,
    benefit_tags=["cardiometabolic_support"],
    notes="CTT meta: 21% CVD reduction per mmol/L LDL.",
))

# ---------------------------------------------------------------------------
# Supplements — current stack
# ---------------------------------------------------------------------------
_add(CatalogEntry(
    "omega3_clo", "Omega-3 CLO ~500mg", "supplement_current",
    hr_observed=0.92, log_sd=0.10, conf_alpha=2.5, conf_beta=3.5,
    annual_cost=180, qol_annual=0.001,
    interaction_tags=["bleeding_stack"],
    interaction_rules=[BLEEDING_STACK_RULE],
    benefit_tags=["cardiometabolic_support"],
    notes="Aung 2018 meta. VITAL.",
))
_add(CatalogEntry(
    "vitamin_d_2000", "Vitamin D 2000 IU", "supplement_current",
    hr_observed=0.94, log_sd=0.08, conf_alpha=3.0, conf_beta=4.0,
    annual_cost=30, qol_annual=0.000,
    interaction_tags=["vitamin_d"],
    interaction_rules=[DUPLICATE_VITAMIN_D_RULE],
    notes="VITAL NS. Bolland meta D3 HR 0.97.",
))
_add(CatalogEntry(
    "magnesium_200", "Magnesium 400mg", "supplement_current",
    hr_observed=0.90, log_sd=0.12, conf_alpha=2.0, conf_beta=3.5,
    annual_cost=146, qol_annual=0.0005,
    sleep_component_relief={
        "duration": 0.08,
        "quality": 0.20,
        "daytime": 0.15,
    },
    benefit_tags=[
        "sleep_duration_support",
        "sleep_quality_support",
        "sleep_daytime_support",
        "cardiometabolic_support",
    ],
    notes=(
        "Current dose is 400mg supplemental magnesium. Benefit is capped for diminishing returns; "
        "watch GI tolerance because the NIH supplemental UL is 350mg/day."
    ),
))
_add(CatalogEntry(
    "garlic_1200", "Garlic 1200mg", "supplement_current",
    hr_observed=0.88, log_sd=0.12, conf_alpha=2.0, conf_beta=4.0,
    annual_cost=300, qol_annual=0.000,
    interaction_tags=["bleeding_stack"],
    interaction_rules=[BLEEDING_STACK_RULE],
    benefit_tags=["cardiometabolic_support"],
    notes="Obs HR 0.88. BP + calcification RCTs.",
))
_add(CatalogEntry(
    "creatine_5g", "Creatine 5g", "supplement_current",
    hr_observed=0.98, log_sd=0.08, conf_alpha=1.0, conf_beta=6.0,
    annual_cost=120,
    qol_effects=[
        QolEffect(
            id="strength_power_lean_mass",
            label="Strength / power / lean mass",
            annual_qaly=Distribution(type="normal", params={"mean": 0.0030, "sd": 0.0011}),
            description=(
                "Resistance-training performance and lean-mass support; more valuable with "
                "aging reserve value and low dietary creatine."
            ),
            source="https://jissn.biomedcentral.com/articles/10.1186/s12970-017-0173-z",
        ),
        QolEffect(
            id="cognitive_resilience",
            label="Cognitive resilience",
            annual_qaly=Distribution(type="normal", params={"mean": 0.0015, "sd": 0.0010}),
            description=(
                "Small average cognitive benefit, likely concentrated in memory/attention "
                "and under higher brain-energy stress."
            ),
            source="https://www.frontiersin.org/journals/nutrition/articles/10.3389/fnut.2024.1424972/full",
        ),
        QolEffect(
            id="functional_reserve",
            label="Functional reserve",
            annual_qaly=Distribution(type="normal", params={"mean": 0.0008, "sd": 0.0006}),
            description="Small long-run reserve value from maintaining training capacity and muscle function.",
        ),
    ],
    harm_effects=[
        HarmEffect(
            id="gi_water_weight_lab_noise",
            description="GI nuisance, water-weight friction, and serum-creatinine/eGFR interpretability cost.",
            annual_qaly_loss=Distribution(type="normal", params={"mean": 0.0003, "sd": 0.0002}),
            source="https://bmcnephrol.biomedcentral.com/articles/10.1186/s12882-025-04558-6",
        ),
    ],
    benefit_tags=["performance_recovery"],
    notes=(
        "No mortality RCTs. QoL decomposed into strength/lean-mass, cognitive-resilience, "
        "and functional-reserve components; nuisance harm captures GI/water-weight and creatinine lab noise."
    ),
    sources=[
        "https://jissn.biomedcentral.com/articles/10.1186/s12970-017-0173-z",
        "https://www.frontiersin.org/journals/nutrition/articles/10.3389/fnut.2024.1424972/full",
        "https://bmcnephrol.biomedcentral.com/articles/10.1186/s12882-025-04558-6",
    ],
))
_add(CatalogEntry(
    "nac_1200", "NAC 1200mg", "supplement_current",
    hr_observed=0.93, log_sd=0.15, conf_alpha=1.5, conf_beta=4.0,
    annual_cost=40, qol_annual=0.001,
    sleep_component_relief={
        "breathing": 0.08,
        "quality": 0.02,
    },
    airway_target_weights={
        "mucus": 0.75,
        "upper_airway": 0.25,
    },
    benefit_tags=["sleep_breathing_support"],
    notes=(
        "Best-supported as a mucolytic in chronic bronchitis/COPD. Much weaker for "
        "upper-airway sleep problems, so any sleep benefit is scaled to mucus-heavy phenotypes."
    ),
    sources=[
        "https://pubmed.ncbi.nlm.nih.gov/38555190/",
        "https://pubmed.ncbi.nlm.nih.gov/28122105/",
    ],
))
_add(CatalogEntry(
    "curcumin_250", "Curcumin 250mg", "supplement_current",
    hr_observed=0.90, log_sd=0.18, conf_alpha=1.5, conf_beta=4.5,
    annual_cost=40, qol_annual=0.000,
    harm_effects=[
        HarmEffect(
            id="rare_liver_injury",
            description="Rare idiosyncratic liver injury concern.",
            event_probability=Distribution(type="point", params={"value": 0.0005}),
            event_qaly_loss=Distribution(type="point", params={"value": 0.08}),
        ),
    ],
    interaction_tags=["bleeding_stack"],
    interaction_rules=[BLEEDING_STACK_RULE],
    notes="Anti-inflam. Bioavailability issues.",
))
_add(CatalogEntry(
    "ginger_400", "Ginger 400mg", "supplement_current",
    hr_observed=0.96, log_sd=0.15, conf_alpha=1.0, conf_beta=5.0,
    annual_cost=0, qol_annual=0.000,
    interaction_tags=["bleeding_stack"],
    interaction_rules=[BLEEDING_STACK_RULE],
    notes="Bundled. Anti-nausea.",
))
_add(CatalogEntry(
    "vitamin_k2", "Vitamin K2 MK-7+MK-4", "supplement_current",
    hr_observed=0.92, log_sd=0.15, conf_alpha=1.5, conf_beta=4.0,
    annual_cost=25, qol_annual=0.000,
    notes="Rotterdam obs. Calcification RCTs.",
))
_add(CatalogEntry(
    "melatonin_300mcg", "Melatonin 300mcg", "supplement_current",
    hr_observed=0.97, log_sd=0.10, conf_alpha=1.2, conf_beta=4.5,
    annual_cost=30, qol_annual=0.0003,
    harm_effects=[
        HarmEffect(
            id="residual_sedation",
            description="Morning grogginess or vivid-dream disutility.",
            annual_qaly_loss=Distribution(type="normal", params={"mean": 0.00012, "sd": 0.00008}),
        ),
    ],
    interaction_tags=["sedating"],
    interaction_rules=[SEDATION_STACK_RULE],
    sleep_component_relief={
        "duration": 0.08,
        "continuity": 0.12,
        "regularity": 0.10,
    },
    benefit_tags=[
        "sleep_duration_support",
        "sleep_continuity_support",
        "sleep_regularity_support",
    ],
    access_profile=AccessProfile(
        tier="otc",
        coverage_outlook="na",
        friction="low",
        notes="Over-the-counter and low-friction. Good first stop before branded prescription sleep agents.",
    ),
    notes="Sleep onset RCTs.",
))
_add(CatalogEntry(
    "collagen_22g", "Collagen 22g", "supplement_current",
    hr_observed=0.99, log_sd=0.05, conf_alpha=1.0, conf_beta=7.0,
    annual_cost=360, qol_annual=0.003,
    notes="No mortality data. Joint/skin RCTs.",
    evidence_quality="low",
))
_add(CatalogEntry(
    "prebiotics", "Prebiotics combo", "supplement_current",
    hr_observed=0.96, log_sd=0.10, conf_alpha=1.0, conf_beta=5.5,
    annual_cost=180, qol_annual=0.003,
    benefit_tags=["gut_support"],
    notes="Gut health markers.",
))
_add(CatalogEntry(
    "probiotic_daily", "Daily probiotics", "supplement_bought",
    hr_observed=1.0, log_sd=0.08, conf_alpha=1.2, conf_beta=5.6,
    annual_cost=273, qol_annual=0.001,
    has_direct_mortality_effect=False,
    evidence_quality="low",
    benefit_tags=["gut_support"],
    notes=(
        "Modeled as a low-evidence GI-support intervention, not a hard-endpoint longevity lever. "
        "Annual cost uses Sports Research Probiotic 60 Billion at the current official subscribe-and-save price; "
        "the currently owned expiring bottle has near-zero marginal cost."
    ),
    sources=[
        "https://www.sportsresearch.store/products/probiotic-60-billion",
        "https://pubmed.ncbi.nlm.nih.gov/24230488/",
        "https://pubmed.ncbi.nlm.nih.gov/41233756/",
    ],
))
_add(CatalogEntry(
    "lutein_zeaxanthin", "Lutein+Zeaxanthin", "supplement_current",
    hr_observed=0.97, log_sd=0.10, conf_alpha=1.0, conf_beta=5.5,
    annual_cost=0, qol_annual=0.002,
    benefit_tags=["antioxidant_support"],
    notes="AREDS2. Eye health. Bundled.",
))
_add(CatalogEntry(
    "astaxanthin_12", "Astaxanthin 12mg", "supplement_current",
    hr_observed=0.95, log_sd=0.12, conf_alpha=1.0, conf_beta=5.0,
    annual_cost=0, qol_annual=0.002,
    benefit_tags=["antioxidant_support"],
    notes="CRP/HDL RCTs. Bundled.",
))
_add(CatalogEntry(
    "lycopene_15", "Lycopene 15mg", "supplement_current",
    hr_observed=0.95, log_sd=0.15, conf_alpha=1.2, conf_beta=4.8,
    annual_cost=0, qol_annual=0.000,
    benefit_tags=["antioxidant_support"],
    notes="Song meta obs. Bundled.",
))
_add(CatalogEntry(
    "nr_300", "NR 300mg", "supplement_current",
    hr_observed=0.97, log_sd=0.10, conf_alpha=1.2, conf_beta=5.0,
    annual_cost=0, qol_annual=0.001,
    benefit_tags=["mitochondrial_support"],
    notes="NAD+ precursor. Bundled.",
))
_add(CatalogEntry(
    "nr_300_unbundled", "NR 300mg (unbundled)", "supplement_candidate",
    hr_observed=0.97, log_sd=0.10, conf_alpha=1.2, conf_beta=5.0,
    annual_cost=396, qol_annual=0.001,
    benefit_tags=["mitochondrial_support"],
    notes=(
        "Standalone NR option using current official Tru Niagen 300mg "
        "180-count subscription pricing."
    ),
    sources=["https://www.truniagen.com/products/tru-niagen-300mg"],
))
_add(CatalogEntry(
    "fisetin_100", "Fisetin 100mg", "supplement_current",
    hr_observed=0.97, log_sd=0.12, conf_alpha=1.0, conf_beta=5.5,
    annual_cost=0, qol_annual=0.000,
    notes="Senolytic. Animal. Bundled.",
))
_add(CatalogEntry(
    "fisetin_100_unbundled", "Fisetin 100mg (unbundled)", "supplement_candidate",
    hr_observed=0.97, log_sd=0.12, conf_alpha=1.0, conf_beta=5.5,
    annual_cost=133, qol_annual=0.000,
    notes=(
        "Standalone fisetin using current Double Wood pricing, modeled at an "
        "Amazon-favored effective cost after 5% Prime cash back."
    ),
    sources=["https://doublewoodsupplements.com/products/fisetin"],
))
_add(CatalogEntry(
    "spermidine_10", "Spermidine 10mg", "supplement_current",
    hr_observed=0.95, log_sd=0.15, conf_alpha=1.2, conf_beta=5.0,
    annual_cost=0, qol_annual=0.000,
    notes="Madeo obs HR 0.70. Animal.",
))
_add(CatalogEntry(
    "luteolin_100", "Luteolin 100mg", "supplement_current",
    hr_observed=0.97, log_sd=0.12, conf_alpha=1.0, conf_beta=5.5,
    annual_cost=0, qol_annual=0.001,
    benefit_tags=["antioxidant_support"],
    notes="Anti-inflammatory. Neuroprotective. Bundled.",
))
_add(CatalogEntry(
    "luteolin_100_unbundled", "Luteolin 100mg (unbundled)", "supplement_candidate",
    hr_observed=0.97, log_sd=0.12, conf_alpha=1.0, conf_beta=5.5,
    annual_cost=115, qol_annual=0.001,
    benefit_tags=["antioxidant_support"],
    notes=(
        "Standalone luteolin using current Double Wood pricing, modeled at an "
        "Amazon-favored effective cost after 5% Prime cash back."
    ),
    sources=["https://doublewoodsupplements.com/products/luteolin"],
))
_add(CatalogEntry(
    "ubiquinol_50", "Ubiquinol 50mg", "supplement_current",
    hr_observed=0.96, log_sd=0.12, conf_alpha=1.5, conf_beta=4.5,
    annual_cost=0, qol_annual=0.001,
    benefit_tags=["mitochondrial_support"],
    notes="Q-SYMBIO RCT in HF. Healthy-pop extrapolation.",
))
_add(CatalogEntry(
    "ubiquinol_50_unbundled", "Ubiquinol 50mg (unbundled)", "supplement_candidate",
    hr_observed=0.96, log_sd=0.12, conf_alpha=1.5, conf_beta=4.5,
    annual_cost=120, qol_annual=0.001,
    benefit_tags=["mitochondrial_support"],
    notes=(
        "Standalone ubiquinol using current Life Extension pricing, modeled at "
        "an Amazon-favored effective cost after 5% Prime cash back."
    ),
    sources=["https://www.lifeextension.com/vitamins-supplements/item01425/super-ubiquinol-coq10-with-ppm-pyrroloquinoline-quinone"],
))
_add(CatalogEntry(
    "boron_3", "Boron 3mg", "supplement_current",
    hr_observed=0.97, log_sd=0.10, conf_alpha=1.0, conf_beta=5.5,
    annual_cost=0, qol_annual=0.000,
    notes="Prostate/bone obs. Bundled.",
))
_add(CatalogEntry(
    "lithium_1mg_orotate", "Lithium 1mg orotate", "supplement_current",
    hr_observed=0.98, log_sd=0.10, conf_alpha=1.2, conf_beta=5.0,
    annual_cost=0, qol_annual=0.001,
    notes="Ecological Li data. Neuroprotective. Bundled.",
))
_add(CatalogEntry(
    "broccoli_seed_200", "Broccoli Seed Ext 200mg", "supplement_current",
    hr_observed=0.95, log_sd=0.15, conf_alpha=1.5, conf_beta=4.5,
    annual_cost=0, qol_annual=0.000,
    notes="Sulforaphane. Phase 2 enzyme induction. Bundled.",
))
_add(CatalogEntry(
    "cocoa_flavanols_500", "Cocoa flavanols ~500mg", "supplement_current",
    hr_observed=0.90, log_sd=0.12, conf_alpha=2.5, conf_beta=3.0,
    annual_cost=260, qol_annual=0.001,
    benefit_tags=["cardiometabolic_support"],
    notes=(
        "COSMOS RCT HR 0.73 CVD. "
        "Blueprint Cocoa priced at $41/container with 60 scoops x 5.76g; "
        "at ~6g/day this is ~58 days/container, or ~$260/yr."
    ),
))
_add(CatalogEntry(
    "hyaluronic_acid_120", "Hyaluronic acid (oral)", "supplement_current",
    hr_observed=0.99, log_sd=0.08, conf_alpha=1.0, conf_beta=7.0,
    annual_cost=0, qol_annual=0.001,
    notes="Joint/skin support. No mortality effect.",
    evidence_quality="low",
))

# ---------------------------------------------------------------------------
# Supplements — already purchased (new additions)
# ---------------------------------------------------------------------------
_add(CatalogEntry(
    "glycine_2g", "Glycine 2g bedtime", "supplement_bought",
    hr_observed=1.0, log_sd=0.05, conf_alpha=1.5, conf_beta=6.0,
    annual_cost=28,  # $17.40 / 227 doses (1lb/151×3g servings, 2g dose) * 365
    qol_annual=0.0002,
    has_direct_mortality_effect=False,
    interaction_tags=["sedating"],
    interaction_rules=[SEDATION_STACK_RULE],
    sleep_component_relief={
        "duration": 0.06,
        "quality": 0.14,
        "daytime": 0.10,
    },
    benefit_tags=[
        "sleep_duration_support",
        "sleep_quality_support",
        "sleep_daytime_support",
    ],
    notes=(
        "Sleep/QOL helper only. Human evidence supports modest next-day fatigue "
        "and sleep-quality improvement, not a mortality claim."
    ),
    sources=[
        "https://pubmed.ncbi.nlm.nih.gov/22529837/",
        "https://www.amazon.com/dp/B0013OVZJW",
    ],
))
_add(CatalogEntry(
    "apigenin_50", "Apigenin 50mg", "supplement_bought",
    hr_observed=0.96, log_sd=0.12, conf_alpha=1.0, conf_beta=6.0,
    annual_cost=76,  # $24.95 / 120 caps * 365
    qol_annual=0.0003,
    interaction_tags=["sedating"],
    interaction_rules=[SEDATION_STACK_RULE],
    sleep_component_relief={
        "quality": 0.12,
        "daytime": 0.08,
    },
    benefit_tags=[
        "sleep_quality_support",
        "sleep_daytime_support",
    ],
    notes="CD38 inhibitor. Anxiolytic.",
    sources=["https://www.amazon.com/dp/B09DGTBBSF"],
))
_add(CatalogEntry(
    "omega3_epa_2g", "High-EPA Omega-3 +2g", "supplement_bought",
    hr_observed=0.955, log_sd=0.10, conf_alpha=2.5, conf_beta=3.0,
    annual_cost=227,  # $27.95 / 90 softgels * 2/day = 45 days, * 365/45
    qol_annual=0.002,
    interaction_tags=["bleeding_stack"],
    interaction_rules=[BLEEDING_STACK_RULE],
    benefit_tags=["cardiometabolic_support"],
    notes="Incremental over CLO. VITAL/REDUCE-IT.",
    sources=["https://www.amazon.com/dp/B07DX89ZHN"],
))
_add(CatalogEntry(
    "taurine_500_topup", "Taurine 500mg top-up", "supplement_bought",
    hr_observed=1.0, log_sd=0.05, conf_alpha=1.2, conf_beta=6.0,
    annual_cost=4.4,  # $23.97 / 2000 doses (1kg powder, 500mg top-up) * 365
    qol_annual=0.0001,
    has_direct_mortality_effect=False,
    benefit_tags=["performance_recovery"],
    notes=(
        "Tiny marginal top-up over 1500mg already in Longevity Mix. Most human "
        "signals are at 1-3g+ or in non-lean phenotypes."
    ),
    sources=[
        "https://pubmed.ncbi.nlm.nih.gov/34039357/",
        "https://pubmed.ncbi.nlm.nih.gov/39796489/",
        "https://www.amazon.com/dp/B00ENSLW7A",
    ],
))

# ---------------------------------------------------------------------------
# Supplements — candidates
# ---------------------------------------------------------------------------
_add(CatalogEntry(
    "urolithin_a_500", "Urolithin A 500mg", "supplement_candidate",
    hr_observed=0.94, log_sd=0.15, conf_alpha=1.5, conf_beta=4.5,
    annual_cost=780, qol_annual=0.003,
    notes="Mitopure. RCTs: improved mitochondrial function. Expensive.",
))
_add(CatalogEntry(
    "ergothioneine_5", "Ergothioneine 5mg", "supplement_candidate",
    hr_observed=0.94, log_sd=0.15, conf_alpha=1.2, conf_beta=5.0,
    annual_cost=240, qol_annual=0.001,
    notes="Longevity vitamin hypothesis. Obs: low ergo → higher mortality.",
))
_add(CatalogEntry(
    "quercetin_500", "Quercetin 500mg", "supplement_candidate",
    hr_observed=0.93, log_sd=0.15, conf_alpha=1.5, conf_beta=4.5,
    annual_cost=60, qol_annual=0.000,
    benefit_tags=["antioxidant_support"],
    notes="Senolytic. Anti-inflammatory. Animal lifespan.",
))
_add(CatalogEntry(
    "sulforaphane_20_extra", "Sulforaphane 20mg (extra)", "supplement_candidate",
    hr_observed=0.94, log_sd=0.15, conf_alpha=1.5, conf_beta=4.5,
    annual_cost=180, qol_annual=0.000,
    notes="NRF2 activator. Incremental over Broccoli Seed Ext.",
))
_add(CatalogEntry(
    "pterostilbene_50", "Pterostilbene 50mg", "supplement_candidate",
    hr_observed=0.96, log_sd=0.15, conf_alpha=1.0, conf_beta=5.5,
    annual_cost=120, qol_annual=0.000,
    notes="Resveratrol analog. AMPK/SIRT1. Animal only.",
))
_add(CatalogEntry(
    "egcg_400", "EGCG 400mg (green tea)", "supplement_candidate",
    hr_observed=0.92, log_sd=0.15, conf_alpha=1.5, conf_beta=4.5,
    annual_cost=60, qol_annual=0.000,
    harm_effects=[
        HarmEffect(
            id="liver_injury",
            description="High-dose extract-associated liver injury concern.",
            event_probability=Distribution(type="point", params={"value": 0.001}),
            event_qaly_loss=Distribution(type="point", params={"value": 0.08}),
        ),
    ],
    benefit_tags=["antioxidant_support", "cardiometabolic_support"],
    notes="Obs meta HR 0.74-0.85. Heavily confounded. Liver risk at high dose.",
))
_add(CatalogEntry(
    "berberine_500", "Berberine 500mg", "supplement_candidate",
    hr_observed=0.88, log_sd=0.18, conf_alpha=1.5, conf_beta=4.5,
    annual_cost=180, qol_annual=-0.004,
    notes="Metformin-like. RCTs in diabetes. GI side effects.",
))
_add(CatalogEntry(
    "alpha_lipoic_acid_300", "Alpha-lipoic acid 300mg", "supplement_candidate",
    hr_observed=0.96, log_sd=0.12, conf_alpha=1.2, conf_beta=5.0,
    annual_cost=60, qol_annual=0.000,
    notes="Antioxidant. RCTs for diabetic neuropathy.",
))
_add(CatalogEntry(
    "pqq_20", "PQQ 20mg", "supplement_candidate",
    hr_observed=0.97, log_sd=0.12, conf_alpha=1.0, conf_beta=6.0,
    annual_cost=180, qol_annual=0.001,
    benefit_tags=["mitochondrial_support", "antioxidant_support"],
    notes="Mitochondrial biogenesis. Small RCTs. Expensive.",
))
_add(CatalogEntry(
    "tmg_1g", "TMG/Betaine 1g", "supplement_candidate",
    hr_observed=0.97, log_sd=0.10, conf_alpha=1.0, conf_beta=5.5,
    annual_cost=30, qol_annual=0.000,
    notes="Methyl donor. Homocysteine reduction. Often paired with NR/NMN.",
))
_add(CatalogEntry(
    "ashwagandha_600", "Ashwagandha 600mg", "supplement_bought",
    hr_observed=0.96, log_sd=0.15, conf_alpha=1.2, conf_beta=5.0,
    annual_cost=60, qol_annual=0.0010,
    harm_effects=[
        HarmEffect(
            id="sedation_or_emotional_blunting",
            description="Next-day dulling, sedation, or emotional blunting during use.",
            annual_qaly_loss=Distribution(type="normal", params={"mean": 0.00015, "sd": 0.00015}),
            source="https://www.nccih.nih.gov/health/ashwagandha",
        ),
        HarmEffect(
            id="gi_intolerance",
            description="GI upset, nausea, diarrhea, or vomiting.",
            event_probability=Distribution(type="point", params={"value": 0.015}),
            event_qaly_loss=Distribution(type="point", params={"value": 0.003}),
            source="https://www.ncbi.nlm.nih.gov/books/NBK548536/",
        ),
        HarmEffect(
            id="thyroid_overactivation",
            description="Thyroid overactivation, thyroiditis, palpitations, or anxiety.",
            event_probability=Distribution(type="point", params={"value": 0.0015}),
            event_qaly_loss=Distribution(type="point", params={"value": 0.035}),
            source="https://pubmed.ncbi.nlm.nih.gov/28829155/",
        ),
        HarmEffect(
            id="rare_liver_injury",
            description="Rare clinically apparent liver injury.",
            event_probability=Distribution(type="point", params={"value": 0.001}),
            event_qaly_loss=Distribution(type="point", params={"value": 0.08}),
            source="https://www.ncbi.nlm.nih.gov/books/NBK548536/",
        ),
    ],
    interaction_tags=["sedating", "thyroid_active"],
    interaction_rules=[SEDATION_STACK_RULE],
    sleep_component_relief={
        "duration": 0.05,
        "quality": 0.12,
        "daytime": 0.12,
    },
    benefit_tags=[
        "sleep_duration_support",
        "sleep_quality_support",
        "sleep_daytime_support",
    ],
    notes="RCTs: cortisol, anxiety, sleep, testosterone. Rare liver concern.",
))
_add(CatalogEntry(
    "lions_mane_1g", "Lions Mane 1g", "supplement_bought",
    hr_observed=0.98, log_sd=0.12, conf_alpha=1.0, conf_beta=6.0,
    annual_cost=287,  # $47.21 / 120 caps, 2/day = 60 days, * 365/60
    qol_annual=0.003,
    notes="NGF stimulation. Small RCTs: cognitive improvement.",
    sources=["https://www.amazon.com/dp/B00OVF9DVM"],
))
_add(CatalogEntry(
    "black_seed_oil_1g", "Black seed oil 1g", "supplement_candidate",
    hr_observed=0.91, log_sd=0.18, conf_alpha=1.2, conf_beta=5.0,
    annual_cost=60, qol_annual=0.000,
    notes="Thymoquinone. Anti-inflammatory. No mortality RCTs.",
))
_add(CatalogEntry(
    "cistanche_200", "Cistanche 200mg", "supplement_bought",
    hr_observed=0.95, log_sd=0.18, conf_alpha=1.0, conf_beta=6.0,
    annual_cost=231,  # $37.99 / 60 tabs, 1/day = 60 days, * 365/60
    qol_annual=0.002,
    benefit_tags=["performance_recovery"],
    notes="Testosterone, anti-aging TCM. Very limited human data.",
    sources=["https://www.amazon.com/dp/B08VTFXWQF"],
))
_add(CatalogEntry(
    "nmn_500", "NMN 500mg", "supplement_candidate",
    hr_observed=0.96, log_sd=0.12, conf_alpha=1.2, conf_beta=5.0,
    annual_cost=360, qol_annual=0.001,
    benefit_tags=["mitochondrial_support"],
    notes="NAD+ precursor (alt to NR). Already getting NR 300mg. Expensive.",
))
_add(CatalogEntry(
    "ghk_cu", "GHK-Cu peptide (topical)", "supplement_candidate",
    hr_observed=0.99, log_sd=0.10, conf_alpha=1.0, conf_beta=7.0,
    annual_cost=300, qol_annual=0.002,
    notes="Wound healing, collagen. Skin only.",
))
_add(CatalogEntry(
    "vitamin_c_500_extra", "Vitamin C 500mg (extra)", "supplement_candidate",
    hr_observed=0.97, log_sd=0.08, conf_alpha=2.0, conf_beta=4.5,
    annual_cost=15, qol_annual=0.000,
    notes="Already getting 250mg from Longevity Mix. Obs meta: modest CVD.",
))
_add(CatalogEntry(
    "zinc_carnosine_75", "Zinc carnosine 75mg", "supplement_bought",
    hr_observed=0.97, log_sd=0.10, conf_alpha=1.5, conf_beta=4.5,
    annual_cost=60, qol_annual=0.001,
    benefit_tags=["gut_support"],
    notes="Gut barrier integrity. Already getting zinc 15mg.",
))
_add(CatalogEntry(
    "traditional_sauna_4x_week", "Traditional dry sauna 4x/week", "supplement_candidate",
    hr_observed=1.0, log_sd=0.08, conf_alpha=1.8, conf_beta=4.8,
    annual_cost=2178, qol_annual=0.0008, qol_years=15,
    has_direct_mortality_effect=False,
    benefit_tags=["performance_recovery"],
    notes=(
        "Modeled as a modest Finnish-style dry sauna intervention, not a direct mortality claim. "
        "Effect assumes roughly 175-194F traditional dry sauna; cost uses current MINT DC club pricing as a local paid-access proxy."
    ),
    sources=[
        "https://pubmed.ncbi.nlm.nih.gov/25705824/",
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC9394774/",
    ],
    evidence_quality="low",
))
_add(CatalogEntry(
    "infrared_sauna_4x_week", "Infrared sauna 4x/week", "supplement_candidate",
    hr_observed=1.0, log_sd=0.07, conf_alpha=1.5, conf_beta=5.2,
    annual_cost=3588, qol_annual=0.00035, qol_years=10,
    has_direct_mortality_effect=False,
    benefit_tags=["performance_recovery"],
    notes=(
        "Infrared sauna is modeled separately from Finnish dry sauna because the evidence is weaker and less directly transportable. "
        "Cost uses current Pure Sweat Georgetown unlimited pricing for 4x/week access."
    ),
    sources=[
        "https://pubmed.ncbi.nlm.nih.gov/41049507/",
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC9394774/",
    ],
    evidence_quality="very-low",
))
_add(CatalogEntry(
    "hbot_60sessions", "HBOT 60-session course", "supplement_candidate",
    hr_observed=1.0, log_sd=0.06, conf_alpha=1.2, conf_beta=6.4,
    annual_cost=1800, qol_annual=0.0002,
    qol_years=5,
    has_direct_mortality_effect=False,
    harm_effects=[
        HarmEffect(
            id="barotrauma_or_oxygen_toxicity",
            description="Barotrauma, middle-ear injury, or rare oxygen-toxicity events.",
            event_probability=Distribution(type="point", params={"value": 0.003}),
            event_qaly_loss=Distribution(type="point", params={"value": 0.02}),
        ),
    ],
    benefit_tags=["performance_recovery"],
    notes=(
        "Cost annualized from a clinic course. Healthy-aging evidence remains early and mostly surrogate-driven."
    ),
    sources=[
        "https://pubmed.ncbi.nlm.nih.gov/35649312/",
        "https://www.fda.gov/medical-devices/letters-health-care-providers/follow-instructions-safe-use-hyperbaric-oxygen-therapy-devices-letter-health-care-providers",
        "https://www.uhms.org/pl/resources/featured-resources/hbo-indications.html",
    ],
    evidence_quality="very-low",
))
_add(CatalogEntry(
    "bpc157_cycle", "BPC-157 cycle", "supplement_candidate",
    hr_observed=1.0, log_sd=0.06, conf_alpha=1.0, conf_beta=6.8,
    annual_cost=1200, qol_annual=0.00005,
    qol_years=2,
    has_direct_mortality_effect=False,
    harm_effects=[
        HarmEffect(
            id="gray_market_peptide_quality_risk",
            description="Injection burden, contamination, dosing, or immunogenicity risk from gray-market peptides.",
            annual_qaly_loss=Distribution(type="normal", params={"mean": 0.0004, "sd": 0.00015}),
        ),
    ],
    notes=(
        "Modeled for a generic annual cycle in an otherwise uninjured user. Human efficacy evidence is extremely thin and product-quality uncertainty is real."
    ),
    sources=[
        "https://pubmed.ncbi.nlm.nih.gov/40756949/",
        "https://www.fda.gov/drugs/human-drug-compounding/understanding-risks-compounded-drugs",
    ],
    evidence_quality="very-low",
))
_add(CatalogEntry(
    "tb500_cycle", "TB-500 cycle", "supplement_candidate",
    hr_observed=1.0, log_sd=0.06, conf_alpha=1.0, conf_beta=7.0,
    annual_cost=1500, qol_annual=0.00003,
    qol_years=2,
    has_direct_mortality_effect=False,
    harm_effects=[
        HarmEffect(
            id="gray_market_tb500_quality_risk",
            description="Injection burden plus contamination and immunogenicity risk with minimal human efficacy data.",
            annual_qaly_loss=Distribution(type="normal", params={"mean": 0.00045, "sd": 0.00018}),
        ),
    ],
    notes=(
        "Treated as an even weaker evidence base than BPC-157 for a general healthy user."
    ),
    sources=[
        "https://www.fda.gov/drugs/human-drug-compounding/understanding-risks-compounded-drugs",
    ],
    evidence_quality="very-low",
))

missing_public_policy_items = sorted(
    item_id for item_id in PUBLIC_ITEM_POLICY_SPECS if item_id not in CATALOG
)
if missing_public_policy_items:
    raise ValueError(
        "public_policy_items.json references unknown catalog ids: "
        f"{missing_public_policy_items}"
    )


# =============================================================================
# POST-HOC ANNOTATIONS
# =============================================================================
#
# Rather than editing every CatalogEntry literal above, we apply three
# orthogonal annotation layers after construction. This keeps each annotation
# auditable (one dict per concern) and easy to override from a calibration
# harness later.
#
# 1. STUDY_QUALITY_BY_ID:   per-item pub-bias shrinkage tier.
# 2. BUNDLE_ALLOCATIONS:    allocate bundle dollar cost to constituent items.
# 3. EXTRA_BENEFIT_TAGS:    attach mechanism-cluster tags so the stack overlap
#                           penalty fires for correlated supplements.
# 4. EVIDENCE_OVERRIDES:    drop evidence_quality for items that have weaker
#                           evidence than their default tier implies.

STUDY_QUALITY_BY_ID: Dict[str, str] = {
    # Preregistered RCTs with hard endpoints — minimal residual inflation.
    "finasteride_1.25mg": "rct_preregistered_hard_endpoint",
    "statin_5mg": "rct_preregistered_hard_endpoint",
    "semaglutide": "rct_preregistered_hard_endpoint",
    "empagliflozin": "rct_preregistered_hard_endpoint",
    "aspirin_81mg": "rct_preregistered_hard_endpoint",
    "daridorexant_25mg": "rct_preregistered_hard_endpoint",
    "lemborexant_5mg": "rct_preregistered_hard_endpoint",
    # Standard RCTs / surrogate endpoints.
    "tadalafil_2.5mg": "rct_standard",
    "magnesium_200": "rct_standard",
    "melatonin_300mcg": "rct_standard",
    "trazodone_50mg": "rct_standard",
    "doxepin_3mg": "rct_standard",
    "suvorexant_10mg": "rct_standard",
    "omega3_epa_2g": "rct_standard",
    "metformin_500mg": "rct_standard",
    "vitamin_d_2000": "rct_standard",
    # Meta-analyses of RCTs.
    "omega3_clo": "meta_analysis_rcts",
    # Large cohort / observational (Ioannidis baseline).
    "garlic_1200": "cohort_large",
    "cocoa_flavanols_500": "cohort_large",
    "vitamin_k2": "cohort_large",
    "vitamin_c_500_extra": "cohort_large",
    # Supplement-industry RCT tier (short, surrogate, unpreregistered, sponsor bias).
    "ashwagandha_600": "supplement_industry_rct",
    "nr_300": "supplement_industry_rct",
    "nr_300_unbundled": "supplement_industry_rct",
    "nmn_500": "supplement_industry_rct",
    "urolithin_a_500": "supplement_industry_rct",
    "apigenin_50": "supplement_industry_rct",
    "creatine_5g": "supplement_industry_rct",
    "glycine_2g": "supplement_industry_rct",
    "collagen_22g": "supplement_industry_rct",
    "lions_mane_1g": "supplement_industry_rct",
    "curcumin_250": "supplement_industry_rct",
    "quercetin_500": "supplement_industry_rct",
    "egcg_400": "supplement_industry_rct",
    "taurine_500_topup": "supplement_industry_rct",
    "fisetin_100": "supplement_industry_rct",
    "fisetin_100_unbundled": "supplement_industry_rct",
    "ubiquinol_50": "supplement_industry_rct",
    "ubiquinol_50_unbundled": "supplement_industry_rct",
    "nac_1200": "supplement_industry_rct",
    "probiotic_daily": "supplement_industry_rct",
    "berberine_500": "supplement_industry_rct",
    "zinc_carnosine_75": "supplement_industry_rct",
    # Observational / ecological / speculative.
    "spermidine_10": "observational_speculative",
    "lithium_5mg": "observational_speculative",
    "lithium_1mg_orotate": "observational_speculative",
    "ergothioneine_5": "observational_speculative",
    "black_seed_oil_1g": "observational_speculative",
    "broccoli_seed_200": "observational_speculative",
    "boron_3": "observational_speculative",
    "hyaluronic_acid_120": "observational_speculative",
    "prebiotics": "observational_speculative",
    "pqq_20": "observational_speculative",
    "tmg_1g": "observational_speculative",
    "alpha_lipoic_acid_300": "observational_speculative",
    "pterostilbene_50": "observational_speculative",
    "cistanche_200": "observational_speculative",
    "ghk_cu": "observational_speculative",
    "luteolin_100": "observational_speculative",
    "luteolin_100_unbundled": "observational_speculative",
    "lutein_zeaxanthin": "observational_speculative",
    "astaxanthin_12": "observational_speculative",
    "lycopene_15": "observational_speculative",
    # Animal-only / mechanistic.
    "17a_estradiol": "animal_or_mechanistic",
    "acarbose_50mg": "animal_or_mechanistic",
    "sulforaphane_20_extra": "animal_or_mechanistic",
    "ginger_400": "animal_or_mechanistic",
    "rapamycin_5mg_wk": "animal_or_mechanistic",
    # Exercise interventions use RCT-plus-cohort evidence but the causal
    # fraction is weak (Ballin 2021, Finnish Twin Cohort). Treat as standard
    # RCTs — the confounding prior (exercise: Beta(1.2, 6.0)) handles most
    # of the shrinkage already.
    "hiit_1x_week": "rct_standard",
    "hiit_2x_week": "rct_standard",
    "hiit_3x_week": "rct_standard",
    "tempo_run_1x_week": "rct_standard",
    "zone2_cardio_2x_week": "rct_standard",
    "strength_maintenance": "rct_standard",
    # Behavioral / environmental sleep interventions.
    "head_elevation_nightly": "observational_speculative",
    "nasacort_nightly": "rct_standard",
}

# Bundle cost allocation. Each tuple is (bundle_id, annual_dollar_share).
# Prices approximate current Blueprint subscription pricing, allocated evenly
# across the Optiqal-tracked constituent ingredients. Prior to this
# annotation, bundled items had annual_cost=0 and inflated their $/QALY.
BUNDLE_ALLOCATIONS: Dict[str, tuple[str, float]] = {
    # Blueprint Essential Capsules subscription: ~$480/yr across 8 tracked
    # constituents → ~$60/yr each.
    "fisetin_100": ("blueprint_essential_capsules", 60.0),
    "spermidine_10": ("blueprint_essential_capsules", 60.0),
    "nr_300": ("blueprint_essential_capsules", 60.0),
    "ubiquinol_50": ("blueprint_essential_capsules", 60.0),
    "lithium_1mg_orotate": ("blueprint_essential_capsules", 60.0),
    "boron_3": ("blueprint_essential_capsules", 60.0),
    "broccoli_seed_200": ("blueprint_essential_capsules", 60.0),
    "luteolin_100": ("blueprint_essential_capsules", 60.0),
    # Blueprint Advanced Antioxidants: ~$180/yr across 3 items → $60 each.
    "astaxanthin_12": ("blueprint_advanced_antioxidants", 60.0),
    "lutein_zeaxanthin": ("blueprint_advanced_antioxidants", 60.0),
    "lycopene_15": ("blueprint_advanced_antioxidants", 60.0),
    # Blueprint Longevity Mix: HA is the only Optiqal-tracked bundled item.
    "hyaluronic_acid_120": ("blueprint_longevity_mix", 80.0),
    # Blueprint NAC+Ginger+Curcumin: allocate a fair share to ginger (NAC and
    # curcumin are priced separately in the catalog).
    "ginger_400": ("blueprint_nac_ginger_curcumin", 25.0),
}

# Extra benefit tags to enable mechanism-cluster diminishing returns. Each
# value is appended to the entry's existing benefit_tags, deduped.
EXTRA_BENEFIT_TAGS: Dict[str, List[str]] = {
    "curcumin_250": ["anti_inflammatory", "antioxidant_support"],
    "ginger_400": ["anti_inflammatory"],
    "quercetin_500": ["anti_inflammatory", "senolytic_support"],
    "egcg_400": ["anti_inflammatory"],
    "apigenin_50": ["anti_inflammatory", "senolytic_support"],
    "ashwagandha_600": ["anti_inflammatory"],
    "black_seed_oil_1g": ["anti_inflammatory"],
    "fisetin_100": ["senolytic_support", "anti_inflammatory", "antioxidant_support"],
    "fisetin_100_unbundled": ["senolytic_support", "anti_inflammatory", "antioxidant_support"],
    "spermidine_10": ["senolytic_support"],
    "luteolin_100": ["anti_inflammatory"],
    "luteolin_100_unbundled": ["anti_inflammatory"],
    "broccoli_seed_200": ["antioxidant_support", "anti_inflammatory"],
    "pterostilbene_50": ["anti_inflammatory", "mitochondrial_support", "senolytic_support"],
    "alpha_lipoic_acid_300": ["antioxidant_support"],
    "tmg_1g": ["methylation_support"],
    "nr_300": ["nad_precursor"],
    "nr_300_unbundled": ["nad_precursor"],
    "nmn_500": ["nad_precursor"],
    "astaxanthin_12": ["anti_inflammatory"],
    "vitamin_c_500_extra": ["antioxidant_support"],
    "ergothioneine_5": ["antioxidant_support"],
    "urolithin_a_500": ["mitochondrial_support"],
    "lions_mane_1g": ["neurotrophic_support"],
    "cistanche_200": ["neurotrophic_support"],
    "creatine_5g": ["neurotrophic_support"],
    "lithium_1mg_orotate": ["neurotrophic_support"],
    "sulforaphane_20_extra": ["antioxidant_support", "anti_inflammatory"],
    "boron_3": ["cardiometabolic_support"],
}

# Drop evidence_quality when it's miscalibrated relative to the actual
# supporting evidence base (mostly surrogate endpoints / rodent data).
EVIDENCE_OVERRIDES: Dict[str, str] = {
    "nr_300": "low",
    "nr_300_unbundled": "low",
    "nmn_500": "low",
    "cistanche_200": "very-low",
    "lions_mane_1g": "low",
    "ergothioneine_5": "low",
    "urolithin_a_500": "low",
    "black_seed_oil_1g": "low",
    "pterostilbene_50": "low",
    "spermidine_10": "low",
    "fisetin_100": "low",
    "fisetin_100_unbundled": "low",
    "apigenin_50": "low",
    "luteolin_100": "low",
    "luteolin_100_unbundled": "low",
    "lithium_1mg_orotate": "low",
    "boron_3": "low",
    "ghk_cu": "low",
    "pqq_20": "low",
    "hyaluronic_acid_120": "low",
    "probiotic_daily": "low",
}


def _replace_entry(item_id: str, **changes) -> None:
    """Replace a CatalogEntry in place using dataclasses.replace."""
    entry = CATALOG.get(item_id)
    if entry is None:
        return
    CATALOG[item_id] = replace(entry, **changes)


def _apply_annotations() -> None:
    """Apply the post-hoc annotation layers to CATALOG."""
    # 1. Study-quality tiers.
    for item_id, tier in STUDY_QUALITY_BY_ID.items():
        _replace_entry(item_id, study_quality=tier)

    # 2. Bundle cost allocations.
    for item_id, (bundle_id, share) in BUNDLE_ALLOCATIONS.items():
        _replace_entry(item_id, bundle_id=bundle_id, bundle_cost_share=float(share))

    # 3. Extra benefit tags (mechanism clusters).
    for item_id, extra_tags in EXTRA_BENEFIT_TAGS.items():
        entry = CATALOG.get(item_id)
        if entry is None:
            continue
        existing = list(entry.benefit_tags or [])
        for tag in extra_tags:
            if tag not in existing:
                existing.append(tag)
        _replace_entry(item_id, benefit_tags=existing)

    # 4. Evidence-quality overrides.
    for item_id, quality in EVIDENCE_OVERRIDES.items():
        _replace_entry(item_id, evidence_quality=quality)

    # 5. Individual calibrations:
    #
    # Aspirin at age 39 with no CVD risk factors. ASPREE (>70y) and ARRIVE
    # (moderate-risk) showed null/harm in healthy primary prevention. The
    # default conf_alpha=4.0, conf_beta=2.0 implies a 67% causal fraction
    # too generous for a healthy 39-year-old. Shrink causal prior and raise
    # bleeding event probability to reflect primary-prevention harm.
    aspirin = CATALOG.get("aspirin_81mg")
    if aspirin is not None:
        new_harms: List[HarmEffect] = []
        for harm in aspirin.harm_effects:
            if harm.id == "bleeding":
                new_harms.append(
                    HarmEffect(
                        id="bleeding",
                        description="Clinically meaningful bleeding risk in primary prevention.",
                        event_probability=Distribution(type="point", params={"value": 0.008}),
                        event_qaly_loss=Distribution(type="point", params={"value": 0.06}),
                    )
                )
            else:
                new_harms.append(harm)
        _replace_entry(
            "aspirin_81mg",
            conf_alpha=2.5,
            conf_beta=5.0,  # mean causal fraction ~0.33
            harm_effects=new_harms,
            profile_effect_rules=list(aspirin.profile_effect_rules) + [
                ProfileEffectRule(
                    multiplier=0.30,
                    bmi_categories=("normal",),
                    has_diabetes=False,
                    has_hypertension=False,
                ),
            ],
        )

    # Statin at LDL 64 (normolipidemia). CTT's per-mmol/L slope is derived
    # from trials starting at higher LDL; extrapolating to primary prevention
    # in normolipidemic healthy adults is aggressive. Dampen via a profile
    # rule so healthy users with normal labs see a smaller expected benefit.
    statin = CATALOG.get("statin_5mg")
    if statin is not None:
        _replace_entry(
            "statin_5mg",
            profile_effect_rules=list(statin.profile_effect_rules) + [
                ProfileEffectRule(
                    multiplier=0.45,
                    bmi_categories=("normal",),
                    has_diabetes=False,
                    has_hypertension=False,
                ),
            ],
        )


_apply_annotations()


# =============================================================================
# GENETIC EFFECT RULES
# =============================================================================
#
# Declarative CPIC-style phenotype → HR-multiplier rules applied to catalog
# items. Guarded so public builds without the genetics submodule still load.
# Multiplier semantics match ProfileEffectRule:
#     hr_adjusted = exp(log(hr) * multiplier)


def _apply_genetic_rules() -> None:
    """Attach PGx rules to the relevant catalog items."""
    try:
        from .genetics.rules import GeneticEffectRule
    except ImportError:
        return

    trazodone_rules = [
        GeneticEffectRule(
            gene="CYP2D6",
            phenotype="ultrarapid_metabolizer",
            multiplier=0.3,
            rationale="CYP2D6 UM clears trazodone too quickly; reduced benefit at standard dose.",
        ),
        GeneticEffectRule(
            gene="CYP2D6",
            phenotype="poor_metabolizer",
            multiplier=0.7,
            rationale="CYP2D6 PM retains trazodone longer; higher next-day sedation partially offsets benefit.",
        ),
    ]

    doxepin_rules = [
        GeneticEffectRule(
            gene="CYP2D6",
            phenotype="poor_metabolizer",
            multiplier=0.8,
            rationale="CYP2D6 PM: standard dose may over-sedate; lower dose retains effect.",
        ),
        GeneticEffectRule(
            gene="CYP2D6",
            phenotype="ultrarapid_metabolizer",
            multiplier=0.6,
            rationale="CYP2D6 UM: under-exposure at standard dose.",
        ),
        GeneticEffectRule(
            gene="CYP2C19",
            phenotype="poor_metabolizer",
            multiplier=0.8,
            rationale="CYP2C19 PM: slower clearance, higher exposure at standard dose.",
        ),
    ]

    attachments = {
        "trazodone_50mg": trazodone_rules,
        "doxepin_3mg": doxepin_rules,
    }
    for item_id, rules in attachments.items():
        entry = CATALOG.get(item_id)
        if entry is None:
            continue
        CATALOG[item_id] = replace(entry, genetic_effect_rules=rules)


_apply_genetic_rules()


PUBLIC_GENERIC_EXCLUDED_REASONS = {
    "aspirin_81mg": (
        "Hidden from the generic public frontier because low-dose aspirin is a "
        "risk-gated, clinician-mediated decision rather than a broad default recommendation."
    ),
    "finasteride_1.25mg": (
        "Hidden from the generic public frontier because finasteride is an "
        "indication-specific personal medication, not a broad public recommendation."
    ),
    "tadalafil_2.5mg": (
        "Hidden from the generic public frontier because tadalafil 2.5mg is "
        "indication- and population-specific, not a generic wellness intervention."
    ),
    "vitamin_d_2000": (
        "Hidden from the generic public frontier because the public model does not "
        "yet capture deficiency risk, intake, or lab status well enough to recommend it broadly."
    ),
}


def get_default_public_policy() -> PublicPolicy:
    """Return the fully resolved public policy used by the live public frontier."""
    return PublicPolicy(
        lane_specs=dict(PUBLIC_LANE_SPECS),
        condition_specs=dict(PUBLIC_CONDITION_SPECS),
        item_policy_specs={
            item_id: PublicItemPolicySpec(
                item_id=item_id,
                public_lane=entry.public_lane,
                public_condition=entry.public_condition,
                public_display_category_override=entry.public_display_category_override,
            )
            for item_id, entry in CATALOG.items()
        },
        excluded_reasons=dict(PUBLIC_GENERIC_EXCLUDED_REASONS),
    )


def _active_public_policy(policy: Optional[PublicPolicy]) -> PublicPolicy:
    return policy if policy is not None else get_default_public_policy()


def _validate_public_lane_spec(
    lane_id: str,
    raw_spec: Mapping[str, Any],
    *,
    base_spec: PublicLaneSpec,
) -> PublicLaneSpec:
    if lane_id not in PUBLIC_RECOMMENDATION_LANE_VALUES:
        raise ValueError(f"Unexpected public lane id override: {lane_id}")
    return PublicLaneSpec(
        id=lane_id,
        label=str(raw_spec.get("label", base_spec.label)),
        description=str(raw_spec.get("description", base_spec.description)),
    )


def _validate_public_threshold_rule(
    raw_rule: Mapping[str, Any],
    *,
    condition_id: str,
) -> PublicThresholdRule:
    signal = str(raw_rule["signal"])
    if signal not in PUBLIC_THRESHOLD_SIGNAL_VALUES:
        raise ValueError(
            f"Unexpected threshold signal {signal!r} in public condition override {condition_id}"
        )
    return PublicThresholdRule(
        signal=signal,
        threshold=float(raw_rule["threshold"]),
        label=str(raw_rule["label"]),
    )


def _validate_public_profile_score_rule(
    raw_rule: Mapping[str, Any],
    *,
    condition_id: str,
) -> PublicProfileScoreRule:
    field_name = str(raw_rule["field"])
    operator = str(raw_rule["operator"])
    if field_name not in PUBLIC_PROFILE_RULE_FIELDS:
        raise ValueError(
            f"Unexpected profile rule field {field_name!r} in public condition override {condition_id}"
        )
    if operator not in PUBLIC_PROFILE_RULE_OPERATORS:
        raise ValueError(
            f"Unexpected profile rule operator {operator!r} in public condition override {condition_id}"
        )
    value = raw_rule["value"]
    if operator == "in":
        value = tuple(value)
    return PublicProfileScoreRule(
        field=field_name,
        operator=operator,
        value=value,
        points=int(raw_rule["points"]),
        label=str(raw_rule["label"]),
    )


def _merge_public_condition_spec(
    condition_id: str,
    raw_override: Mapping[str, Any],
    *,
    base_spec: PublicConditionSpec,
) -> PublicConditionSpec:
    evaluation_kind = str(raw_override.get("evaluation_kind", base_spec.evaluation_kind))
    if evaluation_kind not in PUBLIC_CONDITION_EVALUATION_KINDS:
        raise ValueError(
            f"Unexpected evaluation_kind {evaluation_kind!r} in public condition override {condition_id}"
        )

    threshold_rules = base_spec.threshold_rules
    if "threshold_rules" in raw_override:
        threshold_rules = tuple(
            _validate_public_threshold_rule(raw_rule, condition_id=condition_id)
            for raw_rule in raw_override["threshold_rules"]
        )

    profile_rules = base_spec.profile_rules
    if "profile_rules" in raw_override:
        profile_rules = tuple(
            _validate_public_profile_score_rule(raw_rule, condition_id=condition_id)
            for raw_rule in raw_override["profile_rules"]
        )

    profile_score_threshold = base_spec.profile_score_threshold
    if "profile_score_threshold" in raw_override:
        raw_threshold = raw_override["profile_score_threshold"]
        profile_score_threshold = None if raw_threshold is None else int(raw_threshold)

    return PublicConditionSpec(
        id=condition_id,
        label=str(raw_override.get("label", base_spec.label)),
        description=str(raw_override.get("description", base_spec.description)),
        evaluation_kind=evaluation_kind,
        hidden_reason=str(raw_override.get("hidden_reason", base_spec.hidden_reason)),
        threshold_rules=threshold_rules,
        profile_rules=profile_rules,
        profile_score_threshold=profile_score_threshold,
    )


def _merge_public_item_policy_spec(
    item_id: str,
    raw_override: Mapping[str, Any],
    *,
    base_spec: PublicItemPolicySpec,
) -> PublicItemPolicySpec:
    if item_id not in CATALOG:
        raise ValueError(f"Unknown catalog id in public item policy override: {item_id}")

    public_lane = base_spec.public_lane
    if "public_lane" in raw_override:
        public_lane = raw_override["public_lane"]
    if public_lane is not None and public_lane not in PUBLIC_RECOMMENDATION_LANE_VALUES:
        raise ValueError(
            f"Unexpected public_lane {public_lane!r} in public item policy override {item_id}"
        )

    public_condition = base_spec.public_condition
    if "public_condition" in raw_override:
        public_condition = raw_override["public_condition"]
    if public_condition is not None and public_condition not in PUBLIC_CONDITION_VALUES:
        raise ValueError(
            f"Unexpected public_condition {public_condition!r} in public item policy override {item_id}"
        )

    display_category = base_spec.public_display_category_override
    if "public_display_category_override" in raw_override:
        display_category = raw_override["public_display_category_override"]
    if display_category is not None and display_category not in PUBLIC_DISPLAY_CATEGORY_VALUES:
        raise ValueError(
            "Unexpected public_display_category_override "
            f"{display_category!r} in public item policy override {item_id}"
        )

    return PublicItemPolicySpec(
        item_id=item_id,
        public_lane=public_lane,
        public_condition=public_condition,
        public_display_category_override=display_category,
    )


def load_public_policy_override(
    path: Path | str,
    *,
    base_policy: Optional[PublicPolicy] = None,
) -> PublicPolicy:
    """Load a candidate public-policy override JSON on top of the current resolved policy."""
    active_policy = _active_public_policy(base_policy)
    raw_policy = json.loads(Path(path).read_text())

    lane_specs = dict(active_policy.lane_specs)
    for lane_id, raw_spec in raw_policy.get("lanes", {}).items():
        lane_specs[lane_id] = _validate_public_lane_spec(
            lane_id,
            raw_spec,
            base_spec=lane_specs[lane_id],
        )

    condition_specs = dict(active_policy.condition_specs)
    for condition_id, raw_spec in raw_policy.get("conditions", {}).items():
        if condition_id not in condition_specs:
            raise ValueError(f"Unknown public condition override id: {condition_id}")
        condition_specs[condition_id] = _merge_public_condition_spec(
            condition_id,
            raw_spec,
            base_spec=condition_specs[condition_id],
        )

    item_policy_specs = dict(active_policy.item_policy_specs)
    for item_id, raw_spec in raw_policy.get("items", {}).items():
        base_item_spec = item_policy_specs.get(
            item_id,
            PublicItemPolicySpec(item_id=item_id),
        )
        item_policy_specs[item_id] = _merge_public_item_policy_spec(
            item_id,
            raw_spec,
            base_spec=base_item_spec,
        )

    excluded_reasons = dict(active_policy.excluded_reasons)
    for item_id, reason in raw_policy.get("excluded_reasons", {}).items():
        if item_id not in CATALOG:
            raise ValueError(f"Unknown catalog id in excluded_reasons override: {item_id}")
        if reason in (None, ""):
            excluded_reasons.pop(item_id, None)
            continue
        excluded_reasons[item_id] = str(reason)

    return PublicPolicy(
        lane_specs=lane_specs,
        condition_specs=condition_specs,
        item_policy_specs=item_policy_specs,
        excluded_reasons=excluded_reasons,
    )


def _effective_public_item_policy(
    entry: CatalogEntry,
    policy: Optional[PublicPolicy] = None,
) -> PublicItemPolicySpec:
    active_policy = _active_public_policy(policy)
    return active_policy.item_policy_specs.get(
        entry.id,
        PublicItemPolicySpec(
            item_id=entry.id,
            public_lane=entry.public_lane,
            public_condition=entry.public_condition,
            public_display_category_override=entry.public_display_category_override,
        ),
    )


def has_meaningful_public_airway_signal(
    sleep_estimate: Optional[SleepBurdenEstimate],
    *,
    policy: Optional[PublicPolicy] = None,
) -> bool:
    """Whether public sleep interventions should surface for this phenotype."""
    return evaluate_public_condition(
        _active_public_policy(policy).condition_specs["airway_signal"],
        profile=None,
        sleep_estimate=sleep_estimate,
    )


def has_meaningful_public_osa_therapy_signal(
    sleep_estimate: Optional[SleepBurdenEstimate],
    *,
    policy: Optional[PublicPolicy] = None,
) -> bool:
    """Whether public PAP/oral-appliance escalation should surface for this phenotype."""
    return evaluate_public_condition(
        _active_public_policy(policy).condition_specs["osa_therapy_signal"],
        profile=None,
        sleep_estimate=sleep_estimate,
    )


def has_meaningful_public_nasal_dryness_signal(
    sleep_estimate: Optional[SleepBurdenEstimate],
    *,
    policy: Optional[PublicPolicy] = None,
) -> bool:
    """Whether humidification support should surface for this phenotype."""
    return evaluate_public_condition(
        _active_public_policy(policy).condition_specs["nasal_dryness_signal"],
        profile=None,
        sleep_estimate=sleep_estimate,
    )


def has_meaningful_public_statin_signal(
    profile: Optional[Profile],
    *,
    policy: Optional[PublicPolicy] = None,
) -> bool:
    """Simple public-safe gate for surfacing a generic statin discussion."""
    return evaluate_public_condition(
        _active_public_policy(policy).condition_specs["cardiometabolic_signal"],
        profile=profile,
        sleep_estimate=None,
    )


def has_meaningful_public_metformin_signal(
    profile: Optional[Profile],
    *,
    policy: Optional[PublicPolicy] = None,
) -> bool:
    """Simple public-safe gate for surfacing a generic metformin discussion."""
    return evaluate_public_condition(
        _active_public_policy(policy).condition_specs["metabolic_signal"],
        profile=profile,
        sleep_estimate=None,
    )


def has_meaningful_public_glp1_signal(
    profile: Optional[Profile],
    *,
    policy: Optional[PublicPolicy] = None,
) -> bool:
    """Simple public-safe gate for surfacing a generic GLP-1 discussion."""
    return evaluate_public_condition(
        _active_public_policy(policy).condition_specs["glp1_signal"],
        profile=profile,
        sleep_estimate=None,
    )


def _public_sleep_signal_value(
    signal: PublicThresholdSignal,
    sleep_estimate: SleepBurdenEstimate,
) -> float:
    airway = sleep_estimate.airway
    if signal == "sleep_breathing_burden":
        return float(sleep_estimate.component_burdens.get("breathing", 0.0))
    if airway is None:
        return 0.0
    if signal == "sleep_airway_response_signal":
        return float(airway.response_signal)
    if signal == "sleep_upper_airway_probability":
        return float(airway.upper_airway_probability)
    if signal == "sleep_nasal_inflammation_probability":
        return float(airway.nasal_inflammation_probability)
    if signal == "sleep_mucus_probability":
        return float(airway.mucus_probability)
    return 0.0


def evaluate_public_condition(
    spec: PublicConditionSpec,
    *,
    profile: Optional[Profile],
    sleep_estimate: Optional[SleepBurdenEstimate],
) -> bool:
    """Evaluate a declarative public condition against a profile/sleep phenotype."""
    if spec.evaluation_kind == "sleep_any_threshold":
        if sleep_estimate is None:
            return False
        return any(
            _public_sleep_signal_value(rule.signal, sleep_estimate) >= rule.threshold
            for rule in spec.threshold_rules
        )

    if spec.evaluation_kind == "profile_score":
        if profile is None or spec.profile_score_threshold is None:
            return False
        field_scores: dict[str, int] = {}
        for rule in spec.profile_rules:
            if rule.matches(profile):
                field_scores[rule.field] = max(field_scores.get(rule.field, 0), rule.points)
        return sum(field_scores.values()) >= spec.profile_score_threshold

    return False


def public_recommendation_lane(
    entry: CatalogEntry,
    profile: Optional[Profile] = None,
    policy: Optional[PublicPolicy] = None,
) -> PublicRecommendationLane:
    """Top-level public product lane for this intervention."""
    del profile
    return _effective_public_item_policy(entry, policy).public_lane or entry.public_lane


def has_meaningful_public_condition_signal(
    entry: CatalogEntry,
    profile: Optional[Profile],
    sleep_estimate: Optional[SleepBurdenEstimate],
    policy: Optional[PublicPolicy] = None,
) -> bool:
    """Whether a conditional-public intervention has the needed qualifying signal."""
    public_condition = _effective_public_item_policy(entry, policy).public_condition
    if public_condition is None:
        return False
    spec = _active_public_policy(policy).condition_specs.get(public_condition)
    if spec is None:
        return False
    return evaluate_public_condition(
        spec,
        profile=profile,
        sleep_estimate=sleep_estimate,
    )


def public_display_category(entry: CatalogEntry, policy: Optional[PublicPolicy] = None) -> str:
    """Generic public-facing category, separate from Max-specific stack status."""
    display_category_override = _effective_public_item_policy(
        entry,
        policy,
    ).public_display_category_override
    if display_category_override is not None:
        return display_category_override
    if entry.category.startswith("rx_"):
        return "rx"
    if entry.category.startswith("sleep_"):
        return "sleep"
    return "supplement"


def is_publicly_rankable(
    entry: CatalogEntry,
    profile: Optional[Profile] = None,
    sleep_estimate: Optional[SleepBurdenEstimate] = None,
    policy: Optional[PublicPolicy] = None,
) -> bool:
    """Whether an entry belongs in the public ranked frontier for this phenotype."""
    lane = public_recommendation_lane(entry, policy=policy)
    if lane == "personal_only":
        return False
    if entry.id in _active_public_policy(policy).excluded_reasons:
        return False
    if lane == "conditional_public" and not has_meaningful_public_condition_signal(
        entry,
        profile,
        sleep_estimate,
        policy=policy,
    ):
        return False
    return True


def public_rankability_reason(
    entry: CatalogEntry,
    profile: Optional[Profile] = None,
    sleep_estimate: Optional[SleepBurdenEstimate] = None,
    policy: Optional[PublicPolicy] = None,
) -> Optional[str]:
    """Explain why an item is excluded from the public ranked frontier."""
    if is_publicly_rankable(entry, profile=profile, sleep_estimate=sleep_estimate, policy=policy):
        return None
    active_policy = _active_public_policy(policy)
    effective_item_policy = _effective_public_item_policy(entry, policy)
    lane = public_recommendation_lane(entry, policy=policy)
    if entry.id in active_policy.excluded_reasons:
        return active_policy.excluded_reasons[entry.id]
    if lane == "conditional_public" and not has_meaningful_public_condition_signal(
        entry,
        profile,
        sleep_estimate,
        policy=policy,
    ):
        spec = active_policy.condition_specs.get(effective_item_policy.public_condition)
        if spec is not None:
            return spec.hidden_reason
        return (
            "Hidden from the generic public frontier unless the current profile "
            "triggers a matching conditional lane."
        )
    if effective_item_policy.public_display_category_override == "service":
        return (
            "Hidden from the generic public frontier because high-friction services "
            "are not broad default public recommendations."
        )
    if entry.category.startswith("rx_"):
        return (
            "Hidden from the generic public frontier because this prescription belongs "
            "in a clinician-mediated or condition-specific module, not the generic public lane."
        )
    if entry.category in {"supplement_current", "supplement_bought"}:
        return (
            "Hidden from the generic public frontier because this is modeled as a "
            "personal current-stack item, not a broad public recommendation."
        )
    if entry.category == "supplement_candidate":
        return (
            "Hidden from the generic public frontier because this supplement is not yet "
            "curated as a broad public recommendation."
        )
    if entry.category.startswith("sleep_"):
        return (
            "Hidden from the generic public frontier because this sleep intervention only "
            "belongs in a condition-specific pathway."
        )
    return (
        "Unpriced in the public catalog because the current estimate depends on a "
        "bundle, sunk personal setup, or other non-portable pricing assumption."
    )


def build_public_policy_spec(
    catalog_entries: Optional[Mapping[str, CatalogEntry]] = None,
    policy: Optional[PublicPolicy] = None,
) -> dict[str, list[dict[str, object]]]:
    """Serialize the public gating policy so the UI can visualize it automatically."""
    entries = catalog_entries or CATALOG
    active_policy = _active_public_policy(policy)
    items: list[dict[str, object]] = []
    lane_to_item_ids: dict[str, list[str]] = {
        lane: [] for lane in active_policy.lane_specs
    }
    condition_to_item_ids: dict[str, list[str]] = {
        condition: [] for condition in active_policy.condition_specs
    }

    for item_id, entry in entries.items():
        item_policy = _effective_public_item_policy(entry, policy)
        lane = public_recommendation_lane(entry, policy=policy)
        condition = item_policy.public_condition
        display_category = public_display_category(entry, policy=policy)
        explicitly_excluded = item_id in active_policy.excluded_reasons

        items.append({
            "id": item_id,
            "name": entry.name,
            "lane": lane,
            "condition": condition,
            "display_category": display_category,
            "explicitly_excluded": explicitly_excluded,
        })
        lane_to_item_ids[lane].append(item_id)
        if condition is not None:
            condition_to_item_ids[condition].append(item_id)

    lanes = []
    for lane_id, meta in active_policy.lane_specs.items():
        item_ids = sorted(lane_to_item_ids[lane_id])
        condition_ids = sorted({
            str(_effective_public_item_policy(entries[item_id], policy).public_condition)
            for item_id in item_ids
            if _effective_public_item_policy(entries[item_id], policy).public_condition is not None
        })
        lanes.append({
            "id": lane_id,
            "label": meta.label,
            "description": meta.description,
            "item_ids": item_ids,
            "item_count": len(item_ids),
            "condition_ids": condition_ids,
        })

    conditions = []
    for condition_id, meta in active_policy.condition_specs.items():
        item_ids = sorted(condition_to_item_ids[condition_id])
        if not item_ids:
            continue
        conditions.append({
            "id": condition_id,
            "label": meta.label,
            "description": meta.description,
            "item_ids": item_ids,
            "item_count": len(item_ids),
            "evaluation_kind": meta.evaluation_kind,
            "score_threshold": meta.profile_score_threshold,
            "thresholds": [
                {
                    "signal": rule.signal,
                    "label": rule.label,
                    "threshold": rule.threshold,
                }
                for rule in meta.threshold_rules
            ],
            "score_rules": [
                {
                    "field": rule.field,
                    "operator": rule.operator,
                    "label": rule.label,
                    "points": rule.points,
                }
                for rule in meta.profile_rules
            ],
        })

    items.sort(key=lambda item: (str(item["lane"]), str(item["display_category"]), str(item["name"])))
    return {
        "lanes": lanes,
        "conditions": conditions,
        "items": items,
    }


def get_catalog(
    categories: Optional[List[str]] = None,
) -> Dict[str, CatalogEntry]:
    """Get catalog entries, optionally filtered by category."""
    if categories is None:
        return dict(CATALOG)
    return {k: v for k, v in CATALOG.items() if v.category in categories}


def _sample_catalog_distribution(
    dist: Distribution,
    n_simulations: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Sample a catalog Distribution using the entry-local RNG."""
    return dist.sample(
        n_simulations,
        random_state=int(rng.integers(0, np.iinfo(np.uint32).max)),
    )


def _summarize_qaly_draws(draws: np.ndarray) -> Dict[str, float]:
    """Return expected QALY and day summaries for one uncertain component."""
    return {
        "mean_qaly": float(np.mean(draws)),
        "ci95_qaly_low": float(np.percentile(draws, 2.5)),
        "ci95_qaly_high": float(np.percentile(draws, 97.5)),
        "mean_days": float(np.mean(draws) * 365.25),
        "ci95_days_low": float(np.percentile(draws, 2.5) * 365.25),
        "ci95_days_high": float(np.percentile(draws, 97.5) * 365.25),
        "p_positive": float(np.mean(draws > 0)),
    }


def _simulate_qol_effect_draws(
    entry: CatalogEntry,
    *,
    qol_factor: float,
    evidence_multiplier: float,
    n_simulations: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, List[Dict[str, Any]]]:
    """Sample named QoL components and preserve the legacy scalar component."""
    raw_qol_draws = np.zeros(n_simulations)
    qol_draws = np.zeros(n_simulations)
    component_summaries: List[Dict[str, Any]] = []

    if entry.qol_annual != 0:
        raw_component = np.full(n_simulations, entry.qol_annual * qol_factor)
        component = raw_component * evidence_multiplier
        raw_qol_draws += raw_component
        qol_draws += component

    for effect in entry.qol_effects:
        annual_draws = _sample_catalog_distribution(
            effect.annual_qaly,
            n_simulations,
            rng,
        )
        raw_component = annual_draws * qol_factor
        component = raw_component * evidence_multiplier
        raw_qol_draws += raw_component
        qol_draws += component
        annual_summary = _summarize_qaly_draws(annual_draws * evidence_multiplier)
        lifetime_summary = _summarize_qaly_draws(component)
        component_summaries.append({
            "id": effect.id,
            "label": effect.label,
            "description": effect.description,
            "source": effect.source,
            "annual_mean_qaly": annual_summary["mean_qaly"],
            "annual_ci95_qaly_low": annual_summary["ci95_qaly_low"],
            "annual_ci95_qaly_high": annual_summary["ci95_qaly_high"],
            "mean_qaly": lifetime_summary["mean_qaly"],
            "ci95_qaly_low": lifetime_summary["ci95_qaly_low"],
            "ci95_qaly_high": lifetime_summary["ci95_qaly_high"],
            "mean_days": lifetime_summary["mean_days"],
            "ci95_days_low": lifetime_summary["ci95_days_low"],
            "ci95_days_high": lifetime_summary["ci95_days_high"],
            "p_positive": lifetime_summary["p_positive"],
        })

    return raw_qol_draws, qol_draws, component_summaries


def simulate_catalog(
    profile,
    n_simulations: int = 50_000,
    random_state: int = 42,
    pub_bias_shrinkage: float = 0.30,
    horizon_years: float = 40,
    qaly_discount_rate: float = DEFAULT_QALY_DISCOUNT_RATE,
    cost_discount_rate: float = DEFAULT_COST_DISCOUNT_RATE,
    wtp: float = 200_000,
    categories: Optional[List[str]] = None,
    catalog_entries: Optional[Dict[str, CatalogEntry]] = None,
    active_interaction_tags: Optional[List[str]] = None,
    sleep_estimate: Optional[SleepBurdenEstimate] = None,
) -> List[Dict]:
    """
    Simulate all catalog entries and return sorted results.

    Returns list of dicts with: id, name, category, hr_observed, hr_corrected,
    total_qaly, days, p_benefit, annual_cost, gross_value, cost_per_qaly.

    Costs and QALYs use the shared reference-case discount defaults unless
    explicitly overridden for sensitivity analysis.
    """
    from .simulate import (
        effective_qol_factor_for_years,
        simulate_qaly_profile_vectorized,
    )

    qaly_discount_rate = validate_qaly_discount_rate(qaly_discount_rate)

    if catalog_entries is not None:
        entries = catalog_entries
        if categories is not None:
            entries = {k: v for k, v in entries.items() if v.category in categories}
    else:
        entries = get_catalog(categories)
    results = []
    baseline_sleep_hazard_multiplier = sleep_baseline_mortality_multiplier(sleep_estimate)

    for entry_index, entry in enumerate(entries.values()):
        effect_multiplier = entry.profile_effect_multiplier(profile)
        evidence_multiplier = entry.evidence_effect_multiplier()
        effective_shrinkage = entry.effective_pub_bias_shrinkage(fallback=pub_bias_shrinkage)
        intervention = entry.to_intervention(pub_bias_shrinkage, profile=profile)
        sleep_mortality_hr_multiplier = entry.sleep_mortality_hr_multiplier(sleep_estimate)
        sleep_mortality_relief_fraction = entry.sleep_mortality_relief_fraction(sleep_estimate)
        airway_effect_multiplier = entry.airway_effect_multiplier(sleep_estimate)
        r, base_qaly_draws = simulate_qaly_profile_vectorized(
            intervention, profile,
            n_simulations=n_simulations,
            discount_rate=qaly_discount_rate,
            cost_discount_rate=cost_discount_rate,
            active_interaction_tags=active_interaction_tags,
            baseline_hazard_multiplier=baseline_sleep_hazard_multiplier,
            global_intervention_hr_multiplier=sleep_mortality_hr_multiplier,
            random_state=random_state,
            return_qaly_gains=True,
        )
        hr_corrected = publication_bias_correct(
            entry.hr_observed, shrinkage=effective_shrinkage,
        )
        harm_qaly = r.expected_harm_qalys + r.expected_interaction_harm_qalys
        mort_qaly = r.mean - harm_qaly
        qol_years = min(float(entry.qol_years), float(horizon_years))
        qol_factor = effective_qol_factor_for_years(
            r.expected_qol_weights,
            qol_years,
            r.expected_qol_factor,
        )
        qol_rng = np.random.default_rng(
            np.random.SeedSequence([
                int(random_state) if random_state is not None else 0,
                entry_index,
                9917,
            ])
        )
        raw_qol_draws, qol_draws, qol_effect_summaries = _simulate_qol_effect_draws(
            entry,
            qol_factor=qol_factor,
            evidence_multiplier=evidence_multiplier,
            n_simulations=n_simulations,
            rng=qol_rng,
        )
        raw_qol_qaly = float(np.mean(raw_qol_draws))
        qol_qaly = float(np.mean(qol_draws))
        raw_sleep_qol_annual = entry.raw_sleep_qol_annual(sleep_estimate)
        sleep_qol_annual = entry.sleep_qol_annual(sleep_estimate)
        raw_sleep_qol_qaly = raw_sleep_qol_annual * qol_factor
        sleep_qol_qaly = sleep_qol_annual * qol_factor
        evidence_discount_qaly = (raw_qol_qaly - qol_qaly) + (raw_sleep_qol_qaly - sleep_qol_qaly)
        total_qaly_draws = base_qaly_draws + qol_draws + sleep_qol_qaly
        total_qaly = float(np.mean(total_qaly_draws))
        total_qaly_ci95 = (
            float(np.percentile(total_qaly_draws, 2.5)),
            float(np.percentile(total_qaly_draws, 97.5)),
        )
        # Survival-weighted discounted cost. Uses effective_annual_cost so
        # bundled items (NR, ubiquinol, astaxanthin, etc.) get their allocated
        # share of the Blueprint Essentials bundle price instead of free-riding.
        effective_cost = entry.effective_annual_cost()
        total_cost = effective_cost * r.expected_discounted_cost_factor
        cost_per_qaly = total_cost / total_qaly if total_qaly > 0 and effective_cost > 0 else None
        component_breakdown = {
            "mortality_qaly": mort_qaly,
            "direct_qol_qaly": qol_qaly,
            "sleep_qol_qaly": sleep_qol_qaly,
            "direct_harm_qaly": r.expected_harm_qalys,
            "interaction_harm_qaly": r.expected_interaction_harm_qalys,
            "evidence_discount_qaly": -evidence_discount_qaly,
        }
        top_positive_component = max(
            (
                ("mortality_qaly", mort_qaly),
                ("direct_qol_qaly", qol_qaly),
                ("sleep_qol_qaly", sleep_qol_qaly),
            ),
            key=lambda item: item[1],
        )[0]
        top_negative_component = min(
            (
                ("direct_harm_qaly", r.expected_harm_qalys),
                ("interaction_harm_qaly", r.expected_interaction_harm_qalys),
                ("evidence_discount_qaly", -evidence_discount_qaly),
            ),
            key=lambda item: item[1],
        )[0]

        results.append({
            "id": entry.id,
            "name": entry.name,
            "category": entry.category,
            "hr_observed": entry.hr_observed,
            # hr_corrected = publication-bias-only HR (what the literature
            # "actually shows" after naive bias correction). Kept for back-compat.
            "hr_corrected": hr_corrected,
            # hr_posterior* = HR the simulator actually applies after pub bias
            # PLUS Bayesian confounding + profile transport + evidence shrinkage.
            # This is the column a reader should compare items on.
            "hr_posterior_mean": r.posterior_hr_mean,
            "hr_posterior_median": r.posterior_hr_median,
            "hr_posterior_ci95": r.posterior_hr_ci95,
            "pub_bias_shrinkage": effective_shrinkage,
            "study_quality": entry.study_quality,
            "profile_effect_multiplier": effect_multiplier,
            "evidence_quality": entry.evidence_quality,
            "evidence_effect_multiplier": evidence_multiplier,
            "baseline_sleep_hazard_multiplier": baseline_sleep_hazard_multiplier,
            "airway_effect_multiplier": airway_effect_multiplier,
            "sleep_mortality_relief_fraction": sleep_mortality_relief_fraction,
            "sleep_mortality_hr_multiplier": sleep_mortality_hr_multiplier,
            "mort_qaly": mort_qaly,
            "harm_qaly": harm_qaly,
            "direct_harm_qaly": r.expected_harm_qalys,
            "interaction_harm_qaly": r.expected_interaction_harm_qalys,
            "raw_qol_qaly": raw_qol_qaly,
            "qol_qaly": qol_qaly,
            "qol_effects": qol_effect_summaries,
            "qol_years": qol_years,
            "raw_sleep_qol_annual": raw_sleep_qol_annual,
            "sleep_qol_annual": sleep_qol_annual,
            "raw_sleep_qol_qaly": raw_sleep_qol_qaly,
            "sleep_qol_qaly": sleep_qol_qaly,
            "evidence_discount_qaly": evidence_discount_qaly,
            "component_breakdown": component_breakdown,
            "top_positive_component": top_positive_component,
            "top_negative_component": top_negative_component,
            "total_qaly": total_qaly,
            "days": total_qaly * 365.25,
            "total_qaly_ci95": total_qaly_ci95,
            "ci_low": total_qaly_ci95[0] * 365.25,
            "ci_high": total_qaly_ci95[1] * 365.25,
            # Median QALY of the mortality arm — convexity-invariant
            # diagnostic. Do NOT substitute for total_qaly in ICER / net-
            # monetary-benefit calculations; CEA arithmetic requires expected
            # values, not medians. Median can hide discrete large-loss harm
            # draws and reorder the frontier vs. the mean. Surface this
            # alongside total_qaly to spot cases where the mean has material
            # Jensen-on-survival bias or heavy-tail harm exposure.
            "mortality_qaly_median": float(r.median),
            "mortality_qaly_mean": float(r.mean),
            "p_benefit": float(np.mean(total_qaly_draws > 0)),
            "p_harm": float(np.mean(total_qaly_draws < 0)),
            "expected_upside_days": float(np.mean(np.clip(total_qaly_draws, 0, None)) * 365.25),
            "expected_downside_days": float(np.mean(np.clip(total_qaly_draws, None, 0)) * 365.25),
            "annual_cost": entry.annual_cost,
            "effective_annual_cost": effective_cost,
            "bundle_cost_share": entry.bundle_cost_share,
            "bundle_id": entry.bundle_id,
            "total_cost": total_cost,
            "cost_per_qaly": cost_per_qaly,
            "expected_discounted_cost_factor": r.expected_discounted_cost_factor,
            "gross_value": total_qaly * wtp - total_cost,
        })

    results.sort(key=lambda x: x["gross_value"], reverse=True)
    return results
