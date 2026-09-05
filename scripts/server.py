#!/usr/bin/env python3
"""Serve the first unified planner protocol; only deterministic mock mode exists."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CORE_SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(CORE_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_SOURCE_ROOT))

from planner.mock import MockPlanner
from rerun_sink import RerunSink
from serving.logging_utils import tee_output
from serving.websocket_server import PlannerWebSocketServer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mock", action="store_true", help="Serve the smooth low-amplitude MockPlanner")
    parser.add_argument("--host", default="0.0.0.0", help="Listen address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Listen port (default: 8000)")
    parser.add_argument("--rerun-dir", type=Path, default=None, help="Rerun .rrd output directory")
    parser.add_argument(
        "--no-rerun",
        action="store_true",
        help="Disable Rerun recording of observations (default: record under runs/rerun)",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=Path(os.environ["PLANNER_LOG_PATH"]) if os.environ.get("PLANNER_LOG_PATH") else None,
        help="Optional log file mirrored to the terminal (server logs otherwise stay in the terminal)",
    )
    args = parser.parse_args()
    if not args.mock:
        parser.error("only --mock is implemented in the first communication-interface version")
    if not 1 <= args.port <= 65535:
        parser.error("--port must be in [1, 65535]")
    return args


def _make_recorder(args: argparse.Namespace):
    if args.no_rerun:
        return None
    output_dir = args.rerun_dir if args.rerun_dir is not None else REPOSITORY_ROOT / "runs" / "rerun"
    try:
        recorder = RerunSink(output_dir)
    except (ImportError, RuntimeError) as exc:
        print(f"Rerun recording disabled: {exc}", flush=True)
        return None
    print(f"Recording planner observations to {recorder.path}", flush=True)
    return recorder.log


def main() -> None:
    args = parse_args()
    planner = MockPlanner(action_chunk_size=4, action_dim=12)
    server = PlannerWebSocketServer(
        planner,
        host=args.host,
        port=args.port,
        on_observation=_make_recorder(args),
    )
    if args.log_file is None:
        server.serve_forever()
        return
    with tee_output(args.log_file):
        server.serve_forever()


if __name__ == "__main__":
    main()
