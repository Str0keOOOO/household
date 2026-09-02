#!/usr/bin/env python3
"""Record an initialized BEHAVIOR task scene with R1 Pro."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

os.environ.setdefault("OMNIGIBSON_HEADLESS", "1")

import imageio.v2 as imageio
import numpy as np
import torch as th
import yaml

import omnigibson as og
import omnigibson.lazy as lazy
from omnigibson.macros import gm
from omnigibson.object_states import Open
from omnigibson.utils.sim_utils import land_object
from omnigibson.utils.transform_utils import mat2quat


NATIVE_CAMERA_SPECS = (
    ("left_wrist_realsense", "left_realsense_link"),
    ("zed", "zed_link"),
    ("right_wrist_realsense", "right_realsense_link"),
)
DEFAULT_R1PRO_POSTURE = "tuck"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record an initialized R1 Pro BEHAVIOR task scene.")
    parser.add_argument("--task", required=True, help="Canonical BEHAVIOR activity name")
    parser.add_argument("--scene", required=True, help="OmniGibson scene model name")
    parser.add_argument("--output", type=Path, help="Third-person MP4 path to create")
    parser.add_argument(
        "--scene-file",
        type=Path,
        help="Optional complete local task-template JSON; do not re-sample when it is supplied",
    )
    parser.add_argument(
        "--initialization-config",
        type=Path,
        help="Tracked task configuration whose refrigerator and hamburger state is applied after scene loading",
    )
    parser.add_argument(
        "--streaming",
        action="store_true",
        help="Enable Isaac Sim 4.5 WebRTC streaming for this process",
    )
    parser.add_argument(
        "--streaming-only",
        action="store_true",
        help="Keep the initialized scene streaming until Ctrl+C; do not create MP4 files",
    )
    parser.add_argument(
        "--robot-posture",
        choices=("tuck", "untuck"),
        default=DEFAULT_R1PRO_POSTURE,
        help="Arm initialization applied after the task template is restored (default: tuck)",
    )
    parser.add_argument("--frames", type=int, default=30, help="Frames to record (default: 30)")
    parser.add_argument("--fps", type=int, default=10, help="Output FPS (default: 10)")
    parser.add_argument(
        "--random-jitter",
        action="store_true",
        help="Apply a seeded, small random normalized action at each recorded frame",
    )
    parser.add_argument(
        "--jitter-scale",
        type=float,
        default=0.04,
        help="Multiplier for each sampled normalized action (default: 0.04)",
    )
    parser.add_argument("--seed", type=int, default=20260901, help="Random-action seed (default: 20260901)")
    parser.add_argument("--width", type=int, default=1280, help="Third-person width (default: 1280)")
    parser.add_argument("--height", type=int, default=720, help="Third-person height (default: 720)")
    parser.add_argument(
        "--camera-view",
        choices=("near_right", "task_right", "near_left", "task_left", "side_right", "side_left", "behind", "auto"),
        default="near_right",
        help="Third-person view; near_right is the fast default, auto scans all candidates",
    )
    parser.add_argument(
        "--robot-output",
        type=Path,
        help="Optional horizontally tiled MP4 from the native R1 Pro cameras",
    )
    parser.add_argument(
        "--camera-width",
        type=int,
        default=480,
        help="Native-camera panel width and sensor width in pixels (default: 480)",
    )
    parser.add_argument(
        "--camera-height",
        type=int,
        default=480,
        help="Native-camera panel height and sensor height in pixels (default: 480)",
    )
    args = parser.parse_args()
    for name in ("frames", "fps", "width", "height", "camera_width", "camera_height"):
        if getattr(args, name) <= 0:
            parser.error(f"--{name} must be positive")
    if args.output is not None and args.output.suffix.lower() != ".mp4":
        parser.error("--output must end in .mp4")
    if not args.streaming_only and args.output is None:
        parser.error("--output is required unless --streaming-only is supplied")
    if args.streaming_only and not args.streaming:
        parser.error("--streaming-only requires --streaming")
    if args.streaming_only and args.robot_output is not None:
        parser.error("--robot-output cannot be used with --streaming-only")
    if args.robot_output is not None and args.robot_output.suffix.lower() != ".mp4":
        parser.error("--robot-output must end in .mp4")
    if args.scene_file is not None and not args.scene_file.is_file():
        parser.error(f"scene file does not exist: {args.scene_file}")
    if args.initialization_config is not None and not args.initialization_config.is_file():
        parser.error(f"initialization configuration does not exist: {args.initialization_config}")
    if not 0.0 < args.jitter_scale <= 1.0:
        parser.error("--jitter-scale must be in (0, 1]")
    return args


def as_numpy(value) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    return np.asarray(value, dtype=np.float32)


def enable_webrtc_streaming() -> None:
    """Enable Isaac Sim 4.5 WebRTC after OmniGibson has created its Kit app."""
    # Do not access lazy.omni.kit here: OmniGibson's lazy ``omni`` importer does
    # not expose the Kit submodule. This is the same post-app extension utility
    # the upstream simulator uses for its own streaming backends. Enabling the
    # WebRTC extension automatically enables its streamsdk dependency.
    lazy.isaacsim.core.utils.extensions.enable_extension("omni.kit.livestream.webrtc")
    port = lazy.carb.settings.get_settings().get_as_int("/app/livestream/port")
    print(f"Isaac Sim WebRTC streaming enabled; signaling port={port}.", flush=True)


def frame_from_camera(camera) -> np.ndarray:
    frame = camera.get_obs()[0]["rgb"][:, :, :3]
    return np.asarray(frame.detach().cpu().numpy() if hasattr(frame, "detach") else frame, dtype=np.uint8)


def _native_camera_prim_paths(robot) -> tuple[str, ...]:
    """Resolve the three fixed native Camera prim paths for the loaded R1 Pro.

    The USD layout is fixed by the R1 Pro asset.  Only the scene/robot prefix
    varies at runtime, so derive that prefix from ``robot.prim_path`` and use
    explicit link-relative paths.  This intentionally does not scan the stage
    or select a similarly named camera from another object.
    """
    robot_root = str(robot.prim_path).rstrip("/")
    result = []
    for _, link_name in NATIVE_CAMERA_SPECS:
        prim_path = f"{robot_root}/{link_name}/Camera"
        prim = og.sim.stage.GetPrimAtPath(prim_path)
        if not prim or not prim.IsValid() or prim.GetTypeName() != "Camera":
            raise RuntimeError(
                f"Expected native R1 Pro Camera prim at explicit path {prim_path}, "
                f"but the stage has no valid Camera there (type={prim.GetTypeName() if prim else 'missing'})"
            )
        result.append(prim_path)
    return tuple(result)


def native_r1pro_camera_streams(robot, width: int, height: int) -> tuple[tuple[str, str, object, object], ...]:
    """Create RGB render products directly from the three native USD cameras."""
    prim_paths = _native_camera_prim_paths(robot)
    streams = []
    try:
        for (label, _), prim_path in zip(NATIVE_CAMERA_SPECS, prim_paths):
            render_product = lazy.omni.replicator.core.create.render_product(
                prim_path, (width, height), force_new=True
            )
            annotator = lazy.omni.replicator.core.AnnotatorRegistry.get_annotator("rgb")
            annotator.attach([render_product])
            streams.append((label, prim_path, render_product, annotator))
    except Exception:
        destroy_native_r1pro_camera_streams(tuple(streams))
        raise
    return tuple(streams)


def right_wrist_camera_alignment(env, streams: tuple[tuple[str, str, object, object], ...], path: Path | None) -> str:
    """Report the refrigerator's horizontal offset in the right wrist camera frame.

    A centred target has camera-local x=0 metres.
    """
    if path is None:
        return "Right wrist alignment unavailable: no initialization configuration."
    refrigerator_name = (
        json.loads(path.read_text(encoding="utf-8")).get("initialization", {}).get("refrigerator", {}).get("bddl_name")
    )
    entity = env.task.object_scope.get(refrigerator_name)
    if not isinstance(refrigerator_name, str) or entity is None or not entity.exists or entity.is_system:
        return "Right wrist alignment unavailable: configured refrigerator is absent."
    right_wrist = next((stream for stream in streams if stream[0] == "right_wrist_realsense"), None)
    if right_wrist is None:
        return "Right wrist alignment unavailable: native right wrist camera was not created."

    from pxr import Gf, UsdGeom

    camera_prim = og.sim.stage.GetPrimAtPath(right_wrist[1])
    camera_to_world = UsdGeom.XformCache().GetLocalToWorldTransform(camera_prim)
    camera_position = np.asarray(camera_to_world.ExtractTranslation(), dtype=np.float64)
    refrigerator_position, _ = entity.wrapped_obj.get_position_orientation()
    refrigerator_position = as_numpy(refrigerator_position).astype(np.float64)
    refrigerator_in_camera = np.asarray(
        camera_to_world.GetInverse().Transform(Gf.Vec3d(*refrigerator_position)), dtype=np.float64
    )
    return (
        "Right wrist x alignment "
        f"camera_world_x_m={camera_position[0]:.4f} refrigerator_world_x_m={refrigerator_position[0]:.4f} "
        f"camera_local_x_offset_m={refrigerator_in_camera[0]:.4f} "
        "(0.0000 means centred)"
    )


def frame_from_native_camera(stream: tuple[str, str, object, object]) -> np.ndarray:
    label, prim_path, _, annotator = stream
    raw_frame = annotator.get_data(device=og.sim.device)
    frame = raw_frame["data"] if isinstance(raw_frame, dict) else raw_frame
    if hasattr(frame, "detach"):
        frame = frame.detach().cpu().numpy()
    frame = np.asarray(frame)
    if frame.ndim != 3 or frame.shape[2] < 3 or frame.shape[0] == 0 or frame.shape[1] == 0:
        raise RuntimeError(f"Native camera {label} at {prim_path} returned an invalid RGB shape: {frame.shape}")
    return np.asarray(np.clip(frame[:, :, :3], 0, 255), dtype=np.uint8)


def destroy_native_r1pro_camera_streams(streams: tuple[tuple[str, str, object, object], ...]) -> None:
    """Detach and destroy temporary Replicator products before shutdown."""
    for _, _, render_product, annotator in streams:
        try:
            annotator.detach([render_product.path])
        except Exception:
            pass
        try:
            render_product.destroy()
        except Exception:
            pass


def label_panel(frame: np.ndarray, label: str) -> np.ndarray:
    """Add a small label bar while keeping the camera image unchanged below it."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return frame
    image = Image.fromarray(frame)
    labeled = Image.new("RGB", (image.width, image.height + 32), color=(12, 12, 12))
    labeled.paste(image, (0, 32))
    ImageDraw.Draw(labeled).text((12, 9), label, fill=(245, 245, 245))
    return np.asarray(labeled, dtype=np.uint8)


