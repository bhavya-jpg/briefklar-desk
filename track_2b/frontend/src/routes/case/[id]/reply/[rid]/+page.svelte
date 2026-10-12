<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { api, type Case, type Reply } from '#lib/api.ts';
	import PageView from '#lib/components/PageView.svelte';

	const id = $derived(page.params.id!);
	const rid = $derived(page.params.rid!);
	let data = $state<Case | null>(null);
	let reply = $state<Reply | null>(null);
	let template = $state<Awaited<ReturnType<typeof api.getReply>>['template'] | null>(null);
	let draft = $state<Record<string, string>>({});
	let error = $state('');
	let saved = $state('');
	let active = $state<string[]>([]);
	let timer: ReturnType<typeof setTimeout>;

	const SOURCE_REQUIRED = '[SOURCE REQUIRED]';
	const LABELS: Record<string, string> = {
		debtor_name: 'Name of the client', debtor_address: 'Address of the client', office_name: 'To', office_address: 'Address',
		enforcement_number: 'Enforcement number', reference: 'Reference', place: 'Place', date: 'Date', signature_line: 'Signature line',
		letter_date: 'Date of their letter', amount: 'Amount', reason: 'Reason', proposal: 'Proposal', creditor_name: 'Creditor', due_date: 'Deadline'
	};

	const letter = $derived(data?.letters.find((l) => l.id === reply?.letter_id) ?? null);
	const segments = $derived.by(() => {
		if (!template) return [];
		const out: { slot: string | null; text: string }[] = [];
		let last = 0;
		for (const match of template.body.matchAll(/\{\{\s*(\w+)\s*\}\}/g)) {
			if (match.index > last) out.push({ slot: null, text: template.body.slice(last, match.index) });
			out.push({ slot: match[1], text: '' });
			last = match.index + match[0].length;
		}
		if (last < template.body.length) out.push({ slot: null, text: template.body.slice(last) });
		return out;
	});
	const editable = $derived([...new Set(segments.map((s) => s.slot).filter((s): s is string => !!s && !template!.fixed.includes(s)))]);
	const blocked = $derived(reply ? Object.values(reply.slots).includes(SOURCE_REQUIRED) : true);
	const open = $derived((reply?.missing ?? []).filter((m) => !template?.fixed.includes(m)));

	onMount(async () => {
		try {
			const result = await api.getReply(rid);
			reply = result.reply;
			template = result.template;
			draft = { ...result.reply.slots };
			for (const key of result.reply.missing) if (draft[key]?.startsWith('[')) draft[key] = '';
			data = await api.getCase(id);
		} catch (e) {
			error = (e as Error).message;
		}
	});

	function edit(slot: string, value: string) {
		draft[slot] = value;
		saved = '';
		clearTimeout(timer);
		timer = setTimeout(save, 400);
	}
	async function save() {
		try {
			reply = (await api.editReply(rid, draft)).reply;
			saved = 'Saved';
		} catch (e) {
			error = (e as Error).message;
		}
	}
	const kind = (slot: string) =>
		!reply ? '' : reply.slots[slot] === SOURCE_REQUIRED ? 'blocked' : reply.missing.includes(slot) ? 'missing' : reply.needs_review.includes(slot) ? 'review' : template?.fixed.includes(slot) ? 'fixed' : 'filled';
</script>

<svelte:head><title>{template?.title ?? 'Reply'} · Briefklar Desk</title></svelte:head>

