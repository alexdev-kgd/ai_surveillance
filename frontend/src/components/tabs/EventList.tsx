import type { IEvent } from "@interfaces/event.interface";

interface Props {
	events?: IEvent[];
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
							<small>
								{new Date(ev.timestamp).toLocaleTimeString("ru-RU")}
							</small>
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