def tiled_native_camera_frame(
    camera_streams: tuple[tuple[str, str, object, object], ...], panel_width: int, panel_height: int
) -> np.ndarray:
    """Build a strip from native left-wrist, ZED, and right-wrist RGB frames."""
    from PIL import Image

    panels = []
    for stream in camera_streams:
        label = stream[0]
        frame = frame_from_native_camera(stream)
        resized = np.asarray(
            Image.fromarray(frame).resize((panel_width, panel_height), Image.Resampling.LANCZOS), dtype=np.uint8
        )
        panels.append(label_panel(resized, label.replace("_", " ")))
    return np.concatenate(panels, axis=1)


def look_at_quaternion(position: np.ndarray, target: np.ndarray) -> np.ndarray:
    forward = target - position
    forward /= np.linalg.norm(forward)
    right = np.cross(forward, np.array([0.0, 0.0, 1.0], dtype=np.float32))
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    return as_numpy(mat2quat(th.tensor(np.column_stack((right, up, -forward)), dtype=th.float32)))


def set_saved_robot_pose(env) -> str:
    """Use a stored R1 Pro pose when present; absent legacy metadata is valid."""
    robot = env.robots[0]
    poses = env.scene.get_task_metadata(key="robot_poses")
    if not isinstance(poses, dict) or robot.model_name not in poses:
        return "configured reset pose (no saved R1 Pro pose)"
    pose = poses[robot.model_name][0]
    robot.set_position_orientation(position=as_numpy(pose["position"]), orientation=as_numpy(pose["orientation"]))
    robot.keep_still()
    return "saved R1 Pro pose"


