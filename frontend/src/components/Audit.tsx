import React, { useEffect, useState } from "react";
import { AUDIT_ACTION_LABELS } from "../constants/auditActionLabels.const";
import { api } from "../api/axios";
import { useDebounce } from "../hooks/useDebounce";
import {
	Box,
	MenuItem,
	Select,
	TablePagination,
	TextField,
} from "@mui/material";

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

	const [total, setTotal] = useState(0);

	const [page, setPage] = useState(0);
	const [rowsPerPage, setRowsPerPage] = useState(10);

	const [search, setSearch] = useState("");
	const [action, setAction] = useState("");
	const [role, setRole] = useState("");

	const debouncedSearch = useDebounce(search);

	useEffect(() => {
		const fetchAuditLogs = async () => {
			try {
				const res = await api.get("http://127.0.0.1:8000/audit", {
					params: {
						page,
						size: rowsPerPage,
						search: debouncedSearch || undefined,
						action: action || undefined,
						role: role || undefined,
					},
				});
				setLogs(res.data.items);
				setTotal(res.data.total);
			} catch (err) {
				console.error("Не удалось загрузить журнал аудита");
			}
		};

		fetchAuditLogs();
	}, [page, rowsPerPage, debouncedSearch, action, role]);

	return (
		<>
			<Box display="flex" gap={2} mb={2}>
				<TextField
					label="Search"
					value={search}
					onChange={(e) => setSearch(e.target.value)}
					fullWidth
				/>

				<Select
					value={action}
					onChange={(e) => setAction(e.target.value)}
					displayEmpty
				>
					<MenuItem value="">Все действия</MenuItem>

					{Object.entries(AUDIT_ACTION_LABELS).map(([value, label]) => (
						<MenuItem key={value} value={value}>
							{label}
						</MenuItem>
					))}
				</Select>

				<Select
					value={role}
					onChange={(e) => setRole(e.target.value)}
					displayEmpty
				>
					<MenuItem value="">Все роли</MenuItem>
					<MenuItem value="ADMIN">Администратор</MenuItem>
					<MenuItem value="OPERATOR">Оператор</MenuItem>
				</Select>
			</Box>

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

			<TablePagination
				component="div"
				count={total}
				page={page}
				onPageChange={(_, newPage) => setPage(newPage)}
				rowsPerPage={rowsPerPage}
				onRowsPerPageChange={(e) => {
					setRowsPerPage(+e.target.value);
					setPage(0);
				}}
			/>
		</>
	);
}

const cellStyle: React.CSSProperties = {
	border: "1px solid #ddd",
	padding: "6px 8px",
	textAlign: "center",
};
