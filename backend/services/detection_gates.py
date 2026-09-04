"""
Post-model gates that reduce high-cost false positives.

- FallPoseGate: MediaPipe pose confirms torso is near-horizontal / not upright.
- WeaponThreatGate: pose shooting-like stance and/or YOLO weapon-proxy classes.
"""
from __future__ import annotations

from typing import Optional, Sequence, Tuple

import cv2
import numpy as np

try:
    import mediapipe as mp

    _MP_AVAILABLE = True
except ImportError:  # pragma: no cover
    mp = None
    _MP_AVAILABLE = False

from models.yolo_detector import yolo_model

# COCO names that can weakly support a weapon threat (yolov8n has no "gun").
# Used as an optional second signal together with pose.
WEAPON_PROXY_CLASS_IDS = {
    43,  # knife
    76,  # scissors
}


class FallPoseGate:
    """
    Confirm or veto fall_floor using torso orientation from MediaPipe Pose.

    - Standing / upright torso → veto fall
    - Near-horizontal torso or hips near head height → confirm fall
    - No landmarks → allow model decision (do not veto)
    """

    def __init__(
        self,
        upright_angle_max: float = 35.0,
        fall_angle_min: float = 55.0,
        min_visibility: float = 0.4,
    ):
        self.upright_angle_max = upright_angle_max
        self.fall_angle_min = fall_angle_min
        self.min_visibility = min_visibility
        self._pose = None
        if _MP_AVAILABLE:
            self._pose = mp.solutions.pose.Pose(
                static_image_mode=True,
                model_complexity=0,
                enable_segmentation=False,
                min_detection_confidence=0.5,
            )

    def _landmarks(self, frame_bgr: np.ndarray):
        if self._pose is None:
            return None
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        result = self._pose.process(rgb)
        if not result.pose_landmarks:
            return None
        return result.pose_landmarks.landmark

    @staticmethod
    def _midpoint(a, b):
        return ((a.x + b.x) / 2.0, (a.y + b.y) / 2.0)

    def torso_angle_from_vertical(self, landmarks) -> Optional[float]:
        """
        Angle in degrees between shoulder-hip vector and vertical axis.
        0 ≈ upright, ~90 ≈ lying horizontal.
        """
        # MediaPipe: 11/12 shoulders, 23/24 hips
        ls, rs = landmarks[11], landmarks[12]
        lh, rh = landmarks[23], landmarks[24]
        vis = min(ls.visibility, rs.visibility, lh.visibility, rh.visibility)
        if vis < self.min_visibility:
            return None

        sh = self._midpoint(ls, rs)
        hip = self._midpoint(lh, rh)
        dx = sh[0] - hip[0]
        dy = sh[1] - hip[1]
        # angle vs vertical (0, 1) in image coords (y down)
        # vector from hip to shoulder
        # vertical down is (0, 1); upright standing shoulder is above hip → (0, -1)
        # angle from upright vertical-up (0, -1):
        upright = np.array([0.0, -1.0])
        vec = np.array([dx, dy], dtype=np.float64)
        norm = np.linalg.norm(vec)
        if norm < 1e-6:
            return None
        vec = vec / norm
        cos_a = float(np.clip(np.dot(vec, upright), -1.0, 1.0))
        return float(np.degrees(np.arccos(cos_a)))

    def confirms_fall(self, frame_bgr: np.ndarray) -> Tuple[bool, str]:
        """
        Returns (allow_fall_label, reason).
        allow=False means veto fall → treat as non-fall.
        """
        if self._pose is None:
            return True, "mediapipe_unavailable"

        landmarks = self._landmarks(frame_bgr)
        if landmarks is None:
            return True, "no_pose"

        angle = self.torso_angle_from_vertical(landmarks)
        if angle is None:
            return True, "low_visibility"

        if angle <= self.upright_angle_max:
            return False, f"upright_torso_angle={angle:.1f}"

        if angle >= self.fall_angle_min:
            return True, f"horizontal_torso_angle={angle:.1f}"

        # Ambiguous mid-range (e.g. bending): allow model but tag
        return True, f"ambiguous_torso_angle={angle:.1f}"


