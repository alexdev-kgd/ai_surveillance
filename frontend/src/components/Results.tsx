import React from "react";

interface Props {
	result: any;
}

interface Detection {
	id: number;
	frame: number;
	label: string;
	confidence: number;
	bbox: number[];
}

export default function Results({ result }: Props) {
	if (!result) return null;

	const suspicious = result.detections.filter(
		(detection: Detection) => detection.label !== "normal"
	);

	console.log(suspicious);

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
					{suspicious.map((detection: Detection, idx: number) => {
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
