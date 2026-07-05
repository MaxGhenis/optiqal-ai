"""
Formatted text output for analysis results.

Produces the same rich tables that the ad-hoc scripts generated,
but from structured AnalysisResult data.
"""

import math
from typing import Any, Callable, List, Mapping, Optional, Sequence

DAYS_PER_QALY = 365.25


def format_header(config) -> str:
    """Format analysis header with config summary."""
    lines = [
        "=" * 110,
        "OPTIQAL SUPPLEMENT STACK ANALYSIS",
        f"Profile: {config.profile.sex}, age {config.profile.age}, "
        f"BMI {config.profile.bmi_category}, smoking {config.profile.smoking_status}",
        f"WTP: ${config.wtp:,.0f}/QALY | Horizon: {config.horizon_years:.0f}yr | "
        f"Sims: {config.n_simulations:,}",
        f"Pub bias shrinkage: {config.pub_bias_shrinkage:.0%}",
        "=" * 110,
    ]
    return "\n".join(lines)


def format_item_table(item_results: List[dict]) -> str:
    """Ranked table of all items."""
    lines = [
        "",
        f"{'#':<3} {'Item':<30} {'Cat':<20} {'HR→adj':>10} "
        f"{'E[days]':>8} {'P(+)':>5} {'$/yr':>7} {'Gross $':>10}",
        "-" * 105,
    ]
    for i, r in enumerate(item_results, 1):
        lines.append(
            f"{i:<3} {r['name']:<30} {r['category']:<20} "
            f"{r['hr_observed']:.2f}→{r['hr_corrected']:.3f} "
            f"{r['days']:>+7.1f} {r['p_benefit']:>4.0%} "
            f"${r['annual_cost']:>6} ${r['gross_value']:>+9,.0f}"
        )
    return "\n".join(lines)


def format_portfolio_table(portfolio: List[dict]) -> str:
    """Greedy portfolio construction steps."""
    lines = [
        "",
        "=" * 110,
        "GREEDY PORTFOLIO (adding best marginal value, stopping when negative)",
        "=" * 110,
    ]
    for step in portfolio:
        lines.append(
            f"  {step['step']:>2}. {step['added_intervention']:<30} "
            f"+{step['marginal_qaly'] * 365.25:>5.1f}d  "
            f"${step.get('total_annual_cost', 0) - sum(0 for _ in []):>6}/yr  "
            f"marginal=${step['marginal_net_value']:>+8,.0f}"
        )

    if portfolio:
        last = portfolio[-1]
        total_days = last["total_qaly"] * 365.25
        total_cost = last["total_annual_cost"]
        lines.extend(
            [
                f"\n  --- STOPPED at {len(portfolio)} items ---",
                f"\n  Total E[days]: {total_days:.0f}",
                f"  Total cost: ${total_cost:,.0f}/yr",
            ]
        )

    return "\n".join(lines)


def format_excluded(
    item_results: List[dict],
    selected_ids: List[str],
) -> str:
    """Items that didn't make the portfolio."""
    selected_set = set(selected_ids)
    excluded = [r for r in item_results if r["id"] not in selected_set]

    lines = [
        "",
        "=" * 110,
        f"EXCLUDED ({len(excluded)} items)",
        "=" * 110,
    ]
    for r in excluded:
        lines.append(
            f"  {r['name']:<30} [{r['category']:<20}] "
            f"{r['days']:>+6.1f}d ${r['annual_cost']:>6}/yr "
            f"gross=${r['gross_value']:>+8,.0f}"
        )
    return "\n".join(lines)


def format_category_summary(
    item_results: List[dict],
    selected_ids: List[str],
) -> str:
    """By-category breakdown."""
    selected_set = set(selected_ids)
    categories = sorted(set(r["category"] for r in item_results))

    lines = [
        "",
        "=" * 110,
        "BY CATEGORY",
        "=" * 110,
    ]
    for cat in categories:
        in_cat = [r for r in item_results if r["category"] == cat]
        sel = [r for r in in_cat if r["id"] in selected_set]
        exc = [r for r in in_cat if r["id"] not in selected_set]
        lines.append(f"\n  {cat}: {len(sel)}/{len(in_cat)} selected")
        if sel:
            lines.append(f"    IN:  {', '.join(r['name'] for r in sel)}")
        if exc:
            lines.append(f"    OUT: {', '.join(r['name'] for r in exc)}")

    return "\n".join(lines)


