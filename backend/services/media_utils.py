import os
import shutil
import subprocess
import tempfile
from datetime import datetime

import cv2

from services.anomaly_predictor import (
    analyze_scene,
    analyze_with_yolo,
    reset_predictor_state,
)
from services.settings import get_settings

STATIC_DIR = "static/processed"

# OpenCV on Windows often cannot write H.264 (broken libopenh264).
# Write with a reliable OpenCV codec, then re-encode to H.264 via ffmpeg
# so HTML5 <video> in Chrome/Edge/Firefox can play the result.
_VIDEO_WRITER_CODECS = (
    "mp4v",
    "XVID",
    "MJPG",
)


def open_video_writer(path: str, fps: float, size: tuple[int, int]) -> cv2.VideoWriter:
    """Open a VideoWriter, trying several fourcc codes until one initializes."""
    if fps is None or fps <= 1e-3 or fps > 120:
        fps = 25.0

    width, height = size
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid video size: {size}")

    last_error = None
    for codec in _VIDEO_WRITER_CODECS:
        fourcc = cv2.VideoWriter_fourcc(*codec)
        writer = cv2.VideoWriter(path, fourcc, float(fps), (width, height))
        if writer is not None and writer.isOpened():
            return writer
        last_error = codec
        if writer is not None:
            writer.release()

    raise RuntimeError(
        f"Failed to open VideoWriter for '{path}' "
        f"(tried codecs: {', '.join(_VIDEO_WRITER_CODECS)}; last={last_error})."
    )


def _find_ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def reencode_for_browser(src_path: str, dst_path: str) -> bool:
    """
    Re-encode to H.264 + yuv420p + faststart for browser playback.
    Returns True on success.
    """
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        print("[media_utils] ffmpeg not found; serving OpenCV codec as-is (may not play in browser)")
        return False

    cmd = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        src_path,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-an",
        dst_path,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return os.path.isfile(dst_path) and os.path.getsize(dst_path) > 0
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"[media_utils] ffmpeg re-encode failed: {exc}")
        if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
            try:
                print(exc.stderr.decode("utf-8", errors="replace"))
            except Exception:
                pass
        return False


def analyze_video_file(path: str):
    os.makedirs(STATIC_DIR, exist_ok=True)
    reset_predictor_state()

    output_filename = f"annotated_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    output_path = os.path.join(STATIC_DIR, output_filename)

    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"[media_utils] Input video FPS: {fps}")
    if not fps or fps <= 1e-3:
        fps = 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Write intermediate file with OpenCV-compatible codec
    fd, tmp_path = tempfile.mkstemp(suffix=".mp4", prefix="annotated_raw_")
    os.close(fd)
    try:
        out = open_video_writer(tmp_path, fps, (width, height))

        total_frames = 0
        detections = []

        settings = get_settings() or {}
        use_yolo = settings.get("useObjectDetection", False)

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            total_frames += 1
            annotated_frame = frame.copy()

            result = (
                analyze_with_yolo(annotated_frame, total_frames)
                if use_yolo
                else analyze_scene(annotated_frame, total_frames)
            )

            detections.extend(result["detections"])
            annotated_frame = result["frame_data"]
            out.write(annotated_frame)

        cap.release()
        out.release()

        # Convert to H.264 for browser <video>
        if not reencode_for_browser(tmp_path, output_path):
            # Fallback: copy raw OpenCV output (may not play in Chrome)
            shutil.copy2(tmp_path, output_path)
            print(
                "[media_utils] Warning: output is not browser-friendly H.264. "
                "Install ffmpeg with libx264 for Chrome/Edge playback."
            )
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    return {
        "total_frames": total_frames,
        "fps": float(fps),
        "detections": detections,
        "video_path": f"static/processed/{output_filename}",
    }
