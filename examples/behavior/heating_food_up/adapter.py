"""Pure-NumPy adapter from BEHAVIOR R1 Pro observations to planner observations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np


# The order is the planner contract. Base pose is xyz in meters followed by an
# xyzw quaternion; the remaining components are R1 Pro joint coordinates.
STATE_LAYOUT = (
    "base_x_m",
    "base_y_m",
    "base_z_m",
    "base_quat_x",
    "base_quat_y",
    "base_quat_z",
    "base_quat_w",
    "torso_joint1",
    "torso_joint2",
    "torso_joint3",
    "torso_joint4",
    "left_arm_joint1",
    "left_arm_joint2",
    "left_arm_joint3",
    "left_arm_joint4",
    "left_arm_joint5",
    "left_arm_joint6",
    "left_arm_joint7",
    "left_gripper_q",
    "right_arm_joint1",
    "right_arm_joint2",
    "right_arm_joint3",
    "right_arm_joint4",
    "right_arm_joint5",
    "right_arm_joint6",
    "right_arm_joint7",
    "right_gripper_q",
)

STATE_COMPONENT_SLICES = {
    "base_state": slice(0, 7),
    "torso_q": slice(7, 11),
    "left_arm_q": slice(11, 18),
    "left_gripper_q": slice(18, 19),
    "right_arm_q": slice(19, 26),
    "right_gripper_q": slice(26, 27),
}
STATE_COMPONENT_SIZES = {name: value.stop - value.start for name, value in STATE_COMPONENT_SLICES.items()}
STATE_DIM = len(STATE_LAYOUT)

ACTION_LAYOUT = (
    "torso_joint1",
    "torso_joint2",
    "torso_joint3",
    "torso_joint4",
    "right_arm_joint1",
    "right_arm_joint2",
    "right_arm_joint3",
    "right_arm_joint4",
    "right_arm_joint5",
    "right_arm_joint6",
    "right_arm_joint7",
    "right_gripper",
)
ACTION_DIM = len(ACTION_LAYOUT)

# OmniGibson R1 Pro scene action contract used only by the local execution
# adapter. The planner server returns ACTION_LAYOUT (12 values); rollout.py
# inserts zero base/left-arm controls before passing this 23-D vector to
# env.step. The order matches r1pro_behavior.yaml and values are normalized
# to [-1, 1].
SIM_ACTION_LAYOUT = (
    "base_vx",
    "base_vy",
    "base_wz",
    "torso_joint1",
    "torso_joint2",
    "torso_joint3",
    "torso_joint4",
    "left_arm_joint1",
    "left_arm_joint2",
    "left_arm_joint3",
    "left_arm_joint4",
    "left_arm_joint5",
    "left_arm_joint6",
    "left_arm_joint7",
    "left_gripper",
    "right_arm_joint1",
    "right_arm_joint2",
    "right_arm_joint3",
    "right_arm_joint4",
    "right_arm_joint5",
    "right_arm_joint6",
    "right_arm_joint7",
    "right_gripper",
)
SIM_ACTION_DIM = len(SIM_ACTION_LAYOUT)

_CAMERA_FIELDS = {
    "base": ("zed_rgb", "zed_depth", "K_zed", "T_base_camera_zed"),
    "left_wrist": (
        "left_wrist_rgb",
        "left_wrist_depth",
        "K_left_wrist",
        "T_base_camera_left_wrist",
    ),
    "right_wrist": (
        "right_wrist_rgb",
        "right_wrist_depth",
        "K_right_wrist",
        "T_base_camera_right_wrist",
    ),
}
_STATE_FIELDS = tuple(STATE_COMPONENT_SLICES)
RAW_OBSERVATION_KEYS = frozenset(
    field for fields in _CAMERA_FIELDS.values() for field in fields
) | frozenset(_STATE_FIELDS) | frozenset(("prompt",))


class AdapterValidationError(ValueError):
    """Raised when a BEHAVIOR raw observation violates the adapter contract."""


def _require_array(value: Any, name: str) -> np.ndarray:
    if not isinstance(value, np.ndarray):
        raise AdapterValidationError(f"{name} must be a numpy.ndarray, got {type(value).__name__}")
    return value


def _rgb_float32(rgb: Any, name: str) -> np.ndarray:
    rgb = _require_array(rgb, name)
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise AdapterValidationError(f"{name} must have shape H x W x 3, got {rgb.shape}")
    if rgb.dtype == np.uint8:
        return rgb.astype(np.float32) / 255.0
    if np.issubdtype(rgb.dtype, np.floating):
        result = rgb.astype(np.float32, copy=False)
        if not np.all(np.isfinite(result)) or np.any(result < 0.0) or np.any(result > 1.0):
            raise AdapterValidationError(f"{name} floating RGB must be finite and in [0, 1]")
        return result
    raise AdapterValidationError(f"{name} must be uint8 or floating-point, got {rgb.dtype}")


def _depth_meters(depth: Any, height: int, width: int, name: str) -> np.ndarray:
    depth = _require_array(depth, name)
    if depth.ndim == 3 and depth.shape[2] == 1:
        depth = depth[..., 0]
    if depth.shape != (height, width):
        raise AdapterValidationError(f"{name} must have shape {(height, width)}, got {depth.shape}")
    if not np.issubdtype(depth.dtype, np.number):
        raise AdapterValidationError(f"{name} must be numeric, got {depth.dtype}")
    # Raw depth is already meters. Deliberately do not scale it here.
    result = depth.astype(np.float32, copy=False)
    if not np.all(np.isfinite(result)) or np.any(result < 0.0):
        raise AdapterValidationError(f"{name} must contain finite, non-negative meter values")
    return result


def _matrix(value: Any, shape: tuple[int, int], name: str) -> np.ndarray:
    matrix = _require_array(value, name).astype(np.float32, copy=False)
    if matrix.shape != shape:
        raise AdapterValidationError(f"{name} must have shape {shape}, got {matrix.shape}")
    if not np.all(np.isfinite(matrix)):
        raise AdapterValidationError(f"{name} must contain only finite values")
    return matrix


class BehaviorR1ProAdapter:
    """Convert a plain R1 Pro raw-observation dict into the unified planner schema."""

    def to_planner_observation(self, raw_obs: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(raw_obs, Mapping):
            raise AdapterValidationError(f"raw_obs must be a mapping, got {type(raw_obs).__name__}")
        actual_keys = set(raw_obs)
        if actual_keys != set(RAW_OBSERVATION_KEYS):
            raise AdapterValidationError(
                f"raw_obs keys must be {sorted(RAW_OBSERVATION_KEYS)}, got {sorted(actual_keys)}"
            )
        if not isinstance(raw_obs["prompt"], str):
            raise AdapterValidationError("prompt must be a string")

        rgbd: dict[str, np.ndarray] = {}
        intrinsics: dict[str, np.ndarray] = {}
        extrinsics: dict[str, np.ndarray] = {}
        for planner_camera, (rgb_key, depth_key, intrinsic_key, extrinsic_key) in _CAMERA_FIELDS.items():
            rgb = _rgb_float32(raw_obs[rgb_key], rgb_key)
            depth = _depth_meters(raw_obs[depth_key], rgb.shape[0], rgb.shape[1], depth_key)
            rgbd[planner_camera] = np.concatenate((rgb, depth[..., np.newaxis]), axis=2).astype(np.float32, copy=False)
            intrinsics[planner_camera] = _matrix(raw_obs[intrinsic_key], (3, 3), intrinsic_key)
            extrinsics[planner_camera] = _matrix(raw_obs[extrinsic_key], (4, 4), extrinsic_key)

        state_components = []
        for state_key in _STATE_FIELDS:
            component = _require_array(raw_obs[state_key], state_key).astype(np.float32, copy=False).reshape(-1)
            expected_size = STATE_COMPONENT_SIZES[state_key]
            if component.size != expected_size:
                raise AdapterValidationError(f"{state_key} must have {expected_size} values, got {component.size}")
            if not np.all(np.isfinite(component)):
                raise AdapterValidationError(f"{state_key} must contain only finite values")
            state_components.append(component)
        state = np.concatenate(state_components).astype(np.float32, copy=False)
        if state.shape != (STATE_DIM,):
            raise AdapterValidationError(f"state must have shape {(STATE_DIM,)}, got {state.shape}")

        return {
            "rgbd": rgbd,
            "intrinsics": intrinsics,
            "extrinsics": extrinsics,
            "state": state,
            "prompt": raw_obs["prompt"],
        }

    __call__ = to_planner_observation
