"""Atomic, checksummed storage for graph values and opaque artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePath
from types import MappingProxyType
from typing import Literal

from .canonical import _json_value, _restore_json, canonical_json, sha256_domain
from .errors import StoreCorruptError, StoreMissError

__all__ = [
    "ContentStore",
    "ResumePolicy",
    "StoreCorruptError",
    "StoreMissError",
    "StoredResult",
]

ResumePolicy = Literal["auto", "require", "forbid"]

_FORMAT = "optiqal-graph-content-store-v1"
_KEY = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class StoredResult:
    """A fully validated cached kernel result."""

    value: object
    receipt: Mapping[str, object]
    artifacts: Mapping[str, bytes]
    artifact_checksums: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "receipt", MappingProxyType(dict(self.receipt)))
        object.__setattr__(self, "artifacts", MappingProxyType(dict(self.artifacts)))
        object.__setattr__(
            self,
            "artifact_checksums",
            MappingProxyType(dict(self.artifact_checksums)),
        )


def _repository_store() -> Path:
    return Path(__file__).resolve().parents[3] / "results" / "store"


def _require_key(key: str) -> str:
    if not isinstance(key, str) or _KEY.fullmatch(key) is None:
        raise ValueError("Content-store keys must be 64 lowercase hexadecimal digits.")
    return key


def _artifact_name(name: object) -> str:
    if not isinstance(name, str) or not name:
        raise ValueError("Artifact names must be non-empty strings.")
    candidate = PurePath(name)
    if candidate.name != name or name in {".", ".."} or "\0" in name:
        raise ValueError(f"Unsafe artifact name {name!r}.")
    return name


def _fsync_file(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _record_checksum(body: Mapping[str, object]) -> str:
    return sha256_domain("store-record", canonical_json(body))


class ContentStore:
    """A content store rooted at ``results/store`` by default.

    Each visible object is ``<root>/<key[:2]>/<key>.json``. Opaque artifacts
    are content-named ``.bin`` files beside it. Writes stage in the same shard,
    publish all bins first, and atomically publish the JSON visibility marker
    last, following Microcosm's atomic-publication choice.
    """

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = _repository_store() if root is None else Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key: str) -> Path:
        """Return the canonical JSON path without reading it."""

        identity = _require_key(key)
        return self.root / identity[:2] / f"{identity}.json"

    def has(self, key: str) -> bool:
        """Return whether an object marker is visible, without validating it."""

        return self.path(key).exists()

    contains = has

    def get(self, key: str) -> object:
        """Load and validate a stored value."""

        return self.get_record(key).value

    def get_record(self, key: str) -> StoredResult:
        """Load a value, deterministic receipt, and all opaque artifacts."""

        identity = _require_key(key)
        path = self.path(identity)
        if not path.exists():
            raise StoreMissError(f"No stored object for {identity}.")
        if path.is_symlink() or not path.is_file():
            raise StoreCorruptError(f"Stored object {identity} is not a regular file.")
        try:
            raw = path.read_bytes()
            payload = json.loads(raw)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise StoreCorruptError(
                f"Stored object {identity} is not readable canonical JSON."
            ) from error
        if not isinstance(payload, dict):
            raise StoreCorruptError(f"Stored object {identity} must be a JSON object.")
        try:
            if canonical_json(payload) != raw:
                raise StoreCorruptError(
                    f"Stored object {identity} is not in canonical form."
                )
        except (TypeError, ValueError) as error:
            raise StoreCorruptError(
                f"Stored object {identity} contains noncanonical data."
            ) from error
        required = {"artifacts", "checksum", "format", "key", "receipt", "value"}
        if set(payload) != required:
            raise StoreCorruptError(f"Stored object {identity} has unexpected fields.")
        if payload["format"] != _FORMAT or payload["key"] != identity:
            raise StoreCorruptError(f"Stored object {identity} does not bind its key.")
        checksum = payload["checksum"]
        body = {name: value for name, value in payload.items() if name != "checksum"}
        if not isinstance(checksum, str) or checksum != _record_checksum(body):
            raise StoreCorruptError(f"Stored object {identity} failed its checksum.")
        receipt = payload["receipt"]
        artifacts = payload["artifacts"]
        if not isinstance(receipt, dict) or not isinstance(artifacts, dict):
            raise StoreCorruptError(f"Stored object {identity} metadata is malformed.")
        loaded_artifacts: dict[str, bytes] = {}
        artifact_checksums: dict[str, str] = {}
        for raw_name, raw_spec in artifacts.items():
            try:
                name = _artifact_name(raw_name)
            except ValueError as error:
                raise StoreCorruptError(str(error)) from error
            if not isinstance(raw_spec, dict) or set(raw_spec) != {
                "file",
                "sha256",
                "size",
            }:
                raise StoreCorruptError(
                    f"Stored artifact {name!r} metadata is malformed."
                )
            filename = raw_spec["file"]
            expected_hash = raw_spec["sha256"]
            expected_size = raw_spec["size"]
            if (
                not isinstance(filename, str)
                or PurePath(filename).name != filename
                or not isinstance(expected_hash, str)
                or _KEY.fullmatch(expected_hash) is None
                or type(expected_size) is not int
                or expected_size < 0
            ):
                raise StoreCorruptError(
                    f"Stored artifact {name!r} metadata is malformed."
                )
            artifact_path = path.parent / filename
            if artifact_path.is_symlink() or not artifact_path.is_file():
                raise StoreCorruptError(f"Stored artifact {name!r} is missing.")
            try:
                content = artifact_path.read_bytes()
            except OSError as error:
                raise StoreCorruptError(
                    f"Stored artifact {name!r} cannot be read."
                ) from error
            actual_hash = hashlib.sha256(content).hexdigest()
            if len(content) != expected_size or actual_hash != expected_hash:
                raise StoreCorruptError(
                    f"Stored artifact {name!r} failed its size/SHA-256 check."
                )
            loaded_artifacts[name] = content
            artifact_checksums[name] = actual_hash
        try:
            value = _restore_json(payload["value"])
            restored_receipt = _restore_json(receipt)
        except ValueError as error:
            raise StoreCorruptError(
                f"Stored object {identity} contains a malformed value."
            ) from error
        if not isinstance(restored_receipt, Mapping):
            raise StoreCorruptError(f"Stored object {identity} receipt is malformed.")
        return StoredResult(
            value=value,
            receipt=restored_receipt,
            artifacts=loaded_artifacts,
            artifact_checksums=artifact_checksums,
        )

    def put(
        self,
        key: str,
        value: object,
        artifacts: Mapping[str, bytes] | None = None,
        receipt: Mapping[str, object] | None = None,
        *,
        verify_existing: bool = True,
    ) -> Path:
        """Atomically store a value and its deterministic kernel metadata."""

        identity = _require_key(key)
        if artifacts is None:
            artifacts = {}
        if receipt is None:
            receipt = {}
        if not isinstance(artifacts, Mapping):
            raise TypeError("artifacts must be a mapping")
        if not isinstance(receipt, Mapping):
            raise TypeError("receipt must be a mapping")
        final_path = self.path(identity)
        if verify_existing and final_path.exists():
            self.get_record(identity)
            return final_path
        try:
            value_payload = _json_value(value)
            receipt_payload = _json_value(receipt)
        except (TypeError, ValueError) as error:
            raise TypeError(
                f"Stored values and receipts must be canonical: {error}"
            ) from error
        if not isinstance(receipt_payload, dict):
            raise TypeError("receipt must encode as a JSON object")

        normalized_artifacts: dict[str, bytes] = {}
        artifact_specs: dict[str, dict[str, object]] = {}
        for raw_name, payload in artifacts.items():
            name = _artifact_name(raw_name)
            if not isinstance(payload, bytes):
                raise TypeError(f"Artifact {name!r} must be bytes.")
            content_hash = hashlib.sha256(payload).hexdigest()
            filename = f"{identity}.{content_hash}.bin"
            normalized_artifacts[name] = payload
            artifact_specs[name] = {
                "file": filename,
                "sha256": content_hash,
                "size": len(payload),
            }
        body: dict[str, object] = {
            "artifacts": artifact_specs,
            "format": _FORMAT,
            "key": identity,
            "receipt": receipt_payload,
            "value": value_payload,
        }
        record = {**body, "checksum": _record_checksum(body)}
        encoded = canonical_json(record)
        shard = final_path.parent
        shard.mkdir(parents=True, exist_ok=True)
        temporary: list[Path] = []
        try:
            for name, payload in normalized_artifacts.items():
                filename = str(artifact_specs[name]["file"])
                destination = shard / filename
                staged = shard / f".{identity}.{uuid.uuid4().hex}.bin.tmp"
                temporary.append(staged)
                staged.write_bytes(payload)
                _fsync_file(staged)
                os.replace(staged, destination)
                temporary.remove(staged)
            staged_record = shard / f".{identity}.{uuid.uuid4().hex}.json.tmp"
            temporary.append(staged_record)
            staged_record.write_bytes(encoded)
            _fsync_file(staged_record)
            os.replace(staged_record, final_path)
            temporary.remove(staged_record)
            _fsync_directory(shard)
        finally:
            for staged in temporary:
                try:
                    staged.unlink()
                except FileNotFoundError:
                    pass
        return final_path
