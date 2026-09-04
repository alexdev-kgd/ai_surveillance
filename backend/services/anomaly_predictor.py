from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import torch

from core.config import (
    CLASS_TO_ACTION,
    ENABLE_FALL_POSE_GATE,
    ENABLE_WEAPON_THREAT_GATE,
    FRONTEND_LABELS,
    STRIDE,
)
from models.anomaly_model import class_names, video_model
from models.yolo_detector import yolo_model
from services.detection_gates import get_fall_pose_gate, get_weapon_threat_gate
from services.settings import get_settings
from utils.device import device
from utils.text import TEXT_DEFAULT_POSITION, put_text_ru
from utils.video_preprocess import (
    CLIP_LEN,
    SAMPLE_STRIDE,
    bgr_to_rgb_uint8,
    prepare_model_inputs,
)

# Keep buffer of RGB uint8 frames (not pre-normalized) so flow can be computed.
# Stride is applied when appending so train/serve sampling match.
_rgb_buffer: List[np.ndarray] = []
_raw_frame_counter = 0

current_label = FRONTEND_LABELS["normal"]
current_confidence = 0.0
current_is_alert = False
ttl_counter = 0


# ----------------------------
# thresholds
# ----------------------------
def sensitivity_to_threshold(sensitivity: float) -> float:
    """Map UI sensitivity [0,1] → confidence threshold (higher sens → lower thresh)."""
    return max(0.1, 0.9 - float(sensitivity) * 0.7)


def resolve_thresholds(action_cfg: dict) -> Tuple[float, float]:
    """
    Returns (display_threshold, alert_threshold).

    alert_threshold is always >= display_threshold (stricter or equal).
    """
    display_sens = float(action_cfg.get("sensitivity", 0.5))
    alert_sens = action_cfg.get("alert_sensitivity")
    if alert_sens is None:
        alert_sens = max(0.0, display_sens - 0.2)
    else:
        alert_sens = float(alert_sens)

    display_th = sensitivity_to_threshold(display_sens)
    alert_th = sensitivity_to_threshold(alert_sens)
    # Ensure alert is at least as strict as display
    alert_th = max(alert_th, display_th)
    return display_th, alert_th


def draw_action_label(frame, label, confidence, position=None, is_alert: bool = False):
    is_normal = label == FRONTEND_LABELS["normal"]
    if is_normal:
        color = (0, 255, 0)
    elif is_alert:
        color = (0, 0, 255)
    else:
        color = (0, 165, 255)  # orange: displayed but below alert threshold

    if is_normal:
        text = f"{label} ({confidence:.2f})"
    elif is_alert:
        text = f"Подозрительное действие: {label} ({confidence:.2f})"
    else:
        text = f"{label} ({confidence:.2f})"

    if position is None:
        position = TEXT_DEFAULT_POSITION

    return put_text_ru(frame, text, position=position, color=color), is_normal


def _apply_gates(
    action_key: str,
    frame_bgr: np.ndarray,
) -> Tuple[bool, str]:
    """
    Returns (accepted, reason). If not accepted, caller should skip this class.
    """
    if action_key == "fall_floor" and ENABLE_FALL_POSE_GATE:
        ok, reason = get_fall_pose_gate().confirms_fall(frame_bgr)
        return ok, f"fall_gate:{reason}"

    if action_key == "shoot_gun" and ENABLE_WEAPON_THREAT_GATE:
        ok, reason = get_weapon_threat_gate().confirms_weapon(frame_bgr)
        return ok, f"weapon_gate:{reason}"

    return True, "no_gate"


# ----------------------------
# CORE MODEL INFERENCE
# ----------------------------
def anomaly_model_predict(
    frame_bgr: np.ndarray,
    gate_frame_bgr: Optional[np.ndarray] = None,
) -> Tuple[str, float, bool]:
    """
    Returns (frontend_label, confidence, is_alert).

    `frame_bgr` is used for the model clip (may be a person crop).
    `gate_frame_bgr` is used for pose/weapon gates (defaults to frame_bgr).
    """
    global _rgb_buffer, _raw_frame_counter

    gate_frame = gate_frame_bgr if gate_frame_bgr is not None else frame_bgr

    _raw_frame_counter += 1

    # Match training SAMPLE_STRIDE: only keep every STRIDE-th frame
    if (_raw_frame_counter - 1) % SAMPLE_STRIDE != 0:
        # Between samples: return persistent state via caller; emit neutral here
        return FRONTEND_LABELS["normal"], 0.0, False

    rgb = bgr_to_rgb_uint8(frame_bgr)
    _rgb_buffer.append(rgb)

    # Keep a bit of history; model needs CLIP_LEN strided frames
    max_buf = CLIP_LEN * 2
    if len(_rgb_buffer) > max_buf:
        _rgb_buffer = _rgb_buffer[-max_buf:]

    # print(f"len(_rgb_buffer)={len(_rgb_buffer)}, CLIP_LEN={CLIP_LEN}")
    # print(f"{len(_rgb_buffer) < CLIP_LEN} is len(_rgb_buffer) < CLIP_LEN")
    if len(_rgb_buffer) < CLIP_LEN:
        return FRONTEND_LABELS["normal"], 0.0, False

    clip_frames = _rgb_buffer[-CLIP_LEN:]

    # Real optical flow (same Farneback params as training precompute)
    # print(f"anomaly_model_predict: computing flow for {len(clip_frames)} frames") 
    rgb_tensor, flow_tensor = prepare_model_inputs(clip_frames, flow_array=None, device=device)

    with torch.no_grad():
        logits = video_model(rgb_tensor, flow_tensor)
        probs = torch.softmax(logits, dim=-1)[0]

    topk = torch.topk(probs, min(3, probs.numel()))

    settings = get_settings()
    if not settings:
        conf = float(probs.max())
        return FRONTEND_LABELS["normal"], conf, False

    for i, conf_t in zip(topk.indices, topk.values):
        label = class_names[int(i)]
        confidence = float(conf_t)
        if label == "normal":
            continue

        action_key = CLASS_TO_ACTION.get(label)
        if not action_key:
            continue

        action_cfg = settings["detection"].get(action_key)
        if not action_cfg or not action_cfg.get("enabled"):
            continue

        display_th, alert_th = resolve_thresholds(action_cfg)

        if confidence < display_th:
            continue

        print(f"anomaly_model_predict: action_key={action_key}, label={label}, confidence={confidence:.3f}, display_th={display_th:.3f}, alert_th={alert_th:.3f}")
        # High-cost gates
        accepted, _reason = _apply_gates(action_key, gate_frame)
        if not accepted:
            continue

        is_alert = confidence >= alert_th
        return FRONTEND_LABELS.get(action_key, action_key), confidence, is_alert

    return FRONTEND_LABELS["normal"], float(probs.max()), False


