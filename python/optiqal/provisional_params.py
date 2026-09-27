"""Provisional parameters that await evidence adjudication.

Every value here is a placeholder, not an evidence claim. Each is defined once
and imported by the catalog, the QoL-guard annotations and the protocol spec,
so replacing one after adjudication is a one-line change in this file.

``l_theanine_200_bedtime`` (added 2026-09-23): a standalone 200 mg L-theanine
product taken before bed, separate from the 200 mg in the morning Blueprint
Longevity Mix (catalog id ``l_theanine_200``). The product and dose are the
working assumption recorded in health.db; no study has been linked yet.
"""

from __future__ import annotations

L_THEANINE_BEDTIME_ID = "l_theanine_200_bedtime"

# Fractions of each sleep component's modeled burden the item relieves before
# the QoL evidence guard shrinks them.
L_THEANINE_BEDTIME_SLEEP_COMPONENT_RELIEF: dict[str, float] = {
    "quality": 0.06,
    "duration": 0.03,
    "daytime": 0.03,
}

# QoL-guard tier, set equal to glycine_2g's annotations in qol_annotations.py:
# study quality "supplement_industry_rct", claim category "sleep_symptom"
# (authored_shaded for general QoL, published_delta for sleep relief).
L_THEANINE_BEDTIME_QOL_STUDY_QUALITY = "supplement_industry_rct"
L_THEANINE_BEDTIME_QOL_CATEGORY = "sleep_symptom"

# No mortality effect and no general (non-sleep) QoL claim.
L_THEANINE_BEDTIME_HR = 1.0
L_THEANINE_BEDTIME_QOL_ANNUAL = 0.0

# Years the relief and the cost are counted over; 10 matches glycine_2g,
# ashwagandha_600 and apigenin_50 in the protocol specs.
L_THEANINE_BEDTIME_QOL_YEARS = 10.0

# Interaction tags feed shared stack rules. glycine_2g carries "sedating",
# which triggers the sedation-stack penalty once two sedating items are
# active. Whether L-theanine belongs there is part of the adjudication; it
# carries no interaction tag until then.
L_THEANINE_BEDTIME_INTERACTION_TAGS: tuple[str, ...] = ()

# Sanity range for the protocol spec (total QALY), the same as glycine_2g's.
# This item was added after data/predeclared_ranges_v1.json was frozen, so the
# range is declared here and reported as unfrozen, never written into that file.
L_THEANINE_BEDTIME_SANITY_RANGE: tuple[float, float] = (-0.01, 0.03)


# ---------------------------------------------------------------------------
# ``eight_sleep_pod6_upgrade`` (added 2026-09-24): replacing Max's Eight Sleep
# Pod 5 King cover + hub with a Pod 6 King cover + hub, keeping his existing
# base and Autopilot plan. The item is a DELTA over the Pod 5: his measured
# sleep baseline already reflects nightly Pod 5 use with Autopilot and
# snore-triggered base elevation on, so the relief below is only what the
# Pod 6 could add. Evidence and data behind each number:
# ~/_tmp/pod6-20260924/REPORT.html (product pages fetched 2026-09-25; Europe PMC
# abstracts fetched 2026-09-25; Max's Eight data from the 2026-09-24 snapshot).

EIGHT_SLEEP_POD6_UPGRADE_ID = "eight_sleep_pod6_upgrade"

