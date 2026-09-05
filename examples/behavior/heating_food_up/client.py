"""Reserved real BEHAVIOR R1 Pro planner client.

It does not create an OmniGibson application. A future initialized scene runner
can call ``infer_from_robot`` with its R1 Pro instance.
"""

from __future__ import annotations

from typing import Any

from serving.websocket_client import PlannerWebSocketClient

try:
    from .adapter import BehaviorR1ProAdapter
    from .r1pro_observation import collect_raw_obs
except ImportError:
    from adapter import BehaviorR1ProAdapter
    from r1pro_observation import collect_raw_obs


def infer_from_robot(robot: Any, prompt: str, uri: str = "ws://127.0.0.1:8000") -> dict[str, Any]:
    """Collect one initialized R1 Pro observation and query the planner once."""
    raw_obs = collect_raw_obs(robot, prompt)
    planner_obs = BehaviorR1ProAdapter().to_planner_observation(raw_obs)
    with PlannerWebSocketClient(uri) as client:
        return client.infer(planner_obs)


if __name__ == "__main__":
    raise SystemExit(
        "client.py is a future integration entrypoint; call infer_from_robot() from an initialized OmniGibson runner."
    )
