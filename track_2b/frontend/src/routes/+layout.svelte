<script lang="ts">
	import '#lib/design/base.css';
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { app, loadHealth, modelName } from '#lib/state.svelte.ts';

	let { children } = $props();
	onMount(loadHealth);

	const health = $derived(app.health);
	const showcase = $derived(page.url.pathname.startsWith('/about'));
	const badge = $derived.by(() => {
		if (!health) return '';
		if (health.mode === 'replay') return 'Offline · Replay · this device';
		if (health.offline) return `Offline · ${modelName(health.model)} · this device`;
		return `${modelName(health.model)} · ${health.endpoint_host}`;
	});
</script>

<a class="skip" href="#main">Skip to content</a>

<header class="top bk-noprint" class:top--showcase={showcase}>
	<a class="brand" href="/" aria-label="Briefklar Desk, home">
		<svg viewBox="0 0 32 32" width="28" height="28" aria-hidden="true">
			<rect width="32" height="32" rx="7" fill="var(--bk-teal)" />
			<path d="M9 10.5h14M9 16h14M9 21.5h8" stroke="var(--bk-on-teal)" stroke-width="2.4" stroke-linecap="round" />
		</svg>
		<span>Briefklar <span class="brand__desk">Desk</span></span>
	</a>
	<nav class="top__nav" aria-label="Main">
		<a href="/about" aria-current={showcase ? 'page' : undefined}>About</a>
		{#if health}
			<span class="badge" class:badge--online={!health.offline} title="Where the language model runs">
				<span class="badge__dot" aria-hidden="true"></span>{badge}
			</span>
		{/if}
	</nav>
</header>

{#if health?.mode === 'replay' && !showcase}
	<div class="ribbon bk-noprint" role="status">
		<strong>Replay mode.</strong>
		Cached answers for the demo letters only. No model is running.
		{#if health.replay?.backend === 'fixture'}
			<span class="ribbon__warn">These answers are test fixtures, not Apertus output.</span>
		{/if}
	</div>
{/if}
{#if app.error}
	<div class="ribbon ribbon--error" role="alert">{app.error}</div>
{/if}

<main id="main" tabindex="-1">
	{@render children()}
</main>

<style>
	.skip { position: absolute; inset-inline-start: var(--bk-s3); top: -60px; background: var(--bk-surface); padding: 10px 16px; border-radius: 8px; z-index: 50; }
	.skip:focus { top: var(--bk-s2); }
	.top { display: flex; align-items: center; justify-content: space-between; gap: var(--bk-s3); padding: var(--bk-s3) 72px; border-block-end: 1px solid var(--bk-rule); }
	.top--showcase { border-block-end-color: transparent; }
	.brand { display: inline-flex; align-items: center; gap: 10px; color: var(--bk-ink); text-decoration: none; font-weight: 600; font-size: 19px; letter-spacing: -0.01em; min-height: 44px; }
	.brand__desk { color: var(--bk-ink-2); font-weight: 500; }
	.top__nav { display: flex; align-items: center; gap: var(--bk-s4); }
	.top__nav a { color: var(--bk-ink); text-decoration: none; font-size: var(--bk-size-small); font-weight: 600; min-height: 44px; display: inline-flex; align-items: center; }
	.top__nav a:hover, .top__nav a[aria-current='page'] { text-decoration: underline; text-underline-offset: 6px; }
	.badge { display: inline-flex; align-items: center; gap: 8px; font-size: var(--bk-size-small); font-weight: 600; padding: 6px 14px; border-radius: var(--bk-radius-chip); border: 1px solid var(--bk-rule); background: var(--bk-surface); }
	.badge__dot { width: 8px; height: 8px; border-radius: 50%; background: var(--bk-teal); }
	.badge--online .badge__dot { background: var(--bk-amber); }
	.ribbon { padding: 10px 72px; font-size: var(--bk-size-small); background: var(--bk-surface); border-block-end: 1px solid var(--bk-rule); }
	.ribbon__warn { color: var(--bk-amber); font-weight: 600; margin-inline-start: 6px; }
	.ribbon--error { border-inline-start: 3px solid var(--bk-ink); }
	main:focus { outline: none; }
	@media (max-width: 960px) {
		.top, .ribbon { padding-inline: var(--bk-s3); }
		.top { flex-wrap: wrap; }
		.badge { font-size: 12px; padding: 4px 10px; }
	}
</style>
