#!/usr/bin/env python3
"""Long-lived BEHAVIOR R1 Pro episode server for the planner loop.

One process owns Isaac Sim and one loaded task scene across many episodes.
External ``episode`` clients request a bounded plan/execute round over a control
WebSocket; the task is reset between rounds instead of restarting the
simulator. Only the first request pays the full simulator cold start; later
rounds only pay ``env.reset()`` plus task re-initialization.

The planner connection is created once and kept open for the whole daemon
lifetime, exactly like the single-rollout entrypoint keeps one connection open
per run.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import threading
import time
import traceback
from collections import deque
from pathlib import Path

os.environ.setdefault("OMNIGIBSON_HEADLESS", "1")

import imageio.v2 as imageio
import numpy as np
import yaml
from websockets.exceptions import ConnectionClosed
from websockets.sync.server import ServerConnection, serve as serve_websocket

from serving.logging_utils import tee_output
from serving.serialization import packb, unpackb
from serving.websocket_client import PlannerWebSocketClient

try:
    from .adapter import ACTION_DIM, BehaviorR1ProAdapter
    from .env_utils import (
        CAMERA_VIEW_CHOICES,
        DEFAULT_SCENE,
        DEFAULT_TASK,
        _default_instance,
        build_environment,
        ensure_task_instance,
        execute_action_chunk,
        project_root,
    )
    from .r1pro_observation import R1ProObservationCollector
except ImportError:
    from adapter import ACTION_DIM, BehaviorR1ProAdapter
    from env_utils import (
        CAMERA_VIEW_CHOICES,
        DEFAULT_SCENE,
        DEFAULT_TASK,
        _default_instance,
        build_environment,
        ensure_task_instance,
        execute_action_chunk,
        project_root,
    )
    from r1pro_observation import R1ProObservationCollector
REQUEST_KEYS = frozenset(
    {"type", "cycles", "fps", "output", "prompt", "robot_posture", "camera_view"}
)


def parse_args() -> argparse.Namespace:
    root = project_root()
    parser = argparse.ArgumentParser(
        description="Serve one loaded BEHAVIOR scene across repeated episode requests."
    )
    parser.add_argument("--task", default=DEFAULT_TASK, help=f"BEHAVIOR activity (default: {DEFAULT_TASK})")
    parser.add_argument("--scene", default=DEFAULT_SCENE, help=f"OmniGibson scene model (default: {DEFAULT_SCENE})")
    parser.add_argument("--scene-file", type=Path, default=_default_instance(root))
    parser.add_argument("--initialization-config", type=Path, default=root / "heating_food_up" / "config.json")
    parser.add_argument("--robot-posture", choices=("tuck", "untuck"), default="untuck")
    parser.add_argument("--camera-view", choices=CAMERA_VIEW_CHOICES, default="near_right")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--host", default="0.0.0.0", help="Episode control listen address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8100, help="Episode control listen port (default: 8100)")
    parser.add_argument("--planner-uri", default="ws://127.0.0.1:8000", help="Planner WebSocket URI")
    parser.add_argument("--log-file", type=Path, default=None, help="Optional log file mirrored to the terminal")
    args = parser.parse_args()
    for name in ("width", "height"):
        if getattr(args, name) <= 0:
            parser.error(f"--{name} must be positive")
    if not 1 <= args.port <= 65535:
        parser.error("--port must be in [1, 65535]")
    if not args.scene_file.is_file():
        parser.error(f"scene file does not exist: {args.scene_file}")
    if not args.initialization_config.is_file():
        parser.error(f"initialization config does not exist: {args.initialization_config}")
    if args.log_file is None:
        runs_root = Path(os.environ.get("BEHAVIOR_RUNS_PATH", root / "runs"))
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        args.log_file = runs_root / "logs" / f"episode-server-{stamp}.log"
    # The control-server flags belong to this Python process, not Isaac Kit.
    sys.argv[:] = [sys.argv[0]]
    return args


class _EpisodeRequest:
    """One queued control request waiting for the simulator main loop."""

    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.reply: dict[str, object] | None = None
        self._event = threading.Event()

    def respond(self, reply: dict[str, object]) -> None:
        self.reply = reply
        self._event.set()

    def wait(self) -> None:
        self._event.wait()


class _PendingQueue:
    """Thread-safe FIFO consumed only by the simulator main loop."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: deque[_EpisodeRequest] = deque()

    def put(self, request: _EpisodeRequest) -> None:
        with self._lock:
            self._requests.append(request)

    def take(self) -> _EpisodeRequest | None:
        with self._lock:
            return self._requests.popleft() if self._requests else None