def get_persistent_prediction(
    new_label: str,
    new_confidence: float,
    new_is_alert: bool = False,
) -> Tuple[str, float, bool]:
    global current_label, current_confidence, current_is_alert, ttl_counter

    if new_label != FRONTEND_LABELS["normal"]:
        current_label = new_label
        current_confidence = new_confidence
        current_is_alert = new_is_alert
        ttl_counter = 4
    else:
        if ttl_counter > 0:
            ttl_counter -= 1
        else:
            current_label = FRONTEND_LABELS["normal"]
            current_confidence = new_confidence
            current_is_alert = False

    return current_label, current_confidence, current_is_alert


def analyze_with_yolo(frame: np.ndarray, total_frames: int) -> Dict[str, Any]:
    detections: List[dict] = []
    best_label = FRONTEND_LABELS["normal"]
    best_confidence = 0.0
    best_is_alert = False

    yolo_results = yolo_model.predict(frame, conf=0.2, verbose=False)

    for r in yolo_results[0].boxes:
        cls_id = int(r.cls)

        if cls_id != 0:  # person only
            continue

        x1, y1, x2, y2 = map(int, r.xyxy[0].tolist())
        person_crop = frame[y1:y2, x1:x2]
        if person_crop.size == 0:
            continue

        raw_label, raw_confidence, raw_is_alert = anomaly_model_predict(
            person_crop,
            gate_frame_bgr=person_crop,
        )

        label, confidence, is_alert = get_persistent_prediction(
            raw_label, raw_confidence, raw_is_alert
        )

        rank = confidence + (0.5 if is_alert else 0.0)
        best_rank = best_confidence + (0.5 if best_is_alert else 0.0)
        if rank > best_rank:
            best_label = label
            best_confidence = confidence
            best_is_alert = is_alert

        frame, is_normal = draw_action_label(
            frame,
            label,
            confidence,
            position=(x1 + 5, y1 - 30),
            is_alert=is_alert,
        )

        color = (0, 255, 0) if is_normal else ((0, 0, 255) if is_alert else (0, 165, 255))
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        detections.append(
            {
                "frame": total_frames,
                "bbox": [x1, y1, x2, y2],
                "label": label,
                "confidence": confidence,
                "is_alert": is_alert,
            }
        )

    return {
        "frame_data": frame,
        "frame": total_frames,
        "label": best_label,
        "confidence": best_confidence,
        "is_alert": best_is_alert,
        "detections": detections,
    }


def analyze_scene(frame: np.ndarray, total_frames: int) -> Dict[str, Any]:
    raw_label, raw_confidence, raw_is_alert = anomaly_model_predict(
        frame,
        gate_frame_bgr=frame,
    )

    # print (
    #     f"[analyze_scene] raw_label={raw_label}, raw_confidence={raw_confidence:.3f}, raw_is_alert={raw_is_alert}"
    # )

    label, confidence, is_alert = get_persistent_prediction(
        raw_label, raw_confidence, raw_is_alert
    )

    frame, _ = draw_action_label(frame, label, confidence, is_alert=is_alert)

    # print(
    #     f"[analyze_scene] frame {total_frames}: label={label}, confidence={confidence:.3f}, is_alert={is_alert}"
    # )

    return {
        "frame_data": frame,
        "frame": total_frames,
        "label": label,
        "confidence": confidence,
        "is_alert": is_alert,
        "detections": [
            {
                "frame": total_frames,
                "label": label,
                "confidence": confidence,
                "is_alert": is_alert,
            }
        ],
    }


def reset_predictor_state() -> None:
    """Reset global buffers (useful between videos / tests)."""
    global _rgb_buffer, _raw_frame_counter
    global current_label, current_confidence, current_is_alert, ttl_counter
    _rgb_buffer = []
    _raw_frame_counter = 0
    current_label = FRONTEND_LABELS["normal"]
    current_confidence = 0.0
    current_is_alert = False
    ttl_counter = 0
