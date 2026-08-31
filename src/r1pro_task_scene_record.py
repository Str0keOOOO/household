#!/usr/bin/env python3
"""Record an initialized BEHAVIOR task scene with R1 Pro, without robot actions."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

# OmniGibson reads this macro when imported.
os.environ.setdefault("OMNIGIBSON_HEADLESS", "1")

import imageio.v2 as imageio
import numpy as np
import torch as th
import yaml

import omnigibson as og
from omnigibson.macros import gm
from omnigibson.utils.transform_utils import mat2quat


# A small third-person orbit in the R1 Pro body frame: x is forward and y is
# left. A body-frame orbit avoids placing the viewer on the far side of a wall
# when tasks start in different rooms of a house.
CAMERA_OFFSETS = np.array(
    [
        [-2.20, -1.20, 1.40],
        [-2.10, -1.15, 1.35],
        [-2.20, -1.10, 1.40],
    ],
    dtype=np.float32,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record an initialized R1 Pro BEHAVIOR task scene; no robot action is sent."
    )
    parser.add_argument("--task", required=True, help="Canonical BEHAVIOR activity name")
    parser.add_argument("--scene", required=True, help="OmniGibson scene model name")
    parser.add_argument("--output", required=True, type=Path, help="MP4 path to create")
    parser.add_argument(
        "--online-object-sampling",
        action="store_true",
        help="Create task objects online instead of loading a pre-sampled task instance",
    )
    parser.add_argument("--frames", type=int, default=30, help="Frames to record (default: 30)")
    parser.add_argument("--fps", type=int, default=10, help="Output FPS (default: 10)")
    parser.add_argument("--width", type=int, default=640, help="Viewer width (default: 640)")
    parser.add_argument("--height", type=int, default=360, help="Viewer height (default: 360)")
    args = parser.parse_args()
    for name in ("frames", "fps", "width", "height"):
        if getattr(args, name) <= 0:
            parser.error(f"--{name} must be positive")
    if args.output.suffix.lower() != ".mp4":
        parser.error("--output must end in .mp4")
    return args


def frame_from_camera(camera) -> np.ndarray:
    frame = camera.get_obs()[0]["rgb"][:, :, :3]
    if hasattr(frame, "detach"):
        frame = frame.detach().cpu().numpy()
    return np.asarray(frame, dtype=np.uint8)


def interpolate_camera_offset(frame_index: int, total_frames: int) -> np.ndarray:
    """Interpolate the three overview offsets into one slow deterministic orbit."""
    progress = 0.0 if total_frames <= 1 else frame_index / (total_frames - 1)
    scaled = progress * (len(CAMERA_OFFSETS) - 1)
    low = min(int(scaled), len(CAMERA_OFFSETS) - 2)
    blend = scaled - low
    return (1.0 - blend) * CAMERA_OFFSETS[low] + blend * CAMERA_OFFSETS[low + 1]


def to_numpy(value) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    return np.asarray(value, dtype=np.float32)


def task_view_context(env) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Return R1 Pro pose and the instantiated non-system task-object names."""
    robot_position, robot_orientation = env.robots[0].get_position_orientation()
    object_names = []

    for entity in env.task.object_scope.values():
        if not entity.exists or entity.is_system or entity.wrapped_obj is env.robots[0]:
            continue
        try:
            entity.wrapped_obj.get_position_orientation()
        except (AttributeError, RuntimeError):
            continue
        object_names.append(entity.name or entity.bddl_inst)

    return to_numpy(robot_position), to_numpy(robot_orientation), object_names


def third_person_camera_pose(
    robot_position: np.ndarray, robot_orientation: np.ndarray, frame_index: int, total_frames: int
) -> tuple[np.ndarray, np.ndarray]:
    """Return a third-person camera pose that looks at R1 Pro's torso."""
    x, y, z, w = robot_orientation
    forward = np.array(
        [1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y + z * w), 0.0], dtype=np.float32
    )
    forward /= np.linalg.norm(forward)
    left = np.array([-forward[1], forward[0], 0.0], dtype=np.float32)
    offset = interpolate_camera_offset(frame_index, total_frames)
    camera_position = robot_position + forward * offset[0] + left * offset[1]
    camera_position[2] += offset[2]
    target = robot_position + np.array([0.0, 0.0, 1.0], dtype=np.float32)
    return camera_position, target


