<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api, type Case } from '#lib/api.ts';
	import { app } from '#lib/state.svelte.ts';

	const id = $derived(page.params.id!);
	let data = $state<Case | null>(null);
	let error = $state('');
	let problems = $state<{ filename: string; message: string }[]>([]);
	let busy = $state(false);
	let selected = $state<string[]>([]);
	let dragging = $state<string | null>(null);
	let over = $state(false);

	const replay = $derived(app.health?.mode === 'replay');

	onMount(async () => {
		try {
			data = await api.getCase(id);
			if (data.status !== 'capturing') await goto(`/case/${id}`, { replaceState: true });
		} catch (e) {
			error = (e as Error).message;
		}
	});

	async function add(files: FileList | File[] | null) {
		if (!files || !files.length || busy) return;
		busy = true;
		error = '';
		try {
			const result = await api.upload(id, [...files].slice(0, 20));
			data = result.case;
			problems = result.errors;
		} catch (e) {
			error = (e as Error).message;
		}
		busy = false;
	}

	async function merge(letterIds: string[]) {
		if (!data || letterIds.length < 2) return;
		const pages = data.letters.filter((l) => letterIds.includes(l.id)).flatMap((l) => l.page_ids);
		data = (await api.group(id, pages)).case;
		selected = [];
	}

	async function split(letterId: string) {
		if (!data) return;
		const letter = data.letters.find((l) => l.id === letterId);
		if (!letter) return;
		for (const pageId of letter.page_ids) data = (await api.group(id, [pageId])).case;
	}

	async function remove(pageId: string) {
		data = await api.deletePage(id, pageId);
	}

	async function read() {
		busy = true;
		try {
			await api.process(id);
			await goto(`/case/${id}`);
		} catch (e) {
			error = (e as Error).message;
			busy = false;
		}
	}

	function toggle(letterId: string) {
		selected = selected.includes(letterId) ? selected.filter((s) => s !== letterId) : [...selected, letterId];
	}
</script>

<svelte:head><title>Capture · Briefklar Desk</title></svelte:head>

