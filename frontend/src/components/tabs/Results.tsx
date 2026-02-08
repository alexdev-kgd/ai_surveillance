import React from "react";
import type { IDetection } from "@interfaces/detection.interface";
import { DETECTED_ACTION_LABELS } from "@constants/detectedActionLabels.const";

interface Props {
	result: any;
}

export default function Results({ result }: Props) {
	if (!result) return null;

	const suspicious = result.detections.filter(
		(detection: IDetection) =>
			detection.label !== DETECTED_ACTION_LABELS["normal"]
	);

	if (suspicious.length === 0)
		return (
			<p style={{ marginTop: 16 }}>Подозрительных действий не обнаружено.</p>
		);

	return (
		<div style={{ marginTop: 12 }}>
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
						<th style={cellStyle}>Кадр</th>
						<th style={cellStyle}>Действие</th>
						<th style={cellStyle}>Время</th>
					</tr>
				</thead>
				<tbody>
					{suspicious.map((detection: IDetection, idx: number) => {
						const timeSec = (detection.frame / result.fps).toFixed(2);
						return (
							<tr key={idx}>
								<td style={cellStyle}>{detection.frame}</td>
								<td style={cellStyle}>{detection.label}</td>
								<td style={cellStyle}>{timeSec}s</td>
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
