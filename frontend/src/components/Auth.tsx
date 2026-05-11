import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import "../Auth.css";
import { useAuth } from "@context/AuthContext";

export default function Auth() {
	const [login, setLogin] = useState("");
	const [password, setPassword] = useState("");
	const [error, setError] = useState<string | null>(null);
	const [loading, setLoading] = useState(false);

	const { signin, user, authLoading } = useAuth();
	const navigate = useNavigate();

	if (!authLoading && user) {
		return <Navigate to="/" replace />;
	}

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setError(null);

		if (!login || !password) {
			setError("Введите логин и пароль");
			return;
		}

		try {
			setLoading(true);
			await signin(login, password);
			console.log(user);
			navigate("/");
		} catch (err: any) {
			setError("Неверные данные");
		} finally {
			setLoading(false);
		}
	};

	return (
		<form onSubmit={handleSubmit} className="auth-form">
			<h2 className="auth-title">Вход</h2>

			<input
				className="auth-input"
				type="text"
				placeholder="Логин"
				value={login}
				onChange={(e) => setLogin(e.target.value)}
			/>

			<input
				className="auth-input"
				type="password"
				placeholder="Пароль"
				value={password}
				onChange={(e) => setPassword(e.target.value)}
			/>

			{error && (
				<div className="auth-error" style={{ color: "red", fontSize: 14 }}>
					{error}
				</div>
			)}

			<button className="auth-button" type="submit" disabled={loading}>
				{loading ? "Входим..." : "Войти"}
			</button>
		</form>
	);
}