def look_at_quaternion(camera_position: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Return an [x, y, z, w] camera quaternion looking from position to target."""
    forward = target - camera_position
    forward /= np.linalg.norm(forward)
    world_up = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    right = np.cross(forward, world_up)
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    rotation = np.column_stack((right, up, -forward))
    return to_numpy(mat2quat(th.tensor(rotation, dtype=th.float32)))


def online_task_config(args: argparse.Namespace) -> tuple[dict, list[str] | None]:
    """Build the task configuration used by OmniGibson's official sampler."""
    whitelist = None
    blacklist = None
    room_types = None
    behavior_root = os.environ.get("BEHAVIOR_ROOT")
    if behavior_root:
        list_path = Path(behavior_root) / "OmniGibson" / "omnigibson" / "sampling" / "task_custom_lists.json"
        if list_path.is_file():
            custom_lists = json.loads(list_path.read_text(encoding="utf-8"))
            task_settings = custom_lists.get(args.task, {})
            if isinstance(task_settings, dict):
                room_types = task_settings.get("room_types")
                scene_settings = task_settings.get(args.scene, {})
                if isinstance(scene_settings, dict):
                    whitelist = scene_settings.get("whitelist")
                    blacklist = scene_settings.get("blacklist")

    task_config = {
        "type": "BehaviorTask",
        "activity_name": args.task,
        "activity_definition_id": 0,
        "activity_instance_id": 0,
        "online_object_sampling": True,
        "use_presampled_robot_pose": False,
        "sampling_whitelist": whitelist,
        "sampling_blacklist": blacklist,
    }
    return task_config, room_types


def create_online_sampling_environment(config: dict, args: argparse.Namespace):
    """Create and sample a task using OmniGibson's documented two-stage flow."""
    task_config, room_types = online_task_config(args)
    config.pop("task", None)
    config["scene"]["load_room_types"] = room_types
    config["robots"][0]["obs_modalities"] = []
    config["robots"][0]["default_reset_mode"] = "untuck"
    config["robots"][0]["position"] = [-50.0, -50.0, -50.0]

    # sample_b1k_tasks.py enables transition rules only while the base scene is
    # created, then dynamically attaches the BehaviorTask while simulation is
    # stopped. Loading it directly as an environment task leaves unpopulated
    # BDDL entities in the initial observation space.
    with gm.unlocked():
        gm.ENABLE_TRANSITION_RULES = True
        try:
            env = og.Environment(configs=config)
        finally:
            gm.ENABLE_TRANSITION_RULES = False

    for obj in env.scene.objects:
        obj.keep_still()
    env.scene.update_initial_file()
    og.sim.stop()

    env.task_config.clear()
    env.task_config.update(task_config)
    env._load_task()
    if env.task.feedback is not None:
        raise RuntimeError(f"Online sampling rejected {args.task}: {env.task.feedback}")

    og.sim.play()
    env.task.reset(env)
    for _ in range(4):
        og.sim.step()
    return env


def main() -> None:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    gm.ENABLE_OBJECT_STATES = True
    gm.USE_GPU_DYNAMICS = False

    config_path = Path(og.example_config_path) / "r1pro_behavior.yaml"
    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    config["scene"]["scene_model"] = args.scene
    config["render"]["viewer_width"] = args.width
    config["render"]["viewer_height"] = args.height

    env = None
    writer = None
    try:
        if args.online_object_sampling:
            env = create_online_sampling_environment(config=config, args=args)
        else:
            config["task"]["activity_name"] = args.task
            config["task"]["activity_definition_id"] = 0
            config["task"]["activity_instance_id"] = 0
            config["task"]["online_object_sampling"] = False
            config["task"]["use_presampled_robot_pose"] = True
            env = og.Environment(configs=config)
            env.reset()
        camera = og.sim.viewer_camera
        robot_position, robot_orientation, object_names = task_view_context(env)
        print(
            f"Task camera robot={robot_position.tolist()} objects={object_names}",
            flush=True,
        )

        # The viewer sensor observes a new pose after a simulator tick. This
        # directly follows OmniGibson's CameraMover recording utility and does
        # not call env.step() or send a robot action.
        initial_position, initial_target = third_person_camera_pose(
            robot_position, robot_orientation, 0, args.frames
        )
        camera.set_position_orientation(
            position=initial_position, orientation=look_at_quaternion(initial_position, initial_target)
        )
        og.sim.step()

        writer = imageio.get_writer(args.output, fps=args.fps, macro_block_size=1)
        for index in range(args.frames):
            position, target = third_person_camera_pose(robot_position, robot_orientation, index, args.frames)
            camera.set_position_orientation(
                position=position, orientation=look_at_quaternion(position, target)
            )
            og.sim.step()
            writer.append_data(frame_from_camera(camera))
    finally:
        if writer is not None:
            writer.close()
        if env is not None:
            og.shutdown()

    print(
        f"Saved task scene video: task={args.task} scene={args.scene} "
        f"online_object_sampling={args.online_object_sampling} output={args.output}",
        flush=True,
    )


if __name__ == "__main__":
    main()
