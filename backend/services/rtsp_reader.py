import logging
import os
import threading
import time
from urllib.parse import quote, urlsplit, urlunsplit

import cv2

logger = logging.getLogger(__name__)


class RTSPCameraReader:
    def __init__(
        self,
        rtsp_url: str,
        name: str = "Camera",
        reconnect_delay_sec: float = 2.0,
        open_timeout_ms: int = 5000,
        read_timeout_ms: int = 5000,
    ):
        self.rtsp_url = rtsp_url
        self._safe_rtsp_url = self._normalize_rtsp_url(rtsp_url)
        self.name = name
        self.reconnect_delay_sec = reconnect_delay_sec
        self.open_timeout_ms = open_timeout_ms
        self.read_timeout_ms = read_timeout_ms

        self.cap = None
        self.thread = None
        self.running = False
        self.last_frame = None
        self.last_frame_ts = 0.0

        self._connected = False
        self._was_connected = False

        self.lock = threading.Lock()
        self.stop_event = threading.Event()

        # FFmpeg capture options for RTSP stability/latency:
        # - TCP transport for reliability
        # - connect/read timeout
        # - low-delay/no-buffer
        # - reduced queue/buffer
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
            "rtsp_flags;prefer_tcp|stimeout;5000000|rw_timeout;5000000|timeout;5000000|"
            "fflags;nobuffer|flags;low_delay|reorder_queue_size;0|"
            "buffer_size;65536|max_delay;500000"
        )

    def start(self):
        with self.lock:
            if self.running:
                return
            if self.thread and self.thread.is_alive():
                logger.warning("Camera %s reader thread is already alive", self.name)
                return
            self.running = True
            self.stop_event.clear()
            self.thread = threading.Thread(
                target=self._run,
                name=f"RTSPReader-{self.name}",
                daemon=True,
            )
            self.thread.start()

    def _open_capture(self):
        cap = cv2.VideoCapture(self._safe_rtsp_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if hasattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC"):
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, float(self.open_timeout_ms))
        if hasattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC"):
            cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, float(self.read_timeout_ms))

        return cap

    @staticmethod
    def _normalize_rtsp_url(rtsp_url: str) -> str:
        """
        Percent-encode credentials in RTSP URL to avoid auth failures when
        username/password contain reserved characters.
        """
        try:
            parts = urlsplit(rtsp_url)
            if parts.scheme.lower() != "rtsp":
                return rtsp_url
            if not parts.username and not parts.password:
                return rtsp_url

            username = quote(parts.username or "", safe="")
            password = quote(parts.password or "", safe="")

            host = parts.hostname or ""
            if ":" in host and not host.startswith("["):
                host = f"[{host}]"
            if parts.port:
                host = f"{host}:{parts.port}"

            auth = username
            if parts.password is not None:
                auth = f"{username}:{password}"
            netloc = f"{auth}@{host}" if auth else host

            return urlunsplit(
                (parts.scheme, netloc, parts.path, parts.query, parts.fragment)
            )
        except Exception:
            return rtsp_url

    def _release_capture(self):
        cap = self.cap
        self.cap = None
        if cap is not None:
            cap.release()

    def _mark_disconnected(self):
        if self._connected:
            logger.warning("Camera %s stream lost, reconnecting...", self.name)
        self._connected = False

    def _run(self):
        while not self.stop_event.is_set():
            self.cap = self._open_capture()

            if self.cap is None or not self.cap.isOpened():
                logger.warning("Camera %s failed to connect", self.name)
                self._mark_disconnected()
                self._release_capture()
                self.stop_event.wait(self.reconnect_delay_sec)
                continue

            if not self._connected:
                if self._was_connected:
                    logger.info("Camera %s reconnected", self.name)
                else:
                    logger.info("Camera %s connected", self.name)
            self._connected = True
            self._was_connected = True

            while not self.stop_event.is_set():
                ret, frame = self.cap.read()
                if not ret or frame is None:
                    self._mark_disconnected()
                    self._release_capture()
                    self.stop_event.wait(self.reconnect_delay_sec)
                    break

                with self.lock:
                    self.last_frame = frame
                    self.last_frame_ts = time.time()

        self._release_capture()
        self._connected = False
        with self.lock:
            self.running = False

    def get_frame(self):
        with self.lock:
            return None if self.last_frame is None else self.last_frame.copy()

    def is_connected(self) -> bool:
        return self._connected

    def get_health(self) -> dict:
        return {
            "name": self.name,
            "connected": self._connected,
            "running": self.running,
            "last_frame_ts": self.last_frame_ts or None,
        }

    def stop(self):
        with self.lock:
            if not self.running:
                return
            self.running = False
            self.stop_event.set()
            thread = self.thread

        # Releasing capture first helps unblock a stuck read() in some backends.
        self._release_capture()

        # Join briefly to avoid zombie threads on app shutdown.
        if thread and thread.is_alive():
            thread.join(timeout=2.0)

        with self.lock:
            self.thread = None
