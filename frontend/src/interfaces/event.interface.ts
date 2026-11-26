export interface IEvent {
	id: number;
	event_type: string;
	camera?: string;
	timestamp: Date;
	details?: string;
}
