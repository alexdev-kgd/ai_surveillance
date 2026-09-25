import argparse
import gc
import os
import random
import sys
from typing import List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from pytorchvideo.models.hub import x3d_m
from torch.amp import GradScaler, autocast
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.device import device
from utils.metrics import (
    accuracy_from_cm,
    confusion_matrix,
    format_classification_report,
    macro_f1,
    per_class_precision_recall_f1,
)
from utils.plot_utils import plot_training_curves
from utils.video_preprocess import (
    CLIP_LEN,
    FLOW_SUFFIX,
    FRAME_SIZE,
    RGB_MEAN,
    RGB_STD,
    SAMPLE_STRIDE,
    NormalizeVideo,
    compute_optical_flow_clip,
    flow_array_to_tensor,
    load_precomputed_flow,
    read_video_strided_rgb,
)


# ----------------------------
# CONFIG
# ----------------------------
# class_names = ["normal", "assault", "fall_floor", "run", "shoot_gun", "shoplift"]
class_names = ["normal", "assault", "shoot_gun", "shoplift"]

epochs = 40
backbone_lr = 1e-5
head_lr = 1e-4  # classifier learns faster than frozen-ish backbone
weight_decay = 5e-3  # stronger L2 (was 1e-3) to curb overfitting on ~300 clips
dropout_p = 0.65
label_smoothing = 0.1
focal_gamma = 2.0
use_class_weights = True  # inverse-frequency alpha for FocalLoss
max_grad_norm = 1.0
batch_size = 4
clip_len = CLIP_LEN  # aligned with serve (FRAME_WINDOW)
STRIDE = SAMPLE_STRIDE

# Early stopping: halt when val loss does not improve for `patience` epochs
EARLY_STOP_PATIENCE = 3
EARLY_STOP_MIN_DELTA = 1e-4  # minimum drop in val_loss to count as improvement

# Plots: enable with --plot or PLOT_METRICS=1
PLOT_METRICS = False
PLOT_DIR = "training_plots"
CHECKPOINT_NAME = "suspicious_actions.pth"
ONLINE_FLOW = False  # if True, ignore *_flow.npy and compute Farneback per sample


# ----------------------------
# Focal Loss (+ optional class weights & label smoothing)
# ----------------------------
class FocalLoss(nn.Module):
    def __init__(
        self,
        gamma: float = 2.0,
        alpha: Optional[torch.Tensor] = None,
        reduction: str = "mean",
        label_smoothing: float = 0.0,
    ):
        super().__init__()
        self.gamma = gamma
        self.reduction = reduction
        self.label_smoothing = float(label_smoothing)
        # buffer so .to(device) moves alpha with the module
        if alpha is not None:
            self.register_buffer("alpha", alpha.float())
        else:
            self.alpha = None
        self.ce = nn.CrossEntropyLoss(
            reduction="none",
            label_smoothing=self.label_smoothing,
        )

    def forward(self, logits, targets):
        ce_loss = self.ce(logits, targets)
        batch_indices = torch.arange(targets.size(0), device=targets.device)
        pt = torch.softmax(logits, dim=1)[batch_indices, targets].clamp(min=1e-6)
        focal_term = (1.0 - pt) ** self.gamma

        if self.alpha is not None:
            focal_term = self.alpha[targets] * focal_term

        loss = focal_term * ce_loss
        return loss.mean() if self.reduction == "mean" else loss.sum()


def inverse_frequency_alpha(label_counts: List[int]) -> torch.Tensor:
    """
    Class weights for FocalLoss: higher weight for rarer classes.
    Normalized so mean(alpha) == 1 (stable loss scale).
    """
    counts = np.asarray(label_counts, dtype=np.float64)
    counts = np.maximum(counts, 1.0)
    inv = 1.0 / counts
    alpha = inv / inv.mean()
    return torch.tensor(alpha, dtype=torch.float32)


