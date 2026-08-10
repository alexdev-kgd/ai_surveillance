import torch
import torch.nn as nn
from pytorchvideo.models.hub import x3d_m

from core.config import ANOMALY_MODEL_PATH
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


# ----------------------------
# Load checkpoint
# ----------------------------
checkpoint = torch.load(ANOMALY_MODEL_PATH, map_location=device)

class_names = checkpoint["class_names"]
num_classes = len(class_names)

video_model = TwoStreamModel(num_classes=num_classes, fusion="add")
video_model.load_state_dict(checkpoint["model_state_dict"], strict=True)

video_model = video_model.to(device)
video_model.eval()


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