"""Validation for the first unified planner observation protocol.

Camera extrinsics are ``T_base_camera`` matrices mapping the protocol's RDF
camera axes (right, down, forward) into the R1 Pro base frame.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np


CAMERA_NAMES = ("base", "left_wrist", "right_wrist")
PLANNER_OBSERVATION_KEYS = frozenset(("rgbd", "intrinsics", "extrinsics", "state", "prompt"))


class ProtocolValidationError(ValueError):
    """Raised when data does not satisfy the planner observation contract."""


def _require_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProtocolValidationError(f"{name} must be a mapping, got {type(value).__name__}")
    return value


def _require_keys(mapping: Mapping[str, Any], expected: frozenset[str] | tuple[str, ...], name: str) -> None:
    expected_set = set(expected)
    actual = set(mapping)
    if actual != expected_set:
        raise ProtocolValidationError(
            f"{name} keys must be {sorted(expected_set)}, got {sorted(actual)}"
        )


def _require_float32_array(value: Any, name: str, shape: tuple[int, ...] | None = None) -> np.ndarray:
    if not isinstance(value, np.ndarray):
        raise ProtocolValidationError(f"{name} must be a numpy.ndarray, got {type(value).__name__}")
    if value.dtype != np.float32:
        raise ProtocolValidationError(f"{name} must have dtype float32, got {value.dtype}")
    if shape is not None and value.shape != shape:
        raise ProtocolValidationError(f"{name} must have shape {shape}, got {value.shape}")
    if not np.all(np.isfinite(value)):
        raise ProtocolValidationError(f"{name} must contain only finite values")
    return value


def validate_planner_observation(observation: Mapping[str, Any]) -> None:
    """Validate the wire-level, simulator-independent planner observation."""
    observation = _require_mapping(observation, "observation")
    _require_keys(observation, PLANNER_OBSERVATION_KEYS, "observation")

    rgbd = _require_mapping(observation["rgbd"], "rgbd")
    intrinsics = _require_mapping(observation["intrinsics"], "intrinsics")
    extrinsics = _require_mapping(observation["extrinsics"], "extrinsics")
    _require_keys(rgbd, CAMERA_NAMES, "rgbd")
    _require_keys(intrinsics, CAMERA_NAMES, "intrinsics")
    _require_keys(extrinsics, CAMERA_NAMES, "extrinsics")

    for camera_name in CAMERA_NAMES:
        image = _require_float32_array(rgbd[camera_name], f"rgbd[{camera_name}]")
        if image.ndim != 3 or image.shape[0] <= 0 or image.shape[1] <= 0 or image.shape[2] != 4:
            raise ProtocolValidationError(
                f"rgbd[{camera_name}] must have non-empty H x W x 4 shape, got {image.shape}"
            )
        rgb = image[..., :3]
        depth_m = image[..., 3]
        if np.any(rgb < 0.0) or np.any(rgb > 1.0):
            raise ProtocolValidationError(f"rgbd[{camera_name}] RGB values must be in [0, 1]")
        if np.any(depth_m < 0.0):
            raise ProtocolValidationError(f"rgbd[{camera_name}] depth must be in meters and non-negative")

        intrinsic = _require_float32_array(intrinsics[camera_name], f"intrinsics[{camera_name}]", (3, 3))
        if intrinsic[2, 2] == 0.0:
            raise ProtocolValidationError(f"intrinsics[{camera_name}][2, 2] must be non-zero")

        extrinsic = _require_float32_array(extrinsics[camera_name], f"extrinsics[{camera_name}]", (4, 4))
        if not np.allclose(extrinsic[3], np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32)):
            raise ProtocolValidationError(f"extrinsics[{camera_name}] must be a 4 x 4 homogeneous transform")

    state = _require_float32_array(observation["state"], "state")
    if state.ndim != 1 or state.size == 0:
        raise ProtocolValidationError(f"state must be a non-empty 1D vector, got {state.shape}")
    if not isinstance(observation["prompt"], str):
        raise ProtocolValidationError(f"prompt must be str, got {type(observation['prompt']).__name__}")
