"""Deprojection of planner-camera RGBD into robot-base-frame point clouds.

Pure NumPy, no simulator imports. The planner observation schema
(``protocol.py``) carries one RGBD image plus 3x3 intrinsics and a 4x4
``T_base_camera`` extrinsic per camera, which is enough to reconstruct a
per-camera point cloud expressed in the R1 Pro base frame. Camera-frame
coordinates follow the protocol's RDF convention (right, down, forward):

    p_cam = K^-1 * [u * d, v * d, d]
    p_base = R @ p_cam + t        with (R, t) from T_base_camera

Only the right wrist camera is exposed for now; the same primitives work for
the remaining cameras once they are needed.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from protocol import validate_planner_observation

RIGHT_WRIST_CAMERA = "right_wrist"


def deproject_depth(depth: np.ndarray, K: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Back-project a depth image into the camera frame.

    Args:
        depth: float32 H x W image of per-pixel distances in meters.
        K: float32 3 x 3 camera intrinsics [[fx, 0, cx], [0, fy, cy], [0, 0, 1]].

    Returns:
        (points_camera, valid): points_camera is a float32 H x W x 3 array of
        camera-frame coordinates in meters (zero where invalid), and valid is
        a bool H x W mask of pixels with finite, positive depth.
    """
    depth = np.asarray(depth, dtype=np.float32)
    K = np.asarray(K, dtype=np.float32)
    if depth.ndim != 2 or depth.shape[0] == 0 or depth.shape[1] == 0:
        raise ValueError(f"depth must be a non-empty H x W image, got {depth.shape}")
    if K.shape != (3, 3):
        raise ValueError(f"K must have shape (3, 3), got {K.shape}")
    fx, fy = float(K[0, 0]), float(K[1, 1])
    cx, cy = float(K[0, 2]), float(K[1, 2])
    if fx <= 0.0 or fy <= 0.0:
        raise ValueError(f"K focal lengths must be positive, got fx={fx}, fy={fy}")

    height, width = depth.shape
    u = np.broadcast_to(np.arange(width, dtype=np.float32), (height, width))
    v = np.broadcast_to(np.arange(height, dtype=np.float32)[:, None], (height, width))

    points_camera = np.empty((height, width, 3), dtype=np.float32)
    points_camera[..., 0] = (u - cx) * depth / fx
    points_camera[..., 1] = (v - cy) * depth / fy
    points_camera[..., 2] = depth

    valid = np.isfinite(depth) & (depth > 0.0)
    points_camera[~valid] = 0.0
    return points_camera, valid


def to_base_frame(points_camera: np.ndarray, T_base_camera: np.ndarray) -> np.ndarray:
    """Express camera-frame points in the robot base frame.

    Args:
        points_camera: float32 ... x 3 camera-frame coordinates in meters.
        T_base_camera: float32 4 x 4 homogeneous transform such that
            ``X_base = T_base_camera @ X_camera_RDF``.

    Returns:
        float32 ... x 3 base-frame coordinates in meters.
    """
    points_camera = np.asarray(points_camera, dtype=np.float32)
    T_base_camera = np.asarray(T_base_camera, dtype=np.float32)
    if points_camera.shape[-1] != 3:
        raise ValueError(f"points_camera must have last dimension 3, got {points_camera.shape}")
    if T_base_camera.shape != (4, 4):
        raise ValueError(f"T_base_camera must have shape (4, 4), got {T_base_camera.shape}")
    rotation = T_base_camera[:3, :3]
    translation = T_base_camera[:3, 3]
    return (points_camera @ rotation.T) + translation


def right_wrist_pointcloud(observation: Mapping[str, Any]) -> dict[str, Any]:
    """Deproject the right wrist camera of a planner observation into base frame.

    Args:
        observation: a validated planner observation (see ``protocol.py``).

    Returns:
        dict with ``frame`` ("base"), ``camera`` ("right_wrist"),
        ``num_points``, ``points`` (float32 N x 3 meters), and ``colors``
        (float32 N x 3 RGB in [0, 1]) for the valid-depth pixels.
    """
    validate_planner_observation(observation)
    rgbd = np.asarray(observation["rgbd"][RIGHT_WRIST_CAMERA], dtype=np.float32)
    depth = rgbd[..., 3]
    K = np.asarray(observation["intrinsics"][RIGHT_WRIST_CAMERA], dtype=np.float32)
    T_base_camera = np.asarray(observation["extrinsics"][RIGHT_WRIST_CAMERA], dtype=np.float32)

    points_camera, valid = deproject_depth(depth, K)
    points_base = to_base_frame(points_camera, T_base_camera)
    if not np.all(np.isfinite(points_base[valid])):
        raise ValueError("deprojected points must contain only finite values")

    return {
        "frame": "base",
        "camera": RIGHT_WRIST_CAMERA,
        "num_points": int(valid.sum()),
        "points": points_base[valid],
        "colors": rgbd[valid, :3],
    }