def format_bundle_recommendations(bundles: List[dict]) -> str:
    """Which bundles to buy."""
    if not bundles:
        return ""

    lines = [
        "",
        "=" * 110,
        "BUNDLE RECOMMENDATIONS",
        "=" * 110,
    ]
    for b in bundles:
        verdict = "WORTH IT" if b["worth_it"] else "NOT WORTH IT"
        lines.extend(
            [
                f"\n  {b['bundle_name']} (${b['annual_cost']:.0f}/yr):",
                f"    Contains {b['n_selected']}/{b['n_total']} selected items: "
                f"{', '.join(b['selected_items'])}",
                f"    Combined value: ${b['combined_value']:,.0f} vs "
                f"cost ${b['total_cost']:,.0f}",
                f"    → {verdict} (net ${b['net_value']:>+,.0f})",
            ]
        )

    return "\n".join(lines)


def format_decision_table(decisions: List[dict]) -> str:
    """Decision recommendations table."""
    if not decisions:
        return ""

    lines = [
        "",
        "=" * 110,
        "DECISION ANALYSIS",
        "=" * 110,
        f"\n{'Decision':<55} {'E[days]':>8} {'95% CI':>18} "
        f"{'P(+)':>6} {'$/yr':>7} {'Net $':>10}",
        "-" * 110,
    ]
    for r in decisions:
        ci = f"[{r['ci_low']:+.0f}, {r['ci_high']:+.0f}]"
        cost = r["annual_cost"]
        cost_str = f"${cost:+.0f}" if cost != 0 else "$0"
        lines.append(
            f"{r['label']:<55} {r['days']:>+7.1f} {ci:>18} "
            f"{r['p_benefit']:>5.0%} {cost_str:>7} ${r['net_value']:>+9,.0f}"
        )

    lines.extend(
        [
            "",
            "RECOMMENDATION SUMMARY",
            "=" * 110,
        ]
    )
    for r in decisions:
        lines.append(f"  {r['verdict']:>8}: {r['label']}")

    return "\n".join(lines)


def format_full_report(result) -> str:
    """Combine all sections into a complete report."""
    sections = [
        format_header(result.config),
        format_item_table(result.item_results),
        format_portfolio_table(result.portfolio),
        format_excluded(result.item_results, result.selected_ids),
        format_category_summary(result.item_results, result.selected_ids),
        format_bundle_recommendations(result.bundle_recommendations),
    ]

    if result.decisions:
        sections.append(format_decision_table(result.decisions))

    return "\n".join(sections)


def round_cost_per_qaly(value: Optional[float]) -> Optional[int]:
    """Round cost-per-QALY values when finite, else return None."""
    if value is None or not math.isfinite(value):
        return None
    return round(value)


def serialize_ranked_steps(
    ranking: Sequence[Mapping[str, Any]],
    *,
    item_name_by_id: Mapping[str, str],
    include_cost_details: bool = False,
) -> List[dict[str, Any]]:
    """Serialize ranked intervention steps for JSON/report output."""
    rows: List[dict[str, Any]] = []
    for step in ranking:
        item_id = step["added_intervention"]
        row = {
            "step": step["step"],
            "id": item_id,
            "name": item_name_by_id.get(item_id, item_id),
            "marginal_qaly": round(step["marginal_qaly"], 4),
            "marginal_days": round(step["marginal_qaly"] * DAYS_PER_QALY, 1),
            "marginal_cost_per_qaly": round_cost_per_qaly(
                step.get("marginal_cost_per_qaly")
            ),
            "marginal_interaction_days": round(
                step.get("marginal_interaction_qaly", 0) * DAYS_PER_QALY, 1
            ),
            "cumulative_days": round(step["total_qaly"] * DAYS_PER_QALY, 1),
            "total_annual_cost": round(step["total_annual_cost"]),
        }
        if include_cost_details:
            row["interaction_penalty_days"] = round(
                step.get("interaction_penalty_qaly", 0) * DAYS_PER_QALY, 1
            )
            row["marginal_cost_value"] = round(step.get("marginal_cost_value", 0))
            row["total_cost_value"] = round(step.get("total_cost_value", 0))
        rows.append(row)
    return rows