def apply_scene_initialization(env, path: Path | None, robot_posture: str) -> str:
    """Apply configured presentation state after restoring the saved robot pose."""
    if path is None:
        pose_source = set_saved_robot_pose(env)
        getattr(env.robots[0], robot_posture)()
        return f"{pose_source}; explicit posture={robot_posture}"
    initialization = json.loads(path.read_text(encoding="utf-8")).get("initialization", {})
    refrigerator_spec, hamburger_spec = initialization.get("refrigerator"), initialization.get("hamburger")
    if not isinstance(refrigerator_spec, dict) or not isinstance(hamburger_spec, dict):
        raise ValueError("initialization requires refrigerator and hamburger objects")
    refrigerator_name, opened = refrigerator_spec.get("bddl_name"), refrigerator_spec.get("open")
    hamburger_name = hamburger_spec.get("bddl_name")
    landing_position, orientation = hamburger_spec.get("landing_position"), hamburger_spec.get("orientation")
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
    hamburger = hamburger_entity.wrapped_obj
    land_object(
        hamburger,
        th.tensor(landing_position, dtype=th.float32),
        th.tensor(orientation, dtype=th.float32),
    )
    pose_source = set_saved_robot_pose(env)
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
        applied_orientation = saved_orientation if orientation is None else as_numpy(orientation)
        robot.set_position_orientation(position=as_numpy(position), orientation=applied_orientation)
        robot.keep_still()
        pose_source += f"; configured robot position={position}, orientation={as_numpy(applied_orientation).tolist()}"
    robot = env.robots[0]
    getattr(robot, robot_posture)()
    return (
        f"{pose_source}; explicit posture={robot_posture}; refrigerator {refrigerator.name} open={opened}; "
        "hamburger landed on upper shelf"
    )


