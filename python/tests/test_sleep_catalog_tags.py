"""Sleep interaction tags identify the evidence-backed contributors."""

import pytest

from optiqal.catalog import CATALOG, SEDATION_STACK_RULE
from optiqal.profile import Profile
from optiqal.stack_interactions import expected_stack_interaction_qaly

HYPNOTIC_IDS = frozenset(
    {
        "trazodone_50mg",
        "doxepin_3mg",
        "daridorexant_25mg",
        "lemborexant_5mg",
        "suvorexant_10mg",
    }
)
SUPPLEMENT_IDS = (
    "melatonin_300mcg",
    "glycine_2g",
    "ashwagandha_600",
    "apigenin_50",
)


def test_only_exclusive_pharmacologic_hypnotics_have_sedating_tag():
    tagged = {
        item_id
        for item_id, entry in CATALOG.items()
        if "sedating" in entry.interaction_tags
    }
    assert tagged == HYPNOTIC_IDS
    assert all(CATALOG[item_id].exclusive_group == "insomnia_rx" for item_id in tagged)
    assert "unsourced judgment" in SEDATION_STACK_RULE.description.lower()
    for item_id in ("melatonin_300mcg", "glycine_2g"):
        assert SEDATION_STACK_RULE not in CATALOG[item_id].interaction_rules


@pytest.mark.parametrize("hypnotic", [None, *sorted(HYPNOTIC_IDS)])
def test_sedation_rule_cannot_fire_in_feasible_sleep_stack(hypnotic):
    item_ids = list(SUPPLEMENT_IDS)
    if hypnotic is not None:
        item_ids.append(hypnotic)
    _, details = expected_stack_interaction_qaly(
        item_ids,
        catalog_entries=CATALOG,
        profile=Profile(
            age=39,
            sex="male",
            bmi_category="normal",
            smoking_status="never",
            has_diabetes=False,
        ),
    )
    assert all(detail["id"] != "sedation_stack" for detail in details)


def test_sleep_supplements_do_not_claim_unsupported_non_sleep_clusters():
    for item_id in ("ashwagandha_600", "apigenin_50"):
        assert "anti_inflammatory" not in CATALOG[item_id].benefit_tags
    assert "senolytic_support" not in CATALOG["apigenin_50"].benefit_tags


def test_nac_quality_relief_has_its_matching_sleep_tag():
    entry = CATALOG["nac_1200"]
    assert entry.sleep_component_relief["quality"] > 0
    assert "sleep_quality_support" in entry.benefit_tags
