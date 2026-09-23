"""Exhaustive search over the sleep-domain part of the personal protocol.

The greedy optimizer in :mod:`optiqal.protocol_ground_up` walks one add, drop or
swap at a time and can stop at a local optimum. The sleep stack is small enough
to search completely instead: every feasible subset of the sleep-domain items
(at most one item per exclusive group) is evaluated while every other current
item is held fixed.

Each state is valued exactly as :func:`protocol_ground_up.evaluate_protocol_state`
values it: the paired latent draws of every item in the state, plus the shared
stack interaction computed once on the full id list. The fast path below
precomputes the draws of the held-fixed items once and adds the subset's draws
and ``expected_stack_interaction_qaly`` on the full id list, so the only
per-state work is the interaction call. ``tests/test_sleep_stack.py`` checks the
fast path against ``evaluate_protocol_state`` to 1e-9.

Costs are the pipeline's ``modeled_total_cost`` (cash price over the item's
active years) unless the caller passes ``cost_overrides``, which replaces an
item's modeled total cost. That is how a caller runs an out-of-pocket
perspective; this module does not decide which items any insurer covers.
"""

from __future__ import annotations

import itertools
import math
from typing import Any, Mapping, Sequence

import numpy as np

from . import protocol_ground_up as pgu
from .catalog import CATALOG
from .stack_interactions import expected_stack_interaction_qaly

SLEEP_DOMAIN_EXCLUSIVE_GROUPS = frozenset({"insomnia_rx", "osa_primary_therapy"})
SLEEP_DOMAIN_TIMES_OF_DAY = frozenset({"before_bed", "bedtime"})
SLEEP_STACK_WTPS: tuple[int, ...] = (50_000, 100_000, 150_000, 200_000)
SLEEP_STACK_TOP_N = 25
SLEEP_STACK_P_BEST_TOP_K = 50
SLEEP_STACK_CI_PERCENTILES = (10.0, 90.0)
# A guard, not a model parameter: 2**21 states would take tens of minutes.
SLEEP_STACK_MAX_STATES = 1_000_000
DAYS_PER_YEAR = 365.25


def _exclusive_group(item_id: str) -> str | None:
    entry = CATALOG.get(item_id)
    return entry.exclusive_group if entry is not None else None


def _times_of_day(item: Mapping[str, Any]) -> list[str]:
    raw = item.get("time_of_day") or ""
    return [part.strip() for part in str(raw).split(",") if part.strip()]


def sleep_domain_reasons(item: Mapping[str, Any]) -> list[str]:
    """Why a protocol item counts as sleep-domain; empty when it does not.

    An item is sleep-domain when its catalog entry claims sleep-component
    relief, when it belongs to a sleep exclusive group (insomnia prescription,
    primary OSA therapy), or when the protocol schedules it before bed.
    """
    entry = CATALOG.get(str(item.get("id", "")))
    reasons: list[str] = []
    if entry is not None and entry.sleep_component_relief:
        reasons.append("sleep_component_relief")
    if entry is not None and entry.exclusive_group in SLEEP_DOMAIN_EXCLUSIVE_GROUPS:
        reasons.append(f"exclusive_group:{entry.exclusive_group}")
    for time_of_day in _times_of_day(item):
        if time_of_day in SLEEP_DOMAIN_TIMES_OF_DAY:
            reasons.append(f"time_of_day:{time_of_day}")
    return reasons


def _is_candidate(item: Mapping[str, Any]) -> bool:
    return str(
        item.get("status", "")
    ) in pgu.CURRENT_STACK_STATUSES or pgu.is_actionable_item(dict(item))


