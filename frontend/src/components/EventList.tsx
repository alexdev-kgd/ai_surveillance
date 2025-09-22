import React from "react";

interface Event {
	event_type: string;
	camera: string;
	timestamp?: string;
	details?: string;
}

interface Props {
	events?: Event[];
}

export default function EventList({ events = [] }: Props) {
	return (
		<div>
			<h3>События</h3>
			<ul className="events">
				{events.length === 0 && <li>Нет событий</li>}
				{events.map((ev, idx) => (
					<li key={idx}>
						<div style={{ fontSize: 13, color: "#333" }}>
							<b>{ev.event_type}</b> @ {ev.camera} —{" "}
							<small>{ev.timestamp || ""}</small>
						</div>
						<div style={{ fontSize: 12, color: "#666" }}>
							{ev.details ?? ""}
						</div>
					</li>
				))}
			</ul>
		</div>
	);
}
