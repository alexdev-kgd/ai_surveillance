import React, { useState, useEffect, useRef } from "react";
import UploadForm from "./components/UploadForm";
import Results from "./components/Results";
import LiveStream from "./components/LiveStream";
import EventList from "./components/EventList";
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
		<div className="container">
			<div className="header">
				<h1>АИС: анализ видеопотока — прототип</h1>
			</div>

			<div className="card">
				<UploadForm setResult={setResult} />
				<Results result={result} />
			</div>

			<div className="card" style={{ display: "flex", gap: 16 }}>
				<div style={{ flex: 1 }}>
					<LiveStream />
				</div>
				<div style={{ width: 320 }}>
					<EventList events={events} />
				</div>
			</div>
		</div>
	);
}
