"""Verify the frozen declaration and kernel interface lock."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

__all__ = ["interface_hash", "main", "verify"]

_FILES = ("python/optiqal/graph/decl.py", "python/optiqal/graph/kernel.py")
_LOCK = "docs/rebuild/graph-interface.lock"


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


def interface_hash(root: Path | None = None) -> str:
    """Return the path-independent canonical hash of the frozen files."""

    repository = _root() if root is None else Path(root)
    digest = hashlib.sha256(b"optiqal-graph-interface/1\0")
    for relative in _FILES:
        name = relative.encode("utf-8")
        content = (repository / relative).read_bytes()
        digest.update(len(name).to_bytes(8, "little"))
        digest.update(name)
        digest.update(len(content).to_bytes(8, "little"))
        digest.update(content)
    return digest.hexdigest()


def verify(root: Path | None = None) -> str:
    """Verify the recorded lock and return its hash."""

    repository = _root() if root is None else Path(root)
    path = repository / _LOCK
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Cannot read graph interface lock at {path}.") from error
    expected = payload.get("sha256") if isinstance(payload, dict) else None
    actual = interface_hash(repository)
    if expected != actual:
        raise RuntimeError(
            f"Graph interface lock mismatch: recorded {expected!r}, actual {actual}."
        )
    return actual


def main(argv: list[str] | None = None) -> int:
    """Run the lock verifier CLI."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="verify the lock")
    arguments = parser.parse_args(argv)
    if not arguments.verify:
        parser.error("--verify is required")
    print(f"Graph interface lock verified: {verify()}")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI
    raise SystemExit(main())
