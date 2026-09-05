"""Common planner contracts independent of any simulator or backend."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class Planner(Protocol):
    """Structural interface consumed by the WebSocket server."""

    def infer(self, obs: Mapping[str, Any]) -> dict[str, Any]:
        """Return a planner result, currently ``{'actions': ndarray}``."""
