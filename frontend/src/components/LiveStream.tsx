import React, { useEffect, useRef, useState } from "react";

export default function LiveStream() {
	const videoRef = useRef<HTMLVideoElement>(null);
	const canvasRef = useRef<HTMLCanvasElement>(null);
	const [ws, setWs] = useState<WebSocket | null>(null);
	const [prediction, setPrediction] = useState<any>(null);

	// Websocket Setup and Response Handling
	useEffect(() => {
		const socket = new WebSocket("ws://127.0.0.1:8000/ws/video/");
		socket.onmessage = (event) => {
			const msg = JSON.parse(event.data);
			setPrediction(msg.prediction);

			// draw server-annotated frame
			if (canvasRef.current) {
				const ctx = canvasRef.current.getContext("2d");
				const img = new Image();
				img.onload = () => {
					canvasRef.current!.width = img.width;
					canvasRef.current!.height = img.height;
					ctx?.drawImage(img, 0, 0);
				};
				img.src = "data:image/jpeg;base64," + msg.frame;
			}
		};
		setWs(socket);
		return () => socket.close();
	}, []);

	// capture frames from webcam and send
	useEffect(() => {
		if (!ws) return;
		navigator.mediaDevices.getUserMedia({ video: true, audio: false }).then((stream) => {
			if (videoRef.current) {
				videoRef.current.srcObject = stream;
			}
			setInterval(() => {
				if (!videoRef.current || ws.readyState !== WebSocket.OPEN) return;

				const canvas = document.createElement("canvas");
				canvas.width = 224;
				canvas.height = 224;
				const ctx = canvas.getContext("2d");
				ctx?.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);

				canvas.toBlob((blob) => {
					if (!blob) return;
					const reader = new FileReader();
					reader.onloadend = () => {
						const base64data = (reader.result as string).split(",")[1];
						ws.send(base64data);
					};
					reader.readAsDataURL(blob);
				}, "image/jpeg");
			}, 200);
		});
	}, [ws]);

	return (
		<div className="w-50">
			<h3>Прямой поток (MJPEG)</h3>

			<video ref={videoRef} autoPlay playsInline hidden />
			<canvas ref={canvasRef} className="w-96 h-72 rounded-xl shadow-lg" />

			<div className="mt-4 text-lg font-bold text-blue-600 break-words">
				{prediction ? `Prediction: ${JSON.stringify(prediction)}` : "Waiting..."}
			</div>
		</div>
	);
}
