"""Classification metrics used by the training pipeline (no sklearn dependency)."""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import numpy as np


def confusion_matrix(y_true: Sequence[int], y_pred: Sequence[int], num_classes: int) -> np.ndarray:
    cm = np.zeros((num_classes, num_classes), dtype=np.int64)
    for t, p in zip(y_true, y_pred):
        if 0 <= t < num_classes and 0 <= p < num_classes:
            cm[t, p] += 1
    return cm


def per_class_precision_recall_f1(cm: np.ndarray) -> Dict[str, np.ndarray]:
    """cm[true, pred]. Returns precision, recall, f1 arrays of shape (C,)."""
    tp = np.diag(cm).astype(np.float64)
    support = cm.sum(axis=1).astype(np.float64)
    pred_sum = cm.sum(axis=0).astype(np.float64)

    precision = np.divide(tp, pred_sum, out=np.zeros_like(tp), where=pred_sum > 0)
    recall = np.divide(tp, support, out=np.zeros_like(tp), where=support > 0)
    denom = precision + recall
    f1 = np.divide(2 * precision * recall, denom, out=np.zeros_like(tp), where=denom > 0)
    return {"precision": precision, "recall": recall, "f1": f1, "support": support}


def accuracy_from_cm(cm: np.ndarray) -> float:
    total = cm.sum()
    if total == 0:
        return 0.0
    return float(np.diag(cm).sum() / total)


def macro_f1(cm: np.ndarray) -> float:
    stats = per_class_precision_recall_f1(cm)
    # macro over classes that appear in ground truth (support > 0)
    mask = stats["support"] > 0
    if not np.any(mask):
        return 0.0
    return float(stats["f1"][mask].mean())


def format_classification_report(
    cm: np.ndarray,
    class_names: Optional[List[str]] = None,
) -> str:
    stats = per_class_precision_recall_f1(cm)
    n = cm.shape[0]
    if class_names is None:
        class_names = [str(i) for i in range(n)]

    lines = []
    header = f"{'class':<16}{'precision':>10}{'recall':>10}{'f1':>10}{'support':>10}"
    lines.append(header)
    lines.append("-" * len(header))
    for i in range(n):
        name = class_names[i] if i < len(class_names) else str(i)
        lines.append(
            f"{name:<16}"
            f"{stats['precision'][i]:>10.4f}"
            f"{stats['recall'][i]:>10.4f}"
            f"{stats['f1'][i]:>10.4f}"
            f"{int(stats['support'][i]):>10d}"
        )
    lines.append("-" * len(header))
    lines.append(
        f"{'accuracy':<16}{accuracy_from_cm(cm):>10.4f}"
        f"{'':>10}{'':>10}{int(cm.sum()):>10d}"
    )
    lines.append(
        f"{'macro_f1':<16}{macro_f1(cm):>10.4f}"
    )
    lines.append("\nConfusion matrix (rows=true, cols=pred):")
    lines.append(np.array2string(cm, max_line_width=120))
    return "\n".join(lines)
