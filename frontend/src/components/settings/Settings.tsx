import { useState } from "react";
import { Tabs, Tab } from "@mui/material";
import HubIcon from "@mui/icons-material/Hub";
import PersonIcon from "@mui/icons-material/Person";
import { DetectionSettings } from "./tabs/DetectionSettings";
import { PermissionsSettings } from "./tabs/PermissionsSettings";
import { CustomTabPanel } from "../CustomTabPanel";

export const Settings = () => {
	const [tabValue, setTabValue] = useState(0);

	const handleChange = (_event: React.SyntheticEvent, newValue: number) => {
		setTabValue(newValue);
	};

	return (
		<>
			<Tabs
				value={tabValue}
				onChange={handleChange}
				aria-label="settings tabs"
				centered
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
					label="Управление разрешениями"
					id="tab-1"
				/>
			</Tabs>

			<CustomTabPanel value={tabValue} index={0}>
				<DetectionSettings></DetectionSettings>
			</CustomTabPanel>
			<CustomTabPanel value={tabValue} index={1}>
				<PermissionsSettings></PermissionsSettings>
			</CustomTabPanel>
		</>
	);
};
