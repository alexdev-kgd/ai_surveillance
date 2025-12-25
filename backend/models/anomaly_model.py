import torch
import torch.nn as nn
from config import ANOMALY_MODEL_PATH
from services.device import device

# Load base model
video_model = torch.hub.load("facebookresearch/pytorchvideo", "x3d_m", pretrained=False)

# Add classifier for 9 classes
video_model.blocks[-1].proj = nn.Sequential(
    nn.Dropout(0.5),
    nn.Linear(video_model.blocks[-1].proj.in_features, 3)
)

# Checkpoint loading
checkpoint = torch.load(ANOMALY_MODEL_PATH, map_location=device)
video_model.load_state_dict(checkpoint["model_state_dict"])

# Prepare device
video_model = video_model.to(device)
video_model.eval()

# Restore class names
class_names = checkpoint.get("class_names", None)
