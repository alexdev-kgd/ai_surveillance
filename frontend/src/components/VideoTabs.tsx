import React, { useState } from "react";
import { Tabs, Tab, Box } from "@mui/material";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import VideocamIcon from "@mui/icons-material/Videocam";
import FormatListBulletedIcon from "@mui/icons-material/FormatListBulleted";
import SettingsIcon from "@mui/icons-material/Settings";

import UploadForm from "./UploadForm";
import Results from "./Results";
import LiveStream from "./LiveStream";
import EventList from "./EventList";
import EventLogs from "./EventLogs";
import { useAuth } from "../context/AuthContext";
import { Settings } from "./settings/Settings";
import { CustomTabPanel } from "./CustomTabPanel";

interface Props {
	setResult: React.Dispatch<React.SetStateAction<any>>;
	result: any;
	events: Array<{
		event_type: string;
		camera: string;
		timestamp?: string;
		details?: string;
	}>;
}

export default function VideoTabs({ setResult, result, events }: Props) {
	const [value, setValue] = useState(0);
	const [loading, setLoading] = useState(false);

	const { user } = useAuth();

	const canAccessSettings = user?.permissions.includes("system:configure");

	const handleChange = (_event: React.SyntheticEvent, newValue: number) => {
		setValue(newValue);
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
						label="Веб-камера"
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
				<div style={{ flex: 1 }}>
					<LiveStream />
				</div>
				<div style={{ width: 320 }}>
					<EventList events={events} />
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
		</Box>
	);
}
