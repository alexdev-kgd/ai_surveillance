"""Create a person-cropped copy of the video dataset with YOLO.

The input directory is expected to contain videos in an arbitrary directory
tree (for example ``dataset/train/assault/1.mp4``).  The same tree is created
under the output directory and every detected person track is written as a
separate 224x224 video:

    dataset-cropped/train/assault/1__person_001.mp4

Run from any directory:

    python backend/fine-tune/crop_dataset_with_yolo.py

Use ``--help`` to see options for paths, confidence, crop margin and tracking.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence

import cv2
import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
DEFAULT_INPUT_DIR = BACKEND_DIR / "dataset"
DEFAULT_OUTPUT_DIR = BACKEND_DIR / "dataset-cropped"
DEFAULT_MODEL = BACKEND_DIR / "yolov8n.onnx"

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".m4v", ".webm"}
PERSON_CLASS_ID = 0  # COCO class id used by the standard YOLO models


@dataclass
class Track:
    """A lightweight person track used to keep crops temporally consistent."""

    track_id: int
    bbox: np.ndarray
    temp_path: Path
    final_path: Path
    writer: cv2.VideoWriter
    frame_count: int = 0
    missed_frames: int = 0


@dataclass
class VideoResult:
    source: Path
    crops_created: int = 0
    short_tracks_skipped: int = 0
    existing_crops_skipped: int = 0
    frames_read: int = 0


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Detect people in every dataset video and create one cropped video "
            "per person track while preserving the dataset directory structure."
        )
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=f"Source dataset directory (default: {DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Destination dataset directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--model",
        default=str(DEFAULT_MODEL),
        help=f"Ultralytics model name or local model path (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.25,
        help="Minimum YOLO confidence for a person detection (default: 0.25)",
    )
    parser.add_argument(
        "--image-size",
        type=int,
        default=640,
        help="YOLO inference image size (default: 640)",
    )
    parser.add_argument(
        "--crop-size",
        type=int,
        default=224,
        help="Width and height of each output crop video (default: 224)",
    )
    parser.add_argument(
        "--margin",
        type=float,
        default=0.10,
        help="Extra crop margin as a fraction of bbox size (default: 0.10)",
    )
    parser.add_argument(
        "--match-iou",
        type=float,
        default=0.30,
        help="Minimum IoU for matching a detection to an existing track (default: 0.30)",
    )
    parser.add_argument(
        "--max-missed",
        type=int,
        default=5,
        help="Frames to keep a track alive after a missed detection (default: 5)",
    )
    parser.add_argument(
        "--min-frames",
        type=int,
        default=16,
        help="Discard person tracks shorter than this many frames (default: 16)",
    )
    parser.add_argument(
        "--device",
        default=None,
        help="Ultralytics device, for example 'cpu', '0' or '0,1' (default: auto)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite cropped videos that already exist",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most N source videos (useful for a smoke test)",
    )
    args = parser.parse_args(argv)

    if not 0.0 <= args.confidence <= 1.0:
        parser.error("--confidence must be between 0 and 1")
    if not 0.0 <= args.margin <= 1.0:
        parser.error("--margin must be between 0 and 1")
    if not 0.0 <= args.match_iou <= 1.0:
        parser.error("--match-iou must be between 0 and 1")
    if args.image_size <= 0 or args.crop_size <= 0:
        parser.error("--image-size and --crop-size must be positive")
    if args.max_missed < 0 or args.min_frames <= 0:
        parser.error("--max-missed must be non-negative and --min-frames must be positive")
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")
    return args


def is_relative_to(path: Path, parent: Path) -> bool:
    """Path.is_relative_to compatible helper for older Python versions."""

    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def collect_videos(input_dir: Path, output_dir: Path) -> list[Path]:
    output_dir = output_dir.resolve()
    return sorted(
        path
        for path in input_dir.rglob("*")
        if path.is_file()
        and path.suffix.lower() in VIDEO_EXTENSIONS
        and not is_relative_to(path.resolve(), output_dir)
    )


def bbox_iou(first: np.ndarray, second: np.ndarray) -> float:
    x1 = max(float(first[0]), float(second[0]))
    y1 = max(float(first[1]), float(second[1]))
    x2 = min(float(first[2]), float(second[2]))
    y2 = min(float(first[3]), float(second[3]))
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    first_area = max(0.0, float(first[2] - first[0])) * max(
        0.0, float(first[3] - first[1])
    )
    second_area = max(0.0, float(second[2] - second[0])) * max(
        0.0, float(second[3] - second[1])
    )
    union = first_area + second_area - intersection
    return intersection / union if union > 0.0 else 0.0


def match_detections(
    tracks: dict[int, Track], detections: list[np.ndarray], min_iou: float
) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    """Greedily match boxes using highest IoU first."""

    candidates: list[tuple[float, int, int]] = []
    for track_id, track in tracks.items():
        for detection_index, detection in enumerate(detections):
            iou = bbox_iou(track.bbox, detection)
            if iou >= min_iou:
                candidates.append((iou, track_id, detection_index))

    matched_tracks: set[int] = set()
    matched_detections: set[int] = set()
    matches: list[tuple[int, int]] = []
    for _, track_id, detection_index in sorted(candidates, reverse=True):
        if track_id in matched_tracks or detection_index in matched_detections:
            continue
        matched_tracks.add(track_id)
        matched_detections.add(detection_index)
        matches.append((track_id, detection_index))

    unmatched_tracks = [track_id for track_id in tracks if track_id not in matched_tracks]
    unmatched_detections = [
        index for index in range(len(detections)) if index not in matched_detections
    ]
    return matches, unmatched_tracks, unmatched_detections


def crop_person(
    frame: np.ndarray, bbox: np.ndarray, margin: float, crop_size: int
) -> np.ndarray | None:
    frame_height, frame_width = frame.shape[:2]
    x1, y1, x2, y2 = map(float, bbox)
    box_width = max(0.0, x2 - x1)
    box_height = max(0.0, y2 - y1)
    x1 = max(0, math.floor(x1 - box_width * margin))
    y1 = max(0, math.floor(y1 - box_height * margin))
    x2 = min(frame_width, math.ceil(x2 + box_width * margin))
    y2 = min(frame_height, math.ceil(y2 + box_height * margin))
    if x2 <= x1 or y2 <= y1:
        return None
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    return cv2.resize(crop, (crop_size, crop_size), interpolation=cv2.INTER_LINEAR)


def make_writer(path: Path, fps: float, crop_size: int) -> cv2.VideoWriter:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (crop_size, crop_size),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Could not create output video: {path}")
    return writer


def finish_track(
    track: Track, min_frames: int, overwrite: bool
) -> Literal["created", "short", "exists"]:
    track.writer.release()
    if track.frame_count < min_frames:
        track.temp_path.unlink(missing_ok=True)
        return "short"
    if track.final_path.exists():
        if not overwrite:
            track.temp_path.unlink(missing_ok=True)
            return "exists"
        track.final_path.unlink()
    os.replace(track.temp_path, track.final_path)
    return "created"


def update_result_for_finished_track(
    result: VideoResult, track: Track, min_frames: int, overwrite: bool
) -> None:
    status = finish_track(track, min_frames, overwrite)
    if status == "created":
        result.crops_created += 1
    elif status == "short":
        result.short_tracks_skipped += 1
    else:
        result.existing_crops_skipped += 1


def extract_person_boxes(result: object) -> list[np.ndarray]:
    boxes = getattr(result, "boxes", None)
    if boxes is None or len(boxes) == 0:
        return []
    xyxy = boxes.xyxy.detach().cpu().numpy()
    return [box.astype(np.float32) for box in xyxy]


def process_video(
    model: object,
    source: Path,
    input_dir: Path,
    output_dir: Path,
    args: argparse.Namespace,
) -> VideoResult:
    relative_path = source.relative_to(input_dir)
    destination_dir = output_dir / relative_path.parent
    result = VideoResult(source=source)

    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open source video: {source}")

    fps = float(capture.get(cv2.CAP_PROP_FPS))
    if not math.isfinite(fps) or fps <= 0.0:
        fps = 30.0

    active_tracks: dict[int, Track] = {}
    next_track_id = 1
    completed = False

    def create_track(bbox: np.ndarray) -> Track:
        nonlocal next_track_id
        stem = f"{relative_path.stem}__person_{next_track_id:03d}"
        final_path = destination_dir / f"{stem}.mp4"
        temp_path = destination_dir / f".{stem}.part.mp4"
        if temp_path.exists():
            temp_path.unlink()
        track = Track(
            track_id=next_track_id,
            bbox=bbox,
            temp_path=temp_path,
            final_path=final_path,
            writer=make_writer(temp_path, fps, args.crop_size),
        )
        next_track_id += 1
        return track

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            result.frames_read += 1

            prediction = model.predict(
                frame,
                classes=[PERSON_CLASS_ID],
                conf=args.confidence,
                imgsz=args.image_size,
                device=args.device,
                verbose=False,
            )[0]
            detections = extract_person_boxes(prediction)
            matches, unmatched_tracks, unmatched_detections = match_detections(
                active_tracks, detections, args.match_iou
            )
            detected_track_ids: set[int] = set()

            for track_id, detection_index in matches:
                track = active_tracks[track_id]
                track.bbox = detections[detection_index]
                track.missed_frames = 0
                detected_track_ids.add(track_id)

            for track_id in unmatched_tracks:
                active_tracks[track_id].missed_frames += 1

            for detection_index in unmatched_detections:
                track = create_track(detections[detection_index])
                active_tracks[track.track_id] = track
                detected_track_ids.add(track.track_id)

            finished_track_ids: list[int] = []
            for track_id, track in active_tracks.items():
                if track.missed_frames > args.max_missed:
                    finished_track_ids.append(track_id)
                    continue
                # Match serving behavior: only add a model input when YOLO
                # detected this person on the current frame.
                if track_id not in detected_track_ids:
                    continue
                crop = crop_person(frame, track.bbox, args.margin, args.crop_size)
                if crop is not None:
                    track.writer.write(crop)
                    track.frame_count += 1

            for track_id in finished_track_ids:
                track = active_tracks.pop(track_id)
                update_result_for_finished_track(
                    result, track, args.min_frames, args.overwrite
                )
        completed = True
    finally:
        capture.release()
        for track in active_tracks.values():
            if completed:
                update_result_for_finished_track(
                    result, track, args.min_frames, args.overwrite
                )
            else:
                track.writer.release()
                track.temp_path.unlink(missing_ok=True)

    return result


def describe_path(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    input_dir = args.input_dir.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()

    if not input_dir.is_dir():
        print(f"Input directory does not exist: {input_dir}", file=sys.stderr)
        return 2
    if input_dir == output_dir:
        print("Input and output directories must be different.", file=sys.stderr)
        return 2

    videos = collect_videos(input_dir, output_dir)
    if args.limit is not None:
        videos = videos[: args.limit]
    if not videos:
        print(f"No supported videos found under {input_dir}")
        return 0

    # Importing Ultralytics is intentionally delayed so `--help` remains fast.
    from ultralytics import YOLO

    print(f"Loading YOLO model: {args.model}")
    model = YOLO(args.model, task="detect")
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Found {len(videos)} video(s). Output: {output_dir}")

    total_crops = 0
    failed = 0
    for index, source in enumerate(videos, start=1):
        label = describe_path(source, input_dir)
        print(f"[{index}/{len(videos)}] {label}")
        try:
            video_result = process_video(
                model, source, input_dir, output_dir, args
            )
            total_crops += video_result.crops_created
            print(
                f"  frames={video_result.frames_read}, "
                f"crops={video_result.crops_created}, "
                f"skipped_short={video_result.short_tracks_skipped}, "
                f"skipped_existing={video_result.existing_crops_skipped}"
            )
        except Exception as exc:
            failed += 1
            print(f"  ERROR: {exc}", file=sys.stderr)

    print(
        f"Done: {len(videos) - failed}/{len(videos)} video(s) processed, "
        f"{total_crops} cropped video(s) created."
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
