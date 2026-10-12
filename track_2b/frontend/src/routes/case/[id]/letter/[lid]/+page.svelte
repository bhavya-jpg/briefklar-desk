<script lang="ts">
	import { onMount } from 'svelte';
	import { fade } from 'svelte/transition';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api, daysLabel, FLAG_TITLES, type Case, type Explanation, type Letter } from '#lib/api.ts';
	import DaysNumeral from '#lib/components/DaysNumeral.svelte';
	import PageView from '#lib/components/PageView.svelte';

	const id = $derived(page.params.id!);
	const lid = $derived(page.params.lid!);
	let data = $state<Case | null>(null);
	let error = $state('');
	let view = $state<'client' | 'de'>('client');
	let hovered = $state<string[]>([]);
	let pinned = $state<string[]>([]);
	let picked = $state<string | null>(null);
	let traceOpen = $state(false);
	let delivery = $state('');
	let busy = $state(false);
	let fadeMs = $state(120);

	const letter = $derived(data?.letters.find((l) => l.id === lid) ?? null);
	const deadline = $derived(letter?.verification?.deadline ?? null);
	const flags = $derived(letter?.verification?.red_flags ?? []);
	const shown = $derived<Explanation | null>(view === 'de' ? (letter?.explanation_de ?? null) : (letter?.explanation ?? null));
	const twin = $derived(view === 'client' && letter?.explanation?.low_confidence ? letter.explanation_de : null);
	const strings = $derived(view === 'de' ? data?.strings_de : data?.strings);
	const shownLang = $derived(view === 'de' ? { code: 'de', dir: 'ltr' as const } : { code: data?.language.code ?? 'de', dir: data?.language.dir ?? ('ltr' as const) });
	const active = $derived(hovered.length ? hovered : pinned);
	const sameLanguage = $derived(data?.client_language === 'de');

	const SECTIONS = [
		['what_this_is', 'section_what_this_is'],
		['what_they_want', 'section_what_they_want'],
		['deadline', 'section_deadline'],
		['what_you_can_do', 'section_what_you_can_do'],
		['who_to_contact', 'section_who_to_contact']
	] as const;
	const FACT_ROWS = [
		['sender_name', 'Sender', false],
		['creditor_name', 'Creditor', false],
		['reference_numbers', 'Reference', true],
		['amounts', 'Amount', false],
		['iban', 'IBAN', true],
		['letter_date', 'Letter dated', false]
	] as const;

	onMount(async () => {
		if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) fadeMs = 0;
		try {
			data = await api.getCase(id);
			delivery = data.letters.find((l) => l.id === lid)?.delivery_date ?? data.today;
		} catch (e) {
			error = (e as Error).message;
		}
	});

	function factValue(key: string): string {
		const f = letter?.facts;
		if (!f) return '';
		if (key === 'amounts') return letter?.amount_display ?? '';
		if (key === 'letter_date') return letter?.letter_date_display ?? '';
		if (key === 'reference_numbers') return f.reference_numbers.join(' · ');
		return ((f as Record<string, unknown>)[key] as string) ?? '';
	}
	function factEvidence(key: string): string[] {
		return letter?.facts?.evidence[key === 'amounts' ? 'amount_due' : key] ?? [];
	}
	function pick(spanId: string) {
		picked = spanId;
		pinned = [spanId];
		requestAnimationFrame(() => {
			document.querySelector('.sentence--pulse')?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
		});
		setTimeout(() => (picked = null), 1200);
	}
	async function setDelivery() {
		if (!delivery) return;
		busy = true;
		try {
			data = await api.deliveryDate(lid, delivery);
			error = '';
		} catch (e) {
			error = (e as Error).message;
		}
		busy = false;
	}
	async function reply(templateId: string) {
		busy = true;
		try {
			const { reply } = await api.createReply(lid, templateId);
			await goto(`/case/${id}/reply/${reply.id}`);
		} catch (e) {
			error = (e as Error).message;
			busy = false;
		}
	}
	const existingReply = (templateId: string) => data?.replies.find((r) => r.letter_id === lid && r.template_id === templateId);
