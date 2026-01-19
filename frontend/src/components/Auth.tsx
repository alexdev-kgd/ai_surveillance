import { useState } from "react";
import { auth, hasToken } from "@services/auth.service";
import { Navigate, useNavigate } from "react-router-dom";
import "../Auth.css";

export default function Auth() {
	const [email, setEmail] = useState("");
	const [password, setPassword] = useState("");
	const [error, setError] = useState<string | null>(null);
	const [loading, setLoading] = useState(false);

	const navigate = useNavigate();

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setError(null);

		if (!email || !password) {
			setError("Введите email и пароль");
			return;
		}

		try {
			setLoading(true);
			await auth(email, password);
			navigate("/");
		} catch (err: any) {
			setError("Неверные данные");
		} finally {
			setLoading(false);
		}
	};

	if (hasToken()) return <Navigate to="/" replace />;

	return (
		<form onSubmit={handleSubmit} className="auth-form">
			<h2 className="auth-title">Вход</h2>

			<input
				className="auth-input"
				type="email"
				placeholder="Email"
				value={email}
				onChange={(e) => setEmail(e.target.value)}
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
