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


# Camera offsets use an object's body frame: x is forward and y is left.  The
# recording intentionally contains three short static views (R1 Pro, the
# main fixture, and the smaller task objects) rather than an action rollout.
ROBOT_CAMERA_OFFSET = np.array([-2.10, -1.15, 1.35], dtype=np.float32)
# One installed legacy template does not include R1 Pro in its robot_poses
# metadata.  This position is the R1 Pro pose stored by a different local
# template in the same kitchen and is used only for a static camera preview.
FALLBACK_ROBOT_POSES = {
    "house_single_floor": (
        np.array([6.776428, -0.971100, 0.005005], dtype=np.float32),
        np.array([0.0, 0.0, -0.644101, 0.764941], dtype=np.float32),
    ),
}

# These fixture-relative offsets were calibrated against the three installed
# legacy templates. They keep the virtual camera in a
# visible room instead of behind the walls that surround many old fixtures.
CALIBRATED_FOCUS_OFFSETS = {
    "carrying_in_groceries": (
        np.array([4.0, 0.0, 1.55], dtype=np.float32),
        np.array([0.0, -4.0, 1.55], dtype=np.float32),
    ),
    "thawing_frozen_food": (
        np.array([-4.0, 0.0, 1.55], dtype=np.float32),
        np.array([0.0, -4.0, 1.55], dtype=np.float32),
    ),
    "canning_food": (
        np.array([-4.0, 0.0, 1.55], dtype=np.float32),
        np.array([0.0, -4.0, 1.55], dtype=np.float32),
    ),
}

FIXTURE_CATEGORIES = {"fridge", "microwave", "oven", "countertop", "cabinet", "bottom_cabinet"}


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


def to_numpy(value) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    return np.asarray(value, dtype=np.float32)


def task_view_context(env) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    """Return R1 Pro pose and instantiated non-system task-object context."""
    robot_position, robot_orientation = env.robots[0].get_position_orientation()
    objects = []

    for entity in env.task.object_scope.values():
        if not entity.exists or entity.is_system or entity.wrapped_obj is env.robots[0]:
            continue
        try:
            position, orientation = entity.wrapped_obj.get_position_orientation()
        except (AttributeError, RuntimeError):
            continue
        wrapped = entity.wrapped_obj
        objects.append(
            {
                "name": entity.name or entity.bddl_inst,
                "category": getattr(wrapped, "category", ""),
                "position": to_numpy(position),
                "orientation": to_numpy(orientation),
            }
        )

    return to_numpy(robot_position), to_numpy(robot_orientation), objects


def position_robot_for_recording(env, scene_name: str) -> str:
    """Place R1 Pro at the saved pose, or at a verified same-scene fallback."""
    robot = env.robots[0]
    presampled_poses = env.scene.get_task_metadata(key="robot_poses")
    if isinstance(presampled_poses, dict) and robot.model_name in presampled_poses:
        pose = presampled_poses[robot.model_name][0]
        position = to_numpy(pose["position"])
        orientation = to_numpy(pose["orientation"])
        source = "instance R1 Pro pose"
    elif scene_name in FALLBACK_ROBOT_POSES:
        position, orientation = FALLBACK_ROBOT_POSES[scene_name]
        source = "verified same-scene fallback pose"
    else:
        return "configured reset pose"

    robot.set_position_orientation(position=position, orientation=orientation)
    robot.keep_still()
    og.sim.step()
    return source


