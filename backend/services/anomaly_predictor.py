import torch
import cv2
import numpy as np
from models.anomaly_model import video_model, class_names
from core.config import FRAME_WINDOW, CLASS_TO_ACTION
from utils.device import device
from services.settings import get_settings

frame_buffer = []

def sensitivity_to_threshold(sensitivity: float) -> float:
    return max(0.1, 0.9 - sensitivity * 0.7)

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
        return "normal", 0.0

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
            return "normal", confidence

        # Determine label and action config
        action_key = CLASS_TO_ACTION.get(label)
        action_cfg = settings["detection"].get(action_key)

        print(action_key)
        # Ignore if unknown
        if not action_key:
            return "normal", confidence

        # Action disabled
        if not action_cfg or not action_cfg["enabled"]:
            return "normal", confidence

        threshold = sensitivity_to_threshold(action_cfg["sensitivity"])

        # Sensitivity threshold
        if confidence < threshold:
            return "normal", confidence

        return f"suspicious ({action_key})", confidence
