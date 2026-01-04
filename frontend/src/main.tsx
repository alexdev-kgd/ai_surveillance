import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.tsx";
import { ThemeProvider, createTheme } from "@mui/material/styles";
import { AuthProvider } from "./context/AuthContext.tsx";

const theme = createTheme({
	components: {
		MuiTab: {
			styleOverrides: {
				root: {
					"&:focus": {
						outline: "none",
					},
				},
			},
		},
	},
});

createRoot(document.getElementById("root")!).render(
	<StrictMode>
		<AuthProvider>
			<ThemeProvider theme={theme}>
				<App />
			</ThemeProvider>
		</AuthProvider>
	</StrictMode>
);