def select_sleep_stack_universe(
    protocol_items: Sequence[Mapping[str, Any]],
    estimates_by_id: Mapping[str, Mapping[str, Any]],
    *,
    baseline: Mapping[str, Any] | None = None,
    universe_ids: Sequence[str] | None = None,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Return (universe ids in protocol order, excluded sleep-domain items).

    The default universe is every current or actionable sleep-domain item that
    can be taken or stopped on its own. An item is excluded when the physical
    product that supplies it also supplies another tracked item (a bundle
    capsule or powder), when it has no estimate, or when a held-fixed current
    item already occupies its exclusive group.

    ``universe_ids`` overrides the default; each id must be a current or
    actionable protocol item with an estimate.
    """
    by_id = {str(item["id"]): item for item in protocol_items}
    candidate_ids = [str(item["id"]) for item in protocol_items if _is_candidate(item)]
    current_ids = pgu.active_state_item_ids(list(protocol_items))
    siblings_by_id = pgu.co_packaged_item_ids(dict(baseline or {}), candidate_ids)
    supplying = pgu.resolve_supplying_products(dict(baseline or {}), candidate_ids)

    excluded: list[dict[str, Any]] = []

    def exclude(item_id: str, reason: str) -> None:
        item = by_id[item_id]
        excluded.append(
            {
                "id": item_id,
                "name": str(
                    (estimates_by_id.get(item_id) or {}).get("name")
                    or item.get("name")
                    or item_id
                ),
                "status": item.get("status"),
                "sleep_domain_reasons": sleep_domain_reasons(item),
                "reason": reason,
            }
        )

    if universe_ids is not None:
        chosen = pgu._ordered_state_ids([str(item_id) for item_id in universe_ids])
        for item_id in chosen:
            if item_id not in by_id:
                raise ValueError(f"universe id {item_id!r} is not a protocol item")
            if not _is_candidate(by_id[item_id]):
                raise ValueError(
                    f"universe id {item_id!r} is neither current nor actionable"
                )
            if item_id not in estimates_by_id:
                raise ValueError(f"universe id {item_id!r} has no estimate")
        chosen_set = set(chosen)
        universe = [item_id for item_id in candidate_ids if item_id in chosen_set]
        for item_id in candidate_ids:
            if item_id not in chosen_set and sleep_domain_reasons(by_id[item_id]):
                exclude(item_id, "left out of the caller-supplied universe_ids")
    else:
        universe = []
        for item_id in candidate_ids:
            if not sleep_domain_reasons(by_id[item_id]):
                continue
            if item_id not in estimates_by_id:
                exclude(item_id, "no estimate for this item")
                continue
            siblings = siblings_by_id.get(item_id) or []
            if siblings:
                exclude(
                    item_id,
                    f"supplied through {supplying.get(item_id)} together with "
                    f"{', '.join(siblings)}; not separably droppable or addable",
                )
                continue
            universe.append(item_id)

    # A held-fixed current item that occupies an exclusive group blocks every
    # universe member of that group (at most one item per group).
    universe_set = set(universe)
    fixed_groups = {
        _exclusive_group(item_id): item_id
        for item_id in current_ids
        if item_id not in universe_set and _exclusive_group(item_id)
    }
    kept: list[str] = []
    for item_id in universe:
        group = _exclusive_group(item_id)
        if group and group in fixed_groups:
            exclude(
                item_id,
                f"exclusive group {group} is occupied by held-fixed item "
                f"{fixed_groups[group]}",
            )
            continue
        kept.append(item_id)
    return kept, excluded


class SleepStackEvaluator:
    """Fast, exact evaluation of protocol states that differ only in the universe.

    ``base_ids`` are held fixed in every state. A state is ``base_ids`` plus a
    subset of ``universe_ids`` (given as indices into ``universe_ids``).
    """

    def __init__(
        self,
        base_ids: Sequence[str],
        universe_ids: Sequence[str],
        estimates_by_id: Mapping[str, dict[str, Any]],
        specs: Mapping[str, pgu.StackSpec],
        context: pgu.ProtocolContext,
        *,
        cost_overrides: Mapping[str, float] | None = None,
    ) -> None:
        self.base_ids = list(base_ids)
        self.universe_ids = list(universe_ids)
        overlap = set(self.base_ids) & set(self.universe_ids)
        if overlap:
            raise ValueError(f"ids both held fixed and searched: {sorted(overlap)}")
        self.profile = context.profile
        all_ids = self.base_ids + self.universe_ids
        missing = [item_id for item_id in all_ids if item_id not in estimates_by_id]
        if missing:
            raise ValueError(f"no estimate for {missing}")
        overrides = dict(cost_overrides or {})
        unknown = sorted(set(overrides) - set(estimates_by_id))
        if unknown:
            raise ValueError(f"cost_overrides for unknown items: {unknown}")
        self.active_years = pgu._state_item_active_years(all_ids, dict(specs))
        self.item_qalys = pgu._state_item_qalys(all_ids, dict(estimates_by_id))
        self.draws = {
            item_id: pgu.latent_protocol_item_draws(item_id, estimates_by_id[item_id])
            for item_id in all_ids
        }
        self.cost = {
            item_id: float(
                overrides[item_id]
                if item_id in overrides
                else (estimates_by_id[item_id].get("modeled_total_cost") or 0.0)
            )
            for item_id in all_ids
        }
        self.base_draws = np.zeros(pgu.N_SIMULATIONS)
        for item_id in self.base_ids:
            self.base_draws += self.draws[item_id]
        self.base_mean = float(np.mean(self.base_draws))
        self.base_cost = sum(self.cost[item_id] for item_id in self.base_ids)
        self.universe_mean = [
            float(np.mean(self.draws[item_id])) for item_id in self.universe_ids
        ]
        self.universe_cost = [self.cost[item_id] for item_id in self.universe_ids]

    def state_ids(self, subset: Sequence[int]) -> list[str]:
        return self.base_ids + [self.universe_ids[index] for index in subset]

    def interaction_qaly(self, subset: Sequence[int]) -> float:
        ids = self.state_ids(subset)
        value, _ = expected_stack_interaction_qaly(
            item_ids=ids,
            catalog_entries=CATALOG,
            profile=self.profile,
            qaly_discount_rate=pgu.QALY_DISCOUNT_RATE,
            item_active_years={
                item_id: self.active_years[item_id]
                for item_id in ids
                if item_id in self.active_years
            },
            item_qalys={
                item_id: self.item_qalys[item_id]
                for item_id in ids
                if item_id in self.item_qalys
            },
        )
        return float(value)

    def mean_qaly(self, subset: Sequence[int]) -> float:
        return (
            self.base_mean
            + sum(self.universe_mean[index] for index in subset)
            + self.interaction_qaly(subset)
        )

    def total_cost(self, subset: Sequence[int]) -> float:
        return self.base_cost + sum(self.universe_cost[index] for index in subset)

    def state_draws(self, subset: Sequence[int]) -> np.ndarray:
        draws = self.base_draws.copy()
        for index in subset:
            draws += self.draws[self.universe_ids[index]]
        return draws + self.interaction_qaly(subset)


def _group_slots(universe_ids: Sequence[str]) -> list[list[tuple[int, ...]]]:
    """One slot per exclusive group and per ungrouped item, in universe order."""
    slots: list[list[tuple[int, ...]]] = []
    group_slot: dict[str, int] = {}
    for index, item_id in enumerate(universe_ids):
        group = _exclusive_group(item_id)
        if group:
            if group not in group_slot:
                group_slot[group] = len(slots)
                slots.append([()])
            slots[group_slot[group]].append((index,))
        else:
            slots.append([(), (index,)])
    return slots


def expected_state_count(universe_ids: Sequence[str]) -> int:
    """prod(|group| + 1) * 2**ungrouped for the universe."""
    return math.prod(len(slot) for slot in _group_slots(universe_ids))


def enumerate_feasible_subsets(universe_ids: Sequence[str]) -> list[tuple[int, ...]]:
    """Every subset of the universe with at most one item per exclusive group."""
    subsets: list[tuple[int, ...]] = []
    for choice in itertools.product(*_group_slots(universe_ids)):
        subsets.append(tuple(sorted(index for part in choice for index in part)))
    return subsets


def _feasible(subset: Sequence[int], universe_ids: Sequence[str]) -> bool:
    groups = [
        group
        for group in (_exclusive_group(universe_ids[index]) for index in subset)
        if group
    ]
    return len(groups) == len(set(groups))


def _single_flip(
    subset: Sequence[int], index: int, universe_ids: Sequence[str]
) -> tuple[tuple[int, ...], str, int | None]:
    """The neighbour that toggles one universe item.

    Returns (neighbour subset, action, swapped-out index). Adding an item whose
    exclusive group is already filled swaps out the current member.
    """
    members = set(subset)
    if index in members:
        return tuple(sorted(members - {index})), "drop", None
    group = _exclusive_group(universe_ids[index])
    swapped = None
    if group:
        for other in members:
            if _exclusive_group(universe_ids[other]) == group:
                swapped = other
        if swapped is not None:
            members.discard(swapped)
    members.add(index)
    return tuple(sorted(members)), "add" if swapped is None else "swap", swapped


def _round(value: float, digits: int) -> float:
    return round(float(value), digits)


def _ci80(delta_draws: np.ndarray) -> list[float]:
    low, high = SLEEP_STACK_CI_PERCENTILES
    return [
        _round(np.percentile(delta_draws, low), 5),
        _round(np.percentile(delta_draws, high), 5),
    ]


def optimize_sleep_stack(
    protocol_items: Sequence[Mapping[str, Any]],
    estimates_by_id: Mapping[str, dict[str, Any]],
    specs: Mapping[str, pgu.StackSpec],
    context: pgu.ProtocolContext,
    *,
    universe_ids: Sequence[str] | None = None,
    wtps: Sequence[float] = SLEEP_STACK_WTPS,
    cost_overrides: Mapping[str, float] | None = None,
    top_n: int = SLEEP_STACK_TOP_N,
    p_best_top_k: int = SLEEP_STACK_P_BEST_TOP_K,
    baseline: Mapping[str, Any] | None = None,
    perspective: str | None = None,
) -> dict[str, Any]:
    """Evaluate every feasible sleep stack and report the optimum per objective.

    ``baseline`` supplies health.db's item-to-product mapping for the
    separability check (``resolve_supplying_products``); without it the check
    falls back to catalog bundle ids alone. ``perspective`` only labels the
    payload; it defaults to ``"cash"`` without overrides and ``"custom_costs"``
    with them.
    """
    if top_n < 1 or p_best_top_k < 1:
        raise ValueError("top_n and p_best_top_k must be positive")
    universe, excluded = select_sleep_stack_universe(
        protocol_items,
        estimates_by_id,
        baseline=baseline,
        universe_ids=universe_ids,
    )
    by_id = {str(item["id"]): item for item in protocol_items}
    current_ids = pgu.active_state_item_ids(list(protocol_items))
    universe_set = set(universe)
    base_ids = [item_id for item_id in current_ids if item_id not in universe_set]
    current_members = set(current_ids)
    current_subset = tuple(
        index for index, item_id in enumerate(universe) if item_id in current_members
    )

    n_states = expected_state_count(universe)
    if n_states > SLEEP_STACK_MAX_STATES:
        raise ValueError(
            f"{n_states} sleep-stack states exceed the {SLEEP_STACK_MAX_STATES} guard"
        )
    evaluator = SleepStackEvaluator(
        base_ids,
        universe,
        estimates_by_id,
        specs,
        context,
        cost_overrides=cost_overrides,
    )
    subsets = enumerate_feasible_subsets(universe)
    qaly = np.array([evaluator.mean_qaly(subset) for subset in subsets])
    cost = np.array([evaluator.total_cost(subset) for subset in subsets])

    names = {
        item_id: str(estimates_by_id[item_id].get("name") or item_id)
        for item_id in universe
    }
    current_qaly = evaluator.mean_qaly(current_subset)
    current_cost = evaluator.total_cost(current_subset)
    current_draws = evaluator.state_draws(current_subset)
    draw_cache: dict[tuple[int, ...], np.ndarray] = {current_subset: current_draws}

    def draws_for(subset: tuple[int, ...]) -> np.ndarray:
        if subset not in draw_cache:
            draw_cache[subset] = evaluator.state_draws(subset)
        return draw_cache[subset]

    def ids_of(subset: Sequence[int]) -> list[str]:
        return [universe[index] for index in subset]

    def rank_order(objective: np.ndarray) -> list[int]:
        return sorted(
            range(len(subsets)),
            key=lambda s: (-objective[s], cost[s], len(subsets[s]), ids_of(subsets[s])),
        )

    def state_row(position: int, rank: int, wtp: float | None) -> dict[str, Any]:
        subset = subsets[position]
        delta_draws = draws_for(subset) - current_draws
        delta_qaly = float(qaly[position] - current_qaly)
        delta_cost = float(cost[position] - current_cost)
        row = {
            "rank": rank,
            "item_ids": ids_of(subset),
            "names": [names[item_id] for item_id in ids_of(subset)],
            "n_items": len(subset),
            "state_qaly": _round(qaly[position], 5),
            "state_cost": _round(cost[position], 2),
            "delta_qaly": _round(delta_qaly, 5),
            "delta_days": _round(delta_qaly * DAYS_PER_YEAR, 2),
            "delta_cost": _round(delta_cost, 2),
            "p_delta_positive": _round(np.mean(delta_draws > 0), 4),
        }
        if wtp is not None:
            row["objective_value"] = _round(qaly[position] * wtp - cost[position], 2)
            row["delta_net_benefit"] = _round(delta_qaly * wtp - delta_cost, 2)
        return row

    def delta_vs_current(position: int, wtp: float | None) -> dict[str, Any]:
        subset = subsets[position]
        delta_draws = draws_for(subset) - current_draws
        delta_qaly = float(qaly[position] - current_qaly)
        delta_cost = float(cost[position] - current_cost)
        actions = pgu.state_transition_actions(ids_of(current_subset), ids_of(subset))
        payload = {
            "delta_qaly": _round(delta_qaly, 5),
            "delta_days": _round(delta_qaly * DAYS_PER_YEAR, 2),
            "delta_ci80": _ci80(delta_draws),
            "delta_ci80_days": [
                _round(value * DAYS_PER_YEAR, 2) for value in _ci80(delta_draws)
            ],
            "p_delta_positive": _round(np.mean(delta_draws > 0), 4),
            "delta_cost": _round(delta_cost, 2),
            "actions": actions,
            "add_names": [names[item_id] for item_id in actions["add"]],
            "drop_names": [names[item_id] for item_id in actions["drop"]],
        }
        if wtp is not None:
            payload["delta_net_benefit"] = _round(delta_qaly * wtp - delta_cost, 2)
        return payload

    def neighbour_rows(position: int, wtp: float | None) -> list[dict[str, Any]]:
        subset = subsets[position]
        optimum_draws = draws_for(subset)
        rows: list[dict[str, Any]] = []
        for index, item_id in enumerate(universe):
            neighbour, action, swapped = _single_flip(subset, index, universe)
            neighbour_draws = draws_for(neighbour)
            neighbour_qaly = evaluator.mean_qaly(neighbour)
            neighbour_cost = evaluator.total_cost(neighbour)
            # Orientation: the value of having this item in the stack, all else
            # as in the optimum. Kept items: optimum minus the drop neighbour.
            # Left-out items: the add (or swap) neighbour minus the optimum.
            if action == "drop":
                marginal_draws = optimum_draws - neighbour_draws
                marginal_qaly = float(qaly[position] - neighbour_qaly)
                marginal_cost = float(cost[position] - neighbour_cost)
            else:
                marginal_draws = neighbour_draws - optimum_draws
                marginal_qaly = float(neighbour_qaly - qaly[position])
                marginal_cost = float(neighbour_cost - cost[position])
            row = {
                "id": item_id,
                "name": names[item_id],
                "in_optimum": action == "drop",
                "neighbour_action": action,
                "swap_out": None if swapped is None else universe[swapped],
                "marginal_qaly": _round(marginal_qaly, 5),
                "marginal_days": _round(marginal_qaly * DAYS_PER_YEAR, 2),
                "marginal_cost": _round(marginal_cost, 2),
                "p_marginal_positive": _round(np.mean(marginal_draws > 0), 4),
                "marginal_ci80": _ci80(marginal_draws),
            }
            if wtp is not None:
                row["marginal_net_benefit"] = _round(
                    marginal_qaly * wtp - marginal_cost, 2
                )
            rows.append(row)
        return rows

    def p_best(order: list[int], wtp: float | None) -> dict[str, Any]:
        top = order[: min(p_best_top_k, len(order))]
        stacked = np.vstack([draws_for(subsets[position]) for position in top])
        if wtp is not None:
            stacked = stacked * wtp - cost[top][:, None]
        winners = np.argmax(stacked, axis=0)
        shares = np.bincount(winners, minlength=len(top)) / stacked.shape[1]
        rows = [
            {
                "rank": rank + 1,
                "item_ids": ids_of(subsets[top[rank]]),
                "p_best": _round(shares[rank], 4),
            }
            for rank in range(len(top))
            if shares[rank] > 0
        ]
        rows.sort(key=lambda row: (-row["p_best"], row["rank"]))
        return {
            "top_k": len(top),
            "optimum_p_best": _round(shares[0], 4),
            "states": rows,
        }

    position_of = {subset: position for position, subset in enumerate(subsets)}

    def objective_result(objective: np.ndarray, wtp: float | None) -> dict[str, Any]:
        order = rank_order(objective)
        best = order[0]
        current_position = position_of.get(current_subset)
        current_objective = (
            current_qaly * wtp - current_cost if wtp is not None else current_qaly
        )
        return {
            "optimum": state_row(best, 1, wtp),
            "delta_vs_current": delta_vs_current(best, wtp),
            "current_rank": (
                None if current_position is None else 1 + order.index(current_position)
            ),
            "states_beating_current": int(
                np.sum(objective > current_objective + 1e-12)
            ),
            "top": [
                state_row(position, rank + 1, wtp)
                for rank, position in enumerate(order[:top_n])
            ],
            "single_flip_neighbours": neighbour_rows(best, wtp),
            "p_best": p_best(order, wtp),
        }

    by_wtp = {
        str(int(wtp)) if float(wtp).is_integer() else str(wtp): objective_result(
            qaly * float(wtp) - cost, float(wtp)
        )
        for wtp in wtps
    }
    qaly_objective = objective_result(qaly, None)

    groups: dict[str, list[str]] = {}
    for item_id in universe:
        group = _exclusive_group(item_id)
        if group:
            groups.setdefault(group, []).append(item_id)
    ungrouped = [item_id for item_id in universe if not _exclusive_group(item_id)]
    return {
        "method": (
            "Exhaustive search: every feasible subset of the sleep-domain universe "
            "(at most one item per exclusive group) is valued as a full protocol "
            "state with every other current item held fixed. State value = paired "
            "latent draws of all items + expected_stack_interaction_qaly on the "
            "full id list, identical to evaluate_protocol_state."
        ),
        "perspective": perspective
        or ("cash" if not cost_overrides else "custom_costs"),
        "cost_overrides": {
            item_id: _round(value, 2)
            for item_id, value in sorted((cost_overrides or {}).items())
        },
        "wtps": [float(wtp) for wtp in wtps],
        "universe": [
            {
                "id": item_id,
                "name": names[item_id],
                "status": by_id[item_id].get("status"),
                "current": item_id in current_members,
                "exclusive_group": _exclusive_group(item_id),
                "time_of_day": by_id[item_id].get("time_of_day"),
                "sleep_domain_reasons": sleep_domain_reasons(by_id[item_id]),
                "modeled_total_cost": _round(evaluator.cost[item_id], 2),
                "standalone_total_qaly": estimates_by_id[item_id].get("total_qaly"),
            }
            for item_id in universe
        ],
        "excluded": excluded,
        "exclusive_groups": groups,
        "n_ungrouped": len(ungrouped),
        "held_fixed_item_count": len(base_ids),
        "state_count": len(subsets),
        "expected_state_count": n_states,
        "current_state": {
            "item_ids": ids_of(current_subset),
            "names": [names[item_id] for item_id in ids_of(current_subset)],
            "feasible": _feasible(current_subset, universe),
            "state_qaly": _round(current_qaly, 5),
            "state_cost": _round(current_cost, 2),
        },
        "net_benefit": by_wtp,
        "qaly": qaly_objective,
    }


def _format_ids(names: Sequence[str]) -> str:
    return ", ".join(names) if names else "(none)"


def _format_usd(value: float) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.0f}"


def render_sleep_stack_markdown(result: Mapping[str, Any]) -> list[str]:
    """Markdown lines for the ``## Sleep stack (exhaustive search)`` section."""
    lines = ["## Sleep stack (exhaustive search)", ""]
    lines.append(
        f"Every feasible combination of the {len(result['universe'])} sleep-domain "
        f"items below was valued as a full protocol state ({result['state_count']:,} "
        "states, at most one item per exclusive group), holding the other "
        f"{result['held_fixed_item_count']} current items fixed. Costs: "
        f"{result['perspective']} perspective."
    )
    if result.get("runtime_seconds") is not None:
        lines.append(f"Search time: {result['runtime_seconds']:.1f} s.")
    lines.append("")
    current = result["current_state"]
    lines.append(
        f"- Current sleep stack: {_format_ids(current['names'])} "
        f"(state value {current['state_qaly']:.4f} QALY)"
    )
    universe_names = {row["id"]: row["name"] for row in result["universe"]}
    lines.append(
        "- Searched: "
        + ", ".join(
            f"{row['name']}{' (current)' if row['current'] else ''}"
            for row in result["universe"]
        )
    )
    if result["excluded"]:
        lines.append(
            "- Excluded: "
            + "; ".join(f"{row['name']}: {row['reason']}" for row in result["excluded"])
        )
    lines.append("")
    lines.append(
        "| Objective | Optimal sleep stack | Change from current | ΔQALY | Δdays | "
        "80% interval (days) | P(Δ>0) | Δcost | Δnet benefit | Current rank | P(best) |"
    )
    lines.append(
        "| --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |"
    )

    def change_text(delta: Mapping[str, Any]) -> str:
        parts = []
        if delta["add_names"]:
            parts.append("add " + ", ".join(delta["add_names"]))
        if delta["drop_names"]:
            parts.append("drop " + ", ".join(delta["drop_names"]))
        return "; ".join(parts) or "keep current"

    def objective_line(label: str, block: Mapping[str, Any]) -> str:
        delta = block["delta_vs_current"]
        low, high = delta["delta_ci80_days"]
        net = delta.get("delta_net_benefit")
        rank = block["current_rank"]
        return (
            f"| {label} | {_format_ids(block['optimum']['names'])} | "
            f"{change_text(delta)} | {delta['delta_qaly']:+.4f} | "
            f"{delta['delta_days']:+.1f} | [{low:+.1f}, {high:+.1f}] | "
            f"{delta['p_delta_positive']:.1%} | {_format_usd(delta['delta_cost'])} | "
            f"{'—' if net is None else _format_usd(net)} | "
            f"{'—' if rank is None else rank} | "
            f"{block['p_best']['optimum_p_best']:.1%} |"
        )

    for wtp_key, block in result["net_benefit"].items():
        lines.append(objective_line(f"${int(float(wtp_key)):,}/QALY", block))
    lines.append(objective_line("QALY only", result["qaly"]))
    lines.append("")
    top_k = result["qaly"]["p_best"]["top_k"]
    lines.append(
        "P(best) is the share of Monte Carlo draws in which the optimum has the "
        f"highest value among the top {top_k} states by the same objective; it is "
        "low when many near-equal stacks compete. Current rank is the current "
        "stack's position among all states by that objective."
    )

    headline_key = max(result["net_benefit"], key=lambda key: float(key))
    headline = result["net_benefit"][headline_key]
    lines.append("")
    lines.append(
        f"### Each item against the ${int(float(headline_key)):,}/QALY optimum"
    )
    lines.append("")
    lines.append(
        "Marginal = value with the item minus value without it, everything else as "
        "in the optimum (a left-out item in a filled exclusive group is swapped in)."
    )
    lines.append("")
    lines.append("| Item | In optimum | ΔQALY | Δdays | P(>0) | Δcost | Δnet benefit |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: |")
    for row in sorted(
        headline["single_flip_neighbours"],
        key=lambda row: -row["marginal_net_benefit"],
    ):
        in_label = (
            "yes"
            if row["in_optimum"]
            else (
                f"no (swap for {universe_names[row['swap_out']]})"
                if row["swap_out"]
                else "no"
            )
        )
        lines.append(
            f"| {row['name']} | {in_label} | {row['marginal_qaly']:+.4f} | "
            f"{row['marginal_days']:+.1f} | {row['p_marginal_positive']:.1%} | "
            f"{_format_usd(row['marginal_cost'])} | "
            f"{_format_usd(row['marginal_net_benefit'])} |"
        )
    lines.append("")
    lines.append(f"### Top sleep stacks at ${int(float(headline_key)):,}/QALY")
    lines.append("")
    lines.append(
        "| Rank | Stack | ΔQALY vs current | Δdays | P(Δ>0) | Δcost | Δnet benefit |"
    )
    lines.append("| ---: | --- | ---: | ---: | ---: | ---: | ---: |")
    for row in headline["top"][:10]:
        lines.append(
            f"| {row['rank']} | {_format_ids(row['names'])} | {row['delta_qaly']:+.4f} | "
            f"{row['delta_days']:+.1f} | {row['p_delta_positive']:.1%} | "
            f"{_format_usd(row['delta_cost'])} | {_format_usd(row['delta_net_benefit'])} |"
        )
    return lines
