import React, { useEffect, useState } from "react";
import { AUDIT_ACTION_LABELS } from "@constants/auditActionLabels.const";
import { api, baseURL } from "@api/axios";
import { useDebounce } from "@hooks/useDebounce";
import {
	Box,
	MenuItem,
	Select,
	TablePagination,
	TextField,
	type TextFieldProps,
} from "@mui/material";
import { ROLE_NAMES } from "../../constants/roleNames.const";
import { Dayjs } from "dayjs";
import { DatePicker } from "@mui/x-date-pickers";
import type { IAuditLog } from "../../interfaces/auditLog.interface";

export default function Audit() {
	const [logs, setLogs] = useState<IAuditLog[]>([]);

	const [total, setTotal] = useState(0);

	const [page, setPage] = useState(0);
	const [rowsPerPage, setRowsPerPage] = useState(10);

	const [search, setSearch] = useState("");
	const [action, setAction] = useState("");
	const [role, setRole] = useState("");

	const [dateFrom, setDateFrom] = useState<Dayjs | null>(null);
	const [dateTo, setDateTo] = useState<Dayjs | null>(null);

	const debouncedSearch = useDebounce(search);

	useEffect(() => {
		const controller = new AbortController();

		const fetchAuditLogs = async () => {
			try {
				const res = await api.get(`${baseURL}/audit`, {
					signal: controller.signal,
					params: {
						page,
						size: rowsPerPage,
						search: debouncedSearch || undefined,
						action: action || undefined,
						role: role || undefined,
						date_from: dateFrom
							? dateFrom.startOf("day").toISOString()
							: undefined,
						date_to: dateTo ? dateTo.endOf("day").toISOString() : undefined,
					},
				});
				setLogs(res.data.items);
				setTotal(res.data.total);
			} catch (err) {
				console.error("Не удалось загрузить журнал аудита");
			}
		};

		fetchAuditLogs();

		return () => controller.abort();
	}, [page, rowsPerPage, debouncedSearch, action, role, dateFrom, dateTo]);

	const datePickerTextFieldProps: TextFieldProps = {
		size: "small",
		sx: {
			flex: 1,
			flexDirection: "row",
		},
		InputLabelProps: {
			sx: {
				transform: "translate(14px, 16px) scale(1)",
				"&.MuiFormLabel-filled": {
					transform: "translate(15px, -8px) scale(0.75)",
				},
				"&.Mui-focused": {
					transform: "translate(15px, -8px) scale(0.75)",
				},
			},
		},
	};

	return (
		<>
			<Box display="flex" gap={2} mb={2} alignItems="stretch">
				<TextField
					label="Search"
					value={search}
					onChange={(e) => setSearch(e.target.value)}
					fullWidth
					sx={{
						flex: 2,
						minWidth: 220,
					}}
				/>

				<Select
					value={action}
					onChange={(e) => setAction(e.target.value)}
					displayEmpty
					sx={{
						flex: 1,
					}}
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
					sx={{
						flex: 1,
					}}
				>
					<MenuItem value="">Все роли</MenuItem>

					{Object.entries(ROLE_NAMES).map(([value, name]) => (
						<MenuItem key={value} value={value}>
							{name}
						</MenuItem>
					))}
				</Select>

				<DatePicker
					label="От"
					value={dateFrom}
					onChange={(newValue) => setDateFrom(newValue)}
					slotProps={{ textField: datePickerTextFieldProps }}
				/>

				<DatePicker
					label="До"
					value={dateTo}
					onChange={(newValue) => setDateTo(newValue)}
					slotProps={{ textField: datePickerTextFieldProps }}
				/>
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
							<td style={cellStyle}>{ROLE_NAMES[log.role] ?? log.role}</td>
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