def _validate_payload(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict) or set(payload) != REQUEST_KEYS:
        raise ValueError(
            f"episode request must carry exactly {sorted(REQUEST_KEYS)}, got "
            f"{sorted(payload) if isinstance(payload, dict) else type(payload).__name__}"
        )
    if payload["type"] != "run_episode":
        raise ValueError(f"unsupported episode request type: {payload['type']}")
    cycles, fps = payload["cycles"], payload["fps"]
    if not isinstance(cycles, int) or isinstance(cycles, bool) or cycles <= 0:
        raise ValueError("cycles must be a positive integer")
    if not isinstance(fps, int) or isinstance(fps, bool) or fps <= 0:
        raise ValueError("fps must be a positive integer")
    output = payload["output"]
    if not isinstance(output, str) or not output.endswith(".mp4"):
        raise ValueError("output must be an absolute path ending in .mp4")
    prompt = payload["prompt"]
    if not isinstance(prompt, str):
        raise ValueError("prompt must be a string")
    posture = payload["robot_posture"]
    if posture not in ("tuck", "untuck"):
        raise ValueError("robot_posture must be 'tuck' or 'untuck'")
    camera_view = payload["camera_view"]
    if camera_view not in CAMERA_VIEW_CHOICES:
        raise ValueError(f"camera_view must be one of {CAMERA_VIEW_CHOICES}")
    return {
        "cycles": cycles,
        "fps": fps,
        "output": str(Path(output).resolve()),
        "prompt": prompt,
        "robot_posture": posture,
        "camera_view": camera_view,
    }


def _send_error(connection: ServerConnection, message: str, *, close: bool = True) -> None:
    try:
        connection.send(packb({"error": message}))
        if close:
            connection.close(code=1011, reason="episode request failed")
    except Exception:
        pass


def start_control_server(args: argparse.Namespace, pending: _PendingQueue) -> None:
    """Bind the episode control WebSocket in a daemon thread before the sim loads."""

    def handler(connection: ServerConnection) -> None:
        try:
            for message in connection:
                if not isinstance(message, bytes):
                    raise ValueError("episode protocol accepts binary MessagePack frames only")
                try:
                    payload = _validate_payload(unpackb(message))
                except Exception as exc:
                    error = "".join(traceback.format_exception_only(type(exc), exc)).strip()
                    _send_error(connection, error)
                    return
                request = _EpisodeRequest(payload)
                pending.put(request)
                print(
                    f"Episode request queued: cycles={payload['cycles']} output={payload['output']}",
                    flush=True,
                )
                request.wait()
                connection.send(packb(request.reply))
        except ConnectionClosed:
            return
        except Exception as exc:
            error = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            print(f"Episode control handler ended: {error}", flush=True)

    server = serve_websocket(handler, args.host, args.port, compression=None, max_size=None)
    # The simulator main loop runs on this thread; the control listener and each
    # connection run in daemon threads and are torn down with the process.
    threading.Thread(target=server.serve_forever, name="episode-control", daemon=True).start()
    print(f"Episode control server listening on ws://{args.host}:{args.port}", flush=True)


