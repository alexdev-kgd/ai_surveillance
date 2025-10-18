import torch
import cv2
import numpy as np
from models.anomaly_model import video_model, class_names
from config import FRAME_WINDOW
from services.device import device

frame_buffer = []

def anomaly_model_predict(frame: np.ndarray):
    global frame_buffer

    frame = cv2.resize(frame, (224, 224))
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    frame = frame / 255.0
    frame = (frame - [0.45, 0.45, 0.45]) / [0.225, 0.225, 0.225]
    frame_buffer.append(frame)

    if len(frame_buffer) < FRAME_WINDOW:
        return "normal", 0.0

    # Efficient stacking: combine all frames into one numpy array
    # shape: (T, H, W, C)
    video_np = np.stack(frame_buffer[-FRAME_WINDOW:], axis=0).astype(np.float32)

    # Convert to torch tensor: (1, C, T, H, W)
    video_tensor = torch.from_numpy(video_np).permute(3, 0, 1, 2).unsqueeze(0).float().to(device)

    with torch.no_grad():
        logits = video_model(video_tensor)
        probs = torch.softmax(logits, dim=-1)
        topk = torch.topk(probs[0], 3)
        top_actions = [(class_names[i], float(p)) for p, i in zip(topk.values, topk.indices)]

        # Log top actions
        print("[Detected Actions]")
        for act, conf in top_actions:
            print(f"  • {act}: {conf:.3f}")

        # Determine label
        label, confidence = top_actions[0]
        label_out = "suspicious (" + label + ")" if label != "normal" else "normal"

    return label_out, confidence
