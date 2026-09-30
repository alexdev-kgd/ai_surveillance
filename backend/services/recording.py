import logging
import re
import threading
import time
from datetime import datetime
from pathlib import Path

import cv2

from schemas.recording import RecordingSettings

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RECORDINGS_DIR = PROJECT_ROOT / "saved_recordings"
_settings = RecordingSettings()
_settings_lock = threading.RLock()
_recorders: dict[str, "CameraRecorder"] = {}


def resolve_recordings_dir(directory: str) -> Path:
    value = directory.strip()
    if not value or "\x00" in value:
        raise ValueError("Invalid recording directory")
    if value == "saved_recordings":
        return RECORDINGS_DIR
    path = Path(value).expanduser()
    if path.drive and not path.is_absolute():
        raise ValueError("Recording directory must be absolute or relative to the project")
    return (path if path.is_absolute() else PROJECT_ROOT / path).resolve()


def get_recording_settings() -> RecordingSettings:
    with _settings_lock:
        return _settings.copy(deep=True)


def active_recording_paths() -> set[Path]:
    with _settings_lock:
        return {recorder.path.resolve() for recorder in _recorders.values() if recorder.path}


def set_recording_settings(settings: RecordingSettings) -> None:
    global _settings
    with _settings_lock:
        previous = _settings
        _settings = settings.copy(deep=True)
        for camera_id, recorder in list(_recorders.items()):
            if (
                not settings.enabled
                or not settings.camera_enabled.get(camera_id, True)
                or previous.clip_limit_mode != settings.clip_limit_mode
                or previous.max_clip_size_mb != settings.max_clip_size_mb
                or previous.max_clip_duration_seconds != settings.max_clip_duration_seconds
                or previous.directory != settings.directory
            ):
                recorder.close()


def safe_camera_name(name: str) -> str:
    # Keep human-readable names while excluding path traversal and Windows-invalid characters.
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return cleaned or "Camera"


class CameraRecorder:
    def __init__(self):
        self.lock = threading.RLock()
        self.writer = None
        self.path: Path | None = None
        self.directory: Path | None = None
        self.name = ""
        self.size = None
        self.started_at: float | None = None

    def close(self):
        with self.lock:
            if self.writer is not None:
                self.writer.release()
            self.writer = None
            self.path = None
            self.directory = None
            self.size = None
            self.started_at = None

    def write(
        self, name: str, frame, fps: float, mode: str, directory: Path,
        max_bytes: int, max_duration_seconds: int,
    ):
        with self.lock:
            height, width = frame.shape[:2]
            if self.writer is not None and (
                self.name != name or self.size != (width, height)
                or self.directory != directory
            ):
                self.close()
            if (
                mode == "duration" and self.writer is not None
                and self.started_at is not None
                and time.monotonic() - self.started_at >= max_duration_seconds
            ):
                self.close()
            if self.writer is None:
                folder = directory / safe_camera_name(name)
                folder.mkdir(parents=True, exist_ok=True)
                # A new clip in the same second must not overwrite an existing clip.
                while True:
                    path = folder / f"{datetime.now():%H-%M-%S_%d-%m-%Y}.avi"
                    if not path.exists():
                        break
                    threading.Event().wait(0.05)
                writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (width, height))
                if not writer.isOpened():
                    writer.release()
                    logger.error("Cannot open recording file %s", path)
                    return
                self.writer = writer
                self.path = path
                self.directory = directory
                self.name = name
                self.size = (width, height)
                self.started_at = time.monotonic()
            self.writer.write(frame)
            if mode == "size" and self.path and self.path.stat().st_size >= max_bytes:
                self.close()


def record_frame(
    camera_id: str,
    camera_name: str,
    frame,
    fps: float = 20.0,
    flip_vertical: bool = False,
):
    with _settings_lock:
        settings = _settings
        recorder = _recorders.get(camera_id)
        if not settings.enabled or not settings.camera_enabled.get(camera_id, True):
            if recorder:
                recorder.close()
            return
        if recorder is None:
            recorder = _recorders[camera_id] = CameraRecorder()
        max_bytes = settings.max_clip_size_mb * 1024 * 1024
        mode = settings.clip_limit_mode
        max_duration_seconds = settings.max_clip_duration_seconds
    try:
        directory = resolve_recordings_dir(settings.directory)
        if flip_vertical:
            frame = cv2.flip(frame, 0)
        recorder.write(
            camera_name, frame, fps if 1 <= fps <= 120 else 20.0,
            mode, directory, max_bytes, max_duration_seconds,
        )
    except (OSError, ValueError, cv2.error):
        logger.exception("Recording failed for camera %s", camera_id)
        recorder.close()


def close_camera_recording(camera_id: str):
    with _settings_lock:
        recorder = _recorders.pop(camera_id, None)
        if recorder:
            recorder.close()


def close_all_recordings():
    with _settings_lock:
        for recorder in _recorders.values():
            recorder.close()
        _recorders.clear()
