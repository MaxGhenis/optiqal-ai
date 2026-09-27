"""One shared interaction evaluator for protocol states and exhaustive search."""

from __future__ import annotations

from dataclasses import replace
from typing import Literal

from .catalog import CATALOG
from .profile import Profile
from .sleep import SLEEP_COMPONENT_BENEFIT_TAGS
from .sleep_overlap import SleepOverlapEvaluator
from .stack_interactions import expected_stack_interaction_qaly

OverlapMode = Literal["component", "legacy_rank_retention"]


class ProtocolInteractionEvaluator:
    def __init__(
        self,
        estimates_by_id: dict,
        item_active_years: dict[str, float],
        profile: Profile,
        discount_rate: float,
        overlap_mode: OverlapMode,
    ) -> None:
        if overlap_mode not in ("component", "legacy_rank_retention"):
            raise ValueError(f"Unknown overlap mode: {overlap_mode}")
        self.mode = overlap_mode
        self.profile = profile
        self.discount_rate = discount_rate
        self.active_years = item_active_years
        self.catalog = dict(CATALOG)
        self.item_qalys = {}
        for item_id, estimate in estimates_by_id.items():
            legacy_qaly = estimate.get(
                "_benefit_overlap_qaly",
                estimate.get(
                    "legacy_benefit_qaly",
                    max(float(estimate.get("total_qaly", 0.0)), 0.0),
                ),
            )
            self.item_qalys[item_id] = float(
                legacy_qaly
                if overlap_mode == "legacy_rank_retention"
                else estimate.get(
                    "_non_sleep_benefit_overlap_qaly",
                    estimate.get("non_sleep_benefit_qaly", legacy_qaly),
                )
            )
        if overlap_mode == "component":
            sleep_tags = set(SLEEP_COMPONENT_BENEFIT_TAGS.values())
            # Retention remains unchanged for every non-sleep tag, but its
            # benefit scalar now contains general QoL and direct-HR mortality
            # only. The existing largest-penalty-per-item rule still applies.
            self.catalog = {
                item_id: replace(
                    entry,
                    benefit_tags=[
                        tag for tag in entry.benefit_tags if tag not in sleep_tags
                    ],
                )
                for item_id, entry in self.catalog.items()
            }
            self.sleep = SleepOverlapEvaluator(estimates_by_id, discount_rate)
        else:
            # B2's legacy switch restores its catalog tag edits as well as the
            # old arithmetic. B1 sedation and B3 residuals have separate controls.
            for item_id, tags in {
                "ashwagandha_600": ["anti_inflammatory"],
                "apigenin_50": ["anti_inflammatory", "senolytic_support"],
            }.items():
                entry = self.catalog[item_id]
                self.catalog[item_id] = replace(
                    entry,
                    benefit_tags=list(dict.fromkeys([*entry.benefit_tags, *tags])),
                )
            entry = self.catalog["nac_1200"]
            self.catalog["nac_1200"] = replace(
                entry,
                benefit_tags=[
                    tag for tag in entry.benefit_tags if tag != "sleep_quality_support"
                ],
            )
            self.sleep = None

    def evaluate(
        self, item_ids: list[str], *, details: bool = True
    ) -> tuple[float, list[dict]]:
        value, rows = expected_stack_interaction_qaly(
            item_ids=item_ids,
            catalog_entries=self.catalog,
            profile=self.profile,
            qaly_discount_rate=self.discount_rate,
            item_active_years=self.active_years,
            item_qalys=self.item_qalys,
        )
        if self.sleep is not None:
            if details:
                sleep_value, sleep_rows = self.sleep.evaluate(item_ids)
                rows.extend(sleep_rows)
            else:
                sleep_value = self.sleep.interaction_qaly(item_ids)
            value += sleep_value
        rows.sort(key=lambda row: row["penalty_qaly"])
        return value, rows if details else []
