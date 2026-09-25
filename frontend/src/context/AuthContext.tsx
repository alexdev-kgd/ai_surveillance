import { createContext, useContext, useEffect, useState } from "react";
import { auth, fetchCurrentUser } from "../services/auth.service";
import { api } from "../api/axios";

type User = {
	login: string;
	role: string;
	permissions: string[];
};

type AuthContextType = {
	user: User | null;
	authLoading: boolean;
	signin: (login: string, password: string) => Promise<void>;
	logout: () => void;
};

const AuthContext = createContext<AuthContextType>({
	user: null,
	authLoading: false,
	signin: async () => {},
	logout: () => {},
});

export const AuthProvider = ({ children }: any) => {
	const [user, setUser] = useState<User | null>(null);
	const [authLoading, setAuthLoading] = useState<boolean>(true);

	const signin = async (login: string, password: string) => {
		setAuthLoading(true);
		try {
			await auth(login, password);
			const userData = await fetchCurrentUser();
			setUser(userData);
		} finally {
			setAuthLoading(false);
		}
	};

	const logout = async () => {
		try {
			await api.post("/auth/logout");
		} catch {
		} finally {
			localStorage.removeItem("token");
			setUser(null);
		}
	};

	useEffect(() => {
		const controller = new AbortController();

		fetchCurrentUser(controller.signal)
			.then(setUser)
			.catch((e) => {
				console.error(e);
			})
			.finally(() => setAuthLoading(false));

		return () => controller.abort();
	}, []);

	return (
		<AuthContext.Provider value={{ user, authLoading, signin, logout }}>
			{children}
		</AuthContext.Provider>
	);
};

export const useAuth = () => useContext(AuthContext);
