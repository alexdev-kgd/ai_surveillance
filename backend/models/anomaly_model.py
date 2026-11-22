import os

import torch
import torch.nn as nn
from pytorchvideo.models.hub import x3d_m

from core.config import ANOMALY_MODEL_PATH, ANOMALY_YOLO_MODEL_PATH
from utils.device import device


class TwoStreamModel(nn.Module):
    def __init__(self, num_classes: int, fusion: str = "add"):
        super().__init__()

        if fusion not in {"add", "concat"}:
            raise ValueError("fusion must be 'add' or 'concat'")

        self.fusion = fusion

        # RGB stream
        self.rgb_model = x3d_m(pretrained=False)

        # Flow stream
        self.flow_model = x3d_m(pretrained=False)

        self._convert_flow_to_2ch()

        feature_dim = self.rgb_model.blocks[-1].proj.in_features

        # remove classifiers
        self._strip_head(self.rgb_model)
        self._strip_head(self.flow_model)

        fused_dim = feature_dim * 2 if fusion == "concat" else feature_dim

        self.dropout = nn.Dropout(0.5)
        self.classifier = nn.Linear(fused_dim, num_classes)

    def _convert_flow_to_2ch(self):
        stem = self.flow_model.blocks[0].conv.conv_t

        self.flow_model.blocks[0].conv.conv_t = nn.Conv3d(
            in_channels=2,
            out_channels=stem.out_channels,
            kernel_size=stem.kernel_size,
            stride=stem.stride,
            padding=stem.padding,
            bias=stem.bias is not None,
        )

    def _strip_head(self, model):
        model.blocks[-1].proj = nn.Identity()
        model.blocks[-1].activation = nn.Identity()

    def _extract(self, model, x):
        feat = model(x)

        if feat.ndim > 2:
            feat = feat.mean(dim=tuple(range(2, feat.ndim)))

        return feat

    def forward(self, rgb, flow):
        rgb_f = self._extract(self.rgb_model, rgb)
        flow_f = self._extract(self.flow_model, flow)

        if self.fusion == "concat":
            x = torch.cat([rgb_f, flow_f], dim=1)
        else:
            x = rgb_f + flow_f

        return self.classifier(self.dropout(x))


def _load_two_stream(path: str):
    loaded = torch.load(path, map_location=device)
    names = loaded["class_names"]
    fusion = loaded.get("fusion", "add")
    model = TwoStreamModel(num_classes=len(names), fusion=fusion)
    model.load_state_dict(loaded["model_state_dict"], strict=True)
    model = model.to(device)
    model.eval()
    return loaded, names, model


# ----------------------------
# Load checkpoint
# ----------------------------
checkpoint, class_names, video_model = _load_two_stream(ANOMALY_MODEL_PATH)
num_classes = len(class_names)

yolo_checkpoint = None
yolo_class_names = list(class_names)
yolo_video_model = None
if os.path.isfile(ANOMALY_YOLO_MODEL_PATH):
    yolo_checkpoint, yolo_class_names, yolo_video_model = _load_two_stream(
        ANOMALY_YOLO_MODEL_PATH
    )


def reload_from_checkpoint(path: str | None = None, target: str = "scene") -> None:
    """Replace the in-memory inference model after a training run."""
    global checkpoint, class_names, num_classes, video_model
    global yolo_checkpoint, yolo_class_names, yolo_video_model

    if target == "yolo":
        ckpt_path = path or ANOMALY_YOLO_MODEL_PATH
        yolo_checkpoint, yolo_class_names, yolo_video_model = _load_two_stream(ckpt_path)
        return

    ckpt_path = path or ANOMALY_MODEL_PATH
    checkpoint, class_names, video_model = _load_two_stream(ckpt_path)
    num_classes = len(class_names)


def get_runtime_model(use_crop_model: bool = False):
    if use_crop_model and yolo_video_model is not None:
        return yolo_video_model, yolo_class_names
    return video_model, class_names


# ----------------------------
# SAFE inference API
# ----------------------------
@torch.no_grad()
def predict(rgb_clip: torch.Tensor, flow_clip: torch.Tensor | None = None):
    if flow_clip is None:
        flow_clip = torch.zeros(
            rgb_clip.shape[0],
            2,
            rgb_clip.shape[2],
            rgb_clip.shape[3],
            rgb_clip.shape[4],
            device=rgb_clip.device,
        )

    logits = video_model(rgb_clip, flow_clip)
    probs = torch.softmax(logits, dim=-1)

    return logits, probs