# Breathing: the only Pod 6 feature aimed at airway disease is sleep apnea
# detection and mitigation. The press release says Eight Sleep is "pursuing"
# FDA and Abu Dhabi HTA clearance; one reviewer reports the FDA filing; no date
# is given. Expected relief = P(cleared and shipped to a Pod 6 King with base)
# x relief if available x share of the device life it would be available for.
# If the feature also reached a Pod 5 with a base, the upgrade's share of it
# would be lower, so ignoring that is generous to the upgrade. The conditional relief is an increment over Max's
# fixed 10 degree incline plus the Pod 5's snore-triggered elevation; the
# head-of-bed literature (25-35% AHI reductions at 7.5-30 degrees vs flat)
# bounds it, and his incline already captures part of that.
POD6_P_APNEA_MITIGATION_AVAILABLE = 0.35
POD6_BREATHING_RELIEF_IF_AVAILABLE = 0.08
POD6_SHARE_OF_LIFE_AVAILABLE = 0.75
_POD6_EXPECTED_BREATHING = round(
    POD6_P_APNEA_MITIGATION_AVAILABLE
    * POD6_BREATHING_RELIEF_IF_AVAILABLE
    * POD6_SHARE_OF_LIFE_AVAILABLE,
    4,
)

# Quality: "20% faster" temperature changes (550 W vs 400 W). No study
# compares Pod generations. In Max's last 51 scored nights, the coolest hourly
# bed-surface reading from 1 h before sleep onset to wake was always the first
# one, before he fell asleep, and his room stayed near 20.7 C (max 22.1 C).
# The bed is already at its coolest before sleep; whether it hits its target
# is not observable (the heating-level series is empty). The allowance is small.
POD6_THERMAL_QUALITY_RELIEF = 0.01

EIGHT_SLEEP_POD6_SLEEP_COMPONENT_RELIEF: dict[str, float] = {
    "breathing": _POD6_EXPECTED_BREATHING,
    "quality": POD6_THERMAL_QUALITY_RELIEF,
}

# Breathing relief is phenotype-dependent, as for head elevation. The engine
# applies one airway multiplier to every component of an item
# (sleep.effective_sleep_component_relief), so the small thermal term is also
# scaled by it; that is conservative on a term 16x smaller than breathing.
EIGHT_SLEEP_POD6_AIRWAY_TARGET_WEIGHTS: dict[str, float] = {"upper_airway": 1.0}

# QoL-guard tier: no trial of any Pod 6 feature exists, so the tier is
# head_elevation_nightly's (mechanistic_or_self_experiment,
# respiratory_airway).
EIGHT_SLEEP_POD6_QOL_STUDY_QUALITY = "mechanistic_or_self_experiment"
EIGHT_SLEEP_POD6_QOL_CATEGORY = "respiratory_airway"

EIGHT_SLEEP_POD6_HR = 1.0
EIGHT_SLEEP_POD6_QOL_ANNUAL = 0.0

# Years the relief and the cost are counted over: the device life. Eight's
# warranty is 2 years (Standard plan) or 5 (Enhanced/Elite) while the plan is
# paid.
EIGHT_SLEEP_POD6_QOL_YEARS = 5.0

# Cost: one-time King price, list $2,999 (Eight Sleep press release,
# 2026-09-23). The member discount and US trade-in credit are shown only in
# the member shop, so the list price is modeled and the report gives the
# break-even price. The Autopilot plan carries over (help article updated
# 2026-09-23), so there is no subscription delta. The engine counts
# annual_cost x discount_factor(qol_years) (protocol_ground_up.modeled_total_cost),
# and discount_factor counts year 0 undiscounted, so this annual figure
# reproduces the one-time price exactly.
EIGHT_SLEEP_POD6_ONE_TIME_PRICE_USD = 2999.0
_POD6_DISCOUNT_RATE = 0.03  # COST_DISCOUNT_RATE; a test ties the two together
EIGHT_SLEEP_POD6_ANNUAL_COST = EIGHT_SLEEP_POD6_ONE_TIME_PRICE_USD / sum(
    (1.0 + _POD6_DISCOUNT_RATE) ** -t for t in range(int(EIGHT_SLEEP_POD6_QOL_YEARS))
)

# Sanity range for the protocol spec (total QALY), declared after the
# predeclared_ranges_v1.json freeze.
EIGHT_SLEEP_POD6_SANITY_RANGE: tuple[float, float] = (-0.001, 0.01)
