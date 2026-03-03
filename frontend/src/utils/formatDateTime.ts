/**
 * Formats a date-time value as `DD/MM/YYYY HH:mm:ss`.
 *
 * @param value Date instance or ISO-like date string.
 * @returns Human-readable date and time in local timezone.
 */
export function formatDateTime(value: Date | string): string {
	const date = new Date(value);

	const day = String(date.getDate()).padStart(2, "0");
	const month = String(date.getMonth() + 1).padStart(2, "0");
	const year = date.getFullYear();

	const hours = String(date.getHours()).padStart(2, "0");
	const minutes = String(date.getMinutes()).padStart(2, "0");
	const seconds = String(date.getSeconds()).padStart(2, "0");

	return `${day}/${month}/${year} ${hours}:${minutes}:${seconds}`;
}
