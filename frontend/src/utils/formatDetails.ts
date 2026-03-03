/**
 * Converts event details into a readable multi-line string.
 * If `details` contains JSON text, it is pretty-printed with indentation.
 *
 * @param details Raw details string from API.
 * @returns Formatted details string or `"-"` when details are empty.
 */
export function formatDetails(details?: string): string {
	if (!details) return "-";

	try {
		const parsed = JSON.parse(details);
		return JSON.stringify(parsed, null, 2);
	} catch {
		return details;
	}
}
