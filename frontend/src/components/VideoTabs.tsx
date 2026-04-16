import React, { useState } from "react";
import { Tabs, Tab, Box } from "@mui/material";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import VideocamIcon from "@mui/icons-material/Videocam";
import FormatListBulletedIcon from "@mui/icons-material/FormatListBulleted";
import SettingsIcon from "@mui/icons-material/Settings";
import ViewListIcon from "@mui/icons-material/ViewList";

import UploadForm from "./tabs/UploadForm";
import Results from "./tabs/Results";
import EventList from "./tabs/EventList";
import EventLogs from "./tabs/EventLogs";
import { useAuth } from "@context/AuthContext";
import { Settings } from "./tabs/settings/Settings";
import { CustomTabPanel } from "./CustomTabPanel";
import Audit from "./tabs/Audit";
import type { IEvent } from "@interfaces/event.interface";
import MultiCameraView from "./tabs/liveCameras/MultiCameraView";
import type { ILiveDetectionEvent } from "@interfaces/liveDetectionEvent.interface";

interface Props {
	setResult: React.Dispatch<React.SetStateAction<any>>;
	result: any;
	events: IEvent[];
}

export default function VideoTabs({ setResult, result, events }: Props) {
	const [value, setValue] = useState(0);
	const [loading, setLoading] = useState(false);
	const [liveSuspiciousEvents, setLiveSuspiciousEvents] = useState<
		ILiveDetectionEvent[]
	>([]);

	const { user } = useAuth();

	const canAccessSettings = user?.permissions.includes("system:configure");
	const canAccessAuditLogs = user?.permissions.includes("audit:read");

	const handleChange = (_event: React.SyntheticEvent, newValue: number) => {
		setValue(newValue);
	};

	const handleSuspiciousDetection = (event: ILiveDetectionEvent) => {
		setLiveSuspiciousEvents((prev) => [event, ...prev].slice(0, 50));
	};

	return (
		<Box sx={{ width: "100%" }}>
			<Box sx={{ borderBottom: 1, borderColor: "divider" }}>
				<Tabs
					value={value}
					onChange={handleChange}
					aria-label="video tabs"
					centered
				>
					<Tab
						icon={<CloudUploadIcon />}
						iconPosition="start"
						label="Загрузка видео"
						id="tab-0"
					/>
					<Tab
						icon={<VideocamIcon />}
						iconPosition="start"
						label="Камеры"
						id="tab-1"
					/>
					<Tab
						icon={<FormatListBulletedIcon />}
						iconPosition="start"
						label="Журнал событий"
						id="tab-2"
					/>
					{canAccessSettings && (
						<Tab
							icon={<SettingsIcon />}
							iconPosition="start"
							label="Настройки"
							id="tab-3"
						/>
					)}
					{canAccessAuditLogs && (
						<Tab
							icon={<ViewListIcon />}
							iconPosition="start"
							label="Аудит"
							id="tab-4"
						/>
					)}
				</Tabs>
			</Box>

			<CustomTabPanel value={value} index={0}>
				<UploadForm
					setResult={setResult}
					setLoading={setLoading}
					loading={loading}
				/>
				{!loading && <Results result={result} />}
			</CustomTabPanel>
			<CustomTabPanel value={value} index={1}>
				<div>
					<div style={{ flex: 1 }}>
						{/* <LiveStream /> */}
						<MultiCameraView
							onSuspiciousDetection={handleSuspiciousDetection}
						/>
					</div>
					<div>
						<EventList events={events} liveEvents={liveSuspiciousEvents} />
					</div>
				</div>
			</CustomTabPanel>
			<CustomTabPanel value={value} index={2}>
				<EventLogs />
			</CustomTabPanel>
			{canAccessSettings && (
				<CustomTabPanel value={value} index={3}>
					<Settings />
				</CustomTabPanel>
			)}
			{canAccessAuditLogs && (
				<CustomTabPanel value={value} index={4}>
					<Audit></Audit>
				</CustomTabPanel>
			)}
		</Box>
	);
}
