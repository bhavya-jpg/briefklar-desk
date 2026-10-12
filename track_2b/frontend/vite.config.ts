import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		// Single-page app served by FastAPI. Every route falls back to 200.html.
		sveltekit({
			adapter: adapter({ pages: 'build', assets: 'build', fallback: '200.html' })
		})
	],
	server: { proxy: { '/api': 'http://127.0.0.1:8080' } }
});
