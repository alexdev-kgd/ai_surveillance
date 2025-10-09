import torch
import torch.nn as nn
from config import ANOMALY_MODEL_PATH

video_model = torch.hub.load("facebookresearch/pytorchvideo", "slow_r50", pretrained=False)
video_model.blocks[-1].proj = nn.Linear(video_model.blocks[-1].proj.in_features, 1)

checkpoint = torch.load(ANOMALY_MODEL_PATH, map_location="cpu")
video_model.load_state_dict(checkpoint["model_state_dict"])
video_model.eval()
