"""Print the catalog's evidence linkage and ratchet status."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from .catalog import CATALOG, CatalogEntry
from .ratchets import RATCHET_FILENAMES, RatchetEntry, generate_ratchets


def _catalog_status(
    item_id: str, snapshots: Mapping[str, Sequence[RatchetEntry]]
) -> str:
    statuses: list[str] = []
    unsourced_ids = {entry.id for entry in snapshots["known_unsourced_claims.yaml"]}
    unverified_ids = {entry.id for entry in snapshots["known_unverified_atoms.yaml"]}
    judgment_ids = {entry.id for entry in snapshots["known_judgment_atoms.yaml"]}
    if item_id in unsourced_ids:
        statuses.append("unsourced")
    if any(
        entry_id == f"catalog:{item_id}" or entry_id.startswith(f"catalog:{item_id}:")
        for entry_id in unverified_ids
    ):
        statuses.append("unverified")
    if any(entry_id.startswith(f"catalog:{item_id}:") for entry_id in judgment_ids):
        statuses.append("judgment")
    return ",".join(statuses) if statuses else "clear"


def render_lint(
    catalog: Mapping[str, CatalogEntry] | None = None,
    snapshots: Mapping[str, Sequence[RatchetEntry]] | None = None,
) -> list[str]:
    """Render deterministic per-item lines followed by exactly three counts."""
    live_catalog = CATALOG if catalog is None else catalog
    live_snapshots = generate_ratchets() if snapshots is None else snapshots
    lines: list[str] = []
    for item_id in sorted(live_catalog):
        entry = live_catalog[item_id]
        study_ids = ",".join(entry.study_ids)
        lines.append(
            f"{item_id}\thr_observed={entry.hr_observed!r}\t"
            f"study_ids=[{study_ids}]\t"
            f"ratchet_status={_catalog_status(item_id, live_snapshots)}"
        )
    for filename in RATCHET_FILENAMES:
        lines.append(
            f"{filename.removesuffix('.yaml')}: {len(live_snapshots[filename])}"
        )
    return lines


def main() -> int:
    for line in render_lint():
        print(line)
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through ``python -m``
    raise SystemExit(main())
