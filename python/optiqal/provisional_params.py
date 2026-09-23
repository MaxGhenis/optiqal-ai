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