def serialize_item_results(
    item_results: Sequence[Mapping[str, Any]],
    *,
    effective_results_by_id: Mapping[str, Mapping[str, Any]],
    catalog_entries: Mapping[str, Any],
    selected_ids: Sequence[str],
    category_labels: Mapping[str, str],
    status_labels: Mapping[str, str],
    evidence_confidence_for_entry: Callable[[Any], str],
    row_enricher: Optional[Callable[[dict[str, Any]], None]] = None,
) -> List[dict[str, Any]]:
    """Serialize intervention results for JSON/report output."""
    rows: List[dict[str, Any]] = []
    selected_set = set(selected_ids)

    for raw in item_results:
        result = effective_results_by_id[raw["id"]]
        entry = catalog_entries[result["id"]]
        category = entry.category
        row = {
            "id": result["id"],
            "name": entry.name,
            "category": category,
            "category_label": category_labels.get(category, category),
            "status": status_labels.get(category, category),
            "hr_observed": entry.hr_observed,
            "hr_corrected": round(result["hr_corrected"], 4),
            "days": round(result["days"], 1),
            "p_benefit": round(result["p_benefit"], 2),
            "p_harm": round(result["p_harm"], 2),
            "annual_cost": entry.annual_cost,
            "gross_value": round(result["gross_value"]),
            "harm_qaly": round(result.get("harm_qaly", 0), 4),
            "direct_harm_qaly": round(result.get("direct_harm_qaly", 0), 4),
            "interaction_harm_qaly": round(result.get("interaction_harm_qaly", 0), 4),
            "raw_qol_qaly": round(result.get("raw_qol_qaly", 0), 4),
            "qol_annual": entry.qol_annual,
            "qol_qaly": round(result.get("qol_qaly", 0), 4),
            "raw_sleep_qol_annual": round(result.get("raw_sleep_qol_annual", 0), 6),
            "sleep_qol_annual": round(result.get("sleep_qol_annual", 0), 6),
            "raw_sleep_qol_qaly": round(result.get("raw_sleep_qol_qaly", 0), 4),
            "sleep_qol_qaly": round(result.get("sleep_qol_qaly", 0), 4),
            "evidence_discount_qaly": round(result.get("evidence_discount_qaly", 0), 4),
            "evidence_quality": getattr(entry, "evidence_quality", "moderate"),
            "evidence_effect_multiplier": round(
                result.get("evidence_effect_multiplier", 1.0), 4
            ),
            "component_breakdown": {
                key: round(value, 4)
                for key, value in result.get("component_breakdown", {}).items()
            },
            "top_positive_component": result.get("top_positive_component"),
            "top_negative_component": result.get("top_negative_component"),
            "airway_effect_multiplier": (
                round(result.get("airway_effect_multiplier", 1), 4)
                if result.get("airway_effect_multiplier") is not None
                else None
            ),
            "sleep_mortality_relief_fraction": round(
                result.get("sleep_mortality_relief_fraction", 0), 4
            ),
            "sleep_mortality_hr_multiplier": round(
                result.get("sleep_mortality_hr_multiplier", 1), 6
            ),
            "evidence": evidence_confidence_for_entry(entry),
            "notes": entry.notes,
            "sources": list(entry.sources) if entry.sources else [],
            "in_portfolio": result["id"] in selected_set,
            "cost_per_qaly": round_cost_per_qaly(result.get("cost_per_qaly")),
            "qaly_source": result.get("qaly_source", "catalog"),
            "catalog_days": round(result.get("catalog_days"), 1)
            if result.get("catalog_days") is not None
            else None,
            "range_low_qaly": result.get("range_low_qaly"),
            "range_high_qaly": result.get("range_high_qaly"),
            "within_range": result.get("within_range"),
            "ground_up_rationale": result.get("ground_up_rationale"),
            "ground_up_personalization": result.get("ground_up_personalization"),
            "ground_up_sources": result.get("ground_up_sources", []),
        }
        if row_enricher is not None:
            row_enricher(row)
        rows.append(row)

    rows.sort(key=lambda row: row["gross_value"], reverse=True)
    return rows


def serialize_bundle_recommendations(
    bundle_recommendations: Sequence[Mapping[str, Any]],
    *,
    bundles_by_id: Mapping[str, Any],
) -> List[dict[str, Any]]:
    """Serialize bundle recommendation rows for JSON/report output."""
    rows: List[dict[str, Any]] = []
    for recommendation in bundle_recommendations:
        bundle_id = recommendation["bundle_id"]
        bundle_def = bundles_by_id[bundle_id]
        rows.append(
            {
                "id": bundle_id,
                "name": recommendation["bundle_name"],
                "annual_cost": recommendation["annual_cost"],
                "monthly_cost": round(recommendation["annual_cost"] / 12),
                "items": list(bundle_def.item_ids),
                "selected_items": recommendation["selected_items"],
                "n_selected": recommendation["n_selected"],
                "n_total": recommendation["n_total"],
                "net_value": round(recommendation["net_value"]),
                "worth_it": recommendation["worth_it"],
            }
        )
    return rows


