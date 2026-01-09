import { createContext, useContext, useEffect, useState } from "react";
import { fetchCurrentUser } from "../services/auth.service";
import { useLocation } from "react-router-dom";
import { api } from "../api/axios";

type User = {
	email: string;
	role: string;
	permissions: string[];
};

type AuthContextType = {
	user: User | null;
	authLoading: boolean;
	logout: () => void;
};

const AuthContext = createContext<AuthContextType>({
	user: null,
	authLoading: false,
	logout: () => {},
});

export const AuthProvider = ({ children }: any) => {
	const [user, setUser] = useState<User | null>(null);
	const [authLoading, setAuthLoading] = useState<boolean>(true);

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
		fetchCurrentUser()
			.then(setUser)
			.catch((e) => {
				console.error(e);
			})
			.finally(() => setAuthLoading(false));
	}, []);

	return (
		<AuthContext.Provider value={{ user, authLoading, logout }}>
			{children}
		</AuthContext.Provider>
	);
};

export const useAuth = () => useContext(AuthContext);
