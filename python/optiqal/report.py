"""
Formatted text output for analysis results.

Produces the same rich tables that the ad-hoc scripts generated,
but from structured AnalysisResult data.
"""

from typing import List, Optional


def format_header(config) -> str:
    """Format analysis header with config summary."""
    lines = [
        "=" * 110,
        "OPTIQAL SUPPLEMENT STACK ANALYSIS",
        f"Profile: {config.profile.sex}, age {config.profile.age}, "
        f"BMI {config.profile.bmi_category}, smoking {config.profile.smoking_status}",
        f"WTP: ${config.wtp:,.0f}/QALY | Horizon: {config.horizon_years:.0f}yr | "
        f"Sims: {config.n_simulations:,}",
        f"Pub bias shrinkage: {config.pub_bias_shrinkage:.0%} | "
        f"Complexity: {config.complexity_cost_per_item}/yr after "
        f"{config.complexity_free_slots} items",
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
        dr = step["diminishing_returns_factor"]
        cp = step["complexity_penalty"]
        dr_s = f" DR:{dr:.2f}" if dr < 1.0 else ""
        cp_s = f" complexity:-{cp * 365.25:.0f}d" if cp > 0 else ""
        lines.append(
            f"  {step['step']:>2}. {step['added_intervention']:<30} "
            f"+{step['marginal_qaly'] * 365.25:>5.1f}d  "
            f"${step.get('total_annual_cost', 0) - sum(0 for _ in []):>6}/yr  "
            f"marginal=${step['marginal_net_value']:>+8,.0f}{dr_s}{cp_s}"
        )

    if portfolio:
        last = portfolio[-1]
        total_days = last["total_qaly"] * 365.25
        total_cost = last["total_annual_cost"]
        lines.extend([
            f"\n  --- STOPPED at {len(portfolio)} items ---",
            f"\n  Total E[days]: {total_days:.0f}",
            f"  Total cost: ${total_cost:,.0f}/yr",
        ])

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
        lines.extend([
            f"\n  {b['bundle_name']} (${b['annual_cost']:.0f}/yr):",
            f"    Contains {b['n_selected']}/{b['n_total']} selected items: "
            f"{', '.join(b['selected_items'])}",
            f"    Combined value: ${b['combined_value']:,.0f} vs "
            f"cost ${b['total_cost']:,.0f}",
            f"    → {verdict} (net ${b['net_value']:>+,.0f})",
        ])

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

    lines.extend([
        "",
        "RECOMMENDATION SUMMARY",
        "=" * 110,
    ])
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
