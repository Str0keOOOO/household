"""Interface for household-specific grasp candidate ranking."""

from __future__ import annotations

from collections.abc import Sequence

from planner.anygrasp import GraspCandidate


class GraspRanker:
    """Rank plain AnyGrasp candidates using future reachability metrics."""

    def rank(self, candidates: Sequence[GraspCandidate]) -> list[GraspCandidate]:
        del candidates
        raise NotImplementedError("household grasp ranking is not implemented yet")
