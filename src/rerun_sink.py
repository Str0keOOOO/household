"""Incremental Rerun (.rrd) recording of planner observations.

Each ``log`` call appends one time step to the opened recording with the three
R1 Pro RGBD cameras (``base``, ``left_wrist``, ``right_wrist``) and the
right-wrist point cloud deprojected into the robot base frame. Replaying the
.rrd in the Rerun viewer scrubs through those steps on a ``step`` timeline.

The ``rerun`` import is deferred to ``__init__`` so the module stays
importable in environments that do not carry rerun-sdk.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from observation import right_wrist_pointcloud
from protocol import CAMERA_NAMES, validate_planner_observation


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
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self._path = output_dir / f"rerun-{stamp}.rrd"

        rr.init(app_id, spawn=False)
        rr.save(self._path)
        rr.log("world", rr.ViewCoordinates.RIGHT_HAND_Z_UP)
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
            entity = f"camera/{camera_name}"
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
        rr.log("pointcloud/right_wrist", rr.Points3D(positions, colors=rgba))
        self._step = step + 1
