import React from "react";

export default function LiveStream() {
	return (
		<div>
			<h3>Прямой поток (MJPEG)</h3>
			<img
				className="stream"
				src="http://127.0.0.1:8000/video_feed"
				alt="live"
			/>
		</div>
	);
}
