import React, { useEffect, useState } from "react";
import { AUDIT_ACTION_LABELS } from "../constants/auditActionLabels.const";
import { api } from "../api/axios";

interface AuditLog {
	id: number;
	created_at: string;
	email: string;
	role: string;
	action: string;
	details: Record<string, any> | null;
}

export default function Audit() {
	const [logs, setLogs] = useState<AuditLog[]>([]);

	useEffect(() => {
		const fetchAuditLogs = async () => {
			try {
				const res = await api.get("http://127.0.0.1:8000/audit");
				setLogs(res.data);
			} catch (err) {
				console.error("Не удалось загрузить журнал аудита");
			}
		};

		fetchAuditLogs();
	}, []);

	return (
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
					<th style={cellStyle}>Время</th>
					<th style={cellStyle}>Пользователь</th>
					<th style={cellStyle}>Роль</th>
					<th style={cellStyle}>Действие</th>
					<th style={cellStyle}>Подробности</th>
				</tr>
			</thead>
			<tbody>
				{logs.map((log) => (
					<tr key={log.id}>
						<td style={cellStyle}>
							{new Date(log.created_at).toLocaleString()}
						</td>
						<td style={cellStyle}>{log.email}</td>
						<td style={cellStyle}>{log.role}</td>
						<td style={cellStyle}>
							{AUDIT_ACTION_LABELS[log.action] ?? log.action}
						</td>
						<td style={cellStyle}>{log.details?.message}</td>
					</tr>
				))}
			</tbody>
		</table>
	);
}

const cellStyle: React.CSSProperties = {
	border: "1px solid #ddd",
	padding: "6px 8px",
	textAlign: "center",
};
