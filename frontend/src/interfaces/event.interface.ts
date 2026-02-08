export interface IEvent {
	event_type: string;
	camera?: string;
	timestamp: Date;
	details?: string;
}
