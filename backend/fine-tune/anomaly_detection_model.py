import gc
import os
import random
import sys
from typing import List, Tuple

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from pytorchvideo.models.hub import x3d_m
from torch.amp import GradScaler, autocast
from torch.utils.data import DataLoader, Dataset

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.device import device


# ----------------------------
# CONFIG
# ----------------------------
class_names = ["normal", "assault", "fall_floor", "run", "shoot_gun", "shoplift"]

epochs = 80  # How many times to loop through the entire training dataset
backbone_lr = 1e-5
weight_decay = 1e-3
max_grad_norm = 1.0  # Gradient clipping
batch_size = 4  # Reduced to lower memory pressure while keeping the GPU fed.
clip_len = 50 # Shorter temporal window reduces compute without changing model logic.
STRIDE = 4

# ----------------------------
# Focal Loss Implementation
#
# It's a modification of cross-entropy loss that focuses more on hard-to-classify examples,
# which can help with class imbalance.
# ----------------------------
class FocalLoss(nn.Module):
    def __init__(self, gamma=2, alpha=None, reduction="mean"):
        super().__init__()
        self.gamma = gamma
        self.alpha = alpha
        self.reduction = reduction
        self.ce = nn.CrossEntropyLoss(reduction="none")

    def forward(self, logits, targets):
        ce_loss = self.ce(logits, targets)
        batch_indices = torch.arange(targets.size(0), device=targets.device)
        pt = torch.softmax(logits, dim=1)[batch_indices, targets]
        focal_term = (1 - pt) ** self.gamma

        if self.alpha is not None:
            focal_term = self.alpha[targets] * focal_term

        loss = focal_term * ce_loss
        return loss.mean() if self.reduction == "mean" else loss.sum()


# ----------------------------
# Normalization helper
# ----------------------------
class NormalizeVideo:
    def __init__(self, mean, std, device="cpu"):
        self.mean = torch.tensor(mean, dtype=torch.float32).view(3, 1, 1, 1)
        self.std = torch.tensor(std, dtype=torch.float32).view(3, 1, 1, 1)

    def __call__(self, tensor):
        mean = self.mean.to(tensor.device)
        std = self.std.to(tensor.device)
        return (tensor - mean) / std


# ----------------------------
# Video Dataset with precomputed optical flow
# ----------------------------
class VideoDataset(Dataset):
    def __init__(self, root_dir, class_names, clip_len=24, transform=None, mode="train"):
        self.samples = []
        self.clip_len = clip_len
        self.transform = transform
        self.mode = mode
        self.class_to_idx = {cls: i for i, cls in enumerate(class_names)}
        self.frame_size = (224, 224)  # (width, height)
        self.flow_suffix = "_flow.npy"

        if self.clip_len < 2:
            raise ValueError("clip_len must be at least 2.")

        missing_flow_files = 0

        for cls in class_names:
            cls_dir = os.path.join(root_dir, cls)
            if not os.path.exists(cls_dir):
                continue

            for filename in os.listdir(cls_dir):
                if not filename.lower().endswith((".mp4", ".avi", ".mov", ".mkv")):
                    continue

                video_path = os.path.join(cls_dir, filename)
                stem, _ = os.path.splitext(video_path)
                flow_path = f"{stem}{self.flow_suffix}"

                if not os.path.exists(flow_path):
                    missing_flow_files += 1
                    continue

                self.samples.append((video_path, flow_path, self.class_to_idx[cls]))

        if not self.samples:
            raise RuntimeError(
                f"No video/flow pairs found in '{root_dir}'. "
                f"Expected files like 'video.mp4' and 'video_flow.npy'."
            )

        if missing_flow_files > 0:
            print(f"[{mode}] Skipped {missing_flow_files} videos without matching *_flow.npy files.")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        video_path, flow_path, label = self.samples[idx]

        # === RGB ===
        cap = cv2.VideoCapture(video_path)
        frames = []

        frame_idx = 0

        # ----------------------------
        # STRIDE APPLIED HERE (RGB)
        # ----------------------------
        while len(frames) < self.clip_len:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % STRIDE == 0:
                frame = cv2.resize(frame, self.frame_size)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frames.append(frame)

            frame_idx += 1

        cap.release()

        if len(frames) == 0:
            frames = [np.zeros((224, 224, 3), dtype=np.uint8)]

        while len(frames) < self.clip_len:
            frames.append(frames[-1])

        frames = frames[:self.clip_len]

        rgb_array = np.stack(frames, axis=0).astype(np.float32) / 255.0
        rgb_video = torch.from_numpy(rgb_array).permute(3, 0, 1, 2).contiguous()

        # ----------------------------
        # FLOW STRIDE MATCHING
        # ----------------------------
        flow_array = np.load(flow_path)
        flow_array = flow_array[::STRIDE]

        if flow_array.shape[0] < self.clip_len:
            pad = np.repeat(flow_array[-1][None, ...],
                             self.clip_len - flow_array.shape[0],
                             axis=0)
            flow_array = np.concatenate([flow_array, pad], axis=0)

        flow_array = flow_array[:self.clip_len]

        flow_video = torch.from_numpy(flow_array).permute(3, 0, 1, 2).contiguous()

        # === AUGMENTATION ===
        if self.mode == "train" and random.random() < 0.5:
            rgb_video = torch.flip(rgb_video, dims=[3])
            flow_video = torch.flip(flow_video, dims=[3])
            flow_video[0] = -flow_video[0]

        if self.transform:
            rgb_video = self.transform(rgb_video)

        return rgb_video, flow_video, torch.tensor(label, dtype=torch.long)


