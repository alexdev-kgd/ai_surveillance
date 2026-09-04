"""
Shared video clip preprocessing for train and serve.

Keeps clip length, sampling stride, resize, RGB normalization, and
optical-flow parameters identical across training and inference.
"""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple, Union

import cv2
import numpy as np
import torch

# ---------------------------------------------------------------------------
# Canonical clip settings (train + serve must use these)
# ---------------------------------------------------------------------------
CLIP_LEN = 16
SAMPLE_STRIDE = 2
FRAME_SIZE = (224, 224)  # (width, height)
RGB_MEAN = (0.45, 0.45, 0.45)
RGB_STD = (0.225, 0.225, 0.225)

FLOW_PARAMS = dict(
    pyr_scale=0.5,
    levels=3,
    winsize=15,
    iterations=3,
    poly_n=5,
    poly_sigma=1.2,
    flags=0,
)

FLOW_SUFFIX = "_flow.npy"


def resize_bgr(frame: np.ndarray, size: Tuple[int, int] = FRAME_SIZE) -> np.ndarray:
    return cv2.resize(frame, size)


def bgr_to_rgb_uint8(frame_bgr: np.ndarray, size: Tuple[int, int] = FRAME_SIZE) -> np.ndarray:
    frame = resize_bgr(frame_bgr, size)
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def normalize_rgb_frame(rgb_uint8: np.ndarray) -> np.ndarray:
    """Single RGB uint8 HxWx3 -> float32 normalized HxWx3."""
    x = rgb_uint8.astype(np.float32) / 255.0
    mean = np.array(RGB_MEAN, dtype=np.float32).reshape(1, 1, 3)
    std = np.array(RGB_STD, dtype=np.float32).reshape(1, 1, 3)
    return (x - mean) / std


def rgb_clip_to_tensor(rgb_frames: Sequence[np.ndarray]) -> torch.Tensor:
    """
    List/array of T RGB frames (uint8 or float HxWx3) -> float tensor (3, T, H, W)
    already normalized if uint8; if float assumed already normalized.
    """
    frames = []
    for f in rgb_frames:
        if f.dtype == np.uint8:
            frames.append(normalize_rgb_frame(f))
        else:
            frames.append(f.astype(np.float32))
    arr = np.stack(frames, axis=0)  # T,H,W,3
    return torch.from_numpy(arr).permute(3, 0, 1, 2).contiguous()


def normalize_rgb_tensor(tensor: torch.Tensor) -> torch.Tensor:
    """
    Normalize video tensor in (C, T, H, W) with values in [0, 1].
    """
    mean = torch.tensor(RGB_MEAN, dtype=tensor.dtype, device=tensor.device).view(3, 1, 1, 1)
    std = torch.tensor(RGB_STD, dtype=tensor.dtype, device=tensor.device).view(3, 1, 1, 1)
    return (tensor - mean) / std


class NormalizeVideo:
    """Callable normalize for DataLoader pipelines (C,T,H,W in [0,1])."""

    def __init__(self, mean=RGB_MEAN, std=RGB_STD):
        self.mean = mean
        self.std = std

    def __call__(self, tensor: torch.Tensor) -> torch.Tensor:
        mean = torch.tensor(self.mean, dtype=tensor.dtype, device=tensor.device).view(3, 1, 1, 1)
        std = torch.tensor(self.std, dtype=tensor.dtype, device=tensor.device).view(3, 1, 1, 1)
        return (tensor - mean) / std


def pad_or_trim_frames(frames: List[np.ndarray], clip_len: int = CLIP_LEN) -> List[np.ndarray]:
    if not frames:
        h, w = FRAME_SIZE[1], FRAME_SIZE[0]
        frames = [np.zeros((h, w, 3), dtype=np.uint8)]
    while len(frames) < clip_len:
        frames.append(frames[-1].copy())
    return frames[:clip_len]


def sample_strided_indices(num_frames: int, clip_len: int = CLIP_LEN, stride: int = SAMPLE_STRIDE) -> List[int]:
    """Indices of frames taken every `stride` until `clip_len` samples (or end)."""
    indices = list(range(0, num_frames, stride))
    if not indices:
        return [0]
    if len(indices) >= clip_len:
        return indices[:clip_len]
    # pad with last index
    while len(indices) < clip_len:
        indices.append(indices[-1])
    return indices


