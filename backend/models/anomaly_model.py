import torch
import torch.nn as nn
from config import ANOMALY_MODEL_PATH
from services.device import device

# Load base model
video_model = torch.hub.load("facebookresearch/pytorchvideo", "x3d_m", pretrained=False)

# Add classifier for 9 classes
video_model.blocks[-1].proj = nn.Linear(video_model.blocks[-1].proj.in_features, 9)

# Find the first Conv3d layer (inside Conv2plus1d)
first_block = video_model.blocks[0]
old_conv = first_block.conv.conv_t  # this is the first actual Conv3d

# Create a new Conv3d with one extra input channel (RGB + pose)
new_conv = nn.Conv3d(
    in_channels=old_conv.in_channels + 1,
    out_channels=old_conv.out_channels,
    kernel_size=old_conv.kernel_size,
    stride=old_conv.stride,
    padding=old_conv.padding,
    bias=old_conv.bias is not None,
)

# Copy old pretrained weights into the first 3 input channels
with torch.no_grad():
    new_conv.weight[:, :old_conv.in_channels, :, :, :] = old_conv.weight
    if old_conv.bias is not None:
        new_conv.bias.copy_(old_conv.bias)

# Replace the spatial conv with our new one
first_block.conv.conv_t = new_conv

# Checkpoint loading
checkpoint = torch.load(ANOMALY_MODEL_PATH, map_location=device)
video_model.load_state_dict(checkpoint["model_state_dict"])

# Prepare device
video_model = video_model.to(device)
video_model.eval()

# Restore class names
class_names = checkpoint.get("class_names", None)
