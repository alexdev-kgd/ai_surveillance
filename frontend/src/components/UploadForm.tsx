import React, { useState } from "react";
import axios from "axios";

interface Props {
	setResult: React.Dispatch<React.SetStateAction<any>>;
}

export default function UploadForm({ setResult }: Props) {
	const [file, setFile] = useState<File | null>(null);
	const [loading, setLoading] = useState(false);
	const [videoUrl, setVideoUrl] = useState<string | null>(null);

	const submit = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!file) return;

		const fd = new FormData();
		fd.append("file", file);
		setLoading(true);

		try {
			const res = await axios.post("http://127.0.0.1:8000/analyze/video/", fd, {
				headers: { "Content-Type": "multipart/form-data" },
			});
			setResult(res.data);
			setVideoUrl("http://127.0.0.1:8000" + res.data.video_path);
		} catch (err) {
			alert("Ошибка анализа видео");
			console.error(err);
		}

		setLoading(false);
	};

	return (
		<>
			<form onSubmit={submit}>
				<div style={{ display: "flex", gap: 8, alignItems: "center" }}>
					<input
						type="file"
						accept="video/*"
						onChange={(e) => setFile(e.target.files?.[0] ?? null)}
					/>
					<button type="submit" disabled={loading}>
						{loading ? "Обработка..." : "Загрузить и проанализировать"}
					</button>
				</div>
			</form>

			{videoUrl && (
				<video
					src={videoUrl}
					controls
					style={{ marginTop: 16, maxWidth: "100%", borderRadius: 8 }}
				/>
			)}
		</>
	);
}
