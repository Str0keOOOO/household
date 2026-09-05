"""BEHAVIOR-specific raw R1 Pro observation construction.

This module deliberately has no OmniGibson import at module import time. The
mock transport test imports only this module and the pure NumPy adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np


# These are the fixed R1 Pro camera prims used by the observation collector.
# They are deliberately explicit:
# the collector never scans the stage or matches a camera by a fuzzy name.
R1PRO_CAMERA_PATHS = {
    "zed": "zed_link/Camera",
    "left_wrist": "left_realsense_link/Camera",
    "right_wrist": "right_realsense_link/Camera",
}

R1PRO_CAMERA_LINKS = {
    "zed": "zed_link",
    "left_wrist": "left_realsense_link",
    "right_wrist": "right_realsense_link",
}

# Omniverse's distance-to-camera annotator uses ``+inf`` for rays that do not
# hit scene geometry. The planner protocol requires finite meter values, so a
# missing return is represented by this documented far-depth value instead.
# Valid finite depth values are never scaled or clipped here.
INVALID_DEPTH_M = np.float32(10.0)


def _as_numpy(value: Any) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    return np.asarray(value)


def build_raw_obs(
    *,
    zed_rgb: np.ndarray,
    zed_depth: np.ndarray,
    left_wrist_rgb: np.ndarray,
    left_wrist_depth: np.ndarray,
    right_wrist_rgb: np.ndarray,
    right_wrist_depth: np.ndarray,
    K_zed: np.ndarray,
    K_left_wrist: np.ndarray,
    K_right_wrist: np.ndarray,
    T_base_camera_zed: np.ndarray,
    T_base_camera_left_wrist: np.ndarray,
    T_base_camera_right_wrist: np.ndarray,
    base_state: np.ndarray,
    torso_q: np.ndarray,
    left_arm_q: np.ndarray,
    left_gripper_q: np.ndarray,
    right_arm_q: np.ndarray,
    right_gripper_q: np.ndarray,
    prompt: str,
) -> dict[str, Any]:
    """Build the plain, serializable BEHAVIOR raw-observation dictionary."""
    return {
        "zed_rgb": _as_numpy(zed_rgb),
        "zed_depth": _as_numpy(zed_depth),
        "left_wrist_rgb": _as_numpy(left_wrist_rgb),
        "left_wrist_depth": _as_numpy(left_wrist_depth),
        "right_wrist_rgb": _as_numpy(right_wrist_rgb),
        "right_wrist_depth": _as_numpy(right_wrist_depth),
        "K_zed": _as_numpy(K_zed),
        "K_left_wrist": _as_numpy(K_left_wrist),
        "K_right_wrist": _as_numpy(K_right_wrist),
        "T_base_camera_zed": _as_numpy(T_base_camera_zed),
        "T_base_camera_left_wrist": _as_numpy(T_base_camera_left_wrist),
        "T_base_camera_right_wrist": _as_numpy(T_base_camera_right_wrist),
        "base_state": _as_numpy(base_state),
        "torso_q": _as_numpy(torso_q),
        "left_arm_q": _as_numpy(left_arm_q),
        "left_gripper_q": _as_numpy(left_gripper_q),
        "right_arm_q": _as_numpy(right_arm_q),
        "right_gripper_q": _as_numpy(right_gripper_q),
        "prompt": prompt,
    }


def _pose_xyzw_to_matrix(position: np.ndarray, quaternion_xyzw: np.ndarray) -> np.ndarray:
    """Return column-vector T_world_frame using meters and an xyzw quaternion."""
    position = _as_numpy(position).astype(np.float64).reshape(3)
    x, y, z, w = _as_numpy(quaternion_xyzw).astype(np.float64).reshape(4)
    norm = np.linalg.norm([x, y, z, w])
    if norm == 0.0:
        raise ValueError("camera or base quaternion must be non-zero")
    x, y, z, w = np.array([x, y, z, w]) / norm
    rotation = np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ],
        dtype=np.float64,
    )
    transform = np.eye(4, dtype=np.float64)
    transform[:3, :3] = rotation
    transform[:3, 3] = position
    return transform.astype(np.float32)


def _finite_positive_scalar(value: Any, *, name: str) -> float:
    """Convert a scalar USD value and validate it for metric geometry use."""
    scalar = float(_as_numpy(value).reshape(-1)[0])
    if not np.isfinite(scalar) or scalar <= 0.0:
        raise RuntimeError(f"{name} must be finite and positive, got {scalar}")
    return scalar


def _finite_scalar(value: Any, *, name: str) -> float:
    """Convert a scalar USD value without imposing a sign constraint."""
    scalar = float(_as_numpy(value).reshape(-1)[0])
    if not np.isfinite(scalar):
        raise RuntimeError(f"{name} must be finite, got {scalar}")
    return scalar


def _configured_vision_sensor_resolution(robot: Any) -> tuple[int, int]:
    """Return the RGB-D render size declared before ``Environment`` creation.

    A USD Camera describes optical geometry, not image resolution. Resolution
    belongs to OmniGibson's already-created VisionSensor render product and is
    declared by the R1 Pro environment configuration. Reading this stored
    configuration neither touches a VisionSensor property nor creates a
    modality or annotator.
    """
    try:
        sensor_kwargs = robot._sensor_config["VisionSensor"]["sensor_kwargs"]
        width = int(sensor_kwargs["image_width"])
        height = int(sensor_kwargs["image_height"])
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(
            "R1 Pro VisionSensor image_width/image_height must be configured before Environment creation"
        ) from exc
    if width <= 0 or height <= 0:
        raise RuntimeError(f"configured VisionSensor resolution must be positive, got {width}x{height}")
    return width, height


def _camera_prim_attribute(camera_prim: Any, attribute_name: str) -> Any:
    """Read an authored or schema-default USD Camera property from a prim."""
    attribute = camera_prim.GetAttribute(attribute_name)
    if not attribute or not attribute.IsValid():
        raise RuntimeError(f"USD Camera {camera_prim.GetPath()} has no valid {attribute_name!r} attribute")
    value = attribute.Get()
    if value is None:
        raise RuntimeError(f"USD Camera {camera_prim.GetPath()} has no value for {attribute_name!r}")
    return value


def _intrinsics_from_usd_camera(
    camera_prim: Any,
    width: int,
    height: int,
    *,
    camera_name: str,
    on_stage: Callable[[str], None] | None = None,
) -> np.ndarray:
    """Compute K from raw, fixed USD Camera prim attributes.

    This deliberately does *not* construct ``UsdGeom.Camera`` or a
    ``GfCamera``/``GfFrustum``.  Only the Camera prim's regular USD attributes
    are read, so this does not add a VisionSensor annotator, create a render
    product, or cause a render tick.

    USD perspective cameras define the filmback in matching aperture and focal
    length units (USD currently uses tenths of millimetres for both).  With
    focal length ``f``, apertures ``a_h`` / ``a_v`` and aperture offsets
    ``o_h`` / ``o_v``, OpenUSD's perspective projection is equivalent to:

        fx = f / a_h * width
        fy = f / a_v * height
        cx = width  * (0.5 - o_h / a_h)
        cy = height * (0.5 - o_v / a_v)

    Thus schema defaults for vertical aperture and the two offsets are used
    naturally, rather than being hard-coded.  Image dimensions come from the
    pre-environment VisionSensor configuration because resolution is not a USD
    Camera property.
    """
    def read(attribute_name: str) -> Any:
        if on_stage is not None:
            on_stage(f"stage=before_camera_attr:{camera_name}:{attribute_name}")
        value = _camera_prim_attribute(camera_prim, attribute_name)
        if on_stage is not None:
            on_stage(f"stage=camera_attr_ready:{camera_name}:{attribute_name}")
        return value

    camera_path = str(camera_prim.GetPath())
    projection = str(read("projection"))
    if projection != "perspective":
        raise RuntimeError(f"R1 Pro camera {camera_path} must use perspective projection, got {projection!r}")

    focal_length = _finite_positive_scalar(read("focalLength"), name=f"{camera_path}.focalLength")
    horizontal_aperture = _finite_positive_scalar(
        read("horizontalAperture"), name=f"{camera_path}.horizontalAperture"
    )
    vertical_aperture = _finite_positive_scalar(
        read("verticalAperture"), name=f"{camera_path}.verticalAperture"
    )
    horizontal_offset = _finite_scalar(
        read("horizontalApertureOffset"), name=f"{camera_path}.horizontalApertureOffset"
    )
    vertical_offset = _finite_scalar(
        read("verticalApertureOffset"), name=f"{camera_path}.verticalApertureOffset"
    )

    fx = focal_length * width / horizontal_aperture
    fy = focal_length * height / vertical_aperture
    cx = width * (0.5 - horizontal_offset / horizontal_aperture)
    cy = height * (0.5 - vertical_offset / vertical_aperture)
    intrinsic_matrix = np.array(
        [[fx, 0.0, cx], [0.0, fy, cy], [0.0, 0.0, 1.0]], dtype=np.float32
    )
    if not np.all(np.isfinite(intrinsic_matrix)) or intrinsic_matrix[0, 0] <= 0 or intrinsic_matrix[1, 1] <= 0:
        raise RuntimeError(f"USD camera {camera_path} produced an invalid intrinsic matrix: {intrinsic_matrix}")
    return intrinsic_matrix


def _world_transform_from_usd_camera(
    camera_prim: Any,
    usd_geom: Any,
    meters_per_scene_unit: float,
    *,
    camera_name: str,
    on_stage: Callable[[str], None] | None = None,
) -> np.ndarray:
    """Return column-vector T_world_camera in metres from the live USD prim."""
    # XformCache returns a Gf row-vector transform. Transpose it into the
    # column-vector convention used by _pose_xyzw_to_matrix, then scale only
    # its translation from USD scene units to metres.
    if on_stage is not None:
        on_stage(f"stage=before_camera_world_transform:{camera_name}")
    cache = usd_geom.XformCache()
    if on_stage is not None:
        on_stage(f"stage=camera_xform_cache_ready:{camera_name}")
    gf_transform = cache.GetLocalToWorldTransform(camera_prim)
    if on_stage is not None:
        on_stage(f"stage=camera_world_transform_ready:{camera_name}")
    # Avoid relying on a NumPy buffer conversion for GfMatrix4d. Explicit
    # indexing is stable across the Isaac Sim 4.5 Python bindings.
    world_transform = np.array(
        [[float(gf_transform[row][column]) for column in range(4)] for row in range(4)],
        dtype=np.float64,
    ).T
    if on_stage is not None:
        on_stage(f"stage=after_camera_world_transform_conversion:{camera_name}")
    if world_transform.shape != (4, 4) or not np.all(np.isfinite(world_transform)):
        raise RuntimeError(f"USD camera {camera_prim.GetPath()} returned an invalid world transform")
    world_transform[:3, 3] *= meters_per_scene_unit
    return world_transform.astype(np.float32)


@dataclass(frozen=True)
class _CameraMetadata:
    name: str
    prim_path: str
    prim: Any
    sensor_name: str
    intrinsic_matrix: np.ndarray


def _camera_raw_data(
    metadata: _CameraMetadata,
    sensor_observation: dict[str, Any],
    base_world_transform: np.ndarray,
    meters_per_scene_unit: float,
    usd_geom: Any,
    on_stage: Callable[[str], None] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if on_stage is not None:
        on_stage(f"stage=before_camera_sensor_observation_check:{metadata.name}")
    if not isinstance(sensor_observation, dict):
        raise RuntimeError(
            f"R1 Pro {metadata.name.replace('_', ' ')} sensor observation must be a dict, "
            f"got {type(sensor_observation).__name__}"
        )
    if on_stage is not None:
        on_stage(
            f"stage=camera_sensor_observation_keys:{metadata.name}="
            f"{','.join(sorted(str(key) for key in sensor_observation))}"
        )
    if "rgb" not in sensor_observation or "depth" not in sensor_observation:
        missing = "depth" if "depth" not in sensor_observation else "rgb"
        raise RuntimeError(
            f"R1 Pro {metadata.name.replace('_', ' ')} {missing} modality was not configured before "
            f"Environment creation (sensor={metadata.sensor_name}, prim={metadata.prim_path}, "
            f"obs_keys={sorted(sensor_observation)})"
        )
    if on_stage is not None:
        on_stage(f"stage=before_camera_rgbd_conversion:{metadata.name}")
    rgb = _as_numpy(sensor_observation["rgb"])[..., :3]
    depth = _as_numpy(sensor_observation["depth"])
    if depth.ndim == 3 and depth.shape[2] == 1:
        depth = depth[..., 0]
    if on_stage is not None:
        on_stage(f"stage=after_camera_rgbd_conversion:{metadata.name}")

    # OmniGibson's distance_to_camera image is expressed in scene units.
    # Convert it once here so raw_obs depth is always metres before the adapter.
    depth_m = depth.astype(np.float32) * meters_per_scene_unit
    invalid_depth = ~np.isfinite(depth_m)
    if np.any(invalid_depth):
        depth_m = depth_m.copy()
        depth_m[invalid_depth] = INVALID_DEPTH_M
    if on_stage is not None:
        on_stage(f"stage=after_camera_depth_normalization:{metadata.name}")
    world_camera_transform = _world_transform_from_usd_camera(
        metadata.prim,
        usd_geom,
        meters_per_scene_unit,
        camera_name=metadata.name,
        on_stage=on_stage,
    )
    T_base_camera = (np.linalg.inv(base_world_transform) @ world_camera_transform).astype(np.float32)
    return rgb, depth_m, metadata.intrinsic_matrix, T_base_camera


class R1ProObservationCollector:
    """Collect synchronized R1 Pro observations without adding render ticks.

    RGB-D comes only from the already-configured ``robot.get_obs()`` pipeline.
    The fixed USD Camera prims supply calibration and their live transforms;
    this class never accesses ``VisionSensor.camera_parameters`` or
    ``VisionSensor.intrinsic_matrix`` and never adds modalities.
    """

    def __init__(
        self,
        robot: Any,
        *,
        stage: Any,
        usd_geom: Any,
        on_stage: Callable[[str], None] | None = None,
    ) -> None:
        self._robot = robot
        self._usd_geom = usd_geom
        self._on_stage = on_stage
        self._emit_stage("stage=before_camera_stage_scale")
        self._meters_per_scene_unit = _finite_positive_scalar(
            usd_geom.GetStageMetersPerUnit(stage), name="USD metersPerUnit"
        )
        self._emit_stage("stage=camera_stage_scale_ready")
        self._emit_stage("stage=before_camera_resolution")
        image_width, image_height = _configured_vision_sensor_resolution(robot)
        self._emit_stage("stage=camera_resolution_ready")

        # RobotBase deterministically names each Camera VisionSensor as
        # ``{robot.name}:{link_name}:Camera:0``. Keep that exact key rather
        # than touching robot.sensors during collector construction. It is
        # verified after the sole robot.get_obs() call below, with the actual
        # observation keys included in any error message.
        self._emit_stage("stage=before_camera_observation_keys")
        sensor_keys = {
            camera_name: f"{robot.name}:{link_name}:Camera:0"
            for camera_name, link_name in R1PRO_CAMERA_LINKS.items()
        }
        self._emit_stage("stage=camera_observation_keys_ready")
        resolved_cameras: list[tuple[str, str, Any, str]] = []
        for camera_name, relative_camera_path in R1PRO_CAMERA_PATHS.items():
            prim_path = f"{str(robot.prim_path).rstrip('/')}/{relative_camera_path}"
            self._emit_stage(f"stage=before_camera_prim:{camera_name}")
            camera_prim = stage.GetPrimAtPath(prim_path)
            if not camera_prim or not camera_prim.IsValid() or camera_prim.GetTypeName() != "Camera":
                actual_type = camera_prim.GetTypeName() if camera_prim and camera_prim.IsValid() else "missing"
                raise RuntimeError(f"expected fixed R1 Pro Camera prim at {prim_path}, got {actual_type}")
            self._emit_stage(f"stage=camera_prim_ready:{camera_name}")
            resolved_cameras.append((camera_name, prim_path, camera_prim, sensor_keys[camera_name]))
        self._emit_stage("stage=camera_prims_resolved")

        self._camera_metadata: dict[str, _CameraMetadata] = {}
        for camera_name, prim_path, camera_prim, sensor_name in resolved_cameras:
            self._emit_stage(f"stage=before_camera_intrinsics:{camera_name}")
            self._camera_metadata[camera_name] = _CameraMetadata(
                name=camera_name,
                prim_path=prim_path,
                prim=camera_prim,
                sensor_name=sensor_name,
                intrinsic_matrix=_intrinsics_from_usd_camera(
                    camera_prim,
                    image_width,
                    image_height,
                    camera_name=camera_name,
                    on_stage=self._emit_stage,
                ),
            )
            self._emit_stage(f"stage=camera_intrinsics_ready:{camera_name}")
        self._emit_stage("stage=camera_intrinsics_cached")

    def _emit_stage(self, marker: str) -> None:
        if self._on_stage is not None:
            self._on_stage(marker)

    def collect(self, prompt: str) -> dict[str, Any]:
        """Read one synchronized observation from the current simulator state."""
        self._emit_stage("stage=before_robot_get_obs")
        sensor_observations, _ = self._robot.get_obs()
        self._emit_stage("stage=after_robot_get_obs")
        self._emit_stage("stage=before_robot_pose")
        base_position, base_quaternion_xyzw = self._robot.get_position_orientation()
        self._emit_stage("stage=after_robot_pose")
        base_world_transform = _pose_xyzw_to_matrix(base_position, base_quaternion_xyzw)
        self._emit_stage("stage=robot_pose_matrix_ready")
        self._emit_stage("stage=before_joint_positions")
        joint_positions = _as_numpy(self._robot.get_joint_positions()).astype(np.float32)
        self._emit_stage("stage=after_joint_positions")

        camera_data: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = {}
        for camera_name, metadata in self._camera_metadata.items():
            try:
                self._emit_stage(f"stage=before_camera_data:{camera_name}")
                self._emit_stage(f"stage=before_camera_sensor_lookup:{camera_name}")
                if not isinstance(sensor_observations, dict):
                    raise RuntimeError(
                        f"R1 Pro outer observation must be a dict, got {type(sensor_observations).__name__}"
                    )
                outer_keys = tuple(str(key) for key in sensor_observations.keys())
                self._emit_stage(
                    f"stage=robot_observation_sensor_keys={','.join(outer_keys)}"
                )
                sensor_observation = sensor_observations.get(metadata.sensor_name)
                if sensor_observation is None:
                    raise RuntimeError(
                        f"R1 Pro {camera_name.replace('_', ' ')} observation is absent for configured "
                        f"sensor {metadata.sensor_name}; obs keys={outer_keys}"
                    )
                self._emit_stage(f"stage=after_camera_sensor_lookup:{camera_name}")
                camera_data[camera_name] = _camera_raw_data(
                    metadata,
                    sensor_observation,
                    base_world_transform,
                    self._meters_per_scene_unit,
                    self._usd_geom,
                    self._emit_stage,
                )
                self._emit_stage(f"stage=after_camera_data:{camera_name}")
            except Exception as exc:
                raise RuntimeError(f"failed to collect {camera_name} camera observation: {exc}") from exc

        self._emit_stage("stage=before_gripper_state")
        left_gripper_fingers = _joint_component(joint_positions, self._robot.gripper_control_idx["left"])
        right_gripper_fingers = _joint_component(joint_positions, self._robot.gripper_control_idx["right"])
        self._emit_stage("stage=after_gripper_state")
        self._emit_stage("stage=before_raw_obs_build")
        raw_obs = build_raw_obs(
            zed_rgb=camera_data["zed"][0],
            zed_depth=camera_data["zed"][1],
            left_wrist_rgb=camera_data["left_wrist"][0],
            left_wrist_depth=camera_data["left_wrist"][1],
            right_wrist_rgb=camera_data["right_wrist"][0],
            right_wrist_depth=camera_data["right_wrist"][1],
            K_zed=camera_data["zed"][2],
            K_left_wrist=camera_data["left_wrist"][2],
            K_right_wrist=camera_data["right_wrist"][2],
            T_base_camera_zed=camera_data["zed"][3],
            T_base_camera_left_wrist=camera_data["left_wrist"][3],
            T_base_camera_right_wrist=camera_data["right_wrist"][3],
            base_state=np.concatenate((_as_numpy(base_position), _as_numpy(base_quaternion_xyzw))).astype(np.float32),
            torso_q=_joint_component(joint_positions, self._robot.trunk_control_idx),
            left_arm_q=_joint_component(joint_positions, self._robot.arm_control_idx["left"]),
            left_gripper_q=np.array([left_gripper_fingers.mean()], dtype=np.float32),
            right_arm_q=_joint_component(joint_positions, self._robot.arm_control_idx["right"]),
            right_gripper_q=np.array([right_gripper_fingers.mean()], dtype=np.float32),
            prompt=prompt,
        )
        self._emit_stage("stage=after_raw_obs_build")
        return raw_obs


def _joint_component(joint_positions: np.ndarray, indices: Any) -> np.ndarray:
    index_array = _as_numpy(indices).astype(np.int64).reshape(-1)
    return joint_positions[index_array].astype(np.float32, copy=False)


def collect_raw_obs(robot: Any, prompt: str, *, stage: Any, usd_geom: Any) -> dict[str, Any]:
    """Collect a plain raw_obs from an initialized OmniGibson R1 Pro.

    The caller owns simulator lifecycle and must not pass the resulting robot,
    stage, or sensor objects across the planner boundary. This helper extracts
    only arrays and a prompt before returning.
    """
    return R1ProObservationCollector(robot, stage=stage, usd_geom=usd_geom).collect(prompt)
