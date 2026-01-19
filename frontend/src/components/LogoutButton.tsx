import { useAuth } from "@context/AuthContext";
import { useNavigate } from "react-router-dom";

export const LogoutButton = () => {
	const { logout } = useAuth();
	const navigate = useNavigate();

	const handleLogout = () => {
		logout();
		navigate("/auth");
	};

	return <button onClick={handleLogout}>Выйти</button>;
};
