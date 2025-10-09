import os
import cv2
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
import torch.optim as optim
from pytorchvideo.models.hub import slow_r50   # still use pretrained SlowFast backbone

# Define your action classes
class_names = ["normal", "fall_floor", "hit", "jump", "kick", "punch", "run", "shoot_gun"]   # extend later

class NormalizeVideo:
    def __init__(self, mean, std, device="cpu"):
        self.mean = torch.tensor(mean).view(3, 1, 1, 1)
        self.std = torch.tensor(std).view(3, 1, 1, 1)

    def __call__(self, tensor):
        # Make sure tensors are on the same device
        mean = self.mean.to(tensor.device)
        std = self.std.to(tensor.device)
        return (tensor - mean) / std

# ----------------------------
# Video Dataset with OpenCV
# ----------------------------
class VideoDataset(Dataset):
    def __init__(self, root_dir, class_names, clip_len=16, transform=None):
        self.samples = []
        self.clip_len = clip_len
        self.transform = transform
        self.class_to_idx = {cls: i for i, cls in enumerate(class_names)}

        for cls in class_names:
            cls_dir = os.path.join(root_dir, cls)
            if not os.path.exists(cls_dir):
                continue
            for f in os.listdir(cls_dir):
                if f.lower().endswith((".mp4", ".avi", ".mov", ".mkv")):
                    self.samples.append((os.path.join(cls_dir, f), self.class_to_idx[cls]))

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

        import numpy as np
        video = torch.from_numpy(np.array(frames)).permute(3, 0, 1, 2).float() / 255.0  # (C, T, H, W)

        if self.transform:
            video = self.transform(video)

        return video, label


# ----------------------------
# Training function
# ----------------------------
def train_model():
    print(torch.__file__)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch.backends.cudnn.benchmark = True

    transform = NormalizeVideo((0.45, 0.45, 0.45), (0.225, 0.225, 0.225), device=device)

    train_dataset = VideoDataset("../dataset/train", class_names, clip_len=16, transform=transform)
    val_dataset   = VideoDataset("../dataset/val",   class_names, clip_len=16, transform=transform)

    train_loader = DataLoader(train_dataset, batch_size=4, shuffle=True, num_workers=4)
    val_loader   = DataLoader(val_dataset, batch_size=4, shuffle=False, num_workers=4)

    # Load pretrained Slow R50 backbone
    model = slow_r50(pretrained=True)
    model.blocks[-1].proj = nn.Linear(model.blocks[-1].proj.in_features, len(class_names))

    # Freeze everything except classifier
    for name, param in model.named_parameters():
        if "proj" not in name:
            param.requires_grad = False

    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(filter(lambda p: p.requires_grad, model.parameters()), lr=1e-3)

    model = model.to(device)

    # Training loop
    for epoch in range(10):
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
