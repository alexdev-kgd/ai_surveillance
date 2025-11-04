import cv2
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from pytorchvideo.models.hub import x3d_m
from torch.cuda.amp import autocast, GradScaler
import torch.optim as optim
import sys, os
import numpy as np
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from services.device import device
import random
import gc

# class_names = ["normal", "fall_floor", "hit", "jump", "kick", "punch", "run", "shoot_gun"]
class_names = ["normal", "assault", "shoplift"]

epochs = 40
backbone_lr = 1e-5
head_lr = 5e-5
weight_decay = 1e-3                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   
max_grad_norm = 1.0  # Gradient clipping
batch_size = 16
clip_len = 48 # Number of frames per clip

# ----------------------------
# Focal Loss Implementation
# ----------------------------
class FocalLoss(nn.Module):
    def __init__(self, gamma=2, alpha=None, reduction="mean"):
        super(FocalLoss, self).__init__()
        self.gamma = gamma
        self.alpha = alpha
        self.reduction = reduction
        self.ce = nn.CrossEntropyLoss(reduction="none")

    def forward(self, logits, targets):
        ce_loss = self.ce(logits, targets)
        pt = torch.softmax(logits, dim=1)[torch.arange(len(targets)), targets]
        focal_term = ((1 - pt) ** self.gamma)

        if self.alpha is not None:
            focal_term = self.alpha[targets] * focal_term

        loss = focal_term * ce_loss
        return loss.mean() if self.reduction == "mean" else loss.sum()

# ----------------------------
# Normalization helper
# ----------------------------
class NormalizeVideo:
    def __init__(self, mean, std, device="cpu"):
        self.mean = torch.tensor(mean).view(3, 1, 1, 1)
        self.std = torch.tensor(std).view(3, 1, 1, 1)

    def __call__(self, tensor):
        mean = self.mean.to(tensor.device)
        std = self.std.to(tensor.device)
        return (tensor - mean) / std

# ----------------------------
# Video Dataset with OpenCV
# ----------------------------
class VideoDataset(Dataset):
    def __init__(self, root_dir, class_names, clip_len=16, transform=None, mode="train"):
        self.samples = []
        self.clip_len = clip_len
        self.transform = transform
        self.mode = mode
        self.class_to_idx = {cls: i for i, cls in enumerate(class_names)}

        for cls in class_names:
            cls_dir = os.path.join(root_dir, cls)
            if not os.path.exists(cls_dir):
                continue
            for f in os.listdir(cls_dir):
                if f.lower().endswith((".mp4", ".avi", ".mov", ".mkv")):
                    video_path = os.path.join(cls_dir, f)
                    self.samples.append((video_path, self.class_to_idx[cls]))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]

        cap = cv2.VideoCapture(path)
        frames = []
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # uniformly sample clip_len frames
        indices = torch.linspace(0, total_frames - 1, self.clip_len).long().tolist()

        for i in range(total_frames):
            ret, frame = cap.read()
            if not ret:
                break
            if i in indices:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = cv2.resize(frame, (224, 224))
                frames.append(frame)

        cap.release()

        # If too few frames, pad with last frame
        while len(frames) < self.clip_len:
            frames.append(frames[-1])

        video = torch.from_numpy(np.array(frames)).permute(3, 0, 1, 2).float() / 255.0  # (C, T, H, W)

        # === Random horizontal flip (only training) ===
        if self.mode == "train" and random.random() < 0.5:
            video = torch.flip(video, dims=[3])  # flip width (H stays same)

        if self.transform:
            video = self.transform(video)

        return video, label

# ----------------------------
# Training function
# ----------------------------
def train_model():
    torch.backends.cudnn.benchmark = True
    print(f"Using device: {device}")

    transform = NormalizeVideo((0.45, 0.45, 0.45), (0.225, 0.225, 0.225), device=device)

    train_dataset = VideoDataset("../dataset/train", class_names, clip_len=clip_len, transform=transform, mode="train")
    val_dataset   = VideoDataset("../dataset/val",   class_names, clip_len=clip_len, transform=transform, mode="val")

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=0)
    val_loader   = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=0)

    model = x3d_m(pretrained=True)
    model.blocks[-1].proj = nn.Sequential(
        nn.Dropout(0.5),
        nn.Linear(model.blocks[-1].proj.in_features, len(class_names))
    )

    # example quick changes
    for name, p in model.named_parameters():
        p.requires_grad = False
    # unfreeze last 3 blocks and head
    for name, p in model.named_parameters():
        if "proj" in name or any(f"blocks.{i}" in name for i in range(len(model.blocks)-3, len(model.blocks))):
            p.requires_grad = True

    backbone_params = [p for n,p in model.named_parameters() if p.requires_grad and "proj" not in n]
    head_params = [p for n,p in model.named_parameters() if p.requires_grad and "proj" in n]

    optimizer = optim.AdamW([
        {"params": backbone_params, "lr": 1e-5, "weight_decay": 1e-3},
        {"params": head_params, "lr": 5e-4, "weight_decay": 1e-3},
    ])

    # Learning rate scheduler
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    alpha = torch.tensor([1.0, 2.5, 2.5]).to(device)  # boost assault, shoplift
    criterion = FocalLoss(gamma=2, alpha=alpha)

    model = model.to(device)

    scaler = GradScaler()  # Mixed precision

    # Training loop
    for epoch in range(epochs):
        model.train()
        running_train_loss = 0.0
        total_train = 0

        for videos, labels in train_loader:
            videos, labels = videos.to(device, non_blocking=True), labels.to(device, non_blocking=True)
            optimizer.zero_grad()

            with autocast():
                outputs = model(videos)
                loss = criterion(outputs, labels)
            scaler.scale(loss).backward()

            # Gradient clipping
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_grad_norm)
            scaler.step(optimizer)
            scaler.update()

            running_train_loss += loss.item() * labels.size(0)
            total_train += labels.size(0)

        avg_train_loss = running_train_loss / total_train

        # Validation
        model.eval()
        running_val_loss = 0.0
        correct, total = 0, 0

        with torch.no_grad():
            for videos, labels in val_loader:
                videos, labels = videos.to(device, non_blocking=True), labels.to(device, non_blocking=True)
                
                with autocast():
                    outputs = model(videos)
                    loss = criterion(outputs, labels)

                running_val_loss += loss.item() * labels.size(0)
                _, predicted = torch.max(outputs, 1)
                correct += (predicted == labels).sum().item()
                total += labels.size(0)

        avg_val_loss = running_val_loss / total
        val_acc = 100 * correct / total

        print(f"Epoch {epoch+1}/{epochs} | "
            f"Train Loss: {avg_train_loss:.4f} | "
            f"Val Loss: {avg_val_loss:.4f} | "
            f"Val Accuracy: {val_acc:.2f}%")

        scheduler.step()

        # Clear GPU cache
        torch.cuda.synchronize()
        torch.cuda.empty_cache()
        gc.collect()

    torch.save({
        "model_state_dict": model.state_dict(),
        "class_names": class_names
    }, "suspicious_actions.pth")


if __name__ == "__main__":
    train_model()
