import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import tsconfigPaths from "vite-tsconfig-paths";

// https://vite.dev/config/
export default defineConfig({
	plugins: [react(), tsconfigPaths()],
	optimizeDeps: {
		include: [
			"@emotion/react",
			"@emotion/styled",
			"@mui/material",
			"@mui/x-date-pickers",
		],
	},
	resolve: {
		alias: {
			"@api": new URL("./src/api", import.meta.url).pathname,
			"@interfaces": new URL("./src/interfaces", import.meta.url).pathname,
			"@constants": new URL("./src/constants", import.meta.url).pathname,
			"@services": new URL("./src/services", import.meta.url).pathname,
			"@hooks": new URL("./src/hooks", import.meta.url).pathname,
			"@context": new URL("./src/context", import.meta.url).pathname,
		},
	},
});
