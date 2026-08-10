import torch
import cv2
import numpy as np

from models.anomaly_model import video_model, class_names
from models.yolo_detector import yolo_model
from core.config import FRAME_WINDOW, STRIDE, CLASS_TO_ACTION, FRONTEND_LABELS
from utils.device import device
from services.settings import get_settings
from utils.text import put_text_ru, TEXT_DEFAULT_POSITION


frame_buffer = []
frame_counter = 0

current_label = FRONTEND_LABELS["normal"]
current_confidence = 0.0
ttl_counter = 0  # сколько кадров ещё держим прошлую детекцию

# ----------------------------
# utils
# ----------------------------
def sensitivity_to_threshold(sensitivity: float) -> float:
    return max(0.1, 0.9 - sensitivity * 0.7)


def draw_action_label(frame, label, confidence, position=None):
    is_normal = label == FRONTEND_LABELS["normal"]
    color = (0, 255, 0) if is_normal else (0, 0, 255)

    text = (
        f"{label} ({confidence:.2f})"
        if is_normal
        else f"Подозрительное действие: {label} ({confidence:.2f})"
    )

    if position is None:
        position = TEXT_DEFAULT_POSITION

    return put_text_ru(frame, text, position=position, color=color), is_normal


# ----------------------------
# CORE MODEL INFERENCE
# ----------------------------
def anomaly_model_predict(frame: np.ndarray):
    global frame_buffer, frame_counter

    frame_counter += 1

    frame_rgb = cv2.resize(frame, (224, 224))
    frame_rgb = cv2.cvtColor(frame_rgb, cv2.COLOR_BGR2RGB)

    norm = frame_rgb.astype(np.float32) / 255.0
    norm = (norm - 0.45) / 0.225

    frame_buffer.append(norm)

    if len(frame_buffer) > FRAME_WINDOW * 2:
        frame_buffer = frame_buffer[-FRAME_WINDOW * 2:]

    if len(frame_buffer) < FRAME_WINDOW:
        return FRONTEND_LABELS["normal"], 0.0

    if frame_counter % STRIDE != 0:
        return FRONTEND_LABELS["normal"], 0.0

    clip = np.stack(frame_buffer[-FRAME_WINDOW:], axis=0)
    rgb_tensor = torch.from_numpy(clip).permute(3, 0, 1, 2).unsqueeze(0).to(device)

    flow_tensor = torch.zeros(
        rgb_tensor.shape[0],
        2,
        rgb_tensor.shape[2],
        rgb_tensor.shape[3],
        rgb_tensor.shape[4],
        device=device,
    )

    with torch.no_grad():
        logits = video_model(rgb_tensor, flow_tensor)
        probs = torch.softmax(logits, dim=-1)[0]

    topk = torch.topk(probs, 3)

    settings = get_settings()
    if not settings:
        return FRONTEND_LABELS["normal"], float(probs.max())

    for i, conf in zip(topk.indices, topk.values):
        label = class_names[int(i)]
        confidence = float(conf)

        action_key = CLASS_TO_ACTION.get(label)
        if not action_key:
            continue

        action_cfg = settings["detection"].get(action_key)
        if not action_cfg or not action_cfg["enabled"]:
            continue

        threshold = sensitivity_to_threshold(action_cfg["sensitivity"])

        if confidence < threshold:
            continue

        return FRONTEND_LABELS.get(action_key, action_key), confidence

    return FRONTEND_LABELS["normal"], float(probs.max())


# ----------------------------
# 🔥 NEW: STATE MANAGEMENT
# ----------------------------
def get_persistent_prediction(new_label, new_confidence):
    global current_label, current_confidence, ttl_counter

    # если новая детекция НЕ normal → обновляем состояние
    if new_label != FRONTEND_LABELS["normal"]:
        current_label = new_label
        current_confidence = new_confidence
        ttl_counter = STRIDE  # держим следующие STRIDE кадров
    else:
        # если нет новой детекции — уменьшаем TTL
        if ttl_counter > 0:
            ttl_counter -= 1
        else:
            current_label = FRONTEND_LABELS["normal"]
            current_confidence = new_confidence

    return current_label, current_confidence


# ----------------------------
# YOLO + per-person analysis
# ----------------------------
def analyze_with_yolo(frame: np.ndarray, total_frames: int):
    detections = []
    best_label = FRONTEND_LABELS["normal"]
    best_confidence = 0.0

    yolo_results = yolo_model.predict(frame, conf=0.2)

    for r in yolo_results[0].boxes:
        cls_id = int(r.cls)

        if cls_id == 0:  # person
            x1, y1, x2, y2 = map(int, r.xyxy[0].tolist())

            person_crop = frame[y1:y2, x1:x2]
            if person_crop.size == 0:
                continue

            img = cv2.resize(person_crop, (224, 224))

            raw_label, raw_confidence = anomaly_model_predict(img)

            # 🔥 применяем persistence
            label, confidence = get_persistent_prediction(
                raw_label, raw_confidence
            )

            if confidence > best_confidence:
                best_label = label
                best_confidence = confidence

            frame, is_normal = draw_action_label(
                frame,
                label,
                confidence,
                position=(x1 + 5, y1 - 30),
            )

            color = (0, 255, 0) if is_normal else (0, 0, 255)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            detections.append(
                {
                    "frame": total_frames,
                    "bbox": [x1, y1, x2, y2],
                    "label": label,
                    "confidence": confidence,
                }
            )

    return {
        "frame_data": frame,
        "frame": total_frames,
        "label": best_label,
        "confidence": best_confidence,
        "detections": detections,
    }


# ----------------------------
# full scene analysis
# ----------------------------
def analyze_scene(frame: np.ndarray, total_frames: int):
    raw_label, raw_confidence = anomaly_model_predict(frame)

    # 🔥 persistence
    label, confidence = get_persistent_prediction(
        raw_label, raw_confidence
    )

    frame, _ = draw_action_label(frame, label, confidence)

    return {
        "frame_data": frame,
        "frame": total_frames,
        "label": label,
        "confidence": confidence,
        "detections": [
            {
                "frame": total_frames,
                "label": label,
                "confidence": confidence,
            }
        ],
    }