"""One evidence rule for general QoL residuals of bedtime sleep interventions.

The component-relief leg already carries improvements in sleep outcomes. An
additional general QoL benefit needs a separate evidence base; it cannot reuse
those same outcomes. The authored mode keeps the original values available for
sensitivity analysis without mutating catalog or protocol specifications.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

ResidualMode = Literal["evidence_rule", "authored"]

# Adjudicated bedtime items whose evidence supports sleep outcomes only.
# Magnesium's non-sleep outcomes were null in Schuster 2025 (WF2 B3 decision).
SLEEP_ONLY_RESIDUAL_ITEMS = frozenset(
    {
        "trazodone_50mg",
        "doxepin_3mg",
        "daridorexant_25mg",
        "lemborexant_5mg",
        "suvorexant_10mg",
        "melatonin_300mcg",
        "magnesium_200",
        "glycine_2g",
        "apigenin_50",
        "l_theanine_200_bedtime",
    }
)

# Existing non-bedtime interventions are outside the WF2 B3 residual review.
# This frozen scope list is not a claim that their residuals have independent
# evidence. New sleep interventions do not inherit this exclusion.
EXISTING_NON_BEDTIME_SLEEP_RESIDUAL_ITEMS = frozenset(
    {
        "nasacort_nightly",
        "nasal_strips_nightly",
        "humidifier_nightly",
        "mouth_tape_nightly",
        "head_elevation_nightly",
        "apap_nightly",
        "oral_appliance_custom",
        "nac_1200",
        # The ground-up obesity model adds sleep relief to an otherwise
        # metabolic intervention with distinct weight/function QoL evidence.
        "semaglutide",
    }
)


def apply_sleep_residual_rule(
    item_id: str,
    authored_qol_annual: float,
    mode: ResidualMode = "evidence_rule",
    *,
    sleep_component_relief: Mapping[str, float] | None = None,
) -> float:
    """Remove duplicate sleep benefit while retaining separately authored harms.

    Ashwagandha retains its stress/anxiety residual, which must still receive
    the supplement_industry_rct / mood_stress evidence guard at evaluation.
    A new item with a sleep-component claim defaults to no general residual.
    Existing non-bedtime items retain their current treatment pending a
    separate evidence review.
    """
    if mode not in ("evidence_rule", "authored"):
        raise ValueError(f"Unknown sleep residual mode: {mode}")
    if mode == "authored" or authored_qol_annual <= 0:
        return authored_qol_annual
    if item_id == "ashwagandha_600":
        return authored_qol_annual
    if item_id in SLEEP_ONLY_RESIDUAL_ITEMS or (
        sleep_component_relief
        and item_id not in EXISTING_NON_BEDTIME_SLEEP_RESIDUAL_ITEMS
    ):
        return 0.0
    return authored_qol_annual
