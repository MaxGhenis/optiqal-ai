"""Stack-level interaction and overlap modeling."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from .catalog import CatalogEntry
from .defaults import DEFAULT_QALY_DISCOUNT_RATE, validate_qaly_discount_rate
from .lifecycle import get_mortality_rate
from .profile import Profile, get_baseline_mortality_multiplier
from .sleep import SLEEP_COMPONENT_BENEFIT_TAGS


SLEEP_COMPONENT_RETENTION = (1.0, 0.55, 0.30, 0.15)
# Steeper within-cluster retention schedules reflect that supplements hitting the
# same biological pathway largely compete for the same upstream substrate or the
# same downstream signal. See docs/methodology.md for the calibration rationale.
BENEFIT_OVERLAP_RETENTION: Dict[str, tuple[float, ...]] = {
    **{tag: SLEEP_COMPONENT_RETENTION for tag in SLEEP_COMPONENT_BENEFIT_TAGS.values()},
    "cardiometabolic_support": (1.0, 0.70, 0.50, 0.35, 0.25),
    # Broad redox / antioxidant cluster — saturates fast past the first item
    # because endogenous antioxidant capacity (Nrf2, glutathione) has a ceiling.
    "antioxidant_support": (1.0, 0.40, 0.20, 0.10, 0.05),
    # Mitochondrial biogenesis / NAD+ pathway — strong shared mechanism.
    "mitochondrial_support": (1.0, 0.45, 0.25, 0.15, 0.10),
    # NAD+ precursor competition is even tighter (NR and NMN share the same
    # salvage pathway; stacking provides almost no additional NAD+ lift).
    "nad_precursor": (1.0, 0.25, 0.12, 0.08, 0.05),
    # Anti-inflammatory polyphenol cluster (curcumin, quercetin, apigenin, EGCG,
    # luteolin, cocoa flavanols, astaxanthin, black seed oil). Shared NF-kB /
    # COX / iNOS targets; CRP reductions are not additive beyond the first item.
    "anti_inflammatory": (1.0, 0.40, 0.22, 0.12, 0.08),
    # Senolytic / autophagy cluster (fisetin, spermidine, rapamycin, quercetin
    # via senolytic pathway). Shared cellular clearance mechanism.
    "senolytic_support": (1.0, 0.45, 0.25, 0.15, 0.10),
    # Methylation / one-carbon metabolism (TMG, B12, folate, SAMe).
    "methylation_support": (1.0, 0.55, 0.35, 0.20, 0.12),
    # Neurotrophic / cognitive (Lion's Mane, cistanche, creatine cognitive
    # component, citicoline). Mechanisms partly overlap (NGF/BDNF).
    "neurotrophic_support": (1.0, 0.60, 0.40, 0.25, 0.15),
    "gut_support": (1.0, 0.60, 0.35, 0.22, 0.15),
    "performance_recovery": (1.0, 0.65, 0.42, 0.28, 0.18),
}

# Default retention schedule applied when an item has any benefit_tag at all
# but falls outside the named clusters. Previously this was 0.70 — that
# effectively let 40 loosely-tagged items stack to ~full additivity.
DEFAULT_UNNAMED_CLUSTER_RETENTION: tuple[float, ...] = (1.0, 0.70, 0.50, 0.35, 0.25)


def _retained_fraction(tag: str, rank: int) -> float:
    schedule = BENEFIT_OVERLAP_RETENTION.get(tag)
    if schedule is None:
        if rank == 0:
            return 1.0
        idx = min(rank, len(DEFAULT_UNNAMED_CLUSTER_RETENTION) - 1)
        return DEFAULT_UNNAMED_CLUSTER_RETENTION[idx]
    return schedule[min(rank, len(schedule) - 1)]


def _baseline_survival(profile: Profile) -> np.ndarray:
    """Expected baseline survival probability at the start of each future year."""
    max_age = 100
    n_years = max_age - profile.age
    years = np.arange(n_years)
    ages = profile.age + years
    base_qx = np.array([get_mortality_rate(int(a), profile.sex) for a in ages])
    base_qx = np.minimum(base_qx * get_baseline_mortality_multiplier(profile), 0.99)
    survival = np.cumprod(1 - base_qx)
    return np.concatenate([[1.0], survival[:-1]])


def _get_triggered_rules(
    item_ids: List[str],
    catalog_entries: Dict[str, CatalogEntry],
    extra_tags: Optional[Iterable[str]] = None,
):
    """Collect triggered interaction rules, deduplicated by rule id."""
    tag_counts = Counter(extra_tags or [])
    unique_rules = {}

    for item_id in item_ids:
        entry = catalog_entries.get(item_id)
        if entry is None:
            continue
        for tag in entry.interaction_tags:
            tag_counts[tag] += 1
        for rule in entry.interaction_rules:
            unique_rules.setdefault(rule.id, rule)

    triggered = []
    for rule in unique_rules.values():
        threshold = rule.minimum_matches or len(rule.requires_tags)
        matches = sum(tag_counts[tag] for tag in rule.requires_tags)
        if matches >= threshold and all(tag_counts[tag] > 0 for tag in rule.requires_tags):
            triggered.append(rule)

    return tag_counts, triggered


def _expected_benefit_overlap_qaly(
    item_ids: List[str],
    catalog_entries: Dict[str, CatalogEntry],
    item_qalys: Optional[Dict[str, float]] = None,
    benefit_tag_multipliers: Optional[Dict[str, float]] = None,
) -> Tuple[float, List[dict]]:
    """Return overlap penalty for positive benefits sharing the same domain."""
    if not item_qalys:
        return 0.0, []

    groups: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
    for item_id in item_ids:
        entry = catalog_entries.get(item_id)
        if entry is None:
            continue
        qaly = float(item_qalys.get(item_id, 0.0))
        if qaly <= 0:
            continue
        for tag in entry.benefit_tags:
            groups[tag].append((item_id, qaly))

    item_penalties: Dict[str, tuple[float, str, float]] = {}
    tag_counts: Dict[str, int] = {}
    for tag, members in groups.items():
        if len(members) < 2:
            continue
        tag_counts[tag] = len(members)
        for rank, (item_id, qaly) in enumerate(sorted(members, key=lambda m: (-m[1], m[0]))):
            retained = _retained_fraction(tag, rank)
            penalty_multiplier = float(max(0.0, (benefit_tag_multipliers or {}).get(tag, 1.0)))
            penalty = qaly * (1.0 - retained) * penalty_multiplier
            current = item_penalties.get(item_id)
            if current is None or penalty > current[0]:
                item_penalties[item_id] = (penalty, tag, retained)

    penalty_by_tag: Dict[str, float] = defaultdict(float)
    items_by_tag: Dict[str, List[str]] = defaultdict(list)
    retained_by_tag: Dict[str, List[float]] = defaultdict(list)
    total_penalty = 0.0
    for item_id, (penalty, tag, retained) in item_penalties.items():
        if penalty <= 0:
            continue
        total_penalty -= penalty
        penalty_by_tag[tag] += penalty
        items_by_tag[tag].append(item_id)
        retained_by_tag[tag].append(retained)

    details = [
        {
            "id": f"benefit_overlap:{tag}",
            "description": f"Diminishing marginal benefit within the {tag.replace('_', ' ')} domain.",
            "requires_tags": [tag],
            "matched_tag_count": tag_counts[tag],
            "penalty_qaly": -penalty_by_tag[tag],
            "item_ids": sorted(items_by_tag[tag]),
            "retained_fractions": sorted(retained_by_tag[tag], reverse=True),
        }
        for tag in sorted(penalty_by_tag)
    ]
    return total_penalty, details


def expected_stack_interaction_qaly(
    item_ids: List[str],
    catalog_entries: Dict[str, CatalogEntry],
    profile: Profile,
    qaly_discount_rate: float = DEFAULT_QALY_DISCOUNT_RATE,
    extra_tags: Optional[Iterable[str]] = None,
    item_qalys: Optional[Dict[str, float]] = None,
    benefit_tag_multipliers: Optional[Dict[str, float]] = None,
) -> Tuple[float, List[dict]]:
    """
    Return expected stack-level interaction QALY penalty and triggered rule details.

    The penalty is evaluated once per triggered rule for the whole stack,
    avoiding per-item double counting.
    """
    qaly_discount_rate = validate_qaly_discount_rate(qaly_discount_rate)
    survival = _baseline_survival(profile)
    discount = (1 / (1 + qaly_discount_rate)) ** np.arange(len(survival))
    exposure_factor = float(np.sum(survival * discount))

    tag_counts, triggered_rules = _get_triggered_rules(item_ids, catalog_entries, extra_tags)
    total_penalty = 0.0
    details: List[dict] = []

    for rule in triggered_rules:
        penalty = 0.0
        if rule.annual_qaly_loss is not None:
            penalty -= rule.annual_qaly_loss.mean * exposure_factor
        if rule.event_probability is not None and rule.event_qaly_loss is not None:
            p = float(np.clip(rule.event_probability.mean, 0, 1))
            annual_event_prob = np.clip(survival * p, 0, 1)
            if rule.max_events == 1:
                lifetime_prob = float(1 - np.prod(1 - annual_event_prob))
                penalty -= lifetime_prob * rule.event_qaly_loss.mean
            else:
                expected_events = float(np.sum(annual_event_prob))
                penalty -= min(expected_events, rule.max_events) * rule.event_qaly_loss.mean

        total_penalty += penalty
        details.append({
            "id": rule.id,
            "description": rule.description,
            "requires_tags": list(rule.requires_tags),
            "matched_tag_count": int(sum(tag_counts[tag] for tag in rule.requires_tags)),
            "penalty_qaly": penalty,
        })

    overlap_penalty, overlap_details = _expected_benefit_overlap_qaly(
        item_ids=item_ids,
        catalog_entries=catalog_entries,
        item_qalys=item_qalys,
        benefit_tag_multipliers=benefit_tag_multipliers,
    )
    total_penalty += overlap_penalty
    details.extend(overlap_details)

    details.sort(key=lambda d: d["penalty_qaly"])
    return total_penalty, details


def build_stack_interaction_penalty_fn(
    catalog_entries: Dict[str, CatalogEntry],
    profile: Profile,
    qaly_discount_rate: float = DEFAULT_QALY_DISCOUNT_RATE,
    extra_tags: Optional[Iterable[str]] = None,
    item_qalys: Optional[Dict[str, float]] = None,
    benefit_tag_multipliers: Optional[Dict[str, float]] = None,
):
    """Create a callable suitable for the greedy portfolio optimizer."""

    def _penalty(item_ids: List[str]) -> float:
        penalty, _ = expected_stack_interaction_qaly(
            item_ids=item_ids,
            catalog_entries=catalog_entries,
            profile=profile,
            qaly_discount_rate=qaly_discount_rate,
            extra_tags=extra_tags,
            item_qalys=item_qalys,
            benefit_tag_multipliers=benefit_tag_multipliers,
        )
        return penalty

    return _penalty
