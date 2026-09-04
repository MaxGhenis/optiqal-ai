"""Canonical identity bytes for Optiqal graph values and declarations."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any

import numpy as np

from .decl import DESCRIPTIVE_FIELDS

__all__ = ["canonical_json", "normative", "sha256_domain"]

_ARRAY_MARKER = "__ndarray__"


def _array_value(value: np.ndarray) -> dict[str, object]:
    array = np.asarray(value)
    if array.dtype.hasobject or array.dtype.fields is not None:
        raise TypeError("object and structured arrays are not canonical")
    if np.issubdtype(array.dtype, np.inexact) and not np.isfinite(array).all():
        raise ValueError("non-finite numbers are not canonical JSON")
    # ``ascontiguousarray`` promotes a zero-dimensional array to shape ``(1,)``;
    # an explicit C-order copy preserves the declared shape in identity.
    contiguous = np.array(array, copy=True, order="C", subok=False)
    return {
        _ARRAY_MARKER: {
            "base64": base64.b64encode(contiguous.tobytes(order="C")).decode("ascii"),
            "dtype": contiguous.dtype.str,
            "shape": list(contiguous.shape),
        }
    }


def _json_value(value: object) -> object:
    """Return ``value`` using only the graph's closed canonical grammar."""

    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite numbers are not canonical JSON")
        return value
    if isinstance(value, np.ndarray):
        return _array_value(value)
    if isinstance(value, np.generic):
        return _json_value(value.item())
    if isinstance(value, Enum):
        return _json_value(value.value)
    if isinstance(value, Mapping):
        converted: dict[str, object] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise TypeError("canonical mappings require string keys")
            converted[key] = _json_value(child)
        return converted
    if isinstance(value, (list, tuple)):
        return [_json_value(child) for child in value]
    raise TypeError(
        f"{type(value).__name__} is not part of the canonical JSON value grammar"
    )


def canonical_json(obj: object) -> bytes:
    """Encode deterministic, whitespace-free UTF-8 JSON.

    Mappings are sorted, tuples use JSON arrays, floats use Python's shortest
    round-trip spelling, and numeric NumPy arrays use a dtype/shape/base64
    envelope over their C-order bytes. NaN and both infinities are refused.
    """

    return json.dumps(
        _json_value(obj),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_domain(domain: str, payload: bytes) -> str:
    """Hash ``payload`` after a UTF-8 domain and a NUL separator."""

    if not isinstance(domain, str):
        raise TypeError("hash domain must be a string")
    if "\0" in domain:
        raise ValueError("hash domain must not contain NUL")
    if not isinstance(payload, bytes):
        raise TypeError("hash payload must be bytes")
    return hashlib.sha256(domain.encode("utf-8") + b"\0" + payload).hexdigest()


def _declaration_value(value: object) -> object:
    """Project nested declaration dataclasses without descriptive fields."""

    if isinstance(value, Enum):
        return _declaration_value(value.value)
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: _declaration_value(getattr(value, item.name))
            for item in fields(value)
            if item.name not in DESCRIPTIVE_FIELDS
        }
    if isinstance(value, Mapping):
        # Mapping keys are data. In particular, a Node parameter literally
        # named "description" remains normative, matching Microcosm's choice.
        return {key: _declaration_value(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return tuple(_declaration_value(child) for child in value)
    if isinstance(value, list):
        return [_declaration_value(child) for child in value]
    return value


def normative(value: Any) -> object:
    """Return a declaration's recursive normative projection."""

    project = getattr(value, "normative", None)
    root = project() if callable(project) else value
    return _declaration_value(root)


def _restore_json(value: object) -> object:
    """Restore NumPy envelopes after a canonical store round trip."""

    if isinstance(value, list):
        return [_restore_json(child) for child in value]
    if isinstance(value, dict):
        if set(value) == {_ARRAY_MARKER}:
            spec = value[_ARRAY_MARKER]
            if not isinstance(spec, dict) or set(spec) != {"base64", "dtype", "shape"}:
                raise ValueError("malformed canonical NumPy envelope")
            encoded = spec["base64"]
            dtype_name = spec["dtype"]
            shape = spec["shape"]
            if (
                not isinstance(encoded, str)
                or not isinstance(dtype_name, str)
                or not isinstance(shape, list)
                or any(type(item) is not int or item < 0 for item in shape)
            ):
                raise ValueError("malformed canonical NumPy envelope")
            try:
                dtype = np.dtype(dtype_name)
                if dtype.hasobject or dtype.fields is not None:
                    raise ValueError
                raw = base64.b64decode(encoded, validate=True)
                count = math.prod(shape)
                if len(raw) != count * dtype.itemsize:
                    raise ValueError
                array = np.frombuffer(raw, dtype=dtype).reshape(tuple(shape)).copy()
            except (binascii.Error, TypeError, ValueError) as error:
                raise ValueError("malformed canonical NumPy envelope") from error
            if np.issubdtype(array.dtype, np.inexact) and not np.isfinite(array).all():
                raise ValueError("non-finite canonical NumPy array")
            return array
        return {key: _restore_json(child) for key, child in value.items()}
    return value
