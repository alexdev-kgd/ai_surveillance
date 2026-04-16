export interface IAuditLog {
	id: number;
	created_at: string;
	userId: string;
	role: string;
	action: string;
	details: Record<string, any> | null;
}
