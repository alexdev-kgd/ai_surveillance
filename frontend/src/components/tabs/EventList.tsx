import React from "react";
import { DETECTED_ACTION_LABELS } from "@constants/detectedActionLabels.const";
import type { IEvent } from "@interfaces/event.interface";
import type { ILiveDetectionEvent } from "@interfaces/liveDetectionEvent.interface";

interface Props {
	events?: IEvent[];
	liveEvents?: ILiveDetectionEvent[];
}

export default function EventList({ events = [], liveEvents = [] }: Props) {
	const suspiciousServerEvents = events.filter(
		(ev) => ev.event_type !== DETECTED_ACTION_LABELS.normal
	);
	const hasLiveEvents = liveEvents.length > 0;
	const hasServerEvents = suspiciousServerEvents.length > 0;

	if (!hasLiveEvents && !hasServerEvents) {
		return <p style={{ marginTop: 16 }}>Подозрительных действий не обнаружено.</p>;
	}

	return (
		<div>
			<h3>Обнаружены подозрительные действия</h3>
			<table
				style={{
					marginTop: 16,
					width: "100%",
					borderCollapse: "collapse",
					border: "1px solid #ccc",
				}}
			>
				<thead style={{ backgroundColor: "#f7f7f7" }}>
					<tr>
						<th style={cellStyle}>Камера</th>
						<th style={cellStyle}>Кадр</th>
						<th style={cellStyle}>Действие</th>
						<th style={cellStyle}>Время</th>
					</tr>
				</thead>
				<tbody>
					{hasLiveEvents &&
						liveEvents.map((event) => (
							<tr key={event.id}>
								<td style={cellStyle}>{event.cameraName}</td>
								<td style={cellStyle}>{event.frame}</td>
								<td style={cellStyle}>{event.label}</td>
								<td style={cellStyle}>{event.timeSec.toFixed(2)}s</td>
							</tr>
						))}
					{!hasLiveEvents &&
						suspiciousServerEvents.map((event, idx) => (
							<tr key={`${event.camera ?? "camera"}-${idx}`}>
								<td style={cellStyle}>{event.camera ?? "-"}</td>
								<td style={cellStyle}>-</td>
								<td style={cellStyle}>{event.event_type}</td>
								<td style={cellStyle}>
									{new Date(event.timestamp).toLocaleTimeString("ru-RU")}
								</td>
							</tr>
						))}
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

