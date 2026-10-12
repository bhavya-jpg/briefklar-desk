import { api, type Health } from './api.ts';

export const app = $state<{ health: Health | null; error: string | null }>({ health: null, error: null });

export async function loadHealth(): Promise<void> {
	try {
		app.health = await api.health();
		app.error = null;
	} catch (error) {
		app.error = (error as Error).message;
	}
}

export function modelName(name: string): string {
	return name === 'apertus-8b' ? 'Apertus 1.5 8B' : name;
}