def serialize_choice_evaluation(
    raw_choice: Mapping[str, Any],
    *,
    product_ids_for_stack: Optional[Callable[[Sequence[str]], Sequence[str]]] = None,
    item_summary_for_id: Optional[Callable[[str], Mapping[str, Any]]] = None,
) -> dict[str, Any]:
    """Serialize evaluate_choice_set output for JSON/report output."""
    baseline = dict(raw_choice["baseline"])
    if product_ids_for_stack is not None:
        baseline["product_ids"] = list(product_ids_for_stack(baseline["item_ids"]))

    options: List[dict[str, Any]] = []
    for row in raw_choice["options"]:
        stack = dict(row["stack"])
        if product_ids_for_stack is not None:
            stack["product_ids"] = list(product_ids_for_stack(stack["item_ids"]))

        option = {
            "id": row["id"],
            "label": row["label"],
            "added_item_ids": row["added_item_ids"],
            "marginal_qaly": row["marginal_qaly"],
            "marginal_days": row["marginal_days"],
            "marginal_annual_cost": row["marginal_annual_cost"],
            "marginal_cost_value": row["marginal_cost_value"],
            "marginal_cost_per_qaly": row["marginal_cost_per_qaly"],
            "stack": stack,
        }
        if item_summary_for_id is not None:
            option["added_items"] = [
                dict(item_summary_for_id(item_id)) for item_id in row["added_item_ids"]
            ]
        options.append(option)

    return {
        "baseline": baseline,
        "options": options,
    }


def serialize_frontier_evaluation(
    raw_frontier: Mapping[str, Any],
    *,
    item_name_by_id: Mapping[str, str],
    product_ids_for_stack: Optional[Callable[[Sequence[str]], Sequence[str]]] = None,
) -> dict[str, Any]:
    """Serialize evaluate_frontier_state output for JSON/report output."""
    baseline = dict(raw_frontier["baseline"])
    if product_ids_for_stack is not None:
        baseline["product_ids"] = list(product_ids_for_stack(baseline["item_ids"]))
    return {
        "baseline": baseline,
        "steps": serialize_ranked_steps(
            raw_frontier["steps"],
            item_name_by_id=item_name_by_id,
        ),
    }


def serialize_decision_state_evaluations(
    raw_states: Mapping[str, Mapping[str, Any]],
    *,
    item_name_by_id: Mapping[str, str],
    product_ids_for_stack: Optional[Callable[[Sequence[str]], Sequence[str]]] = None,
    item_summary_for_id: Optional[Callable[[str], Mapping[str, Any]]] = None,
) -> dict[str, Any]:
    """Serialize declarative decision-state evaluations for JSON/report output."""
    serialized: dict[str, Any] = {}
    for state_id, state in raw_states.items():
        kind = state["kind"]
        if kind == "frontier":
            evaluation = serialize_frontier_evaluation(
                state["evaluation"],
                item_name_by_id=item_name_by_id,
                product_ids_for_stack=product_ids_for_stack,
            )
        elif kind == "choice":
            evaluation = serialize_choice_evaluation(
                state["evaluation"],
                product_ids_for_stack=product_ids_for_stack,
                item_summary_for_id=item_summary_for_id,
            )
        else:
            raise ValueError(f"Unknown decision state kind: {kind}")

        serialized[state_id] = {
            "label": state["label"],
            "description": state["description"],
            **evaluation,
        }
    return serialized


def serialize_decision_sequence(
    steps: Sequence[Any],
) -> List[dict[str, Any]]:
    """Serialize declarative decision-sequence steps for JSON/report output."""
    rows: List[dict[str, Any]] = []
    for step in steps:
        row = {
            "step": step.step,
            "id": step.id,
            "label": step.label,
        }
        if step.state_id is not None:
            row["state_id"] = step.state_id
        if step.preferred_state_id is not None:
            row["preferred_state_id"] = step.preferred_state_id
        if step.alternative_state_id is not None:
            row["alternative_state_id"] = step.alternative_state_id
        rows.append(row)
    return rows
