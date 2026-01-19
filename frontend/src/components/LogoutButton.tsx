import { useNavigate } from "react-router-dom";
import { useAuth } from "@context/AuthContext";

export const LogoutButton = () => {
	const { logout } = useAuth();
	const navigate = useNavigate();

	const handleLogout = () => {
		logout();
		navigate("/auth");
	};

	return <button onClick={handleLogout}>Logout</button>;
};
