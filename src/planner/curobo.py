"""Thin, simulator-agnostic boundary for cuRobo planning."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np


class CuRoboPlanner:
    """Plan a joint trajectory from plain state, poses, and scene geometry."""

    def __init__(self, backend: Any | None = None) -> None:
        self._backend = backend

    def plan(
        self,
        state: np.ndarray,
        grasp_poses: Sequence[np.ndarray],
        scene_geometry: Mapping[str, Any],
    ) -> np.ndarray:
        del state, grasp_poses, scene_geometry
        if self._backend is None:
            raise NotImplementedError("cuRobo backend integration is not implemented yet")
        raise NotImplementedError("cuRobo backend invocation is reserved for the next phase")

    def infer(self, obs: Mapping[str, Any]) -> dict[str, np.ndarray]:
        """Reserve the common planner entrypoint for a future full pipeline."""
        del obs
        raise NotImplementedError("compose AnyGrasp, ranking, cuRobo, and retreat before enabling infer")
