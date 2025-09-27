import React, { useEffect, useRef, useState } from "react";

export default function LiveStream() {
	const videoRef = useRef<HTMLVideoElement>(null);
	const [ws, setWs] = useState<WebSocket | null>(null);
	const [prediction, setPrediction] = useState<any>(null);

	useEffect(() => {
		// Запрос доступа к вебке
		navigator.mediaDevices
			.getUserMedia({
				video: { width: 640, height: 480 },
				audio: false,
			})
			.then((stream) => {
				if (videoRef.current) {
					videoRef.current.srcObject = stream;
				}
			});

		// Подключение к WebSocket
		const socket = new WebSocket("ws://127.0.0.1:8000/ws/video/");
		socket.onmessage = (event) => {
			const msg = JSON.parse(event.data);
			setPrediction(msg.prediction);
		};
		setWs(socket);

		return () => {
			socket.close();
		};
	}, []);

	// каждые 200мс снимаем кадр
	useEffect(() => {
		if (!ws) return;

		const interval = setInterval(() => {
			if (!videoRef.current) return;
			if (ws.readyState !== WebSocket.OPEN) return;

			const canvas = document.createElement("canvas");
			canvas.width = 224;
			canvas.height = 224;

			const ctx = canvas.getContext("2d");
			if (!ctx) return;

			ctx.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);

			canvas.toBlob((blob) => {
				if (!blob) return;
				const reader = new FileReader();
				reader.onloadend = () => {
					const base64data = (reader.result as string).split(",")[1];
					if (ws.readyState === WebSocket.OPEN) {
						ws.send(base64data);
					}
				};
				reader.readAsDataURL(blob);
			}, "image/jpeg");
		}, 200);

		return () => clearInterval(interval);
	}, [ws]);

	return (
		<div className="w-50">
			<h3>Прямой поток (MJPEG)</h3>
			<video ref={videoRef} autoPlay playsInline className="w-96 h-72 rounded-xl shadow-lg" />
			<div className="mt-4 text-lg font-bold text-blue-600 break-words">
				{prediction ? `Prediction: ${JSON.stringify(prediction)}` : "Waiting..."}
			</div>
		</div>
	);
}