<div class="bk-page">
	<a class="back" href={letter ? `/case/${id}/letter/${letter.id}` : `/case/${id}`}>← Letter</a>
	{#if error}<p class="bk-banner bk-banner--error" role="alert">{error}</p>{/if}

	{#if reply && template}
		<header class="head">
			<p class="bk-eyebrow">Reply · {reply.language.toUpperCase()}</p>
			<h1>{template.title}</h1>
			<p class="bk-small bk-measure">
				The wording is fixed. Marked fields come from the letter: point at one to see where. The counsellor checks the
				reply; the client signs it.
			</p>
		</header>

		{#if blocked}
			<p class="bk-banner" role="status">
				<strong>Not ready to print.</strong> The fixed sentence of this reply has no official source in this language yet.
				It is never written by the model. A person must add it from official guidance first.
			</p>
		{/if}
		{#if reply.needs_review.length}
			<p class="bk-banner" role="status"><strong>Review the amber text.</strong> It was drafted by the model, not copied from the letter.</p>
		{/if}

		<div class="bk-grid split">
			<div class="source">
				{#if letter?.facts}
					<PageView pages={letter.pages} evidence={letter.facts.evidence_items} {active} />
				{/if}
			</div>

			<div class="paper-col">
				<div class="paper" lang={reply.language}>
					{#each segments as segment}{#if segment.slot}<span
								class="slot slot--{kind(segment.slot)}"
								role="mark"
								onmouseenter={() => (active = reply!.slot_sources[segment.slot!] ?? [])}
								onmouseleave={() => (active = [])}>{reply.slots[segment.slot] === SOURCE_REQUIRED ? 'Fixed sentence: source required' : reply.slots[segment.slot]}</span>{:else}{segment.text}{/if}{/each}
				</div>
				{#if template.source}<p class="bk-small source-note">Template source: {template.source}</p>{/if}
			</div>

			<form class="fields" onsubmit={(e) => e.preventDefault()}>
				<h2 class="fields__h">Fields</h2>
				{#each editable as slot}
					<label class="bk-field" onmouseenter={() => (active = reply!.slot_sources[slot] ?? [])} onmouseleave={() => (active = [])}>
						<span>
							{LABELS[slot] ?? slot}
							{#if reply.needs_review.includes(slot)}<em class="bk-chip bk-chip--amber">Review</em>{/if}
							{#if reply.missing.includes(slot)}<em class="bk-chip bk-chip--amber">Fill in</em>{/if}
						</span>
						{#if template.free_text.includes(slot) || (draft[slot] ?? '').includes('\n')}
							<textarea class="bk-input" rows="3" value={draft[slot] ?? ''} oninput={(e) => edit(slot, e.currentTarget.value)}
								onfocus={() => (active = reply!.slot_sources[slot] ?? [])} onblur={() => (active = [])}></textarea>
						{:else}
							<input class="bk-input" value={draft[slot] ?? ''} oninput={(e) => edit(slot, e.currentTarget.value)}
								onfocus={() => (active = reply!.slot_sources[slot] ?? [])} onblur={() => (active = [])} />
						{/if}
					</label>
				{/each}
				<p class="bk-small" aria-live="polite">{saved}</p>
			</form>
		</div>
	{:else if !error}
		<p class="bk-small" aria-busy="true">Loading the reply…</p>
	{/if}
</div>

{#if reply}
	<div class="bk-action bk-noprint">
		{#if open.length}<span class="bk-small">Still to fill in: {open.map((s) => LABELS[s] ?? s).join(', ')}</span>{/if}
		<a class="bk-btn bk-btn--primary bk-btn--large" href="/api/replies/{rid}.pdf" target="_blank" rel="noopener" aria-disabled={blocked || open.length > 0}>
			Print reply
		</a>
	</div>
{/if}

<style>
	.back { display: inline-flex; align-items: center; min-height: 44px; color: var(--bk-ink-2); text-decoration: none; font-size: var(--bk-size-small); font-weight: 600; }
	.head { display: grid; gap: var(--bk-s2); padding-block: var(--bk-s3) var(--bk-s4); }
	.bk-banner { margin-block-end: var(--bk-s3); }
	.split { margin-block-start: var(--bk-s4); }
	.source { grid-column: 1 / span 4; position: sticky; top: var(--bk-s3); align-self: start; max-height: calc(100vh - 2 * var(--bk-s3)); overflow: auto; }
	.paper-col { grid-column: 5 / span 5; }
	.fields { grid-column: 10 / span 3; display: grid; gap: var(--bk-s3); align-content: start; }
	.fields__h { font-size: var(--bk-size-small); letter-spacing: 0.06em; text-transform: uppercase; color: var(--bk-ink-2); }
	.fields .bk-field > span { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
	.fields em { font-style: normal; }
	textarea.bk-input { resize: vertical; }
	/* The reply is paper: always dark ink on white, whatever the theme. */
	.paper { aspect-ratio: 210 / 297; background: #fff; color: #14161a; border: 1px solid var(--bk-rule); border-radius: 4px; padding: 9% 10%; white-space: pre-wrap;
		font-size: clamp(11px, 1.05vw, 15px); line-height: 1.5; overflow: hidden; }
	.slot { border-radius: 3px; padding: 1px 2px; margin: 0 -2px; background: rgba(15, 110, 106, 0.15); transition: background var(--bk-fast) var(--bk-ease); cursor: default; }
	.slot:hover { background: rgba(15, 110, 106, 0.3); }
	.slot--fixed { background: transparent; }
	.slot--review { background: rgba(232, 163, 23, 0.25); }
	.slot--missing { background: transparent; outline: 1.5px dashed #8f5d00; color: #8f5d00; }
	.slot--blocked { background: transparent; outline: 1.5px dashed #14161a; font-weight: 600; }
	.source-note { margin-block-start: var(--bk-s2); overflow-wrap: anywhere; }
	[aria-disabled='true'] { opacity: 0.5; pointer-events: none; }
	@media (max-width: 1200px) {
		.source { grid-column: 1 / span 5; }
		.paper-col { grid-column: 6 / span 7; }
		.fields { grid-column: 1 / -1; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); }
		.fields__h { grid-column: 1 / -1; }
	}
	@media (max-width: 960px) {
		.source { grid-column: 1 / -1; position: static; max-height: 30vh; }
		.paper-col { grid-column: 1 / -1; }
		.paper { font-size: 12px; }
	}
</style>