# ----------------------------
# Stronger video augmentation
# ----------------------------
def apply_video_augmentations(
    rgb: torch.Tensor,
    flow: torch.Tensor,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    rgb/flow: (C, T, H, W), rgb in [0,1] before NormalizeVideo.
    Slightly aggressive defaults to regularize small datasets.
    """
    # Horizontal flip
    if random.random() < 0.5:
        rgb = torch.flip(rgb, dims=[3])
        flow = torch.flip(flow, dims=[3])
        flow[0] = -flow[0]

    # Temporal speed jitter: subsample / repeat along T
    if random.random() < 0.4 and rgb.shape[1] >= 8:
        t = rgb.shape[1]
        factor = random.choice([0.75, 0.85, 0.9, 1.1, 1.2, 1.25])
        new_t = max(4, int(round(t * factor)))
        idx = torch.linspace(0, t - 1, new_t).round().long().clamp(0, t - 1)
        rgb = rgb[:, idx]
        flow = flow[:, idx]
        # resize temporal dim back to clip_len via nearest
        if rgb.shape[1] != t:
            idx2 = torch.linspace(0, rgb.shape[1] - 1, t).round().long()
            rgb = rgb[:, idx2]
            flow = flow[:, idx2]

    # Random temporal frame dropout (zero a few frames)
    if random.random() < 0.3 and rgb.shape[1] >= 8:
        t = rgb.shape[1]
        n_drop = random.randint(1, max(1, t // 8))
        drop_idx = random.sample(range(t), n_drop)
        rgb[:, drop_idx] = 0.0
        flow[:, drop_idx] = 0.0

    # Random spatial crop + resize back (scale jitter)
    if random.random() < 0.5:
        _, t, h, w = rgb.shape
        scale = random.uniform(0.7, 1.0)
        ch, cw = max(8, int(h * scale)), max(8, int(w * scale))
        top = random.randint(0, h - ch)
        left = random.randint(0, w - cw)
        rgb = rgb[:, :, top : top + ch, left : left + cw]
        flow = flow[:, :, top : top + ch, left : left + cw]
        rgb = torch.nn.functional.interpolate(
            rgb.unsqueeze(0), size=(t, h, w), mode="trilinear", align_corners=False
        ).squeeze(0)
        flow = torch.nn.functional.interpolate(
            flow.unsqueeze(0), size=(t, h, w), mode="trilinear", align_corners=False
        ).squeeze(0)
        # scale flow magnitudes after spatial resize
        flow = flow * (cw / w)

    # Color jitter on RGB only
    if random.random() < 0.6:
        # brightness
        if random.random() < 0.85:
            rgb = (rgb * random.uniform(0.65, 1.35)).clamp(0.0, 1.0)
        # contrast
        if random.random() < 0.85:
            mean = rgb.mean(dim=(1, 2, 3), keepdim=True)
            rgb = ((rgb - mean) * random.uniform(0.65, 1.35) + mean).clamp(0.0, 1.0)
        # saturation-ish: mix with grayscale
        if random.random() < 0.6:
            gray = rgb.mean(dim=0, keepdim=True)
            alpha = random.uniform(0.5, 1.0)
            rgb = (alpha * rgb + (1 - alpha) * gray).clamp(0.0, 1.0)

    # Small Gaussian noise
    if random.random() < 0.35:
        noise = torch.randn_like(rgb) * random.uniform(0.01, 0.04)
        rgb = (rgb + noise).clamp(0.0, 1.0)

    return rgb, flow


# ----------------------------
# Video Dataset
# ----------------------------
class VideoDataset(Dataset):
    def __init__(
        self,
        root_dir,
        class_names,
        clip_len=CLIP_LEN,
        transform=None,
        mode="train",
        online_flow=False,
    ):
        self.samples = []
        self.clip_len = clip_len
        self.transform = transform
        self.mode = mode
        self.online_flow = online_flow
        self.class_to_idx = {cls: i for i, cls in enumerate(class_names)}
        self.frame_size = FRAME_SIZE

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
                flow_path = f"{stem}{FLOW_SUFFIX}"

                if not online_flow and not os.path.exists(flow_path):
                    missing_flow_files += 1
                    continue

                self.samples.append(
                    (video_path, flow_path if os.path.exists(flow_path) else None, self.class_to_idx[cls])
                )

        if not self.samples:
            raise RuntimeError(
                f"No usable videos found in '{root_dir}'. "
                f"online_flow={online_flow}; expected mp4 (+ optional *_flow.npy)."
            )

        if missing_flow_files > 0 and not online_flow:
            print(f"[{mode}] Skipped {missing_flow_files} videos without matching *_flow.npy files.")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        video_path, flow_path, label = self.samples[idx]

        # RGB: same sequential stride sampling as serve
        frames = read_video_strided_rgb(
            video_path,
            clip_len=self.clip_len,
            stride=STRIDE,
            size=self.frame_size,
        )

        rgb_array = np.stack(frames, axis=0).astype(np.float32) / 255.0
        rgb_video = torch.from_numpy(rgb_array).permute(3, 0, 1, 2).contiguous()

        # Flow: online from RGB clip (train≈serve) or precomputed aligned file
        if self.online_flow or flow_path is None:
            flow_np = compute_optical_flow_clip(frames, size=self.frame_size)
        else:
            try:
                flow_np = load_precomputed_flow(flow_path, clip_len=self.clip_len)
                # Ensure spatial size matches
                if flow_np.shape[1:3] != (self.frame_size[1], self.frame_size[0]):
                    flow_np = compute_optical_flow_clip(frames, size=self.frame_size)
            except Exception:
                flow_np = compute_optical_flow_clip(frames, size=self.frame_size)

        flow_video = flow_array_to_tensor(flow_np, clip_len=self.clip_len)

        if self.mode == "train":
            rgb_video, flow_video = apply_video_augmentations(rgb_video, flow_video)

        if self.transform:
            rgb_video = self.transform(rgb_video)

        return rgb_video, flow_video, torch.tensor(label, dtype=torch.long)


# ----------------------------
# Two-stream X3D model
# ----------------------------
class TwoStreamModel(nn.Module):
    def __init__(
        self,
        num_classes,
        fusion="add",
        rgb_pretrained=True,
        dropout: float = dropout_p,
    ):
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

        self.dropout = nn.Dropout(dropout)
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
# Validation
# ----------------------------
@torch.no_grad()
def evaluate(model, loader, criterion, amp_enabled: bool):
    model.eval()
    total_loss = 0.0
    n_batches = 0
    y_true: List[int] = []
    y_pred: List[int] = []

    for rgb, flow, labels in loader:
        rgb = rgb.to(device)
        flow = flow.to(device)
        labels = labels.to(device)

        with autocast(device_type="cuda", enabled=amp_enabled):
            out = model(rgb, flow)
            loss = criterion(out, labels)

        total_loss += float(loss.item())
        n_batches += 1
        preds = out.argmax(dim=1)
        y_true.extend(labels.cpu().tolist())
        y_pred.extend(preds.cpu().tolist())

    avg_loss = total_loss / max(n_batches, 1)
    cm = confusion_matrix(y_true, y_pred, num_classes=len(class_names))
    acc = accuracy_from_cm(cm)
    f1 = macro_f1(cm)
    stats = per_class_precision_recall_f1(cm)
    return avg_loss, acc, f1, cm, stats


def train_model(
    fusion: str = "add",
    plot_metrics: bool = PLOT_METRICS,
    online_flow: bool = ONLINE_FLOW,
    num_epochs: int = epochs,
    early_stop_patience: int = EARLY_STOP_PATIENCE,
    early_stop_min_delta: float = EARLY_STOP_MIN_DELTA,
    weight_decay_val: float = weight_decay,
    dropout: float = dropout_p,
    label_smooth: float = label_smoothing,
    backbone_learning_rate: float = backbone_lr,
    head_learning_rate: float = head_lr,
    class_weights: bool = use_class_weights,
):
    torch.backends.cudnn.benchmark = True
    amp_enabled = device.type == "cuda"

    data_workers = max(1, min(6, os.cpu_count() or 1))

    script_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_root = os.path.normpath(os.path.join(script_dir, "..", "dataset"))
    train_root = os.path.join(dataset_root, "train")
    val_root = os.path.join(dataset_root, "val")
    plot_dir = os.path.join(script_dir, PLOT_DIR)
    ckpt_path = os.path.join(script_dir, "..", CHECKPOINT_NAME)

    print(f"Using device: {device}")
    print(f"Using {data_workers} dataloader workers")
    print(f"CLIP_LEN={clip_len}, STRIDE={STRIDE}, FRAME_SIZE={FRAME_SIZE}")
    print(f"online_flow={online_flow}, plot_metrics={plot_metrics}")
    print(
        f"Regularization: weight_decay={weight_decay_val}, dropout={dropout}, "
        f"label_smoothing={label_smooth}, class_weights={class_weights}, "
        f"backbone_lr={backbone_learning_rate}, head_lr={head_learning_rate}"
    )
    if early_stop_patience > 0:
        print(
            f"Early stopping: patience={early_stop_patience}, "
            f"min_delta={early_stop_min_delta} (monitor=val_loss)"
        )
    else:
        print("Early stopping: disabled")

    transform = NormalizeVideo(RGB_MEAN, RGB_STD)

    train_dataset = VideoDataset(
        train_root,
        class_names,
        clip_len=clip_len,
        transform=transform,
        mode="train",
        online_flow=online_flow,
    )
    val_dataset = VideoDataset(
        val_root,
        class_names,
        clip_len=clip_len,
        transform=transform,
        mode="val",
        online_flow=online_flow,
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=data_workers,
        pin_memory=True,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=data_workers,
        pin_memory=True,
    )

    model = TwoStreamModel(
        num_classes=len(class_names),
        fusion=fusion,
        dropout=dropout,
    ).to(device)

    # Differential LRs: slow backbone, faster classifier head
    backbone_params = list(model.rgb_model.parameters()) + list(
        model.flow_model.parameters()
    )
    head_params = list(model.classifier.parameters())
    optimizer = optim.AdamW(
        [
            {"params": backbone_params, "lr": backbone_learning_rate},
            {"params": head_params, "lr": head_learning_rate},
        ],
        weight_decay=weight_decay_val,
    )
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=num_epochs)

    alpha = None
    if class_weights:
        label_counts = [0] * len(class_names)
        for _, _, lab in train_dataset.samples:
            label_counts[lab] += 1
        alpha = inverse_frequency_alpha(label_counts).to(device)
        print(
            "Class counts / FocalLoss alpha: "
            + ", ".join(
                f"{n}={c} (α={a:.3f})"
                for n, c, a in zip(class_names, label_counts, alpha.tolist())
            )
        )

    criterion = FocalLoss(
        gamma=focal_gamma,
        alpha=alpha,
        label_smoothing=label_smooth,
    ).to(device)
    scaler = GradScaler("cuda", enabled=amp_enabled)

    history = {
        "train_loss": [],
        "val_loss": [],
        "val_f1": [],
        "val_acc": [],
    }
    best_f1 = -1.0
    best_path = os.path.join(script_dir, "..", "suspicious_actions_best.pth")
    best_val_loss = float("inf")
    epochs_without_improvement = 0
    stopped_early = False

    for epoch in range(num_epochs):
        model.train()
        total_loss = 0.0
        n_batches = 0

        pbar = tqdm(train_loader, desc=f"Epoch {epoch + 1}/{num_epochs} [train]", leave=False)
        for rgb, flow, labels in pbar:
            rgb = rgb.to(device)
            flow = flow.to(device)
            labels = labels.to(device)

            optimizer.zero_grad(set_to_none=True)

            with autocast(device_type="cuda", enabled=amp_enabled):
                out = model(rgb, flow)
                loss = criterion(out, labels)

            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_grad_norm)
            scaler.step(optimizer)
            scaler.update()

            total_loss += float(loss.item())
            n_batches += 1
            pbar.set_postfix(loss=f"{loss.item():.4f}")

        scheduler.step()
        train_loss = total_loss / max(n_batches, 1)

        val_loss, val_acc, val_f1, cm, stats = evaluate(
            model, val_loader, criterion, amp_enabled
        )

        history["train_loss"].append(train_loss)
        history["val_loss"].append(val_loss)
        history["val_f1"].append(val_f1)
        history["val_acc"].append(val_acc)

        # P2 #11: log every epoch
        print(
            f"\nEpoch {epoch + 1}/{num_epochs} | "
            f"train_loss={train_loss:.4f} | val_loss={val_loss:.4f} | "
            f"val_acc={val_acc:.4f} | val_macro_f1={val_f1:.4f}"
        )
        print("Per-class precision / recall / F1:")
        for i, name in enumerate(class_names):
            print(
                f"  {name:<12}  P={stats['precision'][i]:.4f}  "
                f"R={stats['recall'][i]:.4f}  F1={stats['f1'][i]:.4f}  "
                f"n={int(stats['support'][i])}"
            )
        print(format_classification_report(cm, class_names))

        if val_f1 > best_f1:
            best_f1 = val_f1
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "class_names": class_names,
                    "epoch": epoch + 1,
                    "val_macro_f1": best_f1,
                    "val_acc": val_acc,
                    "clip_len": clip_len,
                    "stride": STRIDE,
                },
                best_path,
            )
            print(f"  ✓ New best macro-F1={best_f1:.4f} → {best_path}")

        # Early stopping on val_loss (stop when loss is not reducing)
        if early_stop_patience > 0:
            if val_loss < (best_val_loss - early_stop_min_delta):
                best_val_loss = val_loss
                epochs_without_improvement = 0
            else:
                epochs_without_improvement += 1
                print(
                    f"  No val_loss improvement for "
                    f"{epochs_without_improvement}/{early_stop_patience} epoch(s) "
                    f"(best={best_val_loss:.4f})"
                )
                if epochs_without_improvement >= early_stop_patience:
                    stopped_early = True
                    print(
                        f"\n⏹ Early stopping at epoch {epoch + 1}/{num_epochs}: "
                        f"val_loss did not improve by ≥{early_stop_min_delta} "
                        f"for {early_stop_patience} consecutive epochs "
                        f"(best val_loss={best_val_loss:.4f})."
                    )
                    break

        if plot_metrics:
            paths = plot_training_curves(
                history["train_loss"],
                val_losses=history["val_loss"],
                val_f1=history["val_f1"],
                val_acc=history["val_acc"],
                out_dir=plot_dir,
                prefix="train",
            )
            if epoch == 0:
                print(f"  Plots → {paths}")

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()

    # Final checkpoint (last completed epoch)
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "class_names": class_names,
            "val_macro_f1": history["val_f1"][-1] if history["val_f1"] else None,
            "clip_len": clip_len,
            "stride": STRIDE,
        },
        ckpt_path,
    )
    print(f"\nSaved last-epoch checkpoint → {ckpt_path}")
    print(f"Best val macro-F1={best_f1:.4f} → {best_path}")
    if stopped_early:
        print(
            f"Training stopped early after {len(history['val_loss'])} epoch(s) "
            f"(best val_loss={best_val_loss:.4f})."
        )

    if plot_metrics:
        paths = plot_training_curves(
            history["train_loss"],
            val_losses=history["val_loss"],
            val_f1=history["val_f1"],
            val_acc=history["val_acc"],
            out_dir=plot_dir,
            prefix="train_final",
        )
        print(f"Final plots: {paths}")

    return history


def parse_args():
    parser = argparse.ArgumentParser(description="Train two-stream X3D action model")
    parser.add_argument("--epochs", type=int, default=epochs)
    parser.add_argument("--fusion", type=str, default="add", choices=["add", "concat"])
    parser.add_argument(
        "--patience",
        type=int,
        default=EARLY_STOP_PATIENCE,
        help=(
            "Early stop after this many epochs without val_loss improvement "
            f"(default {EARLY_STOP_PATIENCE}; 0 disables)"
        ),
    )
    parser.add_argument(
        "--min-delta",
        type=float,
        default=EARLY_STOP_MIN_DELTA,
        help=(
            "Minimum val_loss decrease to count as improvement "
            f"(default {EARLY_STOP_MIN_DELTA})"
        ),
    )
    parser.add_argument(
        "--weight-decay",
        type=float,
        default=weight_decay,
        help=f"AdamW weight decay L2 (default {weight_decay})",
    )
    parser.add_argument(
        "--dropout",
        type=float,
        default=dropout_p,
        help=f"Classifier dropout probability (default {dropout_p})",
    )
    parser.add_argument(
        "--label-smoothing",
        type=float,
        default=label_smoothing,
        help=f"Cross-entropy label smoothing (default {label_smoothing})",
    )
    parser.add_argument(
        "--backbone-lr",
        type=float,
        default=backbone_lr,
        help=f"Learning rate for X3D backbones (default {backbone_lr})",
    )
    parser.add_argument(
        "--head-lr",
        type=float,
        default=head_lr,
        help=f"Learning rate for classifier head (default {head_lr})",
    )
    parser.add_argument(
        "--no-class-weights",
        action="store_true",
        help="Disable inverse-frequency FocalLoss alpha",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Enable matplotlib F1/loss plots (also PLOT_METRICS=1)",
    )
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="Disable plots even if PLOT_METRICS=1",
    )
    parser.add_argument(
        "--online-flow",
        action="store_true",
        help="Compute optical flow on the fly (matches serve; slower)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    env_plot = os.environ.get("PLOT_METRICS", "").strip().lower() in {"1", "true", "yes"}
    plot_metrics = (args.plot or env_plot) and not args.no_plot

    train_model(
        fusion=args.fusion,
        plot_metrics=plot_metrics,
        online_flow=args.online_flow or ONLINE_FLOW,
        num_epochs=args.epochs,
        early_stop_patience=args.patience,
        early_stop_min_delta=args.min_delta,
        weight_decay_val=args.weight_decay,
        dropout=args.dropout,
        label_smooth=args.label_smoothing,
        backbone_learning_rate=args.backbone_lr,
        head_learning_rate=args.head_lr,
        class_weights=not args.no_class_weights,
    )