def read_video_strided_rgb(
    video_path: str,
    clip_len: int = CLIP_LEN,
    stride: int = SAMPLE_STRIDE,
    size: Tuple[int, int] = FRAME_SIZE,
) -> List[np.ndarray]:
    """Read video and return clip_len RGB uint8 frames using sequential stride sampling."""
    cap = cv2.VideoCapture(video_path)
    frames: List[np.ndarray] = []
    frame_idx = 0
    while len(frames) < clip_len:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % stride == 0:
            frames.append(bgr_to_rgb_uint8(frame, size))
        frame_idx += 1
    cap.release()
    return pad_or_trim_frames(frames, clip_len)


def compute_optical_flow_clip(
    rgb_frames: Sequence[np.ndarray],
    size: Tuple[int, int] = FRAME_SIZE,
    normalize: bool = True,
) -> np.ndarray:
    """
    Farneback optical flow between consecutive frames.

    Args:
        rgb_frames: length T, each HxWx3 (uint8 RGB) or gray
        size: resize target
        normalize: clip to [-1, 1] by max abs (same as precompute_flow)

    Returns:
        float32 array (T, H, W, 2) — last flow repeated to match T.
    """
    grays = []
    for f in rgb_frames:
        if f.ndim == 3:
            if f.shape[2] == 3:
                g = cv2.cvtColor(f, cv2.COLOR_RGB2GRAY)
            else:
                g = f[:, :, 0]
        else:
            g = f
        if (g.shape[1], g.shape[0]) != size:
            g = cv2.resize(g, size)
        grays.append(g)

    if len(grays) < 2:
        h, w = size[1], size[0]
        return np.zeros((max(len(grays), 1), h, w, 2), dtype=np.float32)

    flows = []
    for prev, curr in zip(grays[:-1], grays[1:]):
        flow = cv2.calcOpticalFlowFarneback(prev, curr, None, **FLOW_PARAMS)
        flows.append(flow.astype(np.float32))

    flow_arr = np.stack(flows, axis=0)  # T-1, H, W, 2

    if normalize:
        max_val = np.abs(flow_arr).max()
        if max_val > 0:
            flow_arr = np.clip(flow_arr / max_val, -1.0, 1.0)

    # Pad to T by repeating last flow field
    last = flow_arr[-1][None, ...]
    flow_arr = np.concatenate([flow_arr, last], axis=0)

    return flow_arr.astype(np.float32)


def flow_array_to_tensor(flow_array: np.ndarray, clip_len: int = CLIP_LEN) -> torch.Tensor:
    """(T,H,W,2) -> (2,T,H,W) float32, pad/trim to clip_len."""
    if flow_array.shape[0] < clip_len:
        pad = np.repeat(flow_array[-1][None, ...], clip_len - flow_array.shape[0], axis=0)
        flow_array = np.concatenate([flow_array, pad], axis=0)
    flow_array = flow_array[:clip_len]
    return torch.from_numpy(flow_array.astype(np.float32)).permute(3, 0, 1, 2).contiguous()


def load_precomputed_flow(flow_path: str, clip_len: int = CLIP_LEN) -> np.ndarray:
    """
    Load *_flow.npy and align to clip_len frames (T,H,W,2).

    Supports older precompute shapes (T-1,) without applying an extra stride
    (stride must already match how the file was built).
    """
    flow = np.load(flow_path)
    if flow.ndim != 4 or flow.shape[-1] != 2:
        raise ValueError(f"Unexpected flow shape {flow.shape} in {flow_path}")

    flow = flow.astype(np.float32)
    if flow.shape[0] < clip_len:
        pad = np.repeat(flow[-1][None, ...], clip_len - flow.shape[0], axis=0)
        flow = np.concatenate([flow, pad], axis=0)
    return flow[:clip_len]


def prepare_model_inputs(
    rgb_frames: Sequence[np.ndarray],
    flow_array: Optional[np.ndarray] = None,
    device: Optional[torch.device] = None,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Build batched model inputs (1,C,T,H,W) from RGB frames and optional flow.

    If flow_array is None, optical flow is computed online from rgb_frames.
    """
    frames = pad_or_trim_frames(list(rgb_frames), CLIP_LEN)
    rgb = rgb_clip_to_tensor(frames).unsqueeze(0)

    if flow_array is None:
        flow_array = compute_optical_flow_clip(frames)

    flow = flow_array_to_tensor(flow_array, CLIP_LEN).unsqueeze(0)

    if device is not None:
        rgb = rgb.to(device)
        flow = flow.to(device)
    return rgb, flow
