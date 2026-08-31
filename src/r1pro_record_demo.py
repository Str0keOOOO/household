#!/usr/bin/env python3
"""Render the bundled R1 Pro BEHAVIOR example to a local MP4 file.

This is a small, local integration runner.  It uses OmniGibson's upstream
``r1pro_behavior.yaml`` configuration and viewer camera, but does not edit or
copy any file from the BEHAVIOR-1K submodule.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

# OmniGibson reads this macro during import, so it must precede that import.
os.environ.setdefault("OMNIGIBSON_HEADLESS", "1")

import imageio.v2 as imageio
import numpy as np
import yaml

import omnigibson as og
from omnigibson.macros import gm


CAMERA_POSITION = [1.6, 6.15, 1.5]
CAMERA_ORIENTATION = [-0.2322, 0.5895, 0.7199, -0.2835]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record the upstream R1 Pro BEHAVIOR demo to MP4 without a graphical desktop."
    )
    parser.add_argument("--output", required=True, type=Path, help="MP4 path to create")
    parser.add_argument("--steps", type=int, default=100, help="Random-action simulation steps (default: 100)")
    parser.add_argument("--fps", type=int, default=10, help="Output video frame rate (default: 10)")
    parser.add_argument(
        "--frame-stride",
        type=int,
        default=4,
        help="Keep one frame per this many simulation steps (default: 4)",
    )
    parser.add_argument("--width", type=int, default=640, help="Viewer width in pixels (default: 640)")
    parser.add_argument("--height", type=int, default=360, help="Viewer height in pixels (default: 360)")
    args = parser.parse_args()
    for name in ("steps", "fps", "frame_stride", "width", "height"):
        if getattr(args, name) <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    if args.output.suffix.lower() != ".mp4":
        parser.error("--output must end in .mp4")
    return args


def rgb_frame(camera) -> np.ndarray:
    """Return the upstream viewer camera's RGB observation as an imageio frame."""
    frame = camera.get_obs()[0]["rgb"][:, :, :3]
    if hasattr(frame, "detach"):
        frame = frame.detach().cpu().numpy()
    return np.asarray(frame, dtype=np.uint8)


def main() -> None:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    # These are also set by the upstream behavior_env_demo.py example.
    gm.ENABLE_OBJECT_STATES = True
    gm.USE_GPU_DYNAMICS = False

    config_path = Path(og.example_config_path) / "r1pro_behavior.yaml"
    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)
    config["task"]["online_object_sampling"] = False
    config["task"]["use_presampled_robot_pose"] = True
    config["render"]["viewer_width"] = args.width
    config["render"]["viewer_height"] = args.height

    env = None
    writer = None
    frames = 0
    try:
        env = og.Environment(configs=config)
        camera = og.sim.viewer_camera
        camera.set_position_orientation(position=CAMERA_POSITION, orientation=CAMERA_ORIENTATION)

        writer = imageio.get_writer(args.output, fps=args.fps, macro_block_size=1)
        env.reset()
        og.sim.render()
        writer.append_data(rgb_frame(camera))
        frames += 1

        for step in range(args.steps):
            action = env.robots[0].action_space.sample()
            _, _, terminated, truncated, _ = env.step(action * 0.1)
            if (step + 1) % args.frame_stride == 0 or terminated or truncated:
                writer.append_data(rgb_frame(camera))
                frames += 1
            if terminated or truncated:
                break
    finally:
        if writer is not None:
            writer.close()
        if env is not None:
            og.shutdown()

    if frames == 0:
        raise RuntimeError("No video frames were captured")
    print(f"Saved {frames} frames to {args.output}")


if __name__ == "__main__":
    main()
