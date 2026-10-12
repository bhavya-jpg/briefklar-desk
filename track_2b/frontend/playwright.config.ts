import { defineConfig } from '@playwright/test';

const PORT = 8087;

// End-to-end tests run against the real app in replay mode (no model, no network).
export default defineConfig({
	testDir: 'tests',
	timeout: 60_000,
	workers: 1,
	reporter: 'list',
	use: { baseURL: `http://127.0.0.1:${PORT}`, viewport: { width: 1440, height: 900 } },
	webServer: {
		// macOS strips DYLD_* from child shells, so it is set through env(1); it is ignored on Linux.
		command: `/usr/bin/env DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib uv run uvicorn briefklar.main:app --host 127.0.0.1 --port ${PORT}`,
		cwd: '..',
		url: `http://127.0.0.1:${PORT}/api/health`,
		reuseExistingServer: false,
		env: {
			PYTHONPATH: 'src:.',
			BRIEFKLAR_MODE: 'replay',
			BRIEFKLAR_STATIC_DIR: 'frontend/build'
		}
	}
});
