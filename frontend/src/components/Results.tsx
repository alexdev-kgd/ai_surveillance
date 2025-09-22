import React from "react";

interface Props {
	result: any;
}

export default function Results({ result }: Props) {
	if (!result) return null;
	return (
		<div style={{ marginTop: 12 }}>
			<h3>Результат</h3>
			<pre style={{ whiteSpace: "pre-wrap" }}>
				{JSON.stringify(result, null, 2)}
			</pre>
		</div>
	);
}
