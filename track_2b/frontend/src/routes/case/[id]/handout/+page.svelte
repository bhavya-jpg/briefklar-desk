<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api, type Case } from '#lib/api.ts';

	const id = $derived(page.params.id!);
	let data = $state<Case | null>(null);
	let error = $state('');
	let dialog: HTMLDialogElement | undefined = $state();
	let busy = $state(false);

	onMount(async () => {
		try {
			data = await api.getCase(id);
		} catch (e) {
			error = (e as Error).message;
		}
	});

	async function end() {
		busy = true;
		try {
			await api.wipe(id);
			await goto('/');
		} catch (e) {
			error = (e as Error).message;
			busy = false;
		}
	}
</script>

<svelte:head><title>Handout · Briefklar Desk</title></svelte:head>

<div class="bk-page">
	<a class="back" href="/case/{id}">← Case board</a>
	{#if error}<p class="bk-banner bk-banner--error" role="alert">{error}</p>{/if}
	{#if data}
		<header class="head">
			<p class="bk-eyebrow">Handout · <span lang={data.language.code}>{data.language.native}</span></p>
			<h1>One page for the client to take home.</h1>
			<p class="bk-small bk-measure">
				Black and white, in the client's language. Print it, then end the case: photos and results are deleted from this
				device.
			</p>
		</header>
		<div class="bk-grid">
			<div class="preview">
				<iframe title="Handout preview" src="/api/cases/{id}/handout.html"></iframe>
			</div>
			<aside class="side">
				<a class="bk-btn bk-btn--quiet" href="/api/cases/{id}/case-note.pdf" target="_blank" rel="noopener">Case note for the file (German, PDF)</a>
				{#each data.replies as reply}
					<a class="bk-btn bk-btn--quiet" href="/case/{id}/reply/{reply.id}">Reply: {reply.template_id.replaceAll('_', ' ')}</a>
				{/each}
				<button class="bk-btn bk-btn--quiet" onclick={() => dialog?.showModal()}>End case</button>
				<p class="bk-small">The case note carries no client name unless you typed one. Idle cases are wiped after two hours.</p>
			</aside>
		</div>
	{/if}
</div>

<dialog bind:this={dialog} aria-labelledby="end-h">
	<h2 id="end-h">End this case?</h2>
	<p>All photos and results are deleted from this device. This cannot be undone. Print the handout and any reply first.</p>
	<div class="dialog__btns">
		<button class="bk-btn bk-btn--quiet" onclick={() => dialog?.close()}>Keep working</button>
		<button class="bk-btn bk-btn--primary" disabled={busy} onclick={end}>Delete and end case</button>
	</div>
</dialog>

{#if data}
	<div class="bk-action bk-noprint">
		<a class="bk-btn bk-btn--primary bk-btn--large" href="/api/cases/{id}/handout.pdf" target="_blank" rel="noopener">Print handout</a>
	</div>
{/if}

<style>
	.back { display: inline-flex; align-items: center; min-height: 44px; color: var(--bk-ink-2); text-decoration: none; font-size: var(--bk-size-small); font-weight: 600; }
	.head { display: grid; gap: var(--bk-s2); padding-block: var(--bk-s3) var(--bk-s5); }
	.preview { grid-column: 1 / span 7; }
	iframe { width: 100%; aspect-ratio: 210 / 297; border: 1px solid var(--bk-rule); border-radius: 4px; background: #fff; }
	.side { grid-column: 9 / span 4; display: grid; gap: var(--bk-s2); align-content: start; justify-items: start; }
	dialog { border: 1px solid var(--bk-rule); border-radius: var(--bk-radius); padding: var(--bk-s5); max-width: 480px; background: var(--bk-surface); color: var(--bk-ink); }
	dialog::backdrop { background: rgba(20, 22, 26, 0.5); }
	dialog h2 { margin-block-end: var(--bk-s2); }
	.dialog__btns { display: flex; gap: var(--bk-s2); justify-content: flex-end; margin-block-start: var(--bk-s4); flex-wrap: wrap; }
	@media (max-width: 960px) { .preview, .side { grid-column: 1 / -1; } }
</style>
