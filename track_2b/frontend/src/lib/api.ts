// The only place the UI talks to anything. All URLs are relative: nothing leaves this machine.

export type Light = 'green' | 'amber' | 'red' | 'unmeasured';

export interface Language {
	code: string;
	native: string;
	english: string;
	dir: 'ltr' | 'rtl';
	script: string;
	light: Light;
	median_chrf: number | null;
	native_checked: boolean;
	strings: Record<string, string>;
}

export interface Health {
	mode: 'replay' | 'live';
	model: string;
	endpoint_host: string | null;
	offline: boolean;
	canton: string;
	replay: { backend: string; note: string } | null;
	demo: { available: boolean; letters?: number; as_of?: string; canton?: string; languages?: string[] };
}

export interface Evidence {
	id: string;
	text: string;
	page: number;
	bbox: [number, number, number, number] | null;
}

export interface Sentence {
	text: string;
	support: string[];
}

export interface Explanation {
	language: string;
	what_this_is: Sentence[];
	what_they_want: Sentence[];
	deadline: Sentence[];
	what_you_can_do: Sentence[];
	who_to_contact: Sentence[];
	low_confidence: boolean;
	backtranslation_chrf: number | null;
	failed_field_checks: string[];
}

export interface Deadline {
	due_date: string | null;
	days_left: number | null;
	needs_delivery_date: boolean;
	rule_family: string;
	trace: string[];
	verified_rule: boolean;
}

export interface RedFlag {
	code: string;
	severity: 'warn' | 'high';
	evidence: string;
	span_ids: string[];
	source_url: string | null;
}

export interface Letter {
	id: string;
	label: string | null;
	status: 'queued' | 'processing' | 'done' | 'failed' | 'skipped';
	stage: string | null;
	error: string | null;
	delivery_date: string | null;
	page_ids: string[];
	pages: { id: string; width: number; height: number; url: string }[];
	facts: {
		letter_type: string;
		source_language: string;
		sender_name: string | null;
		sender_contact: string | null;
		creditor_name: string | null;
		recipient_name: string | null;
		letter_date: string | null;
		reference_numbers: string[];
		iban: string | null;
		stated_options: string[];
		evidence: Record<string, string[]>;
		evidence_items: Evidence[];
	} | null;
	verification: {
		deadline: Deadline | null;
		iban_valid: boolean | null;
		iban_country: string | null;
		authority_id: string | null;
		authority_contact: {
			name: string;
			phone: string | null;
			email: string | null;
			web: string | null;
			address: string | null;
			source_url: string | null;
			sourced: boolean;
		} | null;
		red_flags: RedFlag[];
		field_checks: Record<string, 'match' | 'mismatch' | 'ocr_missing'>;
		orchestrator_forced_tools: string[];
	} | null;
	explanation: Explanation | null;
	explanation_de: Explanation | null;
	priority_reason: string | null;
	type_label?: string;
	type_label_de?: string;
	amount_display?: string;
	due_display?: string;
	letter_date_display?: string;
	due_display_client?: string;
	reply_templates?: { id: string; title: string; unsourced: string[] }[];
}

export interface Thread {
	id: string;
	letter_ids: string[];
	reason: string;
	confirmed: boolean;
	origin: string;
	rejected: boolean;
}

export interface Reply {
	id: string;
	letter_id: string;
	template_id: string;
	language: string;
	slots: Record<string, string>;
	slot_sources: Record<string, string[]>;
	needs_review: string[];
	rendered_text: string;
	missing: string[];
}

export interface Case {
	id: string;
	status: 'capturing' | 'processing' | 'ready' | 'closed';
	client_language: string;
	canton: string;
	demo: boolean;
	today: string;
	today_display: string;
	letters: Letter[];
	threads: Thread[];
	order: string[];
	replies: Reply[];
	unassigned_pages: { id: string; url: string; filename: string }[];
	creditor_totals: { creditor: string; display: string; letter_ids: string[] }[];
	language: { code: string; native: string; english: string; dir: 'ltr' | 'rtl' };
	strings: Record<string, string>;
	strings_de: Record<string, string>;
	model_misses: number;
}

export class ApiError extends Error {
	constructor(
		public status: number,
		message: string
	) {
		super(message);
	}
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
	let response: Response;
	try {
		response = await fetch(`/api${path}`, init);
	} catch {
		throw new ApiError(0, 'Briefklar is not reachable on this device. Check that it is still running.');
	}
	if (!response.ok) {
		let message = 'Something went wrong. Try again.';
		try {
			const body = await response.json();
			if (typeof body.detail === 'string') message = body.detail;
		} catch {
			/* keep the default */
		}
		throw new ApiError(response.status, message);
	}
	return response.json();
}

