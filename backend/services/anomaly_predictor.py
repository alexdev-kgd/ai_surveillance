import torch
import cv2
import numpy as np
import mediapipe as mp
from models.anomaly_model import video_model, class_names
from config import FRAME_WINDOW
from services.device import device

frame_buffer = []

mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils
mp_styles = mp.solutions.drawing_styles
pose_estimator = mp_pose.Pose(static_image_mode=True, model_complexity=0)


def anomaly_model_predict(frame: np.ndarray):
    global frame_buffer

    # --- Resize & preprocess RGB ---
    frame_rgb = cv2.resize(frame, (224, 224))
    frame_rgb = cv2.cvtColor(frame_rgb, cv2.COLOR_BGR2RGB)
    norm_frame = frame_rgb / 255.0
    norm_frame = (norm_frame - [0.45, 0.45, 0.45]) / [0.225, 0.225, 0.225]

    # --- Compute pose mask ---
    pose_mask = np.zeros((224, 224, 3), dtype=np.uint8)
    results = pose_estimator.process(frame_rgb)
    if results.pose_landmarks:
        mp_drawing.draw_landmarks(
            image=pose_mask,
            landmark_list=results.pose_landmarks,
            connections=mp_pose.POSE_CONNECTIONS,
            landmark_drawing_spec=mp_drawing.DrawingSpec(color=(255, 255, 255), thickness=2, circle_radius=2),
            connection_drawing_spec=mp_drawing.DrawingSpec(color=(255, 255, 255), thickness=2)
        )

    pose_gray = cv2.cvtColor(pose_mask, cv2.COLOR_RGB2GRAY)
    pose_gray = np.expand_dims(pose_gray, axis=-1) / 255.0  # normalize to [0,1]

    # --- Stack RGB + pose to get 4 channels ---
    frame_4ch = np.concatenate((norm_frame, pose_gray), axis=-1)  # (224, 224, 4)
    frame_buffer.append(frame_4ch)

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
