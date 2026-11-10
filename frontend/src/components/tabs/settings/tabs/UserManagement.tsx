import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import axios from "axios";
import { Button, MenuItem, Stack, TextField } from "@mui/material";
import { api, baseURL } from "@api/axios";
import { ROLE_NAMES } from "@constants/roleNames.const";
import { useAuth } from "@context/AuthContext";
import type { IRole } from "@interfaces/role.interface";
import type { IUserAccount } from "@interfaces/user.interface";

function readError(error: unknown, fallback: string) {
	if (axios.isAxiosError(error)) {
		const detail = error.response?.data?.detail;
		if (typeof detail === "string" && detail.trim()) return detail;
	}
	return fallback;
}

export const UserManagement = () => {
	const { user: currentUser } = useAuth();
	const [users, setUsers] = useState<IUserAccount[]>([]);
	const [roles, setRoles] = useState<IRole[]>([]);
	const [loading, setLoading] = useState(true);
	const [listError, setListError] = useState("");

	const [editingUserId, setEditingUserId] = useState<number | null>(null);
	const [editLogin, setEditLogin] = useState("");
	const [editRole, setEditRole] = useState("");
	const [editPassword, setEditPassword] = useState("");
	const [editPasswordRepeat, setEditPasswordRepeat] = useState("");
	const [editError, setEditError] = useState("");
	const [saving, setSaving] = useState(false);

	const [login, setLogin] = useState("");
	const [password, setPassword] = useState("");
	const [passwordRepeat, setPasswordRepeat] = useState("");
	const [role, setRole] = useState("");
	const [addError, setAddError] = useState("");
	const [adding, setAdding] = useState(false);

	useEffect(() => {
		const controller = new AbortController();

		const load = async () => {
			const [usersRes, rolesRes] = await Promise.all([
				api.get<IUserAccount[]>(`${baseURL}/users`, {
					signal: controller.signal,
				}),
				api.get<IRole[]>(`${baseURL}/roles`, {
					signal: controller.signal,
				}),
			]);
			setUsers(usersRes.data);
			setRoles(rolesRes.data);
		};

		load()
			.catch((error) => {
				if (controller.signal.aborted) return;
				console.error(error);
				setListError(readError(error, "Не удалось загрузить пользователей"));
			})
			.finally(() => {
				if (!controller.signal.aborted) setLoading(false);
			});

		return () => controller.abort();
	}, []);

	const startEditing = (account: IUserAccount) => {
		setEditingUserId(account.id);
		setEditLogin(account.login);
		setEditRole(account.role);
		setEditPassword("");
		setEditPasswordRepeat("");
		setEditError("");
	};

	const saveUser = async (
		event: FormEvent<HTMLFormElement>,
		account: IUserAccount
	) => {
		event.preventDefault();
		const nextLogin = editLogin.trim();
		if (!nextLogin || !editRole) {
			setEditError("Укажите логин и роль.");
			return;
		}
		if (editPassword || editPasswordRepeat) {
			if (editPassword !== editPasswordRepeat) {
				setEditError("Пароли не совпадают.");
				return;
			}
		}

		setSaving(true);
		setEditError("");
		try {
			const res = await api.patch<IUserAccount>(
				`${baseURL}/users/${account.id}`,
				{
					login: nextLogin,
					role: editRole,
					...(editPassword ? { password: editPassword } : {}),
				}
			);
			setUsers((prev) =>
				prev.map((item) => (item.id === account.id ? res.data : item))
			);
			setEditingUserId(null);
		} catch (error) {
			console.error(error);
			setEditError(readError(error, "Не удалось сохранить пользователя."));
		} finally {
			setSaving(false);
		}
	};

	const removeUser = async (account: IUserAccount) => {
		setListError("");
		try {
			await api.delete(`${baseURL}/users/${account.id}`);
			setUsers((prev) => prev.filter((item) => item.id !== account.id));
			if (editingUserId === account.id) setEditingUserId(null);
		} catch (error) {
			console.error(error);
			setListError(readError(error, "Не удалось удалить пользователя."));
		}
	};

	const addUser = async (event: FormEvent<HTMLFormElement>) => {
		event.preventDefault();
		const nextLogin = login.trim();
		if (!nextLogin || !password || !role) {
			setAddError("Заполните логин, пароль и роль.");
			return;
		}
		if (password !== passwordRepeat) {
			setAddError("Пароли не совпадают.");
			return;
		}

		setAdding(true);
		setAddError("");
		try {
			const res = await api.post<IUserAccount>(`${baseURL}/users`, {
				login: nextLogin,
				password,
				role,
			});
			setUsers((prev) => [...prev, res.data]);
			setLogin("");
			setPassword("");
			setPasswordRepeat("");
		} catch (error) {
			console.error(error);
			setAddError(readError(error, "Не удалось добавить пользователя."));
		} finally {
			setAdding(false);
		}
	};

	if (loading) return <div>Загрузка пользователей...</div>;

	return (
		<>
			<h2 style={{ marginBottom: 20 }}>Список пользователей</h2>
			{listError && <div role="alert">{listError}</div>}

			{users.map((account) => {
				const isSelf = account.login === currentUser?.login;
				return (
					<div
						key={account.id}
						style={{
							border: "1px solid #ddd",
							borderRadius: 6,
							padding: 10,
							marginBottom: 10,
						}}
					>
						<strong>{account.login}</strong>
						<div style={{ fontSize: 12 }}>
							Роль: {ROLE_NAMES[account.role] || account.role}
						</div>

						{editingUserId === account.id && (
							<form
								onSubmit={(event) => saveUser(event, account)}
								style={{ display: "grid", gap: 12, marginTop: 12 }}
							>
								<TextField
									label="Логин"
									value={editLogin}
									onChange={(event) => setEditLogin(event.target.value)}
									size="small"
									fullWidth
									required
									disabled={isSelf}
									autoComplete="off"
								/>
								<TextField
									select
									label="Роль"
									value={editRole}
									onChange={(event) => setEditRole(event.target.value)}
									size="small"
									fullWidth
									required
								>
									{roles.map((item) => (
										<MenuItem key={item.name} value={item.name}>
											{ROLE_NAMES[item.name] || item.name}
										</MenuItem>
									))}
								</TextField>
								<TextField
									label="Новый пароль"
									type="password"
									value={editPassword}
									onChange={(event) => setEditPassword(event.target.value)}
									size="small"
									fullWidth
									autoComplete="new-password"
								/>
								<TextField
									label="Повторить пароль"
									type="password"
									value={editPasswordRepeat}
									onChange={(event) =>
										setEditPasswordRepeat(event.target.value)
									}
									size="small"
									fullWidth
									autoComplete="new-password"
								/>
								{editError && <div role="alert">{editError}</div>}
								<div>
									<button type="submit" disabled={saving}>
										Сохранить
									</button>
									<button
										type="button"
										disabled={saving}
										onClick={() => setEditingUserId(null)}
										style={{ marginLeft: 8 }}
									>
										Отмена
									</button>
								</div>
							</form>
						)}

						{editingUserId !== account.id && (
							<div>
								<button
									style={{ marginTop: 6 }}
									onClick={() => startEditing(account)}
								>
									Редактировать
								</button>
								<button
									style={{ marginTop: 6, marginLeft: 8 }}
									onClick={() => removeUser(account)}
								>
									Удалить
								</button>
							</div>
						)}
					</div>
				);
			})}

			<hr style={{ margin: "30px 0" }} />

			<form onSubmit={addUser} autoComplete="off">
				<Stack spacing={2} width={300}>
					<h3>Добавить пользователя</h3>
					<TextField
						label="Логин"
						value={login}
						onChange={(event) => setLogin(event.target.value)}
						autoComplete="off"
						required
					/>
					<TextField
						label="Пароль"
						type="password"
						value={password}
						onChange={(event) => setPassword(event.target.value)}
						autoComplete="new-password"
						required
					/>
					<TextField
						label="Повторить пароль"
						type="password"
						value={passwordRepeat}
						onChange={(event) => setPasswordRepeat(event.target.value)}
						autoComplete="new-password"
						required
					/>
					<TextField
						select
						label="Роль"
						value={role}
						onChange={(event) => setRole(event.target.value)}
						required
					>
						<MenuItem value="" disabled>
							Выберите роль
						</MenuItem>
						{roles.map((item) => (
							<MenuItem key={item.name} value={item.name}>
								{ROLE_NAMES[item.name] || item.name}
							</MenuItem>
						))}
					</TextField>
					{addError && <div role="alert">{addError}</div>}
					<Button type="submit" variant="contained" disabled={adding}>
						Добавить пользователя
					</Button>
				</Stack>
			</form>
		</>
	);
};
