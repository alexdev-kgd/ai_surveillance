import React, { useState, useEffect, useRef } from "react";
import VideoTabs from "./components/VideoTabs";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Auth from "./components/Auth";
import { LogoutButton } from "./components/LogoutButton";

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
		<BrowserRouter>
			<Routes>
				<Route path="/auth" element={<Auth />} />

				<Route
					path="/"
					element={
						<ProtectedRoute>
							<div className="flex flex-col full-width items-center min-h-screen p-5">
								<div className="flex flex-row space-between full-width gap-5">
									<h1 className="text-2xl font-bold">
										АИС: анализ видеопотока — прототип
									</h1>
									<LogoutButton></LogoutButton>
								</div>
								<VideoTabs
									setResult={setResult}
									result={result}
									events={events}
								/>
							</div>
						</ProtectedRoute>
					}
				/>

				<Route path="*" element={<Navigate to="/" />} />
			</Routes>
		</BrowserRouter>
	);
}
