"""Executable synthetic examples are the integration contract's worked cases."""

import json
import runpy
from pathlib import Path


def test_synthetic_demo_reports_keep_remove_replace_and_unknown(capsys):
    demo = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "scripts/product_composition_demo.py")
    )
    assert demo["main"]() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["data_source"].startswith("Synthetic composition fixture")
    expected = {
        "keep": ("unchanged", "7500", False),
        "remove_one": ("reduced", "2500", False),
        "remove_all": ("withdrawn", "0", True),
        "replace_one": ("reduced", "3500", False),
        "retain_unknown_amount": ("unknown", None, False),
    }
    assert set(payload["examples"]) == set(expected)
    for name, (kind, after_amount, withdrawn) in expected.items():
        report = payload["examples"][name]
        row = next(
            row
            for row in report["ingredients"]
            if row["ingredient_id"] == "ingredient_a"
        )
        assert row["change"] == kind
        assert row["full_withdrawal"] is withdrawn
        total = row["after"]["total_per_day"]
        assert (total["amount"] if total else None) == after_amount
        assert report["ranking_eligibility"]["eligible"] is False
        assert (
            "product_effect_mapping_unavailable"
            in report["ranking_eligibility"]["unsupported_reasons"]
        )