def planar_basis(orientation: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return horizontal forward and left unit vectors from an [x, y, z, w] quaternion."""
    x, y, z, w = orientation
    forward = np.array(
        [1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y + z * w), 0.0], dtype=np.float32
    )
    forward /= np.linalg.norm(forward)
    return forward, np.array([-forward[1], forward[0], 0.0], dtype=np.float32)


def object_camera_pose(
    target_position: np.ndarray, target_orientation: np.ndarray, offset: np.ndarray, target_height: float
) -> tuple[np.ndarray, np.ndarray]:
    """Return a camera pose targeting an R1 Pro or task object from its local side."""
    forward, left = planar_basis(target_orientation)
    camera_position = target_position + forward * offset[0] + left * offset[1]
    camera_position[2] += offset[2]
    target = target_position + np.array([0.0, 0.0, target_height], dtype=np.float32)
    return camera_position, target


def focus_context(objects: list[dict]) -> tuple[dict | None, np.ndarray | None]:
    """Choose a stable fixture and the centroid of non-fixture task objects."""
    fixture = next((obj for obj in objects if obj["category"] in FIXTURE_CATEGORIES), None)
    details = [
        obj["position"]
        for obj in objects
        if obj["category"] not in FIXTURE_CATEGORIES and obj["category"] != "floor"
    ]
    detail_centroid = np.mean(details, axis=0).astype(np.float32) if details else None
    return fixture, detail_centroid


def navigable_focus_camera_position(env, robot_position: np.ndarray, robot_orientation: np.ndarray, focus_position: np.ndarray) -> np.ndarray:
    """Choose a free camera point near a focus object using the scene's traversability map."""
    try:
        path, _ = env.scene.get_shortest_path(
            floor=0,
            source_world=th.tensor(robot_position[:2], dtype=th.float32),
            target_world=th.tensor(focus_position[:2], dtype=th.float32),
            entire_path=True,
            robot=env.robots[0],
        )
        if path is not None and len(path) > 0:
            # Stay two map waypoints before the target to avoid putting the
            # virtual viewer inside a refrigerator, counter, or wall.
            waypoint = to_numpy(path[max(0, len(path) - 3)])
            return np.array([waypoint[0], waypoint[1], robot_position[2] + 1.45], dtype=np.float32)
    except (AttributeError, RuntimeError, ValueError):
        pass

    # A saved R1 Pro pose is known to be collision-free, so it is a safer
    # fallback than placing a camera at an arbitrary object-local offset.
    return object_camera_pose(robot_position, robot_orientation, ROBOT_CAMERA_OFFSET, 1.0)[0]


def calibrated_focus_camera_position(task_name: str, fixture_position: np.ndarray, section: int) -> np.ndarray | None:
    """Return a verified fixture view, if this template has one."""
    offsets = CALIBRATED_FOCUS_OFFSETS.get(task_name)
    if offsets is None:
        return None
    return fixture_position + offsets[section - 1]


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
            # The locally installed 2025 task templates do not consistently
            # contain an R1 Pro entry in ``robot_poses``.  The task instance
            # still provides the house and task-object placement; let the R1
            # Pro use its configured reset pose instead of requiring absent
            # legacy pose metadata.
            config["task"]["use_presampled_robot_pose"] = False
            env = og.Environment(configs=config)
            env.reset()
        pose_source = position_robot_for_recording(env, args.scene)
        camera = og.sim.viewer_camera
        robot_position, robot_orientation, task_objects = task_view_context(env)
        fixture, detail_centroid = focus_context(task_objects)
        print(
            f"Task camera robot={robot_position.tolist()} pose={pose_source} "
            f"objects={[obj['name'] for obj in task_objects]}",
            flush=True,
        )

        # The viewer sensor observes a new pose after a simulator tick. This
        # follows OmniGibson's CameraMover recording utility and never calls
        # env.step() or sends a robot action.
        initial_position, initial_target = object_camera_pose(
            robot_position, robot_orientation, ROBOT_CAMERA_OFFSET, 1.0
        )
        camera.set_position_orientation(
            position=initial_position, orientation=look_at_quaternion(initial_position, initial_target)
        )
        og.sim.step()

        writer = imageio.get_writer(args.output, fps=args.fps, macro_block_size=1)
        for index in range(args.frames):
            section = min((index * 3) // args.frames, 2)
            if section == 0 or fixture is None:
                position, target = object_camera_pose(
                    robot_position, robot_orientation, ROBOT_CAMERA_OFFSET, 1.0
                )
            else:
                focus_position = fixture["position"] if section == 1 or detail_centroid is None else detail_centroid
                position = calibrated_focus_camera_position(args.task, fixture["position"], section)
                if position is None:
                    position = navigable_focus_camera_position(
                        env, robot_position, robot_orientation, focus_position
                    )
                target = focus_position + np.array([0.0, 0.0, 0.75], dtype=np.float32)
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
