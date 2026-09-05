"""Launch the persisted heating_food_up scene with Isaac Sim WebRTC streaming."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def project_root() -> Path:
    return Path(os.environ.get("PIXI_PROJECT_ROOT", Path(__file__).resolve().parents[1])).resolve()


def main() -> None:
    root = project_root()
    repository_root = root.parents[1]
    config = root / "heating_food_up" / "config.json"
    instance = (
        root
        / "data"
        / "omnigibson"
        / "local-task-instances"
        / "heating_food_up"
        / "house_single_floor_task_heating_food_up_0_0_template.json"
    )
    sampler = root / "heating_food_up" / "sample_task_instance.py"
    recorder = root / "heating_food_up" / "record_scene.py"

    instance.parent.mkdir(parents=True, exist_ok=True)
    if not instance.is_file():
        subprocess.run(
            [sys.executable, str(sampler), "--config", str(config), "--output", str(instance)],
            check=True,
            cwd=repository_root,
        )

    command = [
        sys.executable,
        str(recorder),
        "--task",
        "heating_food_up",
        "--scene",
        "house_single_floor",
        "--scene-file",
        str(instance),
        "--initialization-config",
        str(config),
        "--streaming",
        "--streaming-only",
        *sys.argv[1:],
    ]
    os.execv(sys.executable, command)


if __name__ == "__main__":
    main()
