#!/usr/bin/env python3
"""Record a finite synchronous BEHAVIOR rollout.

Each cycle extracts one observation, blocks in the planner, then executes the
complete returned action chunk locally before collecting another observation.
The planner connection remains open for the whole rollout.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from pathlib import Path

os.environ.setdefault("OMNIGIBSON_HEADLESS", "1")

import imageio.v2 as imageio
import numpy as np
import yaml

from protocol import validate_planner_observation
from serving.websocket_client import PlannerWebSocketClient
from serving.logging_utils import tee_output

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



def _default_output(root: Path) -> Path:
    runs_root = Path(os.environ.get("BEHAVIOR_RUNS_PATH", root / "runs"))
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return runs_root / "videos" / f"heating-food-up-rollout-{stamp}.mp4"


def _default_log_file(root: Path) -> Path:
    runs_root = Path(os.environ.get("BEHAVIOR_RUNS_PATH", root / "runs"))
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return runs_root / "logs" / f"rollout-{stamp}.log"


def parse_args() -> argparse.Namespace:
    root = project_root()
    parser = argparse.ArgumentParser(
        description="Record a finite synchronous BEHAVIOR R1 Pro planner rollout."
    )
    parser.add_argument("--task", default=DEFAULT_TASK, help=f"BEHAVIOR activity (default: {DEFAULT_TASK})")
    parser.add_argument("--scene", default=DEFAULT_SCENE, help=f"OmniGibson scene model (default: {DEFAULT_SCENE})")
    parser.add_argument("--scene-file", type=Path, default=_default_instance(root))
    parser.add_argument("--initialization-config", type=Path, default=root / "heating_food_up" / "config.json")
    parser.add_argument("--output", type=Path, default=None, help="MP4 output (default: behavior runs/videos/UTC.mp4)")
    parser.add_argument("--log-file", type=Path, default=None, help="Log file (default: behavior runs/logs/UTC.log)")
    parser.add_argument("--planner-uri", default="ws://127.0.0.1:8000", help="Planner WebSocket URI")
    parser.add_argument("--prompt", default=DEFAULT_TASK, help="Task prompt sent to the planner")
    parser.add_argument("--robot-posture", choices=("tuck", "untuck"), default="tuck")
    parser.add_argument("--frames", type=int, default=200, help="Number of complete plan/execute cycles")
    parser.add_argument("--fps", type=int, default=20, help="Output video FPS")
    parser.add_argument(
        "--observation-only",
        action="store_true",
        help="Stop cleanly after one robot.get_obs() call; do not contact the planner",
    )
    parser.add_argument(
        "--warmup-frames",
        type=int,
        default=0,
        help="Deprecated; camera positioning already performs required render settling",
    )
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument(
        "--camera-view",
        choices=CAMERA_VIEW_CHOICES,
        default="near_right",
    )
    args = parser.parse_args()
    for name in ("frames", "fps", "width", "height"):
        if getattr(args, name) <= 0:
            parser.error(f"--{name} must be positive")
    # Keep accepting the old flag for command-line compatibility. It no
    # longer inserts render ticks, but a negative value is still a typo.
    if args.warmup_frames < 0:
        parser.error("--warmup-frames must be non-negative")
    if args.output is None:
        args.output = _default_output(root)
    if args.log_file is None:
        args.log_file = _default_log_file(root)
    if args.output.suffix.lower() != ".mp4":
        parser.error("--output must end in .mp4")
    # Isaac Sim forwards Python's remaining argv to Kit at application launch.
    # These are rollout-only flags, so they must not become Kit arguments.
    sys.argv[:] = [sys.argv[0]]
    return args


def _run(args: argparse.Namespace) -> None:
    root = project_root()
    args.scene_file = args.scene_file.resolve()
    args.initialization_config = args.initialization_config.resolve()
    args.output = args.output.resolve()
    ensure_task_instance(root, args.scene_file, args.initialization_config)

    # Importing OmniGibson is deliberately delayed until after argument and
    # template handling. Importing this module never starts Isaac Sim itself.
    import omnigibson as og
    import omnigibson.lazy as lazy

    # These helpers contain the existing task initialization and generic camera
    # selection logic; they do not cross the planner boundary.
    try:
        from .scene_utils import apply_scene_initialization, frame_from_camera, position_task_camera
    except ImportError:
        from scene_utils import apply_scene_initialization, frame_from_camera, position_task_camera

    env = None
    writer = None
    client = PlannerWebSocketClient(args.planner_uri)
    adapter = BehaviorR1ProAdapter()
    try:
        print("stage=environment_construct", flush=True)
        env = build_environment(og, yaml, args)
        print("stage=environment_ready", flush=True)
        renderer_settings = lazy.carb.settings.get_settings()
        renderer_settings.set("/rtx/rendermode", "RealTimePathTracing")
        renderer_settings.set_int("/rtx/post/dlss/execMode", 2)
        renderer_settings.set_bool("/rtx/pathtracing/fractionalCutoutOpacity", True)

        # Environment construction runs post_play_load(), which already resets
        # the task. A second reset is both expensive and unsafe for this full
        # headless scene; apply the presentation state to that initial reset.
        pose_source = apply_scene_initialization(env, args.initialization_config, args.robot_posture)
        print("stage=scene_initialization_ready", flush=True)
        robot_position = np.asarray(env.robots[0].get_position_orientation()[0], dtype=np.float32)
        robot = env.robots[0]
        sensor_names = tuple(str(name) for name in getattr(robot, "_sensors", {}).keys())
        print(f"stage=robot_sensors_ready:{','.join(sensor_names)}", flush=True)
        if not sensor_names:
            raise RuntimeError(
                "R1 Pro was created without VisionSensor instances; "
                "check scene.include_robots=False and pre-environment sensor_config"
            )
        camera_label = position_task_camera(env, robot_position, args.camera_view, verbose=False)
        print("stage=overview_camera_ready", flush=True)
        print("stage=before_usd_camera_access", flush=True)
        observation_collector = R1ProObservationCollector(
            robot,
            stage=og.sim.stage,
            usd_geom=lazy.pxr.UsdGeom,
            on_stage=lambda marker: print(marker, flush=True),
        )
        print("stage=observation_collector_ready", flush=True)
        camera = og.sim.viewer_camera
        print(
            f"Initialized task={args.task} scene={args.scene} pose={pose_source} camera={camera_label}",
            flush=True,
        )

        args.output.parent.mkdir(parents=True, exist_ok=True)
        for cycle_index in range(args.frames):
            first_cycle = cycle_index == 0
            raw_obs = observation_collector.collect(args.prompt)
            if args.observation_only:
                print("Observation-only check passed", flush=True)
                break
            if first_cycle:
                print("stage=before_adapter", flush=True)
            planner_obs = adapter.to_planner_observation(raw_obs)
            # Catch wire-contract errors locally, before opening the persistent
            # WebSocket. A server connection now means a valid observation is
            # ready to be sent.
            validate_planner_observation(planner_obs)
            if first_cycle:
                print("stage=adapter_ready", flush=True)
                print("stage=before_websocket_send", flush=True)
            client.connect()
            result = client.infer(planner_obs)
            if first_cycle:
                print("stage=after_websocket_send", flush=True)
            actions = result.get("actions")
            if (
                not isinstance(actions, np.ndarray)
                or actions.ndim != 2
                or actions.dtype != np.float32
                or actions.shape[1] != ACTION_DIM
            ):
                raise RuntimeError(f"planner returned invalid action chunk: {getattr(actions, 'shape', None)} / {getattr(actions, 'dtype', None)}")
            if cycle_index == 0:
                print(f"Planner connected; executing action chunks (shape={actions.shape}, dtype={actions.dtype})", flush=True)
            if writer is None:
                writer = imageio.get_writer(args.output, fps=args.fps, macro_block_size=1)
            print(
                f"cycle={cycle_index + 1}/{args.frames} actions="
                f"{np.array2string(actions, precision=4, suppress_small=True, separator=', ')}",
                flush=True,
            )
            done = execute_action_chunk(
                env,
                actions,
                on_step=lambda: writer.append_data(frame_from_camera(camera)),
            )
            if done:
                print("BEHAVIOR task terminated during action chunk", flush=True)
                break

        print(f"Recorded synchronous rollout to {args.output}", flush=True)
        print("Rollout finished", flush=True)
    finally:
        client.close()
        if writer is not None:
            writer.close()
        if env is not None:
            og.shutdown()


def main() -> int:
    args = parse_args()
    with tee_output(args.log_file):
        try:
            _run(args)
        except BaseException:
            # Keep the complete error inside the per-rollout log. The regular
            # Python traceback would otherwise be printed only after the tee
            # context restores stderr.
            import traceback

            traceback.print_exc()
            return 130 if isinstance(sys.exc_info()[1], KeyboardInterrupt) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
