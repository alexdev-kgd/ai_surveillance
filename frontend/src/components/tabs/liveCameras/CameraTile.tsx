import { WSbaseURL } from "@api/ws";
import { DETECTED_ACTION_LABELS } from "@constants/detectedActionLabels.const";
import type { ICameraConfig } from "@interfaces/camera.interface";
import type { ILiveCameraFrameMessage } from "@interfaces/liveDetection.interface";
import type { ILiveDetectionEvent } from "@interfaces/liveDetectionEvent.interface";
import { useEffect, useRef, useState } from "react";

interface Props {
	camera: ICameraConfig;
	onSuspiciousDetection?: (event: ILiveDetectionEvent) => void;
}

const CAMERA_TARGET_FPS = 30;
const ANALYSIS_INPUT_FPS = CAMERA_TARGET_FPS;
const ANALYSIS_FRAME_INTERVAL_MS = 1000 / ANALYSIS_INPUT_FPS;
const MAX_WEBSOCKET_BUFFER_BYTES = 512 * 1024;
const JPEG_QUALITY = 0.65;
const DETECTION_COOLDOWN_MS = 2000;

export default function CameraTile({ camera, onSuspiciousDetection }: Props) {
	const videoRef = useRef<HTMLVideoElement>(null);
	const canvasRef = useRef<HTMLCanvasElement>(null);
	const lastReportedAtRef = useRef<Record<string, number>>({});

	const [ws, setWs] = useState<WebSocket | null>(null);
	const [streamFps, setStreamFps] = useState(0);
	const [analysisFps, setAnalysisFps] = useState(0);
	const [mediaWidth, setMediaWidth] = useState<number | null>(null);

	const isLocalCamera = camera.source === "WEBCAM" || camera.source === "USB";

	useEffect(() => {
		const socket = new WebSocket(`${WSbaseURL}${camera.wsPath}`);
		setWs(socket);

		const logOpen = () => console.log(`WS connected: ${camera.id}`);
		const logClose = () => console.log(`WS closed: ${camera.id}`);
		const logError = (err: Event) => console.error(`WS error ${camera.id}`, err);
		socket.addEventListener("open", logOpen);
		socket.addEventListener("close", logClose);
		socket.addEventListener("error", logError);

		return () => {
			socket.removeEventListener("open", logOpen);
			socket.removeEventListener("close", logClose);
			socket.removeEventListener("error", logError);
			socket.close();
			setWs(null);
		};
	}, [camera.id, camera.wsPath]);

	useEffect(() => {
		if (!ws) return;

		const drawDetections = (
			msg: Partial<ILiveCameraFrameMessage>,
			canvas: HTMLCanvasElement,
			width: number,
			height: number,
			flipVertically = false
		) => {
			if (canvas.width !== width) canvas.width = width;
			if (canvas.height !== height) canvas.height = height;

			const ctx = canvas.getContext("2d");
			if (!ctx) return;
			ctx.font = "600 16px Roboto, sans-serif";
			ctx.lineWidth = 3;

			for (const [index, detection] of (msg.detections ?? []).entries()) {
				const suspicious = detection.label !== DETECTED_ACTION_LABELS.normal;
				const color = suspicious ? "#ef4444" : "#22c55e";
				ctx.strokeStyle = color;
				ctx.fillStyle = color;

				if (detection.bbox?.length === 4) {
					const [x1, y1, x2, y2] = detection.bbox;
					ctx.strokeRect(x1, flipVertically ? height - y2 : y1, x2 - x1, y2 - y1);
				}

				const text = `${detection.label} (${detection.confidence.toFixed(2)})`;
				const textX = flipVertically ? 16 : (detection.bbox?.[0] ?? 16);
				const textY = flipVertically
					? 30 + index * 28
					: Math.max(22, (detection.bbox?.[1] ?? 30) - 8);
				const textWidth = ctx.measureText(text).width;
				ctx.fillStyle = "rgba(0, 0, 0, 0.68)";
				ctx.fillRect(textX - 4, textY - 18, textWidth + 8, 23);
				ctx.fillStyle = color;
				ctx.fillText(text, textX, textY);
			}
		};

		const handleMessage = (event: MessageEvent<string>) => {
			const msg = JSON.parse(event.data) as Partial<ILiveCameraFrameMessage>;
			const detections = Array.isArray(msg.detections) ? msg.detections : [];
			if (typeof msg.analysisFps === "number") setAnalysisFps(msg.analysisFps);

			const suspicious = detections
				.filter((detection) => detection.label !== DETECTED_ACTION_LABELS.normal)
				.sort((a, b) => b.confidence - a.confidence);

			if (suspicious.length > 0 && onSuspiciousDetection) {
				const topDetection = suspicious[0];
				const deduplicationKey = `${camera.id}:${topDetection.label}`;
				const now = Date.now();
				const lastReportedAt = lastReportedAtRef.current[deduplicationKey] ?? 0;

				if (now - lastReportedAt > DETECTION_COOLDOWN_MS) {
					onSuspiciousDetection({
						id: `${camera.id}-${topDetection.label}-${topDetection.frame}-${now}`,
						cameraId: camera.id,
						cameraName: camera.name,
						frame: topDetection.frame,
						label: topDetection.label,
						confidence: topDetection.confidence,
						timeSec: topDetection.frame / ANALYSIS_INPUT_FPS,
						detectedAt: new Date(now).toISOString(),
					});
					lastReportedAtRef.current[deduplicationKey] = now;
				}
			}

			if (isLocalCamera) {
				const canvas = canvasRef.current;
				const video = videoRef.current;
				if (!canvas || !video) return;
				const width = msg.sourceWidth || video.videoWidth || 640;
				const height = msg.sourceHeight || video.videoHeight || 480;
				const ctx = canvas.getContext("2d");
				ctx?.clearRect(0, 0, canvas.width, canvas.height);
				drawDetections({ ...msg, detections }, canvas, width, height);
				return;
			}

			if (!canvasRef.current || !msg.frame) return;
			const canvas = canvasRef.current;
			const ctx = canvas.getContext("2d");
			const img = new Image();
			img.onload = () => {
				canvas.width = img.width;
				canvas.height = img.height;
				setMediaWidth((current) => (current === img.width ? current : img.width));
				if (!ctx) return;
				ctx.clearRect(0, 0, canvas.width, canvas.height);
				ctx.save();
				ctx.translate(0, canvas.height);
				ctx.rotate(Math.PI);
				ctx.scale(-1, 1);
				ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
				ctx.restore();
				drawDetections({ ...msg, detections }, canvas, img.width, img.height, true);
			};
			img.src = `data:image/jpeg;base64,${msg.frame}`;
		};

		ws.addEventListener("message", handleMessage);
		return () => ws.removeEventListener("message", handleMessage);
	}, [ws, camera.id, camera.name, isLocalCamera, onSuspiciousDetection]);

	useEffect(() => {
		if (!isLocalCamera || !ws) return;

		let cancelled = false;
		let stopCamera = () => {};

		const startCamera = async () => {
			try {
				const exactVideoConstraints: MediaTrackConstraints = {
					...(camera.source === "USB" && camera.deviceId
						? { deviceId: { exact: camera.deviceId } }
						: {}),
					width: { exact: 640 },
					height: { exact: 480 },
					frameRate: { exact: CAMERA_TARGET_FPS },
				};
				const exactDefaultCameraConstraints: MediaTrackConstraints = {
					width: { exact: 640 },
					height: { exact: 480 },
					frameRate: { exact: CAMERA_TARGET_FPS },
				};
				const compatibleVideoConstraints: MediaTrackConstraints = {
					width: { ideal: 640 },
					height: { ideal: 480 },
					frameRate: { ideal: CAMERA_TARGET_FPS },
				};

				let stream: MediaStream | undefined;
				let lastConstraintError: unknown;
				for (const videoConstraints of [
					exactVideoConstraints,
					exactDefaultCameraConstraints,
					compatibleVideoConstraints,
				]) {
					try {
						stream = await navigator.mediaDevices.getUserMedia({
							video: videoConstraints,
							audio: false,
						});
						break;
					} catch (err) {
						lastConstraintError = err;
						if (!(err instanceof DOMException) || err.name !== "OverconstrainedError") {
							throw err;
						}
					}
				}
				if (!stream) throw lastConstraintError;

				if (cancelled) {
					stream.getTracks().forEach((track) => track.stop());
					return;
				}

				const video = videoRef.current;
				if (!video) {
					stream.getTracks().forEach((track) => track.stop());
					return;
				}
				const videoTrack = stream.getVideoTracks()[0];
				if (videoTrack) videoTrack.contentHint = "motion";
				video.srcObject = stream;
				await video.play();
				setMediaWidth((current) =>
					current === video.videoWidth ? current : video.videoWidth
				);

				const captureCanvas = document.createElement("canvas");
				const captureContext = captureCanvas.getContext("2d", { alpha: false });
				let encoding = false;
				let nextSendAt = 0;
				let fpsWindowStartedAt = performance.now();
				let fpsWindowFrames = 0;
				let videoFrameCallbackId = 0;

				const onVideoFrame: VideoFrameRequestCallback = (now) => {
					if (cancelled) return;

					fpsWindowFrames += 1;
					const fpsElapsed = now - fpsWindowStartedAt;
					if (fpsElapsed >= 1000) {
						setStreamFps((fpsWindowFrames * 1000) / fpsElapsed);
						fpsWindowFrames = 0;
						fpsWindowStartedAt = now;
					}

					if (
						now >= nextSendAt &&
						!encoding &&
						ws.readyState === WebSocket.OPEN &&
						ws.bufferedAmount < MAX_WEBSOCKET_BUFFER_BYTES
					) {
						nextSendAt =
							nextSendAt === 0 || now - nextSendAt > ANALYSIS_FRAME_INTERVAL_MS * 2
								? now + ANALYSIS_FRAME_INTERVAL_MS
								: nextSendAt + ANALYSIS_FRAME_INTERVAL_MS;
						encoding = true;
						const captureWidth = video.videoWidth || 640;
						const captureHeight = video.videoHeight || 480;
						if (captureCanvas.width !== captureWidth) captureCanvas.width = captureWidth;
						if (captureCanvas.height !== captureHeight) captureCanvas.height = captureHeight;
						captureContext?.drawImage(video, 0, 0, captureCanvas.width, captureCanvas.height);
						captureCanvas.toBlob(
							(blob) => {
								encoding = false;
								if (blob && !cancelled && ws.readyState === WebSocket.OPEN) {
									ws.send(blob);
								}
							},
							"image/jpeg",
							JPEG_QUALITY
						);
					}

					videoFrameCallbackId = video.requestVideoFrameCallback(onVideoFrame);
				};

				videoFrameCallbackId = video.requestVideoFrameCallback(onVideoFrame);

				stopCamera = () => {
					video.cancelVideoFrameCallback(videoFrameCallbackId);
					stream.getTracks().forEach((track) => track.stop());
					video.srcObject = null;
				};
			} catch (err) {
				console.error("Camera error:", err);
				if (!cancelled) alert("Ошибка доступа к камере.");
			}
		};

		const handleOpen = () => void startCamera();
		if (ws.readyState === WebSocket.OPEN) void startCamera();
		else ws.addEventListener("open", handleOpen, { once: true });

		return () => {
			cancelled = true;
			ws.removeEventListener("open", handleOpen);
			stopCamera();
		};
	}, [ws, isLocalCamera, camera.source, camera.deviceId]);

	return (
		<div
			className="w-full rounded-xl border p-2 shadow"
			style={{ maxWidth: mediaWidth ? mediaWidth + 18 : undefined }}
		>
			<h4 className="font-semibold text-center mb-2">{camera.name}</h4>

			<div className="relative overflow-hidden rounded-lg bg-black">
				{isLocalCamera && (
					<video
						ref={videoRef}
						autoPlay
						muted
						playsInline
						className="block h-auto w-full"
					/>
				)}
				<canvas
					ref={canvasRef}
					className={
						isLocalCamera
							? "pointer-events-none absolute inset-0 h-full w-full"
							: "block h-auto w-full"
					}
				/>
				{isLocalCamera && (
					<div
						data-testid={`camera-fps-${camera.id}`}
						className="absolute right-2 top-2 rounded bg-black/70 px-2 py-1 font-mono text-xs text-white"
					>
						Поток: {streamFps.toFixed(1)} FPS · Анализ: {analysisFps.toFixed(1)} FPS
					</div>
				)}
			</div>
		</div>
	);
}