def task_focus_point(env, robot_position: np.ndarray) -> tuple[np.ndarray, list[str]]:
    """Return a task-derived view target, avoiding task-specific camera constants."""
    positions = []
    task_item_positions = []
    names = []
    for bddl_name, entity in env.task.object_scope.items():
        if not entity.exists or entity.is_system or entity.wrapped_obj is env.robots[0]:
            continue
        obj = entity.wrapped_obj
        if obj.category == "floors":
            continue
        position, _ = obj.get_position_orientation()
        position = as_numpy(position)
        positions.append(position)
        if obj.category in {"microwave", "hamburger", "plate"}:
            task_item_positions.append(position)
        names.append(bddl_name)
    if not positions:
        return robot_position + np.array([1.0, 0.0, 0.7], dtype=np.float32), names
    # For heating_food_up, fixtures such as the fridge and countertop are far
    # apart from the actual microwave/food work area. Prefer those task items
    # so the overview camera includes the appliance the task acts on.
    focus_positions = task_item_positions or positions
    return np.mean(focus_positions, axis=0) + np.array([0.0, 0.0, 0.35], dtype=np.float32), names


def image_information_score(frame: np.ndarray) -> float:
    """Prefer a detailed, non-overexposed view over a wall or ceiling."""
    luminance = frame.astype(np.float32).mean(axis=2)
    histogram, _ = np.histogram(luminance, bins=32, range=(0, 256))
    probabilities = histogram[histogram > 0] / histogram.sum()
    entropy = -np.sum(probabilities * np.log(probabilities))
    overexposure_penalty = max(0.0, float(luminance.mean()) - 190.0) / 30.0
    return float(entropy - overexposure_penalty)


