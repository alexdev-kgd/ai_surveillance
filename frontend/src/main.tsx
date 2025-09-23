import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.tsx";
import { ThemeProvider, createTheme } from "@mui/material/styles";

// создаём тему
const theme = createTheme({
	components: {
		MuiTab: {
			styleOverrides: {
				root: {
					"&:focus": {
						outline: "none", // убираем чёрный border при клике
					},
				},
			},
		},
	},
});

createRoot(document.getElementById("root")!).render(
	<StrictMode>
		<ThemeProvider theme={theme}>
			<App />
		</ThemeProvider>
	</StrictMode>
);