def run_episode(env, og, planner_client, adapter, args: argparse.Namespace, payload: dict[str, object], episode_index: int, *, reset: bool) -> dict[str, object]:
    """Execute one bounded plan/execute round and return its summary.

    ``reset`` is False for the first episode because the freshly built
    environment already carries its initial task state.
    """
    started = time.monotonic()
    cycles_requested = int(payload["cycles"])
    fps = int(payload["fps"])
    output = Path(str(payload["output"]))
    prompt = str(payload["prompt"])
    posture = str(payload["robot_posture"])
    camera_view = str(payload["camera_view"])

    try:
        from .scene_utils import apply_scene_initialization, frame_from_camera, position_task_camera
    except ImportError:
        from scene_utils import apply_scene_initialization, frame_from_camera, position_task_camera

    if reset:
        env.reset()
    pose_source = apply_scene_initialization(env, args.initialization_config, posture)
    robot = env.robots[0]
    robot_position = np.asarray(robot.get_position_orientation()[0], dtype=np.float32)
    camera_label = position_task_camera(env, robot_position, camera_view, verbose=False)
    camera = og.sim.viewer_camera
    # The collector resolves only fixed USD Camera prims and never adds a
    # VisionSensor modality or camera-params annotator after construction.
    import omnigibson.lazy as lazy

    observation_collector = R1ProObservationCollector(
        robot,
        stage=og.sim.stage,
        usd_geom=lazy.pxr.UsdGeom,
        on_stage=lambda marker: print(marker, flush=True),
    )

    planner_client.connect()
    output.parent.mkdir(parents=True, exist_ok=True)
    writer = imageio.get_writer(output, fps=fps, macro_block_size=1)
    cycles = 0
    done = False
    completed_cleanly = False
    try:
        for cycle_index in range(cycles_requested):
            raw_obs = observation_collector.collect(prompt)
            planner_obs = adapter.to_planner_observation(raw_obs)
            result = planner_client.infer(planner_obs)
            actions = result.get("actions")
            if (
                not isinstance(actions, np.ndarray)
                or actions.ndim != 2
                or actions.dtype != np.float32
                or actions.shape[1] != ACTION_DIM
            ):
                raise RuntimeError(
                    f"planner returned invalid action chunk: {getattr(actions, 'shape', None)} / {getattr(actions, 'dtype', None)}"
                )
            print(
                f"episode={episode_index} cycle={cycle_index + 1}/{cycles_requested} actions="
                f"{np.array2string(actions, precision=4, suppress_small=True, separator=', ')}",
                flush=True,
            )
            done = execute_action_chunk(
                env,
                actions,
                on_step=lambda: writer.append_data(frame_from_camera(camera)),
            )
            cycles = cycle_index + 1
            if done:
                print(f"BEHAVIOR task terminated during action chunk (episode={episode_index})", flush=True)
                break
        completed_cleanly = True
    finally:
        writer.close()
        if not completed_cleanly:
            # A partial recording cannot be a successful round result.
            try:
                output.unlink(missing_ok=True)
            except OSError:
                pass

    elapsed = time.monotonic() - started
    print(
        f"episode={episode_index} finished: reset={reset} pose={pose_source} camera={camera_label} "
        f"cycles={cycles}/{cycles_requested} done={done} wall={elapsed:.1f}s video={output}",
        flush=True,
    )
    return {"cycles": cycles, "done": done, "output": str(output), "reset": reset}


def serve(args: argparse.Namespace) -> None:
    root = project_root()
    args.scene_file = args.scene_file.resolve()
    args.initialization_config = args.initialization_config.resolve()
    ensure_task_instance(root, args.scene_file, args.initialization_config)

    pending = _PendingQueue()
    start_control_server(args, pending)

    planner_client = PlannerWebSocketClient(args.planner_uri)
    adapter = BehaviorR1ProAdapter()
    env = None
    og = None
    try:
        # Importing OmniGibson is deliberately delayed until after argument and
        # template handling, exactly like rollout.py. Importing this module
        # never starts Isaac Sim itself.
        import omnigibson as og

        print("Creating OmniGibson environment...", flush=True)
        env = build_environment(og, yaml, args)
        from omnigibson.lazy import carb

        renderer_settings = carb.settings.get_settings()
        renderer_settings.set("/rtx/rendermode", "RealTimePathTracing")
        renderer_settings.set_int("/rtx/post/dlss/execMode", 2)
        renderer_settings.set_bool("/rtx/pathtracing/fractionalCutoutOpacity", True)
        print("Environment ready; waiting for episode requests", flush=True)

        episode_index = 0
        while True:
            request = pending.take()
            if request is None:
                og.sim.render()
                time.sleep(1.0)
                continue
            episode_index += 1
            # Only the first round runs on the freshly built environment; any
            # later round resets the task first, even after a failed round.
            reset = episode_index > 1
            try:
                reply = run_episode(
                    env,
                    og,
                    planner_client,
                    adapter,
                    args,
                    request.payload,
                    episode_index,
                    reset=reset,
                )
            except Exception as exc:
                traceback.print_exc()
                error = "".join(traceback.format_exception_only(type(exc), exc)).strip()
                request.respond({"error": error})
            else:
                request.respond(reply)
    except KeyboardInterrupt:
        while True:
            pending_request = pending.take()
            if pending_request is None:
                break
            pending_request.respond({"error": "episode server stopped by Ctrl+C"})
        print("Episode server stopped by Ctrl+C", flush=True)
    finally:
        planner_client.close()
        if env is not None and og is not None:
            og.shutdown()


def main() -> None:
    args = parse_args()
    if args.log_file is None:
        serve(args)
        return
    with tee_output(args.log_file):
        serve(args)


if __name__ == "__main__":
    main()
