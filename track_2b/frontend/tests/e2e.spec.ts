import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Locator, type Page } from '@playwright/test';

const SHOTS = '../docs/screenshots';

/** Activate a control with the keyboard only. */
async function press(target: Locator, key = 'Enter') {
	await target.focus();
	await target.press(key);
}

async function expectAccessible(page: Page) {
	// entrance animations fade content in: measure contrast only once they have finished
	await page.evaluate(() => Promise.all(document.getAnimations().filter((a) => a.effect?.getTiming().iterations !== Infinity).map((a) => a.finished)));
	const results = await new AxeBuilder({ page }).analyze();
	const serious = results.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical');
	expect(serious.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([]);
}

async function startDemo(page: Page, language: string) {
	await page.goto('/case/new');
	await press(page.getByRole('radio', { name: new RegExp(language) }), 'Space');
	await press(page.getByRole('button', { name: /Start/ }));
	await page.waitForURL(/\/capture$/);
	await expect(page.getByRole('heading', { name: '8 letters' })).toBeVisible();
}

async function readLetters(page: Page) {
	await press(page.getByRole('button', { name: 'Read letters' }));
	await expect(page.getByRole('heading', { name: /8 letters, in order of urgency/ })).toBeVisible();
}

test('photos to printed objection, keyboard only, then end the case', async ({ page }) => {
	await page.goto('/');
	await expect(page.getByText('Replay mode.')).toBeVisible();
	await expectAccessible(page);
	await page.screenshot({ path: `${SHOTS}/01-home.png` });

	await press(page.getByRole('link', { name: 'New case' }));
	await page.waitForURL(/\/case\/new$/);
	await expect(page.getByRole('radio')).toHaveCount(13);
	await expectAccessible(page);
	await page.screenshot({ path: `${SHOTS}/02-language-grid.png` });

	await startDemo(page, 'Shqip');
	await expectAccessible(page);
	await page.screenshot({ path: `${SHOTS}/03-capture.png` });

	await readLetters(page);
	await expect(page.getByText('Warning signs · 2')).toBeVisible();
	await expect(page.getByText('Date needed', { exact: true })).toBeVisible();
	await expectAccessible(page);
	await page.screenshot({ path: `${SHOTS}/04-case-board.png`, fullPage: true });

	// payment order: the deadline runs from delivery, so the counsellor enters the date
	await press(page.getByRole('link', { name: /Payment order.*Date needed/s }).last());
	await page.waitForURL(/\/letter\//);
	await page.getByLabel('When did the client receive this letter?').fill('2026-10-08');
	await press(page.getByRole('button', { name: 'Compute deadline' }));
	await expect(page.getByText('Mon 19 Oct 2026')).toBeVisible();
	await expect(page.getByText('9 days left')).toBeVisible();
	await expect(page.getByText(/e hënë, 19 tetor 2026/)).toBeVisible();
	await press(page.getByRole('button', { name: /how this was computed/ }));
	await expect(page.getByText(/SchKG Art. 31/).first()).toBeVisible();
	await page.getByRole('button', { name: /Dita e fundit/ }).hover();
	await expectAccessible(page);
	await page.screenshot({ path: `${SHOTS}/05-letter-view.png`, fullPage: true });

	await press(page.getByRole('button', { name: 'Draft: Rechtsvorschlag' }));
	await page.waitForURL(/\/reply\//);
	await expect(page.getByText('erhebe ich Rechtsvorschlag')).toBeVisible();
	const print = page.getByRole('link', { name: 'Print reply' });
	await expect(print).toHaveAttribute('aria-disabled', 'true'); // the place is still missing
	await page.getByLabel(/Place/).fill('Bern');
	await expect(page.getByText('Saved')).toBeVisible();
	await expect(print).toHaveAttribute('aria-disabled', 'false');
	await expectAccessible(page);
	await page.screenshot({ path: `${SHOTS}/06-reply-editor.png`, fullPage: true });
	const pdf = await page.request.get((await print.getAttribute('href'))!);
	expect(pdf.status()).toBe(200);
	expect(pdf.headers()['content-type']).toBe('application/pdf');

	const caseId = page.url().split('/case/')[1].split('/')[0];
	await page.goto(`/case/${caseId}/handout`);
	await expect(page.frameLocator('iframe').getByText('Letrat tuaja')).toBeVisible();
	await expectAccessible(page);
	await page.screenshot({ path: `${SHOTS}/07-handout.png`, fullPage: true });
	expect((await page.request.get(`/api/cases/${caseId}/handout.pdf`)).status()).toBe(200);

	await press(page.getByRole('button', { name: 'End case' }));
	await press(page.getByRole('button', { name: 'Delete and end case' }));
	await page.waitForURL(/\/$/);
	expect((await page.request.get(`/api/cases/${caseId}`)).status()).toBe(404);
});

test('letter with warning signs: evidence, no verdict', async ({ page }) => {
	await startDemo(page, 'English');
	await readLetters(page);
	await press(page.getByRole('link', { name: /Warning signs · 2/ }).first());
	await page.waitForURL(/\/letter\//);
	await expect(page.getByRole('heading', { name: /Warning signs/ })).toBeVisible();
	await expect(page.getByText('Foreign account for a Swiss authority')).toBeVisible();
	await expect(page.getByText('Be careful: this letter shows warning signs.')).toBeVisible();
	const text = (await page.locator('main').innerText()).toLowerCase();
	expect(text).not.toMatch(/\bfake\b|\bscam\b/);
	await expectAccessible(page);
	await page.screenshot({ path: `${SHOTS}/08-warning-signs.png`, fullPage: true });
});

for (const [name, native, file] of [['Arabic (RTL)', 'العربية', '09-arabic-rtl'], ['Tigrinya', 'ትግርኛ', '10-tigrinya']] as const) {
	test(`${name}: script and direction`, async ({ page }) => {
		await startDemo(page, native);
		await readLetters(page);
		await press(page.getByRole('link', { name: /Tax assessment/ }).last());
		await page.waitForURL(/\/letter\//);
		const block = page.locator('.section .bk-measure').first();
		await expect(block).toHaveAttribute('dir', name.startsWith('Arabic') ? 'rtl' : 'ltr');
		await expect(block).not.toBeEmpty();
		await page.screenshot({ path: `${SHOTS}/${file}.png`, fullPage: true });
		const caseId = page.url().split('/case/')[1].split('/')[0];
		await page.goto(`/api/cases/${caseId}/handout.html`);
		await page.screenshot({ path: `${SHOTS}/${file}-handout.png`, fullPage: true });
	});
}

test('landing page', async ({ page }) => {
	await page.emulateMedia({ reducedMotion: 'reduce' });
	await page.goto('/about');
	await expect(page.getByRole('heading', { name: /Every letter/ })).toBeVisible();
	await expectAccessible(page);
	await page.screenshot({ path: `${SHOTS}/11-about.png`, fullPage: true });
});

test('the page makes no request outside this origin', async ({ page }) => {
	const outside: string[] = [];
	page.on('request', (request) => {
		const url = new URL(request.url());
		if (!['127.0.0.1', 'localhost'].includes(url.hostname) && url.protocol !== 'data:') outside.push(request.url());
	});
	await startDemo(page, 'Shqip');
	await readLetters(page);
	await page.goto('/about');
	await page.waitForLoadState('networkidle');
	expect(outside).toEqual([]);
});

test('dark theme and phone width render the board', async ({ page }) => {
	await page.emulateMedia({ colorScheme: 'dark' });
	await startDemo(page, 'Shqip');
	await readLetters(page);
	await expectAccessible(page);
	await page.screenshot({ path: `${SHOTS}/12-case-board-dark.png`, fullPage: true });
	await page.setViewportSize({ width: 390, height: 844 });
	await press(page.getByRole('link', { name: /Serafe invoice/ }).last());
	await page.waitForURL(/\/letter\//);
	await expect(page.getByRole('heading', { name: /Serafe invoice/ })).toBeVisible();
	expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
	await expectAccessible(page);
	await page.screenshot({ path: `${SHOTS}/13-letter-phone-dark.png` });
});
