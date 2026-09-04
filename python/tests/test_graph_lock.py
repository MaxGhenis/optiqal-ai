"""Tests for the frozen graph-interface lock and its verifier CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from optiqal.graph.lock import interface_hash, main, verify

_FILES = (
    "python/optiqal/graph/decl.py",
    "python/optiqal/graph/kernel.py",
)


def _lock_fixture(tmp_path: Path) -> tuple[Path, Path, str]:
    repository = Path(__file__).resolve().parents[2]
    for relative in _FILES:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((repository / relative).read_bytes())
    lock_path = tmp_path / "docs/rebuild/graph-interface.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    identity = interface_hash(tmp_path)
    lock_path.write_text(json.dumps({"sha256": identity}), encoding="utf-8")
    return repository, lock_path, identity


def test_interface_hash_is_path_independent_and_content_sensitive(tmp_path):
    repository, _, identity = _lock_fixture(tmp_path)
    assert identity == interface_hash(repository)
    declaration = tmp_path / _FILES[0]
    declaration.write_bytes(declaration.read_bytes() + b"\n")
    assert interface_hash(tmp_path) != identity


def test_verify_accepts_the_lock_and_rejects_bad_lock_data(tmp_path):
    _, lock_path, identity = _lock_fixture(tmp_path)
    assert verify(tmp_path) == identity

    lock_path.write_text("{", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Cannot read"):
        verify(tmp_path)

    lock_path.write_text(json.dumps({"sha256": "0" * 64}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="lock mismatch"):
        verify(tmp_path)


def test_lock_cli_requires_verify_and_prints_the_identity(capsys):
    assert main(["--verify"]) == 0
    assert verify() in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main([])
