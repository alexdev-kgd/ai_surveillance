export interface IAuditLog {
	id: number;
	created_at: string;
	userId: number | string | null;
	role: string | null;
	action: string;
	details: Record<string, any> | null;
}
