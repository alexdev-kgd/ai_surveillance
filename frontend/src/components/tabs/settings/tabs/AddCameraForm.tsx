import { Button, TextField, Stack } from "@mui/material";
import { useState } from "react";
import { api, baseURL } from "@api/axios";
import type { ICamera } from "@interfaces/camera.interface";

interface Props {
	onAdded: (cam: ICamera) => void;
}

export default function AddCameraForm({ onAdded }: Props) {
	const [name, setName] = useState("");
	const [rtsp, setRtsp] = useState("");

	const submit = async () => {
		const res = await api.post(`${baseURL}/cameras`, {
			name,
			rtsp,
		});

		onAdded(res.data);

		setName("");
		setRtsp("");
	};

	return (
		<Stack spacing={2} width={300}>
			<h3>Добавить IP камеру</h3>

			<TextField
				label="Название камеры"
				value={name}
				onChange={(e) => setName(e.target.value)}
			/>

			<TextField
				label="RTSP URL"
				value={rtsp}
				onChange={(e) => setRtsp(e.target.value)}
				placeholder="rtsp://user:pass@ip:554/stream"
			/>

			<Button variant="contained" onClick={submit}>
				Добавить камеру
			</Button>
		</Stack>
	);
}
