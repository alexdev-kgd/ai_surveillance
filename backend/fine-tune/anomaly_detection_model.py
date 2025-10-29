import cv2
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from pytorchvideo.models.hub import x3d_m
import torch.optim as optim
import mediapipe as mp
import sys, os
import numpy as np
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from services.device import device

class_names = ["normal", "fall_floor", "hit", "jump", "kick", "punch", "run", "shoot_gun"]

epochs = 6
learning_rate = 1e-4
weight_decay = 1e-2
batch_size = 4
clip_len = 32 # Number of frames per clip

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
# Video Dataset with OpenCV and MediaPipe Pose
# ----------------------------
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

class VideoDataset(Dataset):
    def __init__(self, root_dir, class_names, clip_len=16, transform=None):
        self.samples = []
        self.clip_len = clip_len
        self.transform = transform
        self.class_to_idx = {cls: i for i, cls in enumerate(class_names)}
        self.pose_estimator = mp_pose.Pose(static_image_mode=True, model_complexity=0)

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

                # ---- MediaPipe Pose ----
                pose_mask = np.zeros((224, 224, 3), dtype=np.uint8)
                results = self.pose_estimator.process(frame)
                if results.pose_landmarks:
                    mp_drawing.draw_landmarks(
                        image=pose_mask,
                        landmark_list=results.pose_landmarks,
                        connections=mp_pose.POSE_CONNECTIONS,
                        landmark_drawing_spec=mp_drawing.DrawingSpec(color=(255, 255, 255), thickness=2, circle_radius=2),
                        connection_drawing_spec=mp_drawing.DrawingSpec(color=(255, 255, 255), thickness=2)
                    )

                # Combine RGB + Pose mask into 4 channels
                pose_mask_gray = cv2.cvtColor(pose_mask, cv2.COLOR_RGB2GRAY)
                pose_mask_gray = np.expand_dims(pose_mask_gray, axis=-1)  # shape (224,224,1)
                frame_4ch = np.concatenate((frame, pose_mask_gray), axis=-1)  # (224,224,4)
                frames.append(frame_4ch)

        cap.release()

        # If too few frames, pad with last frame
        while len(frames) < self.clip_len:
            frames.append(frames[-1])

        video = torch.from_numpy(np.array(frames)).permute(3, 0, 1, 2).float() / 255.0  # (C, T, H, W)
        rgb = video[:3]
        if self.transform:
            rgb = self.transform(rgb)
        pose = video[3:].clone()  # keep pose channel separately
        video = torch.cat([rgb, pose], dim=0)  # merge 4 channels

        return video, label

# ----------------------------
# Training function
# ----------------------------
def train_model():
    torch.backends.cudnn.benchmark = True
    print(f"Using device: {device}")

    transform = NormalizeVideo((0.45, 0.45, 0.45), (0.225, 0.225, 0.225), device=device)

    train_dataset = VideoDataset("../dataset/train", class_names, clip_len=clip_len, transform=transform)
    val_dataset   = VideoDataset("../dataset/val",   class_names, clip_len=clip_len, transform=transform)

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=0)
    val_loader   = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=0)

    model = x3d_m(pretrained=True)
    model.blocks[-1].proj = nn.Linear(model.blocks[-1].proj.in_features, len(class_names))

    # Find the first Conv3d layer (inside Conv2plus1d)
    first_block = model.blocks[0]
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

    # Freeze everything except classifier
    for name, param in model.named_parameters():
        if "proj" not in name:
            param.requires_grad = False

    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(filter(lambda p: p.requires_grad, model.parameters()), lr=learning_rate, weight_decay=weight_decay)

    model = model.to(device)

    # Training loop
    for epoch in range(epochs):
        model.train()
        for videos, labels in train_loader:
            videos, labels = videos.to(device, non_blocking=True), labels.to(device, non_blocking=True)
            optimizer.zero_grad()
            outputs = model(videos)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

        # Validation
        model.eval()
        correct, total = 0, 0
        with torch.no_grad():
            for videos, labels in val_loader:
                videos, labels = videos.to(device, non_blocking=True), labels.to(device, non_blocking=True)
                outputs = model(videos)
                _, predicted = torch.max(outputs, 1)
                correct += (predicted == labels).sum().item()
                total += labels.size(0)

        print(f"Epoch {epoch+1}, Val Accuracy: {100*correct/total:.2f}%")

    torch.save({
        "model_state_dict": model.state_dict(),
        "class_names": class_names
    }, "suspicious_actions.pth")


if __name__ == "__main__":
    train_model()
