export interface IAuditLog {
	id: number;
	created_at: string;
	email: string;
	role: string;
	action: string;
	details: Record<string, any> | null;
}
