import { api, authApi } from "../api/axios";

export const hasToken = (): boolean => {
	return !!localStorage.getItem("token");
};

export const auth = async (email: string, password: string) => {
	try {
		const res = await authApi.post("/auth/login", { email, password });
		localStorage.setItem("token", res.data.access_token);
	} catch (err: any) {
		throw err;
	}
};

export async function fetchCurrentUser() {
	try {
		const res = await api.get("/auth/me");
		return res.data;
	} catch (err: any) {
		if (err.response && err.response.status === 401) {
			throw new Error("Unauthorized");
		}

		throw err;
	}
}
