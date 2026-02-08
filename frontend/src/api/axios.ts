import axios from "axios";

export const baseURL = "http://localhost:8000";

export const api = axios.create({
	baseURL: baseURL,
});

export const authApi = axios.create({
	baseURL: baseURL,
});

api.interceptors.request.use((config) => {
	const token = localStorage.getItem("token");
	if (token) config.headers.Authorization = `Bearer ${token}`;

	return config;
});

api.interceptors.response.use(
	(res) => res,
	(error) => {
		if (error.response?.status === 401) {
			localStorage.removeItem("token");
		}

		return Promise.reject(error);
	}
);
