"""Task initialization and third-person camera helpers for heating_food_up."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np


def _as_numpy(value: Any) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    return np.asarray(value, dtype=np.float32)


def frame_from_camera(camera: Any) -> np.ndarray:
    """Read one RGB frame from an initialized OmniGibson camera."""
    frame = camera.get_obs()[0]["rgb"][:, :, :3]
    if hasattr(frame, "detach"):
        frame = frame.detach().cpu().numpy()
    return np.asarray(frame, dtype=np.uint8)


def _look_at_quaternion(position: np.ndarray, target: np.ndarray) -> np.ndarray:
    import torch as th
    from omnigibson.utils.transform_utils import mat2quat

    forward = target - position
    forward /= np.linalg.norm(forward)
    right = np.cross(forward, np.array([0.0, 0.0, 1.0], dtype=np.float32))
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    rotation = th.tensor(np.column_stack((right, up, -forward)), dtype=th.float32)
    return _as_numpy(mat2quat(rotation))


def _set_saved_robot_pose(env: Any) -> str:
    """Restore the saved R1 Pro pose when task metadata contains one."""
    robot = env.robots[0]
    poses = env.scene.get_task_metadata(key="robot_poses")
    if not isinstance(poses, dict) or robot.model_name not in poses:
        return "configured reset pose (no saved R1 Pro pose)"
    pose = poses[robot.model_name][0]
    robot.set_position_orientation(
        position=_as_numpy(pose["position"]),
        orientation=_as_numpy(pose["orientation"]),
    )
    robot.keep_still()
    return "saved R1 Pro pose"


def apply_scene_initialization(env: Any, path: Path | None, robot_posture: str) -> str:
    """Restore the robot and apply the configured refrigerator/food state."""
    if path is None:
        pose_source = _set_saved_robot_pose(env)
        getattr(env.robots[0], robot_posture)()
        return f"{pose_source}; explicit posture={robot_posture}"

    import torch as th
    from omnigibson.object_states import Open
    from omnigibson.utils.sim_utils import land_object

    initialization = json.loads(path.read_text(encoding="utf-8")).get("initialization", {})
    refrigerator_spec = initialization.get("refrigerator")
    hamburger_spec = initialization.get("hamburger")
    if not isinstance(refrigerator_spec, dict) or not isinstance(hamburger_spec, dict):
        raise ValueError("initialization requires refrigerator and hamburger objects")

    refrigerator_name = refrigerator_spec.get("bddl_name")
    opened = refrigerator_spec.get("open")
    hamburger_name = hamburger_spec.get("bddl_name")
    landing_position = hamburger_spec.get("landing_position")
    orientation = hamburger_spec.get("orientation")
    if (
        not isinstance(refrigerator_name, str)
        or not isinstance(opened, bool)
        or not isinstance(hamburger_name, str)
        or not isinstance(landing_position, list)
        or len(landing_position) != 3
        or not isinstance(orientation, list)
        or len(orientation) != 4
    ):
        raise ValueError("invalid refrigerator or hamburger initialization")

    refrigerator_entity = env.task.object_scope.get(refrigerator_name)
    hamburger_entity = env.task.object_scope.get(hamburger_name)
    if (
        refrigerator_entity is None
        or hamburger_entity is None
        or not refrigerator_entity.exists
        or not hamburger_entity.exists
        or refrigerator_entity.is_system
        or hamburger_entity.is_system
    ):
        raise RuntimeError("configured refrigerator or hamburger is absent from this task instance")

    refrigerator = refrigerator_entity.wrapped_obj
    open_state = refrigerator.states.get(Open)
    if open_state is None or not open_state.set_value(opened, fully=True):
        raise RuntimeError(f"Could not set {refrigerator.name} open={opened}")
    land_object(
        hamburger_entity.wrapped_obj,
        th.tensor(landing_position, dtype=th.float32),
        th.tensor(orientation, dtype=th.float32),
    )

    pose_source = _set_saved_robot_pose(env)
    robot_spec = initialization.get("robot")
    if robot_spec is not None:
        position = robot_spec.get("position") if isinstance(robot_spec, dict) else None
        if not isinstance(position, list) or len(position) != 3:
            raise ValueError("initialization.robot requires position [x, y, z]")
        robot = env.robots[0]
        _, saved_orientation = robot.get_position_orientation()
        orientation = robot_spec.get("orientation")
        if orientation is not None and (not isinstance(orientation, list) or len(orientation) != 4):
            raise ValueError("initialization.robot orientation must be [x, y, z, w]")
        applied_orientation = saved_orientation if orientation is None else _as_numpy(orientation)
        robot.set_position_orientation(position=_as_numpy(position), orientation=applied_orientation)
        robot.keep_still()
        pose_source += f"; configured robot position={position}, orientation={_as_numpy(applied_orientation).tolist()}"

    robot = env.robots[0]
    getattr(robot, robot_posture)()
    return (
        f"{pose_source}; explicit posture={robot_posture}; refrigerator {refrigerator.name} open={opened}; "
        "hamburger landed on upper shelf"
    )


def _task_focus_point(env: Any, robot_position: np.ndarray) -> np.ndarray:
    positions = []
    task_item_positions = []
    for entity in env.task.object_scope.values():
        if not entity.exists or entity.is_system or entity.wrapped_obj is env.robots[0]:
            continue
        obj = entity.wrapped_obj
        if obj.category == "floors":
            continue
        position, _ = obj.get_position_orientation()
        position = _as_numpy(position)
        positions.append(position)
        if obj.category in {"microwave", "hamburger", "plate"}:
            task_item_positions.append(position)
    if not positions:
        return robot_position + np.array([1.0, 0.0, 0.7], dtype=np.float32)
    return np.mean(task_item_positions or positions, axis=0) + np.array([0.0, 0.0, 0.35], dtype=np.float32)


def _image_information_score(frame: np.ndarray) -> float:
    luminance = frame.astype(np.float32).mean(axis=2)
    histogram, _ = np.histogram(luminance, bins=32, range=(0, 256))
    probabilities = histogram[histogram > 0] / histogram.sum()
    entropy = -np.sum(probabilities * np.log(probabilities))
    overexposure_penalty = max(0.0, float(luminance.mean()) - 190.0) / 30.0
    return float(entropy - overexposure_penalty)


def position_task_camera(
    env: Any,
    robot_position: np.ndarray,
    camera_view: str,
    *,
    verbose: bool = True,
) -> str:
    """Position the third-person camera and return the selected view name."""
    import omnigibson as og

    target = _task_focus_point(env, robot_position)
    horizontal = target[:2] - robot_position[:2]
    norm = np.linalg.norm(horizontal)
    horizontal = np.array([1.0, 0.0], dtype=np.float32) if norm < 0.1 else horizontal / norm
    side = np.array([-horizontal[1], horizontal[0]], dtype=np.float32)
    candidate_offsets = (
        ("behind", -2.2 * horizontal),
        ("near_left", -0.8 * horizontal + 1.2 * side),
        ("near_right", -0.8 * horizontal - 1.2 * side),
        ("side_left", 0.2 * horizontal + 2.0 * side),
        ("side_right", 0.2 * horizontal - 2.0 * side),
        ("task_left", 1.0 * horizontal + 1.5 * side),
        ("task_right", 1.0 * horizontal - 1.5 * side),
    )
    candidate_positions = {}
    for label, offset in candidate_offsets:
        position = robot_position.copy()
        position[:2] += offset
        position[2] += 1.55
        candidate_positions[label] = position

    camera = og.sim.viewer_camera
    if camera_view != "auto":
        position = candidate_positions[camera_view]
        camera.set_position_orientation(position=position, orientation=_look_at_quaternion(position, target))
        for _ in range(3):
            og.sim.render()
        score = _image_information_score(frame_from_camera(camera))
        if verbose:
            print(f"Camera view={camera_view}:{score:.2f} (settled)", flush=True)
        return camera_view

    choices = []
    for label, _ in candidate_offsets:
        position = candidate_positions[label]
        camera.set_position_orientation(position=position, orientation=_look_at_quaternion(position, target))
        for _ in range(3):
            og.sim.render()
        choices.append((_image_information_score(frame_from_camera(camera)), label, position))
    score, label, position = max(choices, key=lambda choice: choice[0])
    camera.set_position_orientation(position=position, orientation=_look_at_quaternion(position, target))
    if verbose:
        print(
            "Camera candidates="
            + ",".join(f"{name}:{candidate_score:.2f}" for candidate_score, name, _ in choices)
            + f" selected={label}:{score:.2f}",
            flush=True,
        )
    return label
