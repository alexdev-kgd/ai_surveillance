import React, { useEffect, useState } from "react";
import { api, baseURL } from "@api/axios";
import { DETECTED_ACTION_LABELS } from "@constants/detectedActionLabels.const";
import { useDebounce } from "@hooks/useDebounce";
import type { IEvent } from "@interfaces/event.interface";
import type { ISettings } from "@interfaces/settings.interface";
import {
	Box,
	MenuItem,
	Select,
	TablePagination,
	TextField,
	type TextFieldProps,
} from "@mui/material";
import { DatePicker, LocalizationProvider } from "@mui/x-date-pickers";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import { ruRU } from "@mui/x-date-pickers/locales";
import type { Dayjs } from "dayjs";
import "dayjs/locale/ru";
import { formatDateTime } from "../../utils/formatDateTime";
import { formatDetails } from "../../utils/formatDetails";

export default function EventLogs() {
	const [events, setEvents] = useState<IEvent[]>([]);
	const [detectionActions, setDetectionActions] = useState<string[]>([]);
	const [actionLabels, setActionLabels] = useState<Record<string, string>>({});
	const [total, setTotal] = useState(0);
	const [page, setPage] = useState(0);
	const [rowsPerPage, setRowsPerPage] = useState(10);
	const [search, setSearch] = useState("");
	const [action, setAction] = useState("");
	const [dateFrom, setDateFrom] = useState<Dayjs | null>(null);
	const [dateTo, setDateTo] = useState<Dayjs | null>(null);
	const debouncedSearch = useDebounce(search);
	const suspiciousActions = detectionActions
		.filter((key) => key !== "normal" && key !== "shoot_gun")
		.map(
			(key) =>
				[key, actionLabels[key] ?? DETECTED_ACTION_LABELS[key] ?? key] as const
		);

	useEffect(() => {
		const controller = new AbortController();
		api
			.get<ISettings>(`${baseURL}/settings`, { signal: controller.signal })
			.then(({ data }) => {
				setDetectionActions(Object.keys(data.detection ?? {}));
				setActionLabels(data.actionLabels ?? {});
			})
			.catch((error) => {
				if (!controller.signal.aborted) {
					console.error("Не удалось загрузить действия детекции", error);
				}
			});
		return () => controller.abort();
	}, []);

	useEffect(() => {
		const controller = new AbortController();

		const fetchEvents = async () => {
			try {
				const res = await api.get(`${baseURL}/events/`, {
					signal: controller.signal,
					params: {
						page,
						size: rowsPerPage,
						search: debouncedSearch || undefined,
						action: action || undefined,
						date_from: dateFrom
							? dateFrom.startOf("day").toISOString()
							: undefined,
						date_to: dateTo ? dateTo.endOf("day").toISOString() : undefined,
					},
				});
				setEvents(res.data.items);
				setTotal(res.data.total);
			} catch (error) {
				if (!controller.signal.aborted) {
					console.error("Не удалось загрузить журнал событий", error);
				}
			}
		};

		fetchEvents();
		return () => controller.abort();
	}, [page, rowsPerPage, debouncedSearch, action, dateFrom, dateTo]);

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
					label="Поиск"
					value={search}
					onChange={(event) => {
						setSearch(event.target.value);
						setPage(0);
					}}
					fullWidth
					sx={{
						flex: 2,
						minWidth: 220,
					}}
				/>
				<Select
					value={action}
					onChange={(event) => {
						setAction(event.target.value);
						setPage(0);
					}}
					displayEmpty
					sx={{ flex: 1 }}
				>
					<MenuItem value="">Все подозрительные действия</MenuItem>
					{suspiciousActions.map(([value, label]) => (
						<MenuItem key={value} value={value}>
							{label}
						</MenuItem>
					))}
				</Select>
				<LocalizationProvider
					dateAdapter={AdapterDayjs}
					adapterLocale="ru"
					localeText={
						ruRU.components.MuiLocalizationProvider.defaultProps.localeText
					}
				>
					<DatePicker
						label="От"
						value={dateFrom}
						onChange={(value) => {
							setDateFrom(value);
							setPage(0);
						}}
						slotProps={{ textField: datePickerTextFieldProps }}
					/>
					<DatePicker
						label="До"
						value={dateTo}
						onChange={(value) => {
							setDateTo(value);
							setPage(0);
						}}
						slotProps={{ textField: datePickerTextFieldProps }}
					/>
				</LocalizationProvider>
			</Box>

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
						<th style={cellStyle}>Действие</th>
						<th style={cellStyle}>Камера</th>
						<th style={cellStyle}>Время</th>
						<th style={cellStyle}>Подробности</th>
					</tr>
				</thead>
				<tbody>
					{events.map((event) => (
						<tr key={event.id}>
							<td style={cellStyle}>{event.event_type}</td>
							<td style={cellStyle}>{event.camera}</td>
							<td style={cellStyle}>{formatDateTime(event.timestamp)}</td>
							<td style={{ ...cellStyle, textAlign: "left" }}>
								<pre style={detailsStyle}>{formatDetails(event.details)}</pre>
							</td>
						</tr>
					))}
				</tbody>
			</table>
			<TablePagination
				component="div"
				count={total}
				page={page}
				rowsPerPage={rowsPerPage}
				labelRowsPerPage="Строк на странице:"
				labelDisplayedRows={({ from, to, count }) =>
					`${from}–${to} из ${count !== -1 ? count : `более ${to}`}`
				}
				getItemAriaLabel={(type) => {
					if (type === "first") return "Первая страница";
					if (type === "last") return "Последняя страница";
					if (type === "next") return "Следующая страница";
					return "Предыдущая страница";
				}}
				onPageChange={(_, newPage) => setPage(newPage)}
				onRowsPerPageChange={(event) => {
					setRowsPerPage(Number(event.target.value));
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

const detailsStyle: React.CSSProperties = {
	margin: 0,
	whiteSpace: "pre-wrap",
	wordBreak: "break-word",
	fontFamily: "monospace",
	fontSize: 12,
};
