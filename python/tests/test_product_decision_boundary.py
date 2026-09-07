"""Product quantities must not enter the catalog optimizer as effect estimates."""

from unittest.mock import Mock

import pytest

import optiqal.analyzer as analyzer
from optiqal import AnalysisConfig, Decision, Profile
from optiqal.product_composition import (
    IngredientAmount,
    ProductComposition,
    ProductUse,
    UnsupportedProductChangeError,
    remove_products,
)


@pytest.fixture
def synthetic_change():
    products = tuple(
        ProductUse(
            ProductComposition(
                product_id,
                (IngredientAmount("ingredient_a", amount, "g"),),
                composition_complete=True,
                source="synthetic contract fixture",
            )
        )
        for product_id, amount in (("synthetic_single", "5"), ("synthetic_mix", "2.5"))
    )
    return remove_products(products, ("synthetic_single",))


@pytest.mark.parametrize("entrypoint", [analyzer.analyze, analyzer.evaluate_decisions])
@pytest.mark.parametrize("decision_type", ["add", "drop", "adjust"])
def test_product_change_is_rejected_before_any_simulation_or_ranking(
    monkeypatch, synthetic_change, entrypoint, decision_type
):
    single_simulation = Mock(side_effect=AssertionError("must not simulate"))
    catalog_simulation = Mock(side_effect=AssertionError("must not simulate"))
    optimizer = Mock(side_effect=AssertionError("must not optimize"))
    monkeypatch.setattr(analyzer, "_simulate_one", single_simulation)
    monkeypatch.setattr(analyzer, "simulate_catalog", catalog_simulation)
    monkeypatch.setattr(analyzer, "find_optimal_portfolio_with_costs", optimizer)
    config = AnalysisConfig(
        profile=Profile(
            age=40,
            sex="female",
            bmi_category="normal",
            smoking_status="never",
            has_diabetes=False,
        )
    )
    decisions = [
        Decision("add", "creatine_5g", "Catalog decision before product decision"),
        Decision(
            decision_type,
            "creatine_5g",
            "Synthetic product change",
            product_change=synthetic_change,
        ),
    ]
    with pytest.raises(UnsupportedProductChangeError) as exc:
        entrypoint(config=config, decisions=decisions)
    assert "dose_response_not_modeled" in exc.value.unsupported_reasons
    assert "product_effect_mapping_unavailable" in exc.value.unsupported_reasons
    assert exc.value.accounting["ingredients"][0]["full_withdrawal"] is False
    single_simulation.assert_not_called()
    catalog_simulation.assert_not_called()
    optimizer.assert_not_called()


def test_complete_withdrawal_still_requires_an_effect_model_mapping(synthetic_change):
    complete = remove_products(
        synthetic_change.before, ("synthetic_single", "synthetic_mix")
    )
    decision = Decision(
        "drop", "creatine_5g", "Synthetic removal", product_change=complete
    )
    config = AnalysisConfig(
        profile=Profile(
            age=40,
            sex="female",
            bmi_category="normal",
            smoking_status="never",
            has_diabetes=False,
        )
    )
    with pytest.raises(UnsupportedProductChangeError) as exc:
        analyzer.evaluate_decisions([decision], config)
    assert exc.value.accounting["ingredients"][0]["full_withdrawal"] is True
    assert exc.value.unsupported_reasons == ("product_effect_mapping_unavailable",)


def test_decision_requires_a_typed_product_change():
    with pytest.raises(ValueError, match="ProductChange"):
        Decision("drop", "creatine_5g", "Invalid raw composition", product_change={})
