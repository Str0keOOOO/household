"""Shared BEHAVIOR environment and action helpers.

This module is simulator-integration code shared by the finite ``rollout``
entrypoint and the long-lived ``episode_server``. It deliberately does not
import OmniGibson at module import time; the caller supplies the loaded
OmniGibson and YAML modules when an environment is built.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np

try:
    from .adapter import ACTION_DIM
except ImportError:
    from adapter import ACTION_DIM


DEFAULT_TASK = "heating_food_up"
DEFAULT_SCENE = "house_single_floor"
R1PRO_VISION_IMAGE_WIDTH = 256
R1PRO_VISION_IMAGE_HEIGHT = 256

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


def project_root() -> Path:
    """Return the independent BEHAVIOR Pixi project root."""
    return Path(os.environ.get("PIXI_PROJECT_ROOT", Path(__file__).resolve().parents[1])).resolve()


def _default_instance(root: Path) -> Path:
    return (
        root
        / "data"
        / "omnigibson"
        / "local-task-instances"
        / DEFAULT_TASK
        / f"{DEFAULT_SCENE}_task_{DEFAULT_TASK}_0_0_template.json"
    )


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


def build_environment(og: Any, yaml_module: Any, args: Any):
    """Build the initialized R1 Pro scene used by both behavior entrypoints."""
    from omnigibson.macros import gm

    gm.ENABLE_OBJECT_STATES = True
    gm.USE_GPU_DYNAMICS = False
    with (Path(og.example_config_path) / "r1pro_behavior.yaml").open(encoding="utf-8") as file:
        config = yaml_module.safe_load(file)
    config["scene"]["scene_model"] = args.scene
    config["scene"]["load_room_types"] = None
    config["scene"]["scene_file"] = str(args.scene_file.resolve())
    # The BEHAVIOR scene template can contain a robot of its own. When
    # ``include_robots`` is true, OmniGibson imports that robot and skips the
    # configured ``robots`` list entirely (see Environment._load_robots). The
    # imported robot has no R1 Pro VisionSensor configuration, so get_obs()
    # would correctly return an empty dictionary. The integration entrypoints
    # own the robot configuration below, so make the scene object-only and
    # instantiate the configured R1 Pro exactly once.
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
                # OmniGibson configures all attached R1 Pro VisionSensors as
                # one class, so this shared render resolution applies to the
                # ZED, left wrist, and right wrist cameras.
                "image_height": R1PRO_VISION_IMAGE_HEIGHT,
                "image_width": R1PRO_VISION_IMAGE_WIDTH,
            },
        }
    }
    print(
        "stage=robot_sensor_config_ready "
        "scene.include_robots=False modalities=rgb,depth VisionSensor.enabled=True "
        f"resolution={R1PRO_VISION_IMAGE_WIDTH}x{R1PRO_VISION_IMAGE_HEIGHT}",
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


def execute_action_chunk(env: Any, actions: np.ndarray, on_step=None) -> bool:
    """Directly execute every full 23-D OmniGibson action in a chunk."""
    for action in actions:
        if action.shape != (ACTION_DIM,) or action.dtype != np.float32:
            raise RuntimeError(
                f"planner action must have shape {(ACTION_DIM,)} and dtype float32, "
                f"got {action.shape} / {action.dtype}"
            )
        if not np.all(np.isfinite(action)):
            raise RuntimeError("planner action must contain only finite values")
        result = env.step(action)
        if on_step is not None:
            on_step()
        if isinstance(result, tuple) and len(result) >= 4 and bool(result[2] or result[3]):
            return True
    return False
