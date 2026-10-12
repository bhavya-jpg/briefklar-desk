<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { api, CANTONS, type Language } from '#lib/api.ts';
	import { app } from '#lib/state.svelte.ts';
	import Light from '#lib/components/Light.svelte';

	let languages = $state<Language[]>([]);
	let chosen = $state('');
	let canton = $state('BE');
	let busy = $state(false);
	let error = $state('');

	const replay = $derived(app.health?.mode === 'replay');
	const demo = $derived(app.health?.demo);
	const demoLanguages = $derived(new Set(demo?.languages ?? []));

	onMount(async () => {
		try {
			languages = (await api.languages()).languages;
		} catch (e) {
			error = (e as Error).message;
		}
	});
	$effect(() => {
		if (app.health) canton = replay && demo?.canton ? demo.canton : app.health.canton;
	});

	async function start(useDemo: boolean) {
		if (!chosen || busy) return;
		busy = true;
		error = '';
		try {
			const { case_id } = useDemo ? await api.createDemo(chosen) : await api.createCase(chosen, canton);
			await goto(`/case/${case_id}/capture`);
		} catch (e) {
			error = (e as Error).message;
			busy = false;
		}
	}
</script>

<svelte:head><title>New case · Briefklar Desk</title></svelte:head>

<div class="bk-page">
	<header class="head">
		<p class="bk-eyebrow">New case</p>
		<h1>Which language does the client read best?</h1>
		<p class="bk-small bk-measure">
			Every explanation is also shown in simple German, side by side. The mark under each language says how well Apertus
			has been measured to write it.
		</p>
	</header>

	{#if replay}
		<p class="bk-banner bk-measure">
			Replay mode reads only the {demo?.letters ?? 8} demo letters. They are synthetic: every name, address and number on
			them is invented.
		</p>
	{/if}
	{#if error}<p class="bk-banner bk-banner--error" role="alert">{error}</p>{/if}

	<fieldset class="grid">
		<legend class="bk-visually-hidden">Client language</legend>
		{#each languages as language, index (language.code)}
			{@const disabled = replay && !demoLanguages.has(language.code)}
			<label class="tile bk-rise" class:tile--on={chosen === language.code} class:tile--off={disabled} style:--i={index}>
				<input type="radio" name="language" value={language.code} bind:group={chosen} {disabled} />
				<span class="tile__native" lang={language.code} dir={language.dir}>{language.native}</span>
				<span class="tile__english">{language.english}</span>
				<Light light={language.light} />
			</label>
		{/each}
	</fieldset>

	<label class="bk-field canton">
		<span>Canton (for public holidays)</span>
		<select class="bk-input" bind:value={canton} disabled={replay}>
			{#each CANTONS as code}<option value={code}>{code}</option>{/each}
		</select>
	</label>
</div>

<div class="bk-action bk-noprint">
	{#if !replay && demo?.available && demoLanguages.has(chosen)}
		<button class="bk-btn bk-btn--quiet" disabled={!chosen || busy} onclick={() => start(true)}>Use the demo letters</button>
	{/if}
	<button class="bk-btn bk-btn--primary bk-btn--large" disabled={!chosen || busy} onclick={() => start(!!replay)}>
		{replay ? 'Start with the demo letters' : 'Start'}
	</button>
</div>

<style>
	.head { display: grid; gap: var(--bk-s3); padding-block: var(--bk-s5) var(--bk-s5); }
	.grid { border: 0; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: var(--bk-s3); margin-block: var(--bk-s4); }
	.tile { position: relative; display: grid; gap: 4px; align-content: start; min-height: 132px; padding: var(--bk-s3) var(--bk-s3) 14px; cursor: pointer;
		background: var(--bk-surface); border: 1px solid var(--bk-rule); border-radius: var(--bk-radius);
		transition: border-color var(--bk-fast) var(--bk-ease), transform var(--bk-fast) var(--bk-ease); }
	.tile:hover { border-color: var(--bk-ink-2); }
	.tile input { position: absolute; opacity: 0; inset: 0; cursor: pointer; margin: 0; }
	.tile:has(input:focus-visible) { outline: 2px solid var(--bk-teal); outline-offset: 2px; }
	.tile--on { border-color: var(--bk-teal); box-shadow: inset 0 0 0 1px var(--bk-teal); }
	.tile--off { opacity: 0.45; cursor: not-allowed; }
	.tile__native { font-size: 24px; font-weight: 600; line-height: 1.25; letter-spacing: -0.01em; }
	.tile__english { font-size: var(--bk-size-small); color: var(--bk-ink-2); margin-block-end: auto; padding-block-end: var(--bk-s3); }
	.canton { max-width: 260px; }
</style>
