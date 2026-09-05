"""Incremental Rerun (.rrd) recording of planner observations.

Each ``log`` call appends one time step to the opened recording with the three
R1 Pro RGBD cameras (``base``, ``left_wrist``, ``right_wrist``) and the
right-wrist point cloud deprojected into the robot base frame. Camera frusta
and point clouds share the same ``base`` root frame. Replaying the .rrd in
the Rerun viewer scrubs through those steps on a ``step`` timeline.

The ``rerun`` import is deferred to ``__init__`` so the module stays
importable in environments that do not carry rerun-sdk.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import numpy as np

from observation import right_wrist_pointcloud
from protocol import CAMERA_NAMES, validate_planner_observation


# Keep the three physical camera frames easy to distinguish in a 3D View.
# The colors only affect visualization; the wire protocol remains unchanged.
_CAMERA_COLORS = {
    "base": [70, 190, 255, 255],
    "left_wrist": [80, 220, 120, 255],
    "right_wrist": [255, 165, 70, 255],
}
_CAMERA_LABELS = {
    "base": "ZED / base",
    "left_wrist": "left wrist",
    "right_wrist": "right wrist",
}


class RerunSink:
    """One running recorder writing all observations to a single .rrd file."""

    def __init__(self, output_dir: Path, app_id: str = "household-planner") -> None:
        try:
            import rerun as rr
        except ImportError as exc:
            raise RuntimeError("rerun-sdk is not installed in this environment") from exc
        self._rr = rr

        output_dir = Path(output_dir).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d-%H%M%S")
        # ``runs/rerun`` already conveys the recording type, so a compact
        # Beijing-time timestamp is enough to identify each recording.
        self._path = output_dir / f"{stamp}.rrd"

        rr.init(app_id, spawn=False)
        rr.save(self._path)
        # This recording intentionally visualizes the robot-local base frame,
        # not a simulator world frame. The wire protocol defines every camera
        # extrinsic as T_base_camera and the reconstructed point cloud as
        # p_base, so keeping the root as ``base`` prevents an implicit mix of
        # coordinate systems.
        rr.log("base", rr.ViewCoordinates.RIGHT_HAND_Z_UP)
        self._log_base_axes()
        self._camera_models_logged: set[str] = set()
        self._step = 0

    @property
    def path(self) -> Path:
        return self._path

    def log(self, observation: Mapping[str, Any]) -> None:
        """Validate and record one planner observation as the next time step."""
        validate_planner_observation(observation)
        rr = self._rr
        step = self._step
        rr.set_time("step", sequence=step)

        for camera_name in CAMERA_NAMES:
            rgbd = np.asarray(observation["rgbd"][camera_name], dtype=np.float32)
            rgb = np.clip(rgbd[..., :3] * 255.0, 0.0, 255.0).astype(np.uint8)
            depth = rgbd[..., 3]
            entity = f"base/cameras/{camera_name}"
            self._log_camera_model(
                camera_name=camera_name,
                entity=entity,
                intrinsic=observation["intrinsics"][camera_name],
                image_shape=rgbd.shape[:2],
            )
            rr.log(f"{entity}/rgb", rr.Image(rgb))
            rr.log(f"{entity}/depth", rr.DepthImage(depth, meter=1.0))
            transform = np.asarray(observation["extrinsics"][camera_name], dtype=np.float64)
            rr.log(entity, rr.Transform3D(translation=transform[:3, 3], mat3x3=transform[:3, :3]))

        cloud = right_wrist_pointcloud(observation)
        positions = cloud["points"]
        rgba = np.concatenate(
            (np.clip(cloud["colors"] * 255.0, 0.0, 255.0).astype(np.uint8), np.full((len(positions), 1), 255, np.uint8)),
            axis=1,
        )
        rr.log("base/pointcloud/right_wrist", rr.Points3D(positions, colors=rgba))
        self._step = step + 1

    def _log_camera_model(
        self,
        *,
        camera_name: str,
        entity: str,
        intrinsic: Any,
        image_shape: tuple[int, int],
    ) -> None:
        """Log one static, colored camera frustum and its optical-center marker.

        The unified observation protocol uses ``RDF`` camera axes: positive X
        points right, positive Y points down, and positive Z points forward.
        The collector normalizes the USD Camera transform to this convention,
        which is also the convention used by depth backprojection. Declaring
        ``RDF`` therefore makes the Rerun frustum and reconstructed point
        cloud share exactly the same base-frame geometry.
        """
        if camera_name in self._camera_models_logged:
            return

        height, width = image_shape
        K = np.asarray(intrinsic, dtype=np.float32)
        color = _CAMERA_COLORS[camera_name]
        self._rr.log(
            entity,
            self._rr.Pinhole(
                image_from_camera=K,
                resolution=[width, height],
                camera_xyz=self._rr.ViewCoordinates.RDF,
                image_plane_distance=0.20,
                color=color,
                line_width=0.003,
            ),
            static=True,
        )
        self._rr.log(
            f"{entity}/optical_center",
            self._rr.Points3D(
                [[0.0, 0.0, 0.0]],
                radii=[0.025],
                colors=[color],
                labels=[_CAMERA_LABELS[camera_name]],
                show_labels=True,
            ),
            static=True,
        )
        self._camera_models_logged.add(camera_name)

    def _log_base_axes(self) -> None:
        """Draw a prominent, static R1 Pro base-frame triad in the 3D View.

        The BEHAVIOR R1 Pro asset places the left arm on +Y, the right arm on
        -Y, and the torso above the base on +Z. Together with its forward +X
        axis, this is the conventional right-handed robot base frame.
        """
        self._rr.log(
            "base/axes",
            self._rr.Arrows3D(
                origins=[[0.0, 0.0, 0.0]] * 3,
                vectors=[[0.60, 0.0, 0.0], [0.0, 0.60, 0.0], [0.0, 0.0, 0.60]],
                radii=[0.018, 0.018, 0.018],
                colors=[[255, 55, 55, 255], [55, 255, 80, 255], [70, 130, 255, 255]],
                labels=["RED +X: forward", "GREEN +Y: left", "BLUE +Z: up"],
                show_labels=True,
            ),
            static=True,
        )
        self._rr.log(
            "base/origin",
            self._rr.Points3D(
                [[0.0, 0.0, 0.0]],
                radii=[0.055],
                colors=[[255, 255, 255, 255]],
                labels=["R1 Pro base origin (0, 0, 0)"],
                show_labels=True,
            ),
            static=True,
        )
