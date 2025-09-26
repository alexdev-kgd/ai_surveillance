import React, { useState, useEffect, useRef } from "react";
import VideoTabs from "./components/VideoTabs";
import axios from "axios";

interface Event {
	event_type: string;
	camera: string;
	timestamp?: string;
	details?: string;
}

export default function App() {
	const [result, setResult] = useState<any>(null);
	const [events, setEvents] = useState<Event[]>([]);
	const wsRef = useRef<WebSocket | null>(null);

	useEffect(() => {
		axios
			.get<Event[]>("http://127.0.0.1:8000/events/recent")
			.then((res) => setEvents(res.data || []));

		const ws = new WebSocket("ws://127.0.0.1:8000/ws/events");
		ws.onopen = () => console.log("ws open");
		ws.onmessage = (event) => {
			try {
				const data: Event = JSON.parse(event.data);
				setEvents((prev) => [data, ...prev].slice(0, 50));
			} catch (e) {
				// сервер может присылать текст — игнорируем
			}
		};
		wsRef.current = ws;
		return () => {
			ws.close();
		};
	}, []);

	return (
		<div className="flex flex-col items-center min-h-screen p-5">
			<div className="text-center mb-5">
				<h1 className="text-2xl font-bold">
					АИС: анализ видеопотока — прототип
				</h1>
			</div>

			<VideoTabs setResult={setResult} result={result} events={events} />
		</div>
	);
}
