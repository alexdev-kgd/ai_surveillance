"""
Precompute optical flow for the dataset using the same sampling as train/serve.

Sampling: sequential frames every SAMPLE_STRIDE until CLIP_LEN RGB frames,
then Farneback between consecutive RGB frames → (CLIP_LEN, H, W, 2) after pad.

Existing *_flow.npy files are skipped unless --force is passed.
"""
import argparse
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.optical_flow_cache import precompute_missing_flow
from utils.video_preprocess import CLIP_LEN, FRAME_SIZE, SAMPLE_STRIDE

DATASET_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "dataset"))


def process_dataset(
    root: str = DATASET_ROOT,
    skip_existing: bool = True,
    train_dir: str | None = None,
    val_dir: str | None = None,
) -> None:
    if train_dir or val_dir:
        split_dirs = [path for path in (train_dir, val_dir) if path]
    else:
        split_dirs = [
            os.path.join(root, split)
            for split in ("train", "val")
            if os.path.isdir(os.path.join(root, split))
        ]

    stats = precompute_missing_flow(
        split_dirs,
        skip_existing=skip_existing,
        show_progress_bar=True,
    )
    print("\nDone!")
    print(f"Queued (missing flow): {stats['queued']}")
    print(f"Processed: {stats['processed']}")
    print(f"Skipped (too short): {stats['skipped_short']}")
    print(f"Failed: {stats['failed']}")
    print(f"CLIP_LEN={CLIP_LEN}, STRIDE={SAMPLE_STRIDE}, size={FRAME_SIZE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Precompute optical flow for train/val videos")
    parser.add_argument(
        "--root",
        default=DATASET_ROOT,
        help="Dataset root that contains train/ and val/ (default: backend/dataset)",
    )
    parser.add_argument("--train-dir", default=None, help="Explicit train split directory")
    parser.add_argument("--val-dir", default=None, help="Explicit val split directory")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recompute even if a matching *_flow.npy already exists",
    )
    args = parser.parse_args()
    process_dataset(
        root=args.root,
        skip_existing=not args.force,
        train_dir=args.train_dir,
        val_dir=args.val_dir,
    )
