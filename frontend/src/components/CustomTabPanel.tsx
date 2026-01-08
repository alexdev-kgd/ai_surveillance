import React from "react";
import { Box } from "@mui/material";

interface TabPanelProps {
	children?: React.ReactNode;
	index: number;
	value: number;
}

export function CustomTabPanel({ children, value, index }: TabPanelProps) {
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
