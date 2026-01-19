import { useEffect, useState } from "react";
import { api, baseURL } from "@api/axios";
import { ROLE_NAMES } from "@constants/roleNames.const";
import type { IRole } from "@interfaces/role.interface";
import { PERMISSION_NAMES } from "@constants/permissionNames.const";

export const PermissionsSettings = () => {
	const [roles, setRoles] = useState<IRole[]>([]);
	const [allPermissions, setAllPermissions] = useState<string[]>([]);
	const [saving, setSaving] = useState(false);
	const [loading, setLoading] = useState(true);
	const [message, setMessage] = useState("");

	useEffect(() => {
		const load = async () => {
			const [rolesRes, permsRes] = await Promise.all([
				api.get(`${baseURL}/roles`),
				api.get(`${baseURL}/permissions`),
			]);

			setRoles(rolesRes.data);
			setAllPermissions(permsRes.data);
		};

		load()
			.catch(console.error)
			.finally(() => setLoading(false));
	}, []);

	const togglePermission = (roleName: string, permission: string) => {
		setRoles((prev) =>
			prev.map((role) =>
				role.name !== roleName
					? role
					: {
							...role,
							permissions: role.permissions.includes(permission)
								? role.permissions.filter((p) => p !== permission)
								: [...role.permissions, permission],
					  }
			)
		);
	};

	const saveAllRoles = async () => {
		setSaving(true);
		try {
			await Promise.all(
				roles.map((role) =>
					api.put(`${baseURL}/roles/${role.name}/permissions`, {
						permissions: role.permissions,
					})
				)
			);
			setMessage("Настройки сохранены!");
		} catch (err) {
			console.error(err);
			setMessage("Ошибка при сохранении ролей");
		} finally {
			setSaving(false);
		}
	};

	if (loading) return <div>Загрузка настроек...</div>;

	return (
		<div style={{ padding: 20, maxWidth: 600 }}>
			<h2 style={{ marginBottom: 20 }}>
				Управление разрешениями пользователей
			</h2>

			{roles.map((role) => (
				<div
					key={role.name}
					style={{
						border: "1px solid #ddd",
						borderRadius: 6,
						padding: 12,
						marginBottom: 16,
					}}
				>
					<strong>{ROLE_NAMES[role.name] || role.name}</strong>

					{allPermissions.map((perm) => (
						<label key={perm} style={{ display: "block" }}>
							<input
								type="checkbox"
								checked={role.permissions.includes(perm)}
								onChange={() => togglePermission(role.name, perm)}
							/>{" "}
							{PERMISSION_NAMES[perm] || perm}
						</label>
					))}
				</div>
			))}

			<button
				onClick={saveAllRoles}
				disabled={saving}
				style={{
					padding: "8px 16px",
					backgroundColor: "#007bff",
					color: "white",
					border: "none",
					borderRadius: 4,
					cursor: "pointer",
				}}
			>
				{saving ? "Сохраняем..." : "Сохранить"}
			</button>

			{message && <div style={{ marginTop: 10 }}>{message}</div>}
		</div>
	);
};
