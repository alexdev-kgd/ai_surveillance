"""Matplotlib helpers for training curves."""
from __future__ import annotations

import os
from typing import List, Optional, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def plot_training_curves(
    train_losses: Sequence[float],
    val_losses: Optional[Sequence[float]] = None,
    val_f1: Optional[Sequence[float]] = None,
    val_acc: Optional[Sequence[float]] = None,
    out_dir: str = "training_plots",
    prefix: str = "run",
) -> List[str]:
    """
    Save loss / F1 / accuracy plots. Returns list of written file paths.
    """
    os.makedirs(out_dir, exist_ok=True)
    saved: List[str] = []
    epochs = range(1, len(train_losses) + 1)

    # Loss
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(epochs, train_losses, label="Train loss", marker="o", markersize=3)
    if val_losses is not None and len(val_losses) == len(train_losses):
        ax.plot(epochs, val_losses, label="Val loss", marker="s", markersize=3)
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Loss")
    ax.set_title("Training / Validation Loss")
    ax.grid(True, alpha=0.3)
    ax.legend()
    path = os.path.join(out_dir, f"{prefix}_loss.png")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    saved.append(path)

    # F1
    if val_f1 is not None and len(val_f1) > 0:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(range(1, len(val_f1) + 1), val_f1, label="Val macro-F1", color="tab:green", marker="o", markersize=3)
        ax.set_xlabel("Epoch")
        ax.set_ylabel("Macro F1")
        ax.set_title("Validation Macro-F1")
        ax.set_ylim(0.0, 1.05)
        ax.grid(True, alpha=0.3)
        ax.legend()
        path = os.path.join(out_dir, f"{prefix}_f1.png")
        fig.tight_layout()
        fig.savefig(path, dpi=120)
        plt.close(fig)
        saved.append(path)

    # Accuracy
    if val_acc is not None and len(val_acc) > 0:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(range(1, len(val_acc) + 1), val_acc, label="Val accuracy", color="tab:orange", marker="o", markersize=3)
        ax.set_xlabel("Epoch")
        ax.set_ylabel("Accuracy")
        ax.set_title("Validation Accuracy")
        ax.set_ylim(0.0, 1.05)
        ax.grid(True, alpha=0.3)
        ax.legend()
        path = os.path.join(out_dir, f"{prefix}_accuracy.png")
        fig.tight_layout()
        fig.savefig(path, dpi=120)
        plt.close(fig)
        saved.append(path)

    # Combined overview
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    axes[0].plot(epochs, train_losses, label="Train loss")
    if val_losses is not None and len(val_losses) == len(train_losses):
        axes[0].plot(epochs, val_losses, label="Val loss")
    axes[0].set_title("Loss")
    axes[0].set_xlabel("Epoch")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()

    if val_f1 is not None and len(val_f1) > 0:
        axes[1].plot(range(1, len(val_f1) + 1), val_f1, label="Macro-F1", color="tab:green")
    if val_acc is not None and len(val_acc) > 0:
        axes[1].plot(range(1, len(val_acc) + 1), val_acc, label="Accuracy", color="tab:orange")
    axes[1].set_title("Validation metrics")
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylim(0.0, 1.05)
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()

    path = os.path.join(out_dir, f"{prefix}_overview.png")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    saved.append(path)

    return saved
