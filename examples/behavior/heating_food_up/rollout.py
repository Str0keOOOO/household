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
import subprocess
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
    from .adapter import ACTION_DIM, SIM_ACTION_DIM, BehaviorR1ProAdapter
    from .r1pro_observation import R1ProObservationCollector
except ImportError:
    from adapter import ACTION_DIM, SIM_ACTION_DIM, BehaviorR1ProAdapter
    from r1pro_observation import R1ProObservationCollector


DEFAULT_TASK = "heating_food_up"
DEFAULT_SCENE = "house_single_floor"


def project_root() -> Path:
    """Return the independent BEHAVIOR Pixi project root."""
    return Path(os.environ.get("PIXI_PROJECT_ROOT", Path(__file__).resolve().parents[1])).resolve()


def _default_output(root: Path) -> Path:
    runs_root = Path(os.environ.get("BEHAVIOR_RUNS_PATH", root / "runs"))
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return runs_root / "videos" / f"heating-food-up-rollout-{stamp}.mp4"


def _default_log_file(root: Path) -> Path:
    runs_root = Path(os.environ.get("BEHAVIOR_RUNS_PATH", root / "runs"))
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return runs_root / "logs" / f"rollout-{stamp}.log"


def _default_instance(root: Path) -> Path:
    return (
        root
        / "data"
        / "omnigibson"
        / "local-task-instances"
        / DEFAULT_TASK
        / f"{DEFAULT_SCENE}_task_{DEFAULT_TASK}_0_0_template.json"
    )


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
        choices=("near_right", "task_right", "near_left", "task_left", "side_right", "side_left", "behind", "auto"),
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


def ensure_task_instance(root: Path, scene_file: Path, initialization_config: Path) -> None:
    """Create the local deterministic template when it has not been sampled."""
    if scene_file.is_file():
        return
    if not initialization_config.is_file():
        raise FileNotFoundError(f"initialization configuration does not exist: {initialization_config}")
    sampler = root / "heating_food_up" / "sample_task_instance.py"
    scene_file.parent.mkdir(parents=True, exist_ok=True)
    repository_root = root.parents[1]
    print(f"Task instance not found; sampling once into {scene_file}", flush=True)
    subprocess.run(
        [sys.executable, str(sampler), "--config", str(initialization_config), "--output", str(scene_file)],
        check=True,
        cwd=repository_root,
    )


def build_environment(og, yaml_module, args: argparse.Namespace):
    """Build the same initialized R1 Pro scene as ``record_scene.py``."""
    from omnigibson.macros import gm

    gm.ENABLE_OBJECT_STATES = True
    gm.USE_GPU_DYNAMICS = False
    with (Path(og.example_config_path) / "r1pro_behavior.yaml").open(encoding="utf-8") as file:
        config = yaml_module.safe_load(file)
    config["scene"]["scene_model"] = args.scene
    config["scene"]["load_room_types"] = None
    config["scene"]["scene_file"] = str(args.scene_file.resolve())
    # The BEHAVIOR scene template can contain a robot of its own.  When
    # ``include_robots`` is true, OmniGibson imports that robot and skips the
    # configured ``robots`` list entirely (see Environment._load_robots).  The
    # imported robot has no R1 Pro VisionSensor configuration, so get_obs()
    # would correctly return an empty dictionary.  Rollout owns the robot
    # configuration below, so make the scene object-only and instantiate the
    # configured R1 Pro exactly once.
    config["scene"]["include_robots"] = False
    config["render"]["viewer_width"] = args.width
    config["render"]["viewer_height"] = args.height
    robot_config = config["robots"][0]
    robot_config["default_reset_mode"] = args.robot_posture
    robot_config["obs_modalities"] = ["rgb", "depth"]
    robot_config["include_sensor_names"] = None
    robot_config["exclude_sensor_names"] = None
    # Declare every native VisionSensor modality before Environment creation.
    # Never add rgb / depth / camera_params after Isaac Sim has started.
    robot_config["sensor_config"] = {
        "VisionSensor": {
            "modalities": ["rgb", "depth"],
            "enabled": True,
            "sensor_kwargs": {
                "image_height": 128,
                "image_width": 128,
            },
        }
    }
    print(
        "stage=robot_sensor_config_ready "
        "scene.include_robots=False modalities=rgb,depth VisionSensor.enabled=True",
        flush=True,
    )
    config["task"].update(
        activity_name=args.task,
        activity_definition_id=0,
        activity_instance_id=0,
        online_object_sampling=False,
        use_presampled_robot_pose=False,
    )
    return og.Environment(configs=config)


def convert_planner_action_to_behavior(action: np.ndarray) -> np.ndarray:
    """Validate and copy one planner action for the BEHAVIOR environment.

    The planner contract is the 12-D ``ACTION_LAYOUT`` (torso + right arm +
    right gripper). OmniGibson's controller expects a 23-D scene action, so
    base and left-arm controls are held at zero until those planners are added.
    """
    action = np.asarray(action)
    if action.shape != (ACTION_DIM,) or action.dtype != np.float32:
        raise RuntimeError(
            f"planner action must have shape {(ACTION_DIM,)} and dtype float32, "
            f"got {action.shape} / {action.dtype}"
        )
    if not np.all(np.isfinite(action)):
        raise RuntimeError("planner action must contain only finite values")
    behavior_action = np.zeros((SIM_ACTION_DIM,), dtype=np.float32)
    behavior_action[3:7] = action[0:4]       # torso
    behavior_action[15:22] = action[4:11]    # right arm
    behavior_action[22] = action[11]         # right gripper
    return behavior_action


def execute_action_chunk(env, actions: np.ndarray, on_step=None) -> bool:
    """Execute every action in a chunk before collecting the next observation."""
    for action in actions:
        result = env.step(convert_planner_action_to_behavior(action))
        if on_step is not None:
            on_step()
        if isinstance(result, tuple) and len(result) >= 4 and bool(result[2] or result[3]):
            return True
    return False


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
    from omnigibson.macros import gm

    # These helpers contain the existing task initialization and generic camera
    # selection logic; they do not cross the planner boundary.
    try:
        from .record_scene import apply_scene_initialization, frame_from_camera, position_task_camera
    except ImportError:
        from record_scene import apply_scene_initialization, frame_from_camera, position_task_camera

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
        _, _, camera_label, _, _, _ = position_task_camera(env, robot_position, args.camera_view, verbose=False)
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
