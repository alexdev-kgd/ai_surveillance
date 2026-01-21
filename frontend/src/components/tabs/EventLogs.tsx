import axios from "axios";
import React, { useEffect } from "react";
import { baseURL } from "@api/axios";
import type { IEvent } from "@interfaces/event.interface";

export default function EventLogs() {
	const [events, setEvents] = React.useState<IEvent[]>([]);

	useEffect(() => {
		const controller = new AbortController();

		const fetchEvents = async () => {
			const res = await axios.get(`${baseURL}/events/`, {
				signal: controller.signal,
			});
			setEvents(res.data);
		};

		fetchEvents();

		return () => controller.abort();
	}, []);

	return (
		<div>
			<h3>Журнал событий</h3>
			<table
				style={{
					marginTop: 16,
					width: "100%",
					borderCollapse: "collapse",
					border: "1px solid #ccc",
				}}
			>
				<thead style={{ backgroundColor: "#000000" }}>
					<tr>
						<th style={cellStyle}>Действие</th>
						<th style={cellStyle}>Камера</th>
						<th style={cellStyle}>Время</th>
						<th style={cellStyle}>Подробности</th>
					</tr>
				</thead>
				<tbody>
					{events.map((ev: IEvent, idx: number) => {
						return (
							<tr key={idx}>
								<td style={cellStyle}>{ev.event_type}</td>
								<td style={cellStyle}>{ev.camera}</td>
								<td style={cellStyle}>
									{new Date(ev.timestamp).toLocaleTimeString("ru-RU")}
								</td>
								<td style={cellStyle}>{ev.details}</td>
							</tr>
						);
					})}
				</tbody>
			</table>
		</div>
	);
}

const cellStyle: React.CSSProperties = {
	border: "1px solid #ddd",
	padding: "6px 8px",
	textAlign: "center",
};