class WeaponThreatGate:
    """
    Confirm shoot_gun-like threat via:

    1) YOLO weapon-proxy classes (knife/scissors — no firearm in COCO)
    2) Pose: extended arm(s) consistent with aiming / pointing a weapon

    If neither signal supports a weapon threat, veto shoot_gun.
    """

    def __init__(
        self,
        yolo_conf: float = 0.25,
        arm_extension_ratio: float = 1.15,
        min_visibility: float = 0.4,
        require_pose_or_object: bool = True,
    ):
        self.yolo_conf = yolo_conf
        self.arm_extension_ratio = arm_extension_ratio
        self.min_visibility = min_visibility
        self.require_pose_or_object = require_pose_or_object
        self._pose = None
        if _MP_AVAILABLE:
            self._pose = mp.solutions.pose.Pose(
                static_image_mode=True,
                model_complexity=0,
                enable_segmentation=False,
                min_detection_confidence=0.5,
            )

    def _has_weapon_proxy(self, frame_bgr: np.ndarray) -> Tuple[bool, str]:
        try:
            results = yolo_model.predict(frame_bgr, conf=self.yolo_conf, verbose=False)
        except Exception as exc:  # pragma: no cover
            return False, f"yolo_error={exc}"

        if not results:
            return False, "no_yolo_results"

        names = results[0].names or {}
        for box in results[0].boxes:
            cls_id = int(box.cls)
            if cls_id in WEAPON_PROXY_CLASS_IDS:
                label = names.get(cls_id, str(cls_id))
                return True, f"weapon_proxy={label}"
        return False, "no_weapon_proxy"

    def _arm_extension_pose(self, frame_bgr: np.ndarray) -> Tuple[bool, str]:
        if self._pose is None:
            return False, "mediapipe_unavailable"

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        result = self._pose.process(rgb)
        if not result.pose_landmarks:
            return False, "no_pose"

        lm = result.pose_landmarks.landmark
        # shoulders 11/12, elbows 13/14, wrists 15/16
        pairs = [(11, 13, 15), (12, 14, 16)]
        extended = 0
        details = []

        for sh_i, el_i, wr_i in pairs:
            sh, el, wr = lm[sh_i], lm[el_i], lm[wr_i]
            if min(sh.visibility, el.visibility, wr.visibility) < self.min_visibility:
                continue
            upper = np.hypot(el.x - sh.x, el.y - sh.y)
            forearm = np.hypot(wr.x - el.x, wr.y - el.y)
            reach = np.hypot(wr.x - sh.x, wr.y - sh.y)
            # extended arm: wrist far from shoulder relative to upper arm length
            if upper > 1e-3 and reach / upper >= self.arm_extension_ratio:
                # prefer roughly horizontal extension (weapon aim often lateral/forward)
                dx = abs(wr.x - sh.x)
                dy = abs(wr.y - sh.y)
                if dx >= dy * 0.6:  # not purely vertical raise
                    extended += 1
                    details.append(f"arm{sh_i}_reach={reach / upper:.2f}")

        if extended > 0:
            return True, "extended_arm:" + ",".join(details)
        return False, "no_extended_arm"

    def confirms_weapon(self, frame_bgr: np.ndarray) -> Tuple[bool, str]:
        obj_ok, obj_reason = self._has_weapon_proxy(frame_bgr)
        pose_ok, pose_reason = self._arm_extension_pose(frame_bgr)

        if obj_ok or pose_ok:
            return True, f"{obj_reason}|{pose_reason}"

        if not self.require_pose_or_object:
            return True, "gate_disabled_mode"

        return False, f"veto:{obj_reason}|{pose_reason}"


# Lazy singletons used by the predictor
_fall_gate: Optional[FallPoseGate] = None
_weapon_gate: Optional[WeaponThreatGate] = None


def get_fall_pose_gate() -> FallPoseGate:
    global _fall_gate
    if _fall_gate is None:
        _fall_gate = FallPoseGate()
    return _fall_gate


def get_weapon_threat_gate() -> WeaponThreatGate:
    global _weapon_gate
    if _weapon_gate is None:
        _weapon_gate = WeaponThreatGate()
    return _weapon_gate
