#!/usr/bin/env python3
"""Sample one BEHAVIOR task once and persist its complete scene JSON locally."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
from pathlib import Path

os.environ.setdefault("OMNIGIBSON_HEADLESS", "1")

import numpy as np
import torch as th
import yaml

import omnigibson as og
from omnigibson.macros import gm


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sample one task instance and save a complete, reusable scene JSON."
    )
    parser.add_argument("--config", required=True, type=Path, help="Tracked local task-selection JSON")
    parser.add_argument("--output", required=True, type=Path, help="Canonical task-template JSON to create")
    parser.add_argument("--force", action="store_true", help="Replace an existing local instance")
    args = parser.parse_args()
    if args.output.suffix != ".json":
        parser.error("--output must end in .json")
    if not args.config.is_file():
        parser.error(f"configuration does not exist: {args.config}")
    if args.output.exists() and not args.force:
        parser.error(f"output already exists: {args.output} (pass --force to replace it)")
    return args


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def to_list(value) -> list[float]:
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    return [float(item) for item in value]


def load_spec(path: Path) -> dict:
    spec = json.loads(path.read_text(encoding="utf-8"))
    required = {"task", "scene", "random_seed", "room_types", "sampling_whitelist", "sampling_blacklist"}
    missing = required.difference(spec)
    if missing:
        raise ValueError(f"sampling config is missing keys: {', '.join(sorted(missing))}")
    if not isinstance(spec["room_types"], list) or not spec["room_types"]:
        raise ValueError("room_types must be a non-empty list")
    return spec


def main() -> None:
    args = parse_args()
    spec = load_spec(args.config)
    task_name = spec["task"]
    scene_name = spec["scene"]
    expected_name = f"{scene_name}_task_{task_name}_0_0_template.json"
    if args.output.name != expected_name:
        raise ValueError(f"output filename must be {expected_name}")

    seed = int(spec["random_seed"])
    random.seed(seed)
    np.random.seed(seed)
    th.manual_seed(seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    gm.ENABLE_OBJECT_STATES = True
    gm.USE_GPU_DYNAMICS = False
    with (Path(og.example_config_path) / "r1pro_behavior.yaml").open(encoding="utf-8") as file:
        config = yaml.safe_load(file)
    config.pop("task", None)
    config["scene"]["scene_model"] = scene_name
    config["scene"]["load_room_types"] = spec["room_types"]
    config["robots"][0]["obs_modalities"] = []
    config["robots"][0]["default_reset_mode"] = "untuck"
    config["robots"][0]["position"] = [-50.0, -50.0, -50.0]

    env = None
    try:
        print(f"Loading {scene_name}; sampling {task_name} with random seed {seed}.", flush=True)
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
        env.task_config.update(
            {
                "type": "BehaviorTask",
                "activity_name": task_name,
                "activity_definition_id": 0,
                "activity_instance_id": 0,
                "online_object_sampling": True,
                "use_presampled_robot_pose": False,
                "sampling_whitelist": spec["sampling_whitelist"],
                "sampling_blacklist": spec["sampling_blacklist"],
            }
        )
        env._load_task()
        if env.task.feedback is not None:
            raise RuntimeError(f"sampling rejected {task_name}: {env.task.feedback}")

        og.sim.play()
        env.task.reset(env)
        robot = env.robots[0]
        robot_position, robot_orientation = robot.get_position_orientation()
        env.scene.write_task_metadata(
            key="robot_poses",
            data={robot.model_name: [{"position": to_list(robot_position), "orientation": to_list(robot_orientation)}]},
        )
        env.task.save_task(env=env, save_dir=str(args.output.parent), override=args.force)
        if not args.output.is_file():
            raise RuntimeError(f"OmniGibson did not write the expected instance: {args.output}")

        manifest = {
            "schema_version": 1,
            "task": task_name,
            "scene": scene_name,
            "activity_definition_id": 0,
            "activity_instance_id": 0,
            "random_seed": seed,
            "config": str(args.config.resolve()),
            "config_sha256": sha256(args.config),
            "instance": str(args.output.resolve()),
            "instance_sha256": sha256(args.output),
            "robot_model": robot.model_name,
            "robot_position": to_list(robot_position),
            "robot_orientation": to_list(robot_orientation),
        }
        manifest_path = args.output.with_suffix(".manifest.json")
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Saved instance: {args.output}", flush=True)
        print(f"Saved local manifest: {manifest_path}", flush=True)
    finally:
        if env is not None:
            og.shutdown()


if __name__ == "__main__":
    main()
