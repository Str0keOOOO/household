"""Interface for safe post-grasp retreat planning."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np


class RetreatPlanner:
    """Plan a collision-safe retreat after an object has been grasped."""

    def plan(
        self,
        state: np.ndarray,
        grasp_pose: np.ndarray,
        scene_geometry: Mapping[str, Any],
    ) -> np.ndarray:
        del state, grasp_pose, scene_geometry
        raise NotImplementedError("retreat planning is not implemented yet")
