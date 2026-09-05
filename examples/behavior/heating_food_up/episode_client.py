#!/usr/bin/env python3
"""Request one bounded BEHAVIOR episode from the long-lived episode server.

This entrypoint is deliberately light: it imports neither OmniGibson nor Isaac
Sim, so every round starts in about a second instead of paying the multi-minute
simulator cold start. Start ``episode_server`` once, then call this command as
often as the outer harness needs another round; the server resets the loaded
task between requests.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
from pathlib import Path

from websockets.sync.client import connect

from serving.serialization import packb, unpackb


DEFAULT_TASK = "heating_food_up"
CAMERA_VIEW_CHOICES = (
    "near_right",
    "task_right",
    "near_left",
    "task_left",
    "side_right",
    "side_left",
    "behind",
    "auto",
)


def _default_output() -> Path:
    runs_root = Path(os.environ.get("BEHAVIOR_RUNS_PATH", Path.cwd() / "runs"))
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return runs_root / "videos" / f"episode-{stamp}.mp4"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ask the persistent episode server to run one bounded BEHAVIOR round."
    )
    parser.add_argument("--server-uri", default="ws://127.0.0.1:8100", help="Episode server WebSocket URI")
    parser.add_argument("--output", type=Path, default=None, help="MP4 output (default: behavior runs/videos/UTC.mp4)")
    parser.add_argument("--frames", type=int, default=200, help="Number of complete plan/execute cycles")
    parser.add_argument("--fps", type=int, default=20, help="Output video FPS")
    parser.add_argument("--prompt", default=DEFAULT_TASK, help="Task prompt sent to the planner")
    parser.add_argument("--robot-posture", choices=("tuck", "untuck"), default="tuck")
    parser.add_argument("--camera-view", choices=CAMERA_VIEW_CHOICES, default="near_right")
    args = parser.parse_args()
    for name in ("frames", "fps"):
        if getattr(args, name) <= 0:
            parser.error(f"--{name} must be positive")
    if args.output is None:
        args.output = _default_output()
    if args.output.suffix.lower() != ".mp4":
        parser.error("--output must end in .mp4")
    return args


def main() -> None:
    args = parse_args()
    request = {
        "type": "run_episode",
        "frames": args.frames,
        "fps": args.fps,
        "output": str(args.output.resolve()),
        "prompt": args.prompt,
        "robot_posture": args.robot_posture,
        "camera_view": args.camera_view,
    }
    print(
        f"Requesting episode from {args.server_uri}: frames={args.frames} fps={args.fps} "
        f"prompt={args.prompt!r} posture={args.robot_posture} camera={args.camera_view}",
        flush=True,
    )
    print(f"Output: {request['output']}", flush=True)
    with connect(args.server_uri, compression=None, max_size=None) as connection:
        connection.send(packb(request))
        response = connection.recv()
        if isinstance(response, str):
            raise RuntimeError(f"episode server returned a text error: {response}")
        result = unpackb(response)
        if not isinstance(result, dict):
            raise RuntimeError(f"episode server returned {type(result).__name__}, expected dict")
        if "error" in result:
            raise RuntimeError(f"episode server rejected request: {result['error']}")
        print(
            f"Episode finished: cycles={result['cycles']}/{args.frames} "
            f"done={result['done']} reset={result['reset']}",
            flush=True,
        )
        print(f"Output: {result['output']}", flush=True)


if __name__ == "__main__":
    main()
