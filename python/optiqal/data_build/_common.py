"""Shared snapshot-writing helpers for data build modules."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from optiqal.snapshots import data_checksum


def file_checksum(path: Path) -> str:
    """Return the sha256 digest of a source artifact's exact bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot_payload(provenance: dict[str, Any], data: dict[str, Any]) -> dict:
    """Add the canonical data checksum to a snapshot payload."""
    stamped_provenance = dict(provenance)
    stamped_provenance["sha256_of_data"] = data_checksum(data)
    return {"provenance": stamped_provenance, "data": data}


def write_snapshot(
    output_path: Path, provenance: dict[str, Any], data: dict[str, Any]
) -> Path:
    """Write a snapshot without disturbing numeric insertion order."""
    payload = snapshot_payload(provenance, data)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, allow_nan=False, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path
