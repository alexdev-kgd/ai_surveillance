import { Box } from "@mui/material";
import type { ITabPanelProps } from "@interfaces/tabPanel.interface";

export function CustomTabPanel({ children, value, index }: ITabPanelProps) {
	return (
		<div
			role="tabpanel"
			hidden={value !== index}
			id={`tabpanel-${index}`}
			aria-labelledby={`tab-${index}`}
		>
			{value === index && <Box sx={{ p: 2 }}>{children}</Box>}
		</div>
	);
}
