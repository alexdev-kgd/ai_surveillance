"""Measure physical USB capture and the latest-frame WebSocket pipeline."""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import time
from dataclasses import dataclass

import websockets


@dataclass
class Metrics:
    captured: int = 0
    sent: int = 0
    analyzed: int = 0
    latest_analysis_fps: float = 0.0
    latest_analysis_ms: float = 0.0
    dropped_frames: int = 0


class MJPEGReader:
    def __init__(self, stream) -> None:
        self.stream = stream
        self.buffer = bytearray()

    def read(self) -> bytes | None:
        while True:
            start = self.buffer.find(b"\xff\xd8")
            end = self.buffer.find(b"\xff\xd9", start + 2) if start >= 0 else -1
            if start >= 0 and end >= 0:
                jpeg = bytes(self.buffer[start : end + 2])
                del self.buffer[: end + 2]
                return jpeg

            chunk = self.stream.read(4096)
            if not chunk:
                return None
            self.buffer.extend(chunk)
            new_start = self.buffer.find(b"\xff\xd8")
            if new_start > 0:
                del self.buffer[:new_start]
            elif new_start < 0 and len(self.buffer) > 1:
                del self.buffer[:-1]


async def receive_metrics(websocket, metrics: Metrics) -> None:
    async for payload in websocket:
        message = json.loads(payload)
        metrics.analyzed += 1
        metrics.latest_analysis_fps = float(message.get("analysisFps", 0.0))
        metrics.latest_analysis_ms = float(message.get("analysisMs", 0.0))
        metrics.dropped_frames = int(message.get("droppedFrames", 0))


async def benchmark(args: argparse.Namespace) -> Metrics:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "dshow",
        "-video_size",
        args.size,
        "-framerate",
        str(args.fps),
        "-vcodec",
        "mjpeg",
        "-i",
        f"video={args.device}",
        "-an",
        "-c:v",
        "copy",
        "-f",
        "image2pipe",
        "pipe:1",
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=0,
    )
    if process.stdout is None:
        raise RuntimeError("ffmpeg stdout pipe was not created")
    reader = MJPEGReader(process.stdout)

    metrics = Metrics()
    started_at: float | None = None
    ended_at: float | None = None
    next_send_at = 0.0

    try:
        async with websockets.connect(args.websocket, max_size=2**22) as websocket:
            receiver = asyncio.create_task(receive_metrics(websocket, metrics))
            try:
                while started_at is None or time.perf_counter() - started_at < args.duration:
                    jpeg = await asyncio.to_thread(reader.read)
                    if jpeg is None:
                        break
                    now = time.perf_counter()
                    if started_at is None:
                        started_at = now
                    metrics.captured += 1
                    ended_at = now

                    send_interval = 1.0 / args.send_fps
                    if now >= next_send_at:
                        await websocket.send(jpeg)
                        metrics.sent += 1
                        next_send_at = (
                            now + send_interval
                            if next_send_at == 0.0 or now - next_send_at > send_interval * 2
                            else next_send_at + send_interval
                        )
            finally:
                await asyncio.sleep(0.5)
                receiver.cancel()
                await asyncio.gather(receiver, return_exceptions=True)
    finally:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)

    if started_at is None or ended_at is None:
        raise RuntimeError("The camera produced no frames")
    capture_elapsed = max(ended_at - started_at, 1e-6)
    print(
        json.dumps(
            {
                "device": args.device,
                "elapsed_s": round(capture_elapsed, 3),
                "capture_fps": round(max(0, metrics.captured - 1) / capture_elapsed, 2),
                "transport_fps": round(metrics.sent / capture_elapsed, 2),
                "analysis_messages": metrics.analyzed,
                "latest_analysis_fps": round(metrics.latest_analysis_fps, 2),
                "latest_analysis_ms": round(metrics.latest_analysis_ms, 2),
                "dropped_frames": metrics.dropped_frames,
            },
            ensure_ascii=False,
        )
    )
    return metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="Venus USB2.0 Camera")
    parser.add_argument("--size", default="640x480")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--send-fps", type=float, default=10.0)
    parser.add_argument("--duration", type=float, default=10.0)
    parser.add_argument("--websocket", required=True)
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(benchmark(parse_args()))