<div class="bk-page">
	<header class="head">
		<p class="bk-eyebrow">Capture{data ? ` · ${data.language.english}` : ''}</p>
		<h1>Photograph every letter the client brought.</h1>
		<p class="bk-small bk-measure">
			One tile is one letter. If a letter has several pages, tick them and choose “Same letter”, or drag one tile onto
			another.
		</p>
	</header>

	{#if error}<p class="bk-banner bk-banner--error" role="alert">{error}</p>{/if}
	{#each problems as problem}
		<p class="bk-banner" role="alert"><strong>{problem.filename}:</strong> {problem.message}</p>
	{/each}

	{#if replay && !data?.demo}
		<p class="bk-banner bk-measure">
			Replay mode has no model, so new letters cannot be read. Start a case with the demo letters, or connect a live
			Apertus endpoint.
		</p>
	{:else if !data?.demo}
		<label
			class="drop"
			class:drop--over={over}
			ondragover={(e) => { e.preventDefault(); over = true; }}
			ondragleave={() => (over = false)}
			ondrop={(e) => { e.preventDefault(); over = false; add(e.dataTransfer?.files ?? null); }}
		>
			<input type="file" accept="image/*,application/pdf" multiple onchange={(e) => add(e.currentTarget.files)} disabled={busy} />
			<span class="drop__title">{busy ? 'Reading the pages…' : 'Add photos or PDFs'}</span>
			<span class="bk-small">Drop files here, or press Enter to choose. Up to 20 at a time. Flat page, good light, no flash.</span>
		</label>
	{/if}

	{#if data && data.letters.length}
		<section aria-labelledby="letters-h" class="letters">
			<div class="letters__head">
				<h2 id="letters-h">{data.letters.length} {data.letters.length === 1 ? 'letter' : 'letters'}</h2>
				<button class="bk-btn bk-btn--quiet" disabled={selected.length < 2} onclick={() => merge(selected)}>Same letter</button>
			</div>
			<ul class="strip">
				{#each data.letters as letter, index (letter.id)}
					<li
						class="thumb bk-rise"
						class:thumb--on={selected.includes(letter.id)}
						style:--i={index}
						draggable={!data.demo}
						ondragstart={() => (dragging = letter.id)}
						ondragend={() => (dragging = null)}
						ondragover={(e) => e.preventDefault()}
						ondrop={(e) => { e.preventDefault(); if (dragging && dragging !== letter.id) merge([letter.id, dragging]); }}
					>
						<div class="thumb__pages">
							{#each letter.pages as p, n (p.id)}
								<img src={p.url} alt="Letter {index + 1}, page {n + 1}" loading="lazy" style:--n={n} />
							{/each}
						</div>
						<div class="thumb__bar">
							<label class="thumb__check">
								<input type="checkbox" checked={selected.includes(letter.id)} onchange={() => toggle(letter.id)} disabled={data.demo} />
								<span>Letter {index + 1}{letter.pages.length > 1 ? ` · ${letter.pages.length} pages` : ''}</span>
							</label>
							{#if !data.demo}
								{#if letter.pages.length > 1}
									<button class="thumb__btn" onclick={() => split(letter.id)}>Split</button>
								{:else}
									<button class="thumb__btn" aria-label="Remove letter {index + 1}" onclick={() => remove(letter.page_ids[0])}>Remove</button>
								{/if}
							{/if}
						</div>
					</li>
				{/each}
			</ul>
		</section>
	{:else if data && !replay}
		<p class="bk-small empty">No letters yet.</p>
	{/if}
</div>

<div class="bk-action bk-noprint">
	<button class="bk-btn bk-btn--primary bk-btn--large" disabled={!data?.letters.length || busy} onclick={read}>Read letters</button>
</div>

<style>
	.head { display: grid; gap: var(--bk-s3); padding-block: var(--bk-s5) var(--bk-s4); }
	.drop { display: grid; gap: 6px; place-items: center; text-align: center; padding: var(--bk-s6) var(--bk-s4); margin-block: var(--bk-s4);
		border: 1.5px dashed var(--bk-ink-2); border-radius: var(--bk-radius); background: var(--bk-surface); cursor: pointer; position: relative;
		transition: background var(--bk-fast) var(--bk-ease), border-color var(--bk-fast) var(--bk-ease); }
	.drop--over, .drop:hover { border-color: var(--bk-teal); background: var(--bk-teal-wash); }
	.drop input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
	.drop:has(input:focus-visible) { outline: 2px solid var(--bk-teal); outline-offset: 2px; }
	.drop__title { font-size: var(--bk-size-h2); font-weight: 600; }
	.letters { margin-block-start: var(--bk-s5); display: grid; gap: var(--bk-s3); }
	.letters__head { display: flex; justify-content: space-between; align-items: center; }
	.strip { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(168px, 1fr)); gap: var(--bk-s3); }
	.thumb { background: var(--bk-surface); border: 1px solid var(--bk-rule); border-radius: var(--bk-radius); overflow: hidden; }
	.thumb--on { border-color: var(--bk-teal); box-shadow: inset 0 0 0 1px var(--bk-teal); }
	.thumb__pages { position: relative; aspect-ratio: 210 / 297; background: var(--bk-paper); }
	.thumb__pages img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; object-position: top;
		transform: translate(calc(var(--n) * 6px), calc(var(--n) * 6px)); box-shadow: 0 0 0 1px var(--bk-rule); }
	.thumb__bar { display: flex; justify-content: space-between; align-items: center; gap: var(--bk-s2); padding: 4px 4px 4px 12px; font-size: var(--bk-size-small); }
	.thumb__check { display: flex; align-items: center; gap: 8px; min-height: 44px; cursor: pointer; font-weight: 600; }
	.thumb__check input { width: 18px; height: 18px; accent-color: var(--bk-teal); }
	.thumb__btn { min-height: 44px; padding-inline: 10px; background: none; border: 0; color: var(--bk-ink-2); cursor: pointer; text-decoration: underline; text-underline-offset: 3px; }
	.empty { margin-block-start: var(--bk-s4); }
</style>
