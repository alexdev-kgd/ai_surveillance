import { WSbaseURL } from "@api/ws";
import type { ICameraConfig } from "@interfaces/camera.interface";
import { DETECTED_ACTION_LABELS } from "@constants/detectedActionLabels.const";
import type { ILiveCameraFrameMessage } from "@interfaces/liveDetection.interface";
import type { ILiveDetectionEvent } from "@interfaces/liveDetectionEvent.interface";
import { useEffect, useRef, useState } from "react";

interface Props {
	camera: ICameraConfig;
	onSuspiciousDetection?: (event: ILiveDetectionEvent) => void;
}

const LIVE_STREAM_FPS = 5;
const DETECTION_COOLDOWN_MS = 2000;

export default function CameraTile({ camera, onSuspiciousDetection }: Props) {
	const videoRef = useRef<HTMLVideoElement>(null);
	const canvasRef = useRef<HTMLCanvasElement>(null);
	const lastReportedAtRef = useRef<Record<string, number>>({});

	const [ws, setWs] = useState<WebSocket | null>(null);

	// --- WS ---
	useEffect(() => {
		const socket = new WebSocket(`${WSbaseURL}${camera.wsPath}`);
		setWs(socket);

		socket.onopen = () => console.log(`WS connected: ${camera.id}`);

		socket.onclose = () => console.log(`WS closed: ${camera.id}`);

		socket.onerror = (err) => console.error(`WS error ${camera.id}`, err);

		// Cleanup on unmount
		return () => socket.close();
	}, [camera]);

	// --- Receive frames ---
	useEffect(() => {
		if (!ws) return;

		ws.onmessage = (event) => {
			const msg = JSON.parse(event.data) as Partial<ILiveCameraFrameMessage>;
			const detections = Array.isArray(msg.detections) ? msg.detections : [];
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
						timeSec: topDetection.frame / LIVE_STREAM_FPS,
						detectedAt: new Date(now).toISOString(),
					});
					lastReportedAtRef.current[deduplicationKey] = now;
				}
			}

			if (!canvasRef.current) return;

			const ctx = canvasRef.current.getContext("2d");
			const img = new Image();

			img.onload = () => {
				const canvas = canvasRef.current!;
				canvas.width = img.width;
				canvas.height = img.height;

				if (!ctx) return;
				ctx.clearRect(0, 0, canvas.width, canvas.height);

				// IP stream in this project is mounted inverted; rotate 180deg for correct orientation.
				if (camera.source === "IP") {
					ctx.save();
					ctx.translate(canvas.width - canvas.width, canvas.height);
					ctx.rotate(Math.PI);
					ctx.scale(-1, 1);
					ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
					ctx.restore();
					return;
				}

				ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
			};

			img.src = "data:image/jpeg;base64," + (msg.frame ?? "");
		};
	}, [ws, camera.source]);

	// --- Webcam only ---
	// Capture frames from webcam and send
	useEffect(() => {
		if ((camera.source !== "WEBCAM" && camera.source !== "USB") || !ws) return;

		const startCamera = async () => {
			try {
				const stream = await navigator.mediaDevices.getUserMedia({
					video:
						camera.source === "USB" && camera.deviceId
							? {
									deviceId: { exact: camera.deviceId },
									width: 640,
									height: 480,
							  }
							: { width: 640, height: 480 },
					audio: false,
				});

				if (videoRef.current) {
					videoRef.current.srcObject = stream;
				}

				const sendFrame = () => {
					if (!videoRef.current || ws.readyState !== WebSocket.OPEN) return;

					const canvas = document.createElement("canvas");
					canvas.width = 640;
					canvas.height = 480;

					const ctx = canvas.getContext("2d");
					ctx?.drawImage(videoRef.current, 0, 0);

					canvas.toBlob((blob) => {
						if (!blob) return;
						const reader = new FileReader();
						reader.onloadend = () => {
							const base64 = (reader.result as string).split(",")[1];
							ws.send(base64);
						};
						reader.readAsDataURL(blob);
					}, "image/jpeg");
				};

				const interval = setInterval(sendFrame, 200);
				return () => clearInterval(interval);
			} catch (err) {
				console.error("Camera error:", err);
				alert("Ошибка доступа к камере.");
			}
		};

		if (ws.readyState === WebSocket.OPEN) startCamera();
		else ws.onopen = startCamera;
	}, [ws, camera.source, camera.deviceId]);

	return (
		<div className="rounded-xl border p-2 shadow">
			<h4 className="font-semibold text-center mb-2">{camera.name}</h4>

			<video ref={videoRef} autoPlay playsInline hidden />

			<canvas ref={canvasRef} style={{ width: "100%", borderRadius: 8 }} />
		</div>
	);
}