# ----------------------------
# Two-stream X3D model
# ----------------------------
class TwoStreamModel(nn.Module):
    def __init__(self, num_classes, fusion="add", rgb_pretrained=True):
        super().__init__()

        if fusion not in {"add", "concat"}:
            raise ValueError("fusion must be either 'add' or 'concat'.")

        self.fusion = fusion
        self.rgb_model = x3d_m(pretrained=rgb_pretrained)
        self.flow_model = x3d_m(pretrained=False)

        self._convert_flow_stem_to_two_channels()

        feature_dim = self.rgb_model.blocks[-1].proj.in_features

        self._strip_classifier(self.rgb_model)
        self._strip_classifier(self.flow_model)

        classifier_in_dim = feature_dim * 2 if fusion == "concat" else feature_dim

        self.dropout = nn.Dropout(0.5)
        self.classifier = nn.Linear(classifier_in_dim, num_classes)

    def _convert_flow_stem_to_two_channels(self):
        stem = self.flow_model.blocks[0].conv.conv_t

        self.flow_model.blocks[0].conv.conv_t = nn.Conv3d(
            in_channels=2,
            out_channels=stem.out_channels,
            kernel_size=stem.kernel_size,
            stride=stem.stride,
            padding=stem.padding,
            bias=stem.bias is not None,
        )

    def _strip_classifier(self, model):
        model.blocks[-1].proj = nn.Identity()
        model.blocks[-1].activation = nn.Identity()

    def _extract_features(self, model, x):
        feat = model(x)
        if feat.ndim > 2:
            feat = feat.mean(dim=tuple(range(2, feat.ndim)))
        return feat

    def forward(self, rgb, flow):
        rgb_f = self._extract_features(self.rgb_model, rgb)
        flow_f = self._extract_features(self.flow_model, flow)

        if self.fusion == "concat":
            x = torch.cat([rgb_f, flow_f], dim=1)
        else:
            x = rgb_f + flow_f

        x = self.dropout(x)
        return self.classifier(x)


# ----------------------------
# TRAIN LOOP (UNCHANGED LOGIC)
# ----------------------------
def train_model(fusion="add"):
    torch.backends.cudnn.benchmark = True
    amp_enabled = device.type == "cuda"

    data_workers = max(1, min(6, os.cpu_count() or 1))

    script_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_root = os.path.normpath(os.path.join(script_dir, "..", "dataset"))
    train_root = os.path.join(dataset_root, "train")
    val_root = os.path.join(dataset_root, "val")

    print(f"Using device: {device}")
    print(f"Using {data_workers} dataloader workers")

    transform = NormalizeVideo((0.45, 0.45, 0.45), (0.225, 0.225, 0.225))

    train_dataset = VideoDataset(train_root, class_names, clip_len=clip_len, transform=transform, mode="train")
    val_dataset = VideoDataset(val_root, class_names, clip_len=clip_len, transform=transform, mode="val")

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True,
                              num_workers=data_workers, pin_memory=True)

    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False,
                            num_workers=data_workers, pin_memory=True)

    model = TwoStreamModel(num_classes=len(class_names), fusion=fusion).to(device)

    optimizer = optim.AdamW(model.parameters(), lr=backbone_lr, weight_decay=weight_decay)
    # Learning rate scheduler
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    criterion = FocalLoss()

    scaler = GradScaler("cuda", enabled=amp_enabled)

    # Training loop
    for epoch in range(epochs):
        model.train()

        total_loss = 0

        for rgb, flow, labels in train_loader:
            rgb = rgb.to(device)
            flow = flow.to(device)
            labels = labels.to(device)

            optimizer.zero_grad(set_to_none=True)

            with autocast(device_type="cuda", enabled=amp_enabled):
                out = model(rgb, flow)
                loss = criterion(out, labels)

            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()

            total_loss += loss.item()

        scheduler.step()

        print(f"Epoch {epoch+1}/{epochs} | Loss: {total_loss:.4f}")

        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        gc.collect()

    torch.save({
        "model_state_dict": model.state_dict(),
        "class_names": class_names
    }, "suspicious_actions.pth")


if __name__ == "__main__":
    train_model()
