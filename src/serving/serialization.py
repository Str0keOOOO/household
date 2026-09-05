"""MessagePack serialization that preserves NumPy dtype and shape exactly."""

from __future__ import annotations

import hashlib
from typing import Any

import msgpack
import numpy as np


_NDARRAY_MARKER = "__household_ndarray__"


def _encode(value: Any) -> dict[str, Any]:
    if not isinstance(value, np.ndarray):
        raise TypeError(f"cannot MessagePack-encode {type(value).__name__}")
    if value.dtype.hasobject:
        raise TypeError("object-dtype arrays are not supported on the planner wire protocol")
    array = np.ascontiguousarray(value)
    return {
        _NDARRAY_MARKER: True,
        "dtype": array.dtype.str,
        "shape": list(array.shape),
        "data": array.tobytes(order="C"),
    }


def _decode(value: dict[str, Any]) -> Any:
    if value.get(_NDARRAY_MARKER) is not True:
        return value
    try:
        dtype = np.dtype(value["dtype"])
        shape = tuple(int(size) for size in value["shape"])
        data = value["data"]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid encoded ndarray") from exc
    if dtype.hasobject or any(size < 0 for size in shape) or not isinstance(data, bytes):
        raise ValueError("invalid encoded ndarray metadata")
    expected_nbytes = int(np.prod(shape, dtype=np.int64)) * dtype.itemsize
    if len(data) != expected_nbytes:
        raise ValueError(f"encoded ndarray has {len(data)} bytes, expected {expected_nbytes}")
    return np.frombuffer(data, dtype=dtype).reshape(shape).copy()


def packb(value: Any) -> bytes:
    """Encode nested dicts and NumPy arrays without JSON conversion or base64."""
    return msgpack.packb(value, default=_encode, use_bin_type=True, strict_types=True)


def unpackb(payload: bytes) -> Any:
    """Decode a MessagePack payload and reconstruct each NumPy ndarray."""
    return msgpack.unpackb(payload, raw=False, strict_map_key=False, object_hook=_decode)


def _canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    if isinstance(value, tuple):
        return [_canonicalize(item) for item in value]
    return value


def payload_checksum(value: Any) -> str:
    """Return a deterministic checksum over the exact protocol representation."""
    return hashlib.sha256(packb(_canonicalize(value))).hexdigest()
