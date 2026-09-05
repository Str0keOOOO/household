"""A small smooth planner used only to verify the transport contract."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np


class MockPlanner:
    """Return a deterministic, low-amplitude smooth action chunk.

    The values are deliberately small because this class is only a transport
    smoke-test backend. The BEHAVIOR rollout may execute the returned chunk in
    simulation, so the amplitude stays well below the normalized action limits.
    """

    def __init__(
        self,
        action_chunk_size: int = 4,
        action_dim: int = 23,
        active_indices: tuple[int, ...] | None = None,
        amplitude: float = 0.02,
        phase_step: float = 0.18,
    ) -> None:
        if action_chunk_size <= 0 or action_dim <= 0:
            raise ValueError("action_chunk_size and action_dim must be positive")
        if amplitude < 0.0 or phase_step <= 0.0:
            raise ValueError("amplitude must be non-negative and phase_step must be positive")
        self._action_chunk_size = action_chunk_size
        self._action_dim = action_dim
        if active_indices is None:
            active_indices = tuple(range(action_dim))
        if len(set(active_indices)) != len(active_indices) or any(
            index < 0 or index >= action_dim for index in active_indices
        ):
            raise ValueError("active_indices must be unique action indices in range")
        self._active_indices = np.asarray(active_indices, dtype=np.intp)
        self._amplitude = np.float32(amplitude)
        self._phase_step = np.float32(phase_step)
        self._phase = np.float32(0.0)

    def infer(self, obs: Mapping[str, Any]) -> dict[str, np.ndarray]:
        del obs
        # Consecutive chunks continue the same phase, so the first row of the
        # next chunk follows smoothly from the last row of the previous one.
        time = self._phase + self._phase_step * np.arange(self._action_chunk_size, dtype=np.float32)
        joint_phase = np.float32(0.11) * np.arange(len(self._active_indices), dtype=np.float32)
        actions = np.zeros((self._action_chunk_size, self._action_dim), dtype=np.float32)
        actions[:, self._active_indices] = self._amplitude * np.sin(time[:, None] + joint_phase[None, :])
        self._phase = np.float32(self._phase + self._phase_step * self._action_chunk_size)
        return {"actions": actions}