</script>

<svelte:head><title>{letter?.type_label ?? 'Letter'} · Briefklar Desk</title></svelte:head>

<div class="bk-page">
	<a class="back" href="/case/{id}">← Case board</a>
	{#if error}<p class="bk-banner bk-banner--error" role="alert">{error}</p>{/if}

	{#if letter && letter.facts && data}
		<header class="head">
			<div>
				<p class="bk-eyebrow">{letter.type_label_de} · {letter.facts.source_language.toUpperCase()}</p>
				<h1>{letter.type_label}{letter.facts.sender_name ? `, ${letter.facts.sender_name}` : ''}</h1>
			</div>
			{#if !sameLanguage}
				<div class="toggle" role="group" aria-label="Language of the explanation">
					<button class:on={view === 'client'} aria-pressed={view === 'client'} onclick={() => (view = 'client')}>
						<span lang={data.language.code}>{data.language.native}</span>
					</button>
					<button class:on={view === 'de'} aria-pressed={view === 'de'} onclick={() => (view = 'de')}>Einfaches Deutsch</button>
				</div>
			{/if}
		</header>

		<div class="bk-grid split">
			<div class="sheet-col">
				<PageView pages={letter.pages} evidence={letter.facts.evidence_items} {active} onpick={pick} />
			</div>

			<div class="cards">
				{#if letter.explanation?.low_confidence && view === 'client'}
					<p class="bk-banner" role="status">
						<strong>Check with the counsellor.</strong>
						The back-translation of this explanation does not match the German closely enough{letter.explanation.failed_field_checks.length ? ` (${letter.explanation.failed_field_checks.join(', ')} changed)` : ''}.
						Simple German is shown next to it.
					</p>
				{/if}

				{#if flags.length}
					<section class="flags" class:flags--lit={active.includes('flags')} aria-labelledby="flags-h">
						<h2 id="flags-h">
							<span lang={data.language.code} dir={data.language.dir}>{data.strings.warning_heading}</span>
							{#if !sameLanguage}<span class="flags__de" lang="de"> · Warnsignale</span>{/if}
						</h2>
						<ul>
							{#each flags as flag, index}
								<li class="bk-rise" style:--i={index * 1.3}>
									<button type="button" class="flag" onmouseenter={() => (hovered = flag.span_ids)} onmouseleave={() => (hovered = [])}
										onfocus={() => (hovered = flag.span_ids)} onblur={() => (hovered = [])}>
										<strong>{FLAG_TITLES[flag.code] ?? flag.code}</strong>
										<span>{flag.evidence}</span>
									</button>
									{#if flag.source_url}
										<a class="flag__src bk-small" href={flag.source_url} target="_blank" rel="noopener noreferrer">Source of this check: {new URL(flag.source_url).hostname.replace('www.', '')}</a>
									{/if}
								</li>
							{/each}
						</ul>
						<div class="flags__contact">
							{#if letter.verification?.authority_contact?.sourced}
								{@const c = letter.verification.authority_contact}
								<p><strong>Official contact from the directory:</strong> {c.name}</p>
								<p class="bk-mono">{[c.phone, c.email, c.web].filter(Boolean).join(' · ')}</p>
							{:else if letter.verification?.authority_contact}
								<p><strong>{letter.verification.authority_contact.name}</strong> is in the directory, but its official contact has not been sourced yet. Look it up on the authority's own website, not on this letter.</p>
							{:else}
								<p>The sender is not in the directory. Do not use a phone number or address printed on this letter.</p>
							{/if}
							<p class="bk-small">These are observations with their evidence. Briefklar does not decide whether a letter is genuine.</p>
						</div>
					</section>
				{/if}

				<section class="bk-card deadline" aria-labelledby="dl-h">
					<h2 id="dl-h" class="card-h">Deadline</h2>
					{#if !deadline}
						<p>This letter sets no deadline.</p>
					{:else if deadline.due_date}
						<div class="deadline__row">
							<DaysNumeral days={Math.abs(deadline.days_left ?? 0)} from={10} />
							<div>
								<p class="deadline__date">{letter.due_display}</p>
								<p class="bk-small">{daysLabel(deadline.days_left)}</p>
							</div>
						</div>
						{#if !deadline.verified_rule}
							<p class="bk-chip bk-chip--amber">Rule unverified: check this date by hand</p>
						{/if}
					{:else if deadline.needs_delivery_date}
						<p class="bk-chip bk-chip--amber">Date needed</p>
					{:else}
						<p class="bk-small">{deadline.trace[0]}</p>
					{/if}

					{#if deadline && (deadline.needs_delivery_date || letter.delivery_date)}
						<form class="delivery" onsubmit={(e) => { e.preventDefault(); setDelivery(); }}>
							<label class="bk-field">
								<span>When did the client receive this letter?</span>
								<input class="bk-input" type="date" bind:value={delivery} max={data.today} required />
							</label>
							<button class="bk-btn bk-btn--quiet" disabled={busy}>{letter.delivery_date ? 'Change' : 'Compute deadline'}</button>
						</form>
					{/if}

					{#if deadline}
						<button class="trace-btn" aria-expanded={traceOpen} aria-controls="trace" onclick={() => (traceOpen = !traceOpen)}>
							{traceOpen ? 'Hide' : 'Show'} how this was computed
						</button>
						{#if traceOpen}
							<ol id="trace" class="trace" transition:fade={{ duration: fadeMs * 2 }}>
								{#each deadline.trace as step}<li>{step}</li>{/each}
								<li class="bk-small">Computed by the rule engine, not by the language model.</li>
							</ol>
						{/if}
					{/if}
				</section>

				{#if shown && strings}
					{#key view}
						<div class="explain" in:fade={{ duration: fadeMs }}>
							{#each SECTIONS as [key, heading]}
								<section class="bk-card section" aria-label={strings[heading]}>
									<h2 class="card-h" lang={shownLang.code} dir={shownLang.dir}>{strings[heading]}</h2>
									<div class="bk-measure" lang={shownLang.code} dir={shownLang.dir}>
										{#each shown[key] as sentence}
											<button
												type="button"
												class="sentence"
												class:sentence--on={sentence.support.some((s) => active.includes(s))}
												class:sentence--pulse={picked !== null && sentence.support.includes(picked)}
												onmouseenter={() => (hovered = sentence.support)}
												onmouseleave={() => (hovered = [])}
												onfocus={() => (hovered = sentence.support)}
												onblur={() => (hovered = [])}
												onclick={() => (pinned = pinned.join() === sentence.support.join() ? [] : sentence.support)}
											>{sentence.text}{#if sentence.support.some((s) => s.startsWith('card:'))}<span class="src" dir="ltr">info sheet</span>{/if}</button>{' '}
										{/each}
									</div>
									{#if twin}
										<p class="twin bk-measure" lang="de">{twin[key].map((s) => s.text).join(' ')}</p>
									{/if}
								</section>
							{/each}
						</div>
					{/key}
				{/if}

				<section class="bk-card" aria-labelledby="facts-h">
					<h2 id="facts-h" class="card-h">Read from the letter</h2>
					<dl class="facts">
						{#each FACT_ROWS as [key, label, mono]}
							{#if factValue(key)}
								{@const check = letter.verification?.field_checks[key]}
								<dt>{label}</dt>
								<dd>
									<button type="button" class="fact" class:bk-mono={mono} onmouseenter={() => (hovered = factEvidence(key))} onmouseleave={() => (hovered = [])}
										onfocus={() => (hovered = factEvidence(key))} onblur={() => (hovered = [])}>{factValue(key)}</button>
									{#if check && check !== 'match'}
										<span class="bk-chip bk-chip--amber" title={check === 'mismatch' ? 'The text recognition read a different value.' : 'The text recognition did not find this value.'}>Check</span>
									{/if}
									{#if key === 'iban' && letter.verification?.iban_valid === false}<span class="bk-chip bk-chip--amber">Checksum invalid</span>{/if}
								</dd>
							{/if}
						{/each}
					</dl>
					<p class="bk-small">“Check” means the model and the text recognition disagree. Compare with the page.</p>
				</section>

				<footer class="disclaimer bk-small">
					<p lang={data.language.code} dir={data.language.dir}>{data.strings.disclaimer}</p>
					{#if !sameLanguage}<p lang="de">{data.strings_de.disclaimer}</p>{/if}
				</footer>
			</div>
		</div>
	{:else if data && letter}
		<p class="bk-banner">{letter.error ?? 'This letter has not been read yet.'}</p>
	{:else if !error}
		<p class="bk-small" aria-busy="true">Loading the letter…</p>
	{/if}
</div>

{#if letter?.reply_templates?.length}
	<div class="bk-action bk-noprint">
		{#each letter.reply_templates as template, index}
			{@const existing = existingReply(template.id)}
			{#if existing}
				<a class="bk-btn" class:bk-btn--primary={index === 0} href="/case/{id}/reply/{existing.id}">Open: {template.title}</a>
			{:else}
				<button class="bk-btn" class:bk-btn--primary={index === 0} class:bk-btn--quiet={index > 0} disabled={busy} onclick={() => reply(template.id)}
					title={template.unsourced.length ? 'The fixed wording of this reply has no official source yet. It can be drafted but not printed.' : undefined}>
					Draft: {template.title}
				</button>
			{/if}
		{/each}
	</div>
{/if}

<style>
	.back { display: inline-flex; align-items: center; min-height: 44px; color: var(--bk-ink-2); text-decoration: none; font-size: var(--bk-size-small); font-weight: 600; }
	.back:hover { color: var(--bk-ink); }
	.head { display: flex; justify-content: space-between; align-items: end; gap: var(--bk-s4); flex-wrap: wrap; padding-block: var(--bk-s3) var(--bk-s5); }
	.head > div:first-child { display: grid; gap: var(--bk-s2); }
	.toggle { display: inline-flex; border: 1px solid var(--bk-ink); border-radius: var(--bk-radius-chip); padding: 3px; background: var(--bk-surface); }
	.toggle button { min-height: 40px; padding: 6px 18px; border: 0; border-radius: var(--bk-radius-chip); background: transparent; cursor: pointer; font-weight: 600;
		transition: background var(--bk-fast) var(--bk-ease), color var(--bk-fast) var(--bk-ease); }
	.toggle button.on { background: var(--bk-ink); color: var(--bk-paper); }
	.sheet-col { grid-column: 1 / span 7; position: sticky; top: var(--bk-s3); align-self: start; max-height: calc(100vh - 2 * var(--bk-s3)); overflow: auto; border-radius: 6px; }
	.cards { grid-column: 8 / span 5; display: grid; gap: var(--bk-s3); align-content: start; }
	.explain { display: grid; gap: var(--bk-s3); }
	.card-h { font-size: var(--bk-size-small); font-weight: 600; letter-spacing: 0.04em; color: var(--bk-ink-2); margin-block-end: var(--bk-s2); }
	.section { padding: var(--bk-s3) var(--bk-s4); }
	.sentence { display: inline; text-align: start; background: none; border: 0; padding: 2px 3px; margin: 0 -3px; border-radius: 4px; cursor: pointer; font-size: 19px; line-height: 1.5;
		transition: background var(--bk-fast) var(--bk-ease); -webkit-box-decoration-break: clone; box-decoration-break: clone; }
	.sentence:hover, .sentence--on { background: var(--bk-teal-wash); }
	.sentence--pulse { animation: pulse 1100ms var(--bk-ease); }
	@keyframes pulse { 0%, 100% { box-shadow: 0 0 0 0 transparent; } 30% { box-shadow: 0 0 0 3px var(--bk-teal); background: var(--bk-teal-wash); } }
	.src { margin-inline-start: 6px; font-size: 12px; font-weight: 600; color: var(--bk-teal); border: 1px solid currentColor; border-radius: 4px; padding: 0 5px; vertical-align: 2px; }
	.twin { margin-block-start: var(--bk-s2); padding-block-start: var(--bk-s2); border-block-start: 1px dashed var(--bk-rule); color: var(--bk-ink-2); font-size: var(--bk-size-body); }
	.flags { background: var(--bk-red-wash); border-inline-start: 4px solid var(--bk-red); border-radius: var(--bk-radius); padding: var(--bk-s4); display: grid; gap: var(--bk-s3);
		transition: box-shadow var(--bk-fast) var(--bk-ease); }
	.flags--lit { box-shadow: 0 0 0 2px var(--bk-red); }
	.flags h2 { color: var(--bk-red); font-size: var(--bk-size-h2); }
	.flags__de { color: var(--bk-ink-2); font-weight: 500; font-size: var(--bk-size-body); }
	.flags ul { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--bk-s2); }
	.flag { display: grid; gap: 2px; text-align: start; width: 100%; background: var(--bk-surface); border: 1px solid var(--bk-rule); border-radius: 8px; padding: 12px 14px; cursor: pointer; overflow-wrap: anywhere; }
	.flag span { font-size: var(--bk-size-small); color: var(--bk-ink-2); }
	.flag__src { display: inline-flex; min-height: 32px; align-items: center; }
	.flags__contact { display: grid; gap: 6px; }
	.deadline { display: grid; gap: var(--bk-s3); justify-items: start; }
	.deadline__row { display: flex; align-items: center; gap: var(--bk-s3); }
	.deadline__date { font-size: var(--bk-size-h2); font-weight: 600; letter-spacing: -0.01em; }
	.delivery { display: flex; gap: var(--bk-s2); align-items: end; flex-wrap: wrap; width: 100%; }
	.delivery .bk-field { flex: 1; min-width: 200px; }
	.trace-btn { background: none; border: 0; padding: 0; min-height: 44px; color: var(--bk-teal); font-weight: 600; cursor: pointer; text-decoration: underline; text-underline-offset: 4px; }
	.trace { margin: 0; padding-inline-start: 1.2em; display: grid; gap: 6px; font-size: var(--bk-size-small); }
	.facts { display: grid; grid-template-columns: max-content 1fr; gap: 6px var(--bk-s3); margin: 0 0 var(--bk-s2); align-items: baseline; }
	.facts dt { font-size: var(--bk-size-small); color: var(--bk-ink-2); }
	.facts dd { margin: 0; display: flex; flex-wrap: wrap; gap: 6px; align-items: baseline; }
	.fact { background: none; border: 0; padding: 2px 4px; margin: 0 -4px; border-radius: 4px; cursor: pointer; text-align: start; }
	.fact:hover, .fact:focus-visible { background: var(--bk-teal-wash); }
	.disclaimer { display: grid; gap: 4px; padding-block: var(--bk-s2); }
	@media (max-width: 960px) {
		.sheet-col { grid-column: 1 / -1; position: sticky; top: 0; max-height: 30vh; z-index: 5; box-shadow: 0 1px 0 var(--bk-rule); }
		.cards { grid-column: 1 / -1; }
		.bk-action { flex-wrap: wrap; }
	}
	@media (prefers-reduced-motion: reduce) { .sentence--pulse { animation: none; outline: 3px solid var(--bk-teal); } }
</style>
