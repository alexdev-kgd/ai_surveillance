import torch
import cv2
import numpy as np
from models.anomaly_model import video_model
from config import FRAME_WINDOW

frame_buffer = []

def anomaly_model_predict(frame: np.ndarray):
    global frame_buffer

    frame = cv2.resize(frame, (224, 224))
    frame_buffer.append(frame)

    if len(frame_buffer) < FRAME_WINDOW:
        return "normal", 0.0

    video_tensor = torch.tensor(frame_buffer).permute(3, 0, 1, 2).unsqueeze(0).float()
    frame_buffer.clear()

    with torch.no_grad():
        preds = video_model(video_tensor)
        probs = torch.sigmoid(preds)
        confidence = float(probs.item())
        label = "suspicious" if confidence > 0.5 else "normal"

    return label, confidence
