"""Thin, simulator-agnostic boundary for AnyGrasp integration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, TypedDict

import numpy as np


class GraspCandidate(TypedDict):
    """The only grasp representation exposed outside the AnyGrasp adapter."""

    pose: np.ndarray
    score: float


class AnyGraspAdapter:
    """Translate unified RGB-D observations to plain grasp candidates.

    The actual AnyGrasp dependency is intentionally not imported here yet. A
    future implementation may keep the native model and tensor objects inside
    this class, but must return only ``GraspCandidate`` dictionaries.
    """

    def __init__(self, backend: Any | None = None) -> None:
        self._backend = backend

    def infer_candidates(
        self,
        planner_obs: Mapping[str, Any],
        *,
        camera: str = "right_wrist",
        top_k: int = 32,
    ) -> list[GraspCandidate]:
        del planner_obs, camera, top_k
        if self._backend is None:
            raise NotImplementedError("AnyGrasp backend integration is not implemented yet")
        raise NotImplementedError("AnyGrasp backend invocation is reserved for the next phase")

    __call__ = infer_candidates