def position_task_camera(
    env, robot_position: np.ndarray, camera_view: str
) -> tuple[np.ndarray, list[str], str, np.ndarray, dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Select a generic, unobstructed-looking overview camera for the task."""
    target, names = task_focus_point(env, robot_position)
    horizontal = target[:2] - robot_position[:2]
    norm = np.linalg.norm(horizontal)
    if norm < 0.1:
        horizontal = np.array([1.0, 0.0], dtype=np.float32)
    else:
        horizontal /= norm
    side = np.array([-horizontal[1], horizontal[0]], dtype=np.float32)
    # Indoor walls make a single fixed "behind robot" viewpoint unreliable.
    # These candidates are derived solely from the robot and task-object cluster,
    # so the rule is reusable for arbitrary saved BEHAVIOR instances.
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
        camera_position = robot_position.copy()
        camera_position[:2] += offset
        camera_position[2] += 1.55
        candidate_positions[label] = camera_position

    camera = og.sim.viewer_camera
    if camera_view != "auto":
        label = camera_view
        camera_position = candidate_positions[label]
        camera.set_position_orientation(position=camera_position, orientation=look_at_quaternion(camera_position, target))
        # Isaac Sim applies a viewer-camera transform asynchronously. Three
        # render ticks are required before the readback corresponds to this
        # camera rather than the preceding camera's image.
        for _ in range(3):
            og.sim.render()
        frame = frame_from_camera(camera)
        score = image_information_score(frame)
        print(f"Camera view={label}:{score:.2f} (settled)", flush=True)
        return target, names, label, frame, {label: frame}, candidate_positions

    choices = []
    for label, _ in candidate_offsets:
        camera_position = candidate_positions[label]
        camera.set_position_orientation(position=camera_position, orientation=look_at_quaternion(camera_position, target))
        # Auto mode is intentionally slower: it settles every candidate before
        # scoring so the selected frame is not a stale previous-view buffer.
        for _ in range(3):
            og.sim.render()
        frame = frame_from_camera(camera)
        choices.append((image_information_score(frame), label, camera_position, frame))

    # Indoor fixtures can obscure one side of the robot entirely. Choose the
    # highest-information robot-relative candidate for the third-person view.
    score, label, camera_position, frame = max(choices, key=lambda choice: choice[0])
    camera.set_position_orientation(position=camera_position, orientation=look_at_quaternion(camera_position, target))
    print(
        "Camera candidates="
        + ",".join(f"{candidate_label}:{candidate_score:.2f}" for candidate_score, candidate_label, _, _ in choices)
        + f" selected={label}:{score:.2f}",
        flush=True,
    )
    return (
        target,
        names,
        label,
        frame,
        {candidate_label: candidate_frame for _, candidate_label, _, candidate_frame in choices},
        {candidate_label: candidate_position for _, candidate_label, candidate_position, _ in choices},
    )


def main() -> None:
    args = parse_args()
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
    gm.ENABLE_OBJECT_STATES = True
    gm.USE_GPU_DYNAMICS = False
    with (Path(og.example_config_path) / "r1pro_behavior.yaml").open(encoding="utf-8") as file:
        config = yaml.safe_load(file)
    config["scene"]["scene_model"] = args.scene
    # A cached task template already determines the loaded rooms.
    config["scene"]["load_room_types"] = None
    if args.scene_file is not None:
        config["scene"]["scene_file"] = str(args.scene_file.resolve())
    config["render"]["viewer_width"] = args.width
    config["render"]["viewer_height"] = args.height
    # Use the R1 Pro's compact arm posture. This is an initialization choice
    # only; it does not apply a task action or change the base pose.
    config["robots"][0]["default_reset_mode"] = args.robot_posture
    env = third_person_writer = robot_writer = None
    native_camera_streams = ()
    try:
        print("Creating OmniGibson environment...", flush=True)
        config["task"].update(
            activity_name=args.task,
            activity_definition_id=0,
            activity_instance_id=0,
            online_object_sampling=False,
            use_presampled_robot_pose=False,
        )
        env = og.Environment(configs=config)
        if args.streaming:
            enable_webrtc_streaming()
        # Environment.post_play_load() already resets the task before the
        # constructor returns. Calling env.reset() here would restore the same
        # task state a second time and is needlessly expensive for a full house.
        print("Environment created with its initial task state; preparing cameras...", flush=True)
        # NVIDIA recommends RTX Real-Time 2.0 for robotics and synthetic-data
        # workflows, and DLSS Quality for sensor images (especially below
        # 600x600). This does not alter the upstream repository.
        renderer_settings = lazy.carb.settings.get_settings()
        renderer_settings.set("/rtx/rendermode", "RealTimePathTracing")
        renderer_settings.set_int("/rtx/post/dlss/execMode", 2)
        renderer_settings.set_bool("/rtx/pathtracing/fractionalCutoutOpacity", True)

        pose_source = apply_scene_initialization(env, args.initialization_config, args.robot_posture)
        robot_position, _ = map(as_numpy, env.robots[0].get_position_orientation())
        native_camera_frame = None
        if args.robot_output is not None:
            native_camera_streams = native_r1pro_camera_streams(
                env.robots[0], args.camera_width, args.camera_height
            )
            print(
                "Native cameras="
                + "|".join(f"{label}:{prim_path}" for label, prim_path, _, _ in native_camera_streams),
                flush=True,
            )
        (
            target,
            focus_objects,
            camera_label,
            third_person_frame,
            candidate_frames,
            candidate_positions,
        ) = position_task_camera(env, robot_position, args.camera_view)
        if args.robot_output is not None:
            # The candidate-camera renders above also advance the native
            # Camera prim transforms. Read the alignment only now: before the
            # first render USD can still expose the template's stale camera
            # transform after we have repositioned the robot base.
            print(right_wrist_camera_alignment(env, native_camera_streams, args.initialization_config), flush=True)
            # Do not add viewer-only render ticks here: Isaac Sim 4.5 can
            # close a completed headless app after redundant calls.
            native_camera_frame = tiled_native_camera_frame(
                native_camera_streams, args.camera_width, args.camera_height
            )
        # Camera selection above already performs multiple offscreen renders.
        # Do not add render ticks here: Isaac Sim 4.5 may close a completed
        # headless app after repeated viewer-only render calls.
        print("Capturing third-person frame", flush=True)
        print(
            f"Task={args.task} scene={args.scene} R1 Pro pose={pose_source} "
            f"focus={target.tolist()} camera={camera_label} objects={','.join(focus_objects)} "
            f"renderer=RealTimePathTracing dlss=quality viewer={args.width}x{args.height} "
            f"native_camera_resolution={args.camera_width}x{args.camera_height} "
            f"random_jitter={args.random_jitter} jitter_scale={args.jitter_scale} seed={args.seed}",
            flush=True,
        )

        if args.streaming_only:
            print("Streaming-only session is ready; press Ctrl+C in this terminal to stop it.", flush=True)
            while True:
                og.sim.render()
                time.sleep(1.0 / 30.0)

        third_person_writer = imageio.get_writer(args.output, fps=args.fps, macro_block_size=1)
        if args.robot_output is not None:
            args.robot_output.parent.mkdir(parents=True, exist_ok=True)
            robot_writer = imageio.get_writer(args.robot_output, fps=args.fps, macro_block_size=1)
        if args.random_jitter:
            env.robots[0].action_space.seed(args.seed)
            # The first camera frame was rendered during candidate selection and
            # is already stable. Write it before the first action so the video
            # never starts with the transient white buffer seen after a camera
            # transform update.
            third_person_writer.append_data(third_person_frame)
            if robot_writer is not None:
                robot_writer.append_data(native_camera_frame)

            for _ in range(args.frames - 1):
                # OmniGibson actions are normalized by the robot action space.
                # Scaling a valid sample yields a deliberately small, visible
                # perturbation while preserving a deterministic replay seed.
                action = env.robots[0].action_space.sample()
                _, _, terminated, truncated, _ = env.step(action * args.jitter_scale)
                camera = og.sim.viewer_camera
                selected_position = candidate_positions[camera_label]
                camera.set_position_orientation(
                    position=selected_position, orientation=look_at_quaternion(selected_position, target)
                )
                # A viewer camera transform needs several render updates before
                # its render product is ready for readback.
                for _ in range(3):
                    og.sim.render()
                    third_person_frame = frame_from_camera(camera)
                if robot_writer is not None:
                    native_camera_frame = tiled_native_camera_frame(
                        native_camera_streams, args.camera_width, args.camera_height
                    )
                third_person_writer.append_data(third_person_frame)
                if robot_writer is not None:
                    robot_writer.append_data(native_camera_frame)
                if terminated or truncated:
                    print("Task ended during random jitter; stopping recording early.", flush=True)
                    break
        else:
            for _ in range(args.frames):
                third_person_writer.append_data(third_person_frame)
                if robot_writer is not None:
                    robot_writer.append_data(native_camera_frame)
    except Exception:
        import traceback

        traceback.print_exc()
        raise
    finally:
        if third_person_writer is not None:
            third_person_writer.close()
        if robot_writer is not None:
            robot_writer.close()
        if native_camera_streams:
            destroy_native_r1pro_camera_streams(native_camera_streams)
        if env is not None:
            og.shutdown()

    if args.output is not None:
        print(f"Saved task scene video: {args.output}", flush=True)
    if args.robot_output is not None:
        print(f"Saved native R1 Pro camera video: {args.robot_output}", flush=True)


if __name__ == "__main__":
    main()
