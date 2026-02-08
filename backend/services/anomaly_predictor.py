import torch
import cv2
import numpy as np
from models.anomaly_model import video_model, class_names
from models.yolo_detector import yolo_model
from core.config import FRAME_WINDOW, CLASS_TO_ACTION, FRONTEND_LABELS
from utils.device import device
from services.settings import get_settings
from utils.text import put_text_ru, TEXT_DEFAULT_POSITION

frame_buffer = []

def sensitivity_to_threshold(sensitivity: float) -> float:
    return max(0.1, 0.9 - sensitivity * 0.7)

def draw_action_label(
    frame: np.ndarray,
    label: str,
    confidence: float,
    position: tuple[int, int] | None = None,
):
    is_normal = label == FRONTEND_LABELS["normal"]
    color = (0, 255, 0) if is_normal else (255, 0, 0)

    if is_normal:
        text = f"{label} ({confidence:.2f})"
    else:
        text = f"Подозрительное действие: {label} ({confidence:.2f})"

    if position is None:
        position = TEXT_DEFAULT_POSITION

    return put_text_ru(
        frame,
        text,
        position=position,
        color=color
    ), is_normal

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
            img = cv2.resize(person_crop, (224, 224))

            label, confidence = anomaly_model_predict(img)
        
            if confidence > best_confidence:
                best_label = label
                best_confidence = confidence

            frame, is_normal = draw_action_label(
                frame,
                label,
                confidence,
                position=(x1+5, y1 - 30)
            )

            color = (0, 255, 0) if is_normal else (0, 0, 255)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            detections.append({
                "frame": total_frames,
                "bbox": [x1, y1, x2, y2],
                "label": label,
                "confidence": confidence,
            })

    return {
        "frame_data": frame,
        "frame": total_frames,
        "label": best_label,
        "confidence": best_confidence,
        "detections": detections,
    }

def analyze_scene(frame: np.ndarray, total_frames: int):
    label, confidence = anomaly_model_predict(frame)

    frame, _ = draw_action_label(frame, label, confidence)

    return {
        "frame_data": frame,
        "frame": total_frames,
        "label": label,
        "confidence": confidence,
        "detections": [{
            "frame": total_frames,
            "label": label,
            "confidence": confidence,
        }],
    }

def anomaly_model_predict(frame: np.ndarray):
    global frame_buffer

    # --- Resize & preprocess RGB ---
    frame_rgb = cv2.resize(frame, (224, 224))
    frame_rgb = cv2.cvtColor(frame_rgb, cv2.COLOR_BGR2RGB)
    norm_frame = frame_rgb / 255.0
    norm_frame = (norm_frame - [0.45, 0.45, 0.45]) / [0.225, 0.225, 0.225]

    frame_buffer.append(norm_frame)

    # Wait until we have enough frames
    if len(frame_buffer) < FRAME_WINDOW:
        return FRONTEND_LABELS["normal"], 0.0

    # --- Prepare tensor for model ---
    # Efficient stacking: combine all frames into one numpy array
    video_np = np.stack(frame_buffer[-FRAME_WINDOW:], axis=0).astype(np.float32)
    video_tensor = torch.from_numpy(video_np).permute(3, 0, 1, 2).unsqueeze(0).float().to(device)

    # --- Predict ---
    with torch.no_grad():
        logits = video_model(video_tensor)
        probs = torch.softmax(logits, dim=-1)[0]

    topk = torch.topk(probs, 3)
    top_actions = [(class_names[i], float(p)) for p, i in zip(topk.values, topk.indices)]

    # Log top actions
    print("[Detected Actions]")
    for label, confidence in top_actions:
        print(f"  • {label}: {confidence:.3f}")

        # Parameters Settings
        settings = get_settings()

        if not settings:
            return FRONTEND_LABELS["normal"], confidence

        # Determine label and action config
        action_key = CLASS_TO_ACTION.get(label)
        action_cfg = settings["detection"].get(action_key)
    
        # Ignore if unknown
        if not action_key:
            return FRONTEND_LABELS["normal"], confidence

        # Action disabled
        if not action_cfg or not action_cfg["enabled"]:
            return FRONTEND_LABELS["normal"], confidence

        threshold = sensitivity_to_threshold(action_cfg["sensitivity"])

        # Sensitivity threshold
        if confidence < threshold:
            return FRONTEND_LABELS["normal"], confidence

        frontend_label = FRONTEND_LABELS.get(action_key, action_key)

        return frontend_label, confidence