const json = (method: string, body: unknown): RequestInit => ({
	method,
	headers: { 'Content-Type': 'application/json' },
	body: JSON.stringify(body)
});

export const api = {
	health: () => request<Health>('/health'),
	languages: () => request<{ languages: Language[]; generated_by: string }>('/languages'),
	cases: () => request<{ id: string; status: string; client_language: string; letters: number; demo: boolean }[]>('/cases'),
	createCase: (client_language: string, canton: string) =>
		request<{ case_id: string }>('/cases', json('POST', { client_language, canton })),
	createDemo: (client_language: string) => request<{ case_id: string }>('/demo', json('POST', { client_language })),
	getCase: (id: string) => request<Case>(`/cases/${id}`),
	upload: (id: string, files: File[]) => {
		const form = new FormData();
		for (const file of files) form.append('files', file);
		return request<{ errors: { filename: string; message: string }[]; case: Case }>(`/cases/${id}/pages`, {
			method: 'POST',
			body: form
		});
	},
	deletePage: (id: string, pageId: string) => request<Case>(`/cases/${id}/pages/${pageId}`, { method: 'DELETE' }),
	group: (id: string, page_ids: string[]) =>
		request<{ case: Case }>(`/cases/${id}/letters`, json('POST', { page_ids })),
	process: (id: string) => request<{ started: boolean }>(`/cases/${id}/process`, { method: 'POST' }),
	deliveryDate: (letterId: string, date: string | null) =>
		request<Case>(`/letters/${letterId}/delivery-date`, json('POST', { date })),
	retry: (letterId: string) => request<{ started: boolean }>(`/letters/${letterId}/retry`, { method: 'POST' }),
	skip: (letterId: string) => request<Case>(`/letters/${letterId}/skip`, { method: 'POST' }),
	confirmThread: (caseId: string, threadId: string, confirmed: boolean) =>
		request<Case>(`/threads/${threadId}/confirm`, json('POST', { confirmed, case_id: caseId })),
	createReply: (letterId: string, template_id: string) =>
		request<{ reply: Reply }>(`/letters/${letterId}/replies`, json('POST', { template_id })),
	getReply: (id: string) =>
		request<{
			reply: Reply;
			case_id: string;
			template: { title: string; body: string; fixed: string[]; free_text: string[]; source: string | null };
		}>(`/replies/${id}`),
	editReply: (id: string, slots: Record<string, string>) =>
		request<{ reply: Reply }>(`/replies/${id}`, json('PUT', { slots })),
	wipe: (id: string) => request<{ wiped: boolean }>(`/cases/${id}`, { method: 'DELETE' })
};

/** Server-sent progress events. Returns a function that closes the stream. */
export function watchCase(id: string, onEvent: (event: string, data: Record<string, unknown>) => void): () => void {
	const source = new EventSource(`/api/cases/${id}/events`);
	for (const name of ['letter.stage', 'letter.done', 'case.done', 'error', 'case.closed']) {
		source.addEventListener(name, (event) => {
			let data = {};
			try {
				data = JSON.parse((event as MessageEvent).data);
			} catch {
				/* events without a payload */
			}
			onEvent(name, data);
		});
	}
	return () => source.close();
}

export const CANTONS = [
	'AG', 'AI', 'AR', 'BE', 'BL', 'BS', 'FR', 'GE', 'GL', 'GR', 'JU', 'LU', 'NE',
	'NW', 'OW', 'SG', 'SH', 'SO', 'SZ', 'TG', 'TI', 'UR', 'VD', 'VS', 'ZG', 'ZH'
];

export const STAGES = ['reading', 'sender', 'dates', 'warnings', 'writing'] as const;
export const STAGE_STRING: Record<string, string> = {
	reading: 'step_reading',
	sender: 'step_sender',
	dates: 'step_dates',
	warnings: 'step_warnings',
	writing: 'step_writing'
};

export function daysLabel(days: number | null | undefined): string {
	if (days === null || days === undefined) return '';
	if (days < 0) return `${-days} ${days === -1 ? 'day' : 'days'} overdue`;
	if (days === 0) return 'today';
	return `${days} ${days === 1 ? 'day' : 'days'} left`;
}

export const FLAG_TITLES: Record<string, string> = {
	SENDER_NOT_IN_DIRECTORY: 'Sender not in the directory',
	CONTACT_MISMATCH: 'Contact differs from the directory',
	FOREIGN_IBAN_FOR_AUTHORITY: 'Foreign account for a Swiss authority',
	QR_MISMATCH: 'QR code and printed text differ',
	URGENCY_PAYMENT_UNUSUAL_CHANNEL: 'Unusual way to pay',
	LEGAL_BASIS_INCONSISTENT: 'Legal basis does not fit',
	NO_LEGAL_REMEDY_NOTICE: 'No instructions on appeal'
};
