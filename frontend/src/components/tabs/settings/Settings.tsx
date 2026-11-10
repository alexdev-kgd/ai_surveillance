import { useState } from "react";
import { Tabs, Tab } from "@mui/material";
import HubIcon from "@mui/icons-material/Hub";
import PersonIcon from "@mui/icons-material/Person";
import VideocamIcon from "@mui/icons-material/Videocam";
import BackupIcon from "@mui/icons-material/Backup";
import FiberManualRecordIcon from "@mui/icons-material/FiberManualRecord";
import { DetectionSettings } from "./tabs/DetectionSettings";
import { PermissionsSettings } from "./tabs/PermissionsSettings";
import { CustomTabPanel } from "@components/CustomTabPanel";
import { CameraSettings } from "./tabs/CameraSettings";
import { BackupSettings } from "./tabs/BackupSettings";
import { RecordingSettings } from "./tabs/RecordingSettings";

export const Settings = () => {
	const [tabValue, setTabValue] = useState(0);

	const handleChange = (_event: React.SyntheticEvent, newValue: number) => {
		setTabValue(newValue);
	};

	return (
		<>
			<Tabs
				className="app-tabs"
				value={tabValue}
				onChange={handleChange}
				aria-label="settings tabs"
				variant="scrollable"
				scrollButtons="auto"
			>
				<Tab
					icon={<HubIcon />}
					iconPosition="start"
					label="ИИ Модель"
					id="tab-0"
				/>
				<Tab
					icon={<PersonIcon />}
					iconPosition="start"
					label="Управление пользователями"
					id="tab-1"
				/>
				<Tab
					icon={<VideocamIcon />}
					iconPosition="start"
					label="Управление камерами"
					id="tab-2"
				/>
				<Tab icon={<BackupIcon />} iconPosition="start" label="Резервное копирование" id="tab-3" />
				<Tab icon={<FiberManualRecordIcon />} iconPosition="start" label="Видеозапись" id="tab-4" />
			</Tabs>

			<CustomTabPanel value={tabValue} index={0}>
				<DetectionSettings></DetectionSettings>
			</CustomTabPanel>
			<CustomTabPanel value={tabValue} index={1}>
				<PermissionsSettings></PermissionsSettings>
			</CustomTabPanel>
			<CustomTabPanel value={tabValue} index={2}>
				<CameraSettings></CameraSettings>
			</CustomTabPanel>
			<CustomTabPanel value={tabValue} index={3}>
				<BackupSettings />
			</CustomTabPanel>
			<CustomTabPanel value={tabValue} index={4}>
				<RecordingSettings />
			</CustomTabPanel>
		</>
	);
};
