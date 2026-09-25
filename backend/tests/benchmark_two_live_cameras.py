"""Measure one USB and one RTSP camera through the running WebSocket server.

This is an observational benchmark of the current host, not a synthetic model
benchmark. GPU utilisation and VRAM are host-wide and may include other apps.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import statistics
import subprocess
import time

import psutil
import websockets


class MJPEGReader:
    def __init__(self, stream):
        self.stream = stream
        self.buffer = bytearray()

    def read(self):
        while True:
            start = self.buffer.find(b"\xff\xd8")
            end = self.buffer.find(b"\xff\xd9", start + 2) if start >= 0 else -1
            if start >= 0 and end >= 0:
                frame = bytes(self.buffer[start : end + 2])
                del self.buffer[: end + 2]
                return frame
            chunk = self.stream.read(4096)
            if not chunk:
                return None
            self.buffer.extend(chunk)
            if len(self.buffer) > 8_000_000:
                raise RuntimeError("MJPEG frame boundary was not found")


def sample_host(backend_pid):
    result = subprocess.run(
        ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
        capture_output=True, text=True, timeout=5, check=True,
    )
    utilization, vram = [float(x.strip()) for x in result.stdout.splitlines()[0].split(",")]
    ram = psutil.Process(backend_pid).memory_info().rss / 2**20 if backend_pid else None
    return {"gpu_pct": utilization, "vram_mib": vram, "backend_ram_mib": ram}


async def samples(backend_pid, until, output):
    while time.perf_counter() < until:
        try:
            output.append(await asyncio.to_thread(sample_host, backend_pid))
        except Exception as exc:
            output.append({"error": type(exc).__name__})
        await asyncio.sleep(0.8)


async def usb_stream(args, until, output):
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "dshow",
               "-video_size", args.size, "-framerate", str(args.fps), "-vcodec", "mjpeg",
               "-i", f"video={args.device}", "-an", "-c:v", "copy", "-f", "image2pipe", "pipe:1"]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
    stderr_task = asyncio.create_task(asyncio.to_thread(process.stderr.read))
    reader = MJPEGReader(process.stdout)
    capture_times = []
    send_times = []
    inbound_bytes = 0
    results = []

    async def receive(ws):
        async for payload in ws:
            try:
                msg = json.loads(payload)
                if "analysisMs" in msg:
                    results.append((time.perf_counter(), msg))
            except (TypeError, ValueError):
                pass

    try:
        async with websockets.connect(f"{args.ws_base}/{args.usb_camera_id}", max_size=2**23) as ws:
            task = asyncio.create_task(receive(ws))
            next_send = 0.0
            try:
                while time.perf_counter() < until:
                    frame = await asyncio.to_thread(reader.read)
                    if frame is None:
                        break
                    now = time.perf_counter()
                    capture_times.append(now)
                    if now >= next_send:
                        await ws.send(frame)
                        inbound_bytes += len(frame)
                        send_times.append(now)
                        next_send = now + 1 / args.send_fps
                await asyncio.sleep(1.0)
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
    finally:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
        err = (await stderr_task).decode(errors="replace").strip()
        if err:
            output["ffmpeg_error"] = err[:300]

    output.update({
        "capture_frames": len(capture_times), "uploaded_frames": len(send_times),
        "uploaded_bytes": inbound_bytes, "analysis_messages": len(results),
        "capture_observation_s": round(capture_times[-1] - capture_times[0], 3) if len(capture_times) > 1 else None,
        "upload_observation_s": round(send_times[-1] - send_times[0], 3) if len(send_times) > 1 else None,
        "analysis_observation_s": round(results[-1][0] - results[0][0], 3) if len(results) > 1 else None,
        "latest_analysis_fps": results[-1][1].get("analysisFps") if results else None,
        "analysis_ms_mean": statistics.mean(x[1]["analysisMs"] for x in results) if results else None,
        "analysis_ms_p95": sorted(x[1]["analysisMs"] for x in results)[int((len(results)-1)*.95)] if results else None,
        "reported_skipped_frames": results[-1][1].get("droppedFrames") if results else None,
    })


async def ip_stream(args, until, output):
    times = []
    outbound_bytes = 0
    errors = []
    async with websockets.connect(f"{args.ws_base}/{args.ip_camera_id}", max_size=2**23) as ws:
        while time.perf_counter() < until:
            try:
                payload = await asyncio.wait_for(ws.recv(), timeout=2.0)
            except asyncio.TimeoutError:
                continue
            now = time.perf_counter()
            try:
                message = json.loads(payload)
                if "error" in message:
                    errors.append(str(message["error"]))
                elif "frame" in message:
                    times.append(now)
                    outbound_bytes += len(base64.b64decode(message["frame"]))
            except (ValueError, TypeError):
                pass
    output.update({"delivered_frames": len(times), "delivered_bytes": outbound_bytes,
                   "delivery_observation_s": round(times[-1] - times[0], 3) if len(times) > 1 else None,
                   "stream_errors": errors[:3]})


def summarize(values):
    if not values:
        return None
    sorted_values = sorted(values)
    return {"mean": round(statistics.mean(values), 2),
            "p95": round(sorted_values[int((len(values)-1)*.95)], 2),
            "max": round(max(values), 2)}


async def main(args):
    baseline = []
    for _ in range(3):
        baseline.append(await asyncio.to_thread(sample_host, args.backend_pid))
        await asyncio.sleep(0.6)
    start = time.perf_counter()
    until = start + args.duration
    usb, ip, host = {}, {}, []
    outcomes = await asyncio.gather(
        usb_stream(args, until, usb), ip_stream(args, until, ip),
        samples(args.backend_pid, until, host), return_exceptions=True,
    )
    elapsed = time.perf_counter() - start
    result = {
        "test": "USB + IP simultaneously", "duration_s": round(elapsed, 2),
        "requested_duration_s": args.duration, "resolution_usb": args.size,
        "capture_fps_usb": round(usb.get("capture_frames", 0) / elapsed, 2),
        "upload_fps_usb": round(usb.get("uploaded_frames", 0) / elapsed, 2),
        "upload_mbit_s_usb": round(usb.get("uploaded_bytes", 0) * 8 / elapsed / 1e6, 3),
        "analysis_fps_usb": round(usb.get("analysis_messages", 0) / elapsed, 2),
        "ip_delivery_fps": round(ip.get("delivered_frames", 0) / elapsed, 2),
        "ip_downstream_mbit_s": round(ip.get("delivered_bytes", 0) * 8 / elapsed / 1e6, 3),
        "usb": usb, "ip": ip,
        "gpu_pct_host": summarize([x["gpu_pct"] for x in host if "gpu_pct" in x]),
        "gpu_sample_count": len([x for x in host if "gpu_pct" in x]),
        "vram_mib_host": summarize([x["vram_mib"] for x in host if "vram_mib" in x]),
        "backend_ram_mib": summarize([x["backend_ram_mib"] for x in host if x.get("backend_ram_mib") is not None]),
        "baseline": baseline,
        "errors": [f"{type(x).__name__}: {x}" for x in outcomes if isinstance(x, Exception)],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--usb-camera-id", required=True)
    parser.add_argument("--ip-camera-id", required=True)
    parser.add_argument("--backend-pid", type=int, required=True)
    parser.add_argument("--ws-base", default="ws://127.0.0.1:8000/ws/video")
    parser.add_argument("--device", default="Venus USB2.0 Camera")
    parser.add_argument("--size", default="640x480")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--send-fps", type=float, default=30.0)
    parser.add_argument("--duration", type=float, default=30.0)
    asyncio.run(main(parser.parse_args()))
