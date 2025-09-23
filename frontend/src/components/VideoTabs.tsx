import React, { useState } from "react";
import { Tabs, Tab, Box } from "@mui/material";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import VideocamIcon from "@mui/icons-material/Videocam";

import UploadForm from "./UploadForm";
import Results from "./Results";
import LiveStream from "./LiveStream";
import EventList from "./EventList";

interface TabPanelProps {
	children?: React.ReactNode;
	index: number;
	value: number;
}

function CustomTabPanel({ children, value, index }: TabPanelProps) {
	return (
		<div role="tabpanel" hidden={value !== index} id={`tabpanel-${index}`} aria-labelledby={`tab-${index}`}>
			{value === index && <Box sx={{ p: 2 }}>{children}</Box>}
		</div>
	);
}

interface Props {
	setResult: React.Dispatch<React.SetStateAction<any>>;
	result: any;
	events: Array<{ event_type: string; camera: string; timestamp?: string; details?: string }>;
}

export default function VideoTabs({ setResult, result, events }: Props) {
	const [value, setValue] = useState(0);

	const handleChange = (event: React.SyntheticEvent, newValue: number) => {
		setValue(newValue);
	};

	return (
		<Box sx={{ width: "100%" }}>
			<Box sx={{ borderBottom: 1, borderColor: "divider" }}>
				<Tabs value={value} onChange={handleChange} aria-label="video tabs" centered>
					<Tab icon={<CloudUploadIcon />} iconPosition="start" label="Загрузка видео" id="tab-0" />
					<Tab icon={<VideocamIcon />} iconPosition="start" label="Веб-камера" id="tab-1" />
				</Tabs>
			</Box>

			<CustomTabPanel value={value} index={0}>
				<UploadForm setResult={setResult} />
				<Results result={result} />
			</CustomTabPanel>
			<CustomTabPanel value={value} index={1}>
				<div style={{ flex: 1 }}>
					<LiveStream />
				</div>
				<div style={{ width: 320 }}>
					<EventList events={events} />
				</div>
			</CustomTabPanel>
		</Box>
	);
}
