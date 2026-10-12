<script lang="ts">
	import { onMount } from 'svelte';
	import { flip } from 'svelte/animate';
	import { page } from '$app/state';
	import { api, daysLabel, watchCase, type Case, type Letter, type Thread } from '#lib/api.ts';
	import DaysNumeral from '#lib/components/DaysNumeral.svelte';
	import StageList from '#lib/components/StageList.svelte';

	const id = $derived(page.params.id!);
	let data = $state<Case | null>(null);
	let error = $state('');
	let notices = $state<string[]>([]);
	let flipMs = $state(420);

	async function refresh() {
		try {
			data = await api.getCase(id);
		} catch (e) {
			error = (e as Error).message;
		}
	}

	onMount(() => {
		if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) flipMs = 0;
		refresh();
		let timer: ReturnType<typeof setTimeout>;
		const close = watchCase(id, (event, payload) => {
			if (event === 'error' && !payload.letter_id && typeof payload.message === 'string') notices = [payload.message];
			clearTimeout(timer);
			timer = setTimeout(refresh, 60);
		});
		return () => {
			close();
			clearTimeout(timer);
		};
	});

	const byId = $derived(new Map((data?.letters ?? []).map((l) => [l.id, l])));
	const ordered = $derived((data?.order.length ? data.order : (data?.letters ?? []).map((l) => l.id)).map((i) => byId.get(i)!).filter(Boolean));
	const flagged = (l: Letter) => (l.verification?.red_flags.length ?? 0) > 0;
	const liveThreads = $derived((data?.threads ?? []).filter((t) => !t.rejected));
	const confirmed = $derived(liveThreads.filter((t) => t.confirmed));
	const open = $derived(liveThreads.filter((t) => !t.confirmed));

	// The most recent letter of a confirmed thread is the one that counts now.
	const superseded = $derived.by(() => {
		const out = new Set<string>();
		for (const thread of confirmed) {
			const members = thread.letter_ids.map((i) => byId.get(i)).filter((l): l is Letter => !!l?.facts);
			if (members.length < 2) continue;
			const head = members.reduce((a, b) => ((b.facts!.letter_date ?? '') >= (a.facts!.letter_date ?? '') ? b : a));
			for (const m of members) if (m.id !== head.id) out.add(m.id);
		}
		return out;
	});

	type Group = { key: string; thread: Thread | null; letters: Letter[] };
	const groups = $derived.by(() => {
		const seen = new Set<string>();
		const out: Group[] = [];
		for (const letter of ordered) {
			if (seen.has(letter.id)) continue;
			const thread = confirmed.find((t) => t.letter_ids.includes(letter.id)) ?? null;
			const letters = thread ? ordered.filter((l) => thread.letter_ids.includes(l.id)) : [letter];
			for (const l of letters) seen.add(l.id);
			out.push({ key: thread ? thread.id : letter.id, thread, letters });
		}
		return out;
	});
	const timeline = $derived(ordered.filter((l) => l.status === 'done' && !superseded.has(l.id) && l.verification?.deadline));
	const working = $derived(data?.status === 'processing');
	const doneCount = $derived((data?.letters ?? []).filter((l) => l.status === 'done').length);

	function needsCheck(letter: Letter) {
		return Object.values(letter.verification?.field_checks ?? {}).some((v) => v !== 'match');
	}
	async function decide(thread: Thread, yes: boolean) {
		data = await api.confirmThread(id, thread.id, yes);
	}
	async function retry(letter: Letter) {
		await api.retry(letter.id);
		refresh();
	}
	async function skip(letter: Letter) {
		data = await api.skip(letter.id);
	}
	const sender = (l: Letter) => l.facts?.sender_name ?? 'Sender not found';
</script>

<svelte:head><title>Case board · Briefklar Desk</title></svelte:head>

<div class="bk-page">
	{#if error}
		<p class="bk-banner bk-banner--error" role="alert">{error} <a href="/">Back to start</a></p>
	{:else if data}
		<header class="head">
			<div>
				<p class="bk-eyebrow">Case board · <span lang={data.language.code}>{data.language.native}</span> · {data.canton}</p>
				<h1>
					{#if working}Reading {data.letters.length} letters…{:else}{data.letters.length} letters, in order of urgency{/if}
				</h1>
			</div>
			<p class="bk-small asof">
				Days are counted from {data.today_display}{data.demo ? ' (demo case, date fixed)' : ''}.
				<span aria-live="polite">{working ? `${doneCount} of ${data.letters.length} read.` : ''}</span>
			</p>
		</header>

		{#each notices as notice}<p class="bk-banner" role="status">{notice}</p>{/each}

		{#if data.creditor_totals.length}
			<section class="totals" aria-label="Open total per creditor">
				{#each data.creditor_totals as total}
					<div class="total">
						<span class="bk-small">{total.creditor}</span>
						<span class="total__amount">{total.display}</span>
					</div>
				{/each}
				<p class="bk-small totals__note">Open per creditor. A matter counts once, at its latest letter. Letters with warning signs are not counted.</p>
			</section>
		{/if}

		<div class="bk-grid board">
			<section class="timeline" aria-labelledby="tl-h">
				<h2 id="tl-h" class="col-h">Deadlines</h2>
				{#if timeline.length === 0}
					<p class="bk-small">{working ? 'Deadlines appear here as letters are read.' : 'No letter in this case sets a deadline.'}</p>
				{/if}
				<ol class="tl">
					{#each timeline as letter, index (letter.id)}
						{@const d = letter.verification!.deadline!}
						<li class="tl__item" class:tl__item--flag={flagged(letter)} animate:flip={{ duration: flipMs }} title={letter.priority_reason ?? undefined}>
							<a href="/case/{id}/letter/{letter.id}" class="tl__link">
								<span class="tl__n" class:tl__n--late={d.days_left !== null && d.days_left < 0}>
									{#if d.days_left !== null}
										<DaysNumeral days={Math.abs(d.days_left)} from={index === 0 ? 10 : null} size={index === 0 ? 56 : 32} />
									{:else}
										<span class="tl__q" aria-hidden="true">?</span>
									{/if}
								</span>
								<span class="tl__text">
									<span class="tl__when">
										{#if d.due_date}{letter.due_display} · {daysLabel(d.days_left)}{:else}Delivery date needed{/if}
									</span>
									<span class="tl__what">{letter.type_label}{letter.amount_display ? ` · ${letter.amount_display}` : ''}</span>
									<span class="bk-small">{sender(letter)}</span>
								</span>
							</a>
						</li>
					{/each}
				</ol>
			</section>

			<section class="threads" aria-labelledby="th-h">
				<h2 id="th-h" class="col-h">Letters</h2>
				{#each open as thread (thread.id)}
					<div class="ask">
						<p>
							<strong>Do these belong together?</strong>
							{thread.letter_ids.map((i) => byId.get(i)?.type_label ?? 'Letter').join(' + ')}.
							<span class="bk-small">Suggested by the model: {thread.reason}. No shared reference, account or amount was found.</span>
						</p>
						<div class="ask__btns">
							<button class="bk-btn bk-btn--quiet" onclick={() => decide(thread, true)}>Yes, link them</button>
							<button class="bk-btn bk-btn--quiet" onclick={() => decide(thread, false)}>No</button>
						</div>
					</div>
				{/each}

				<div class="stacks">
					{#each groups as group, g (group.key)}
						<div class="stack" class:stack--thread={group.thread} animate:flip={{ duration: flipMs }}>
							{#if group.thread}
								<p class="stack__why bk-small"><span class="stack__dot" aria-hidden="true"></span>Linked: {group.thread.reason}</p>
							{/if}
							{#each group.letters as letter, n (letter.id)}
								{@const d = letter.verification?.deadline}
								<article class="card bk-rise" class:card--flag={flagged(letter)} class:card--old={superseded.has(letter.id)} style:--i={g + n}>
									{#if letter.status === 'done' && letter.facts}
										<a class="card__link" href="/case/{id}/letter/{letter.id}">
											<span class="card__top">
												<span class="card__type">{letter.type_label}</span>
												{#if letter.amount_display}<span class="card__amount">{letter.amount_display}</span>{/if}
											</span>
											<span class="bk-small">{sender(letter)}{letter.facts.creditor_name ? ` · for ${letter.facts.creditor_name}` : ''}</span>
											<span class="card__chips">
												{#if flagged(letter)}<span class="bk-chip bk-chip--red">Warning signs · {letter.verification!.red_flags.length}</span>{/if}
												{#if d?.due_date}
													<span class="bk-chip" class:bk-chip--amber={!superseded.has(letter.id) && d.days_left !== null && d.days_left <= 10}>
														{letter.due_display} · {daysLabel(d.days_left)}
													</span>
												{:else if d?.needs_delivery_date}
													<span class="bk-chip bk-chip--amber">Date needed</span>
												{:else}
													<span class="bk-chip">No deadline</span>
												{/if}
												{#if d && !d.verified_rule && d.due_date}<span class="bk-chip bk-chip--amber">Rule unverified</span>{/if}
												{#if needsCheck(letter)}<span class="bk-chip bk-chip--amber">Check values</span>{/if}
												{#if letter.explanation?.low_confidence}<span class="bk-chip bk-chip--amber">Check language</span>{/if}
												{#if superseded.has(letter.id)}<span class="bk-chip">Earlier letter</span>{/if}
											</span>
										</a>
									{:else if letter.status === 'failed'}
										<div class="card__body">
											<p class="card__type">Letter not read</p>
											<p class="bk-small">{letter.error}</p>
											<div class="ask__btns">
												<button class="bk-btn bk-btn--quiet" onclick={() => retry(letter)}>Retry</button>
												<button class="bk-btn bk-btn--quiet" onclick={() => skip(letter)}>Skip</button>
											</div>
										</div>
									{:else if letter.status === 'skipped'}
										<div class="card__body"><p class="card__type">Skipped</p><p class="bk-small">This letter was left out.</p></div>
									{:else}
										<div class="card__body card__body--work">
											<img class="card__thumb" src={letter.pages[0]?.url} alt="" />
											<StageList stage={letter.stage} strings={data.strings} language={data.language.native} lang={data.language.code} dir={data.language.dir} />
										</div>
									{/if}
								</article>
							{/each}
						</div>
					{/each}
				</div>
			</section>
		</div>
	{:else}
		<p class="bk-small" aria-busy="true">Loading the case…</p>
	{/if}
</div>

{#if data}
	<div class="bk-action bk-noprint">
		<a class="bk-btn bk-btn--quiet" href="/api/cases/{id}/case-note.pdf" target="_blank" rel="noopener">Case note (PDF)</a>
		<a class="bk-btn bk-btn--primary bk-btn--large" href="/case/{id}/handout" aria-disabled={working}>Handout</a>
	</div>
{/if}

<style>
	.head { display: flex; justify-content: space-between; align-items: end; gap: var(--bk-s4); flex-wrap: wrap; padding-block: var(--bk-s5) var(--bk-s4); }
	.head > div { display: grid; gap: var(--bk-s2); }
	.totals { display: flex; flex-wrap: wrap; gap: var(--bk-s3) var(--bk-s6); padding-block: var(--bk-s3); border-block: 1px solid var(--bk-rule); margin-block-end: var(--bk-s5); }
	.total { display: grid; }
	.total__amount { font-size: var(--bk-size-h2); font-weight: 600; font-variant-numeric: tabular-nums; letter-spacing: -0.01em; }
	.totals__note { flex-basis: 100%; }
	.col-h { font-size: var(--bk-size-small); font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--bk-ink-2); margin-block-end: var(--bk-s3); }
	.timeline { grid-column: 1 / span 5; }
	.threads { grid-column: 6 / span 7; }
	.tl { list-style: none; margin: 0; padding: 0; border-inline-start: 1px solid var(--bk-rule); }
	.tl__item { position: relative; }
	.tl__item::before { content: ''; position: absolute; inset-inline-start: -5px; top: 28px; width: 9px; height: 9px; border-radius: 50%; background: var(--bk-ink); }
	.tl__item--flag::before { background: var(--bk-red); border-radius: 0; transform: rotate(45deg); }
	.tl__link { display: grid; grid-template-columns: 88px 1fr; gap: var(--bk-s3); align-items: center; padding: var(--bk-s3) var(--bk-s3) var(--bk-s3) var(--bk-s4); color: var(--bk-ink); text-decoration: none; border-radius: var(--bk-radius); min-height: 64px; }
	.tl__link:hover { background: var(--bk-surface); }
	.tl__n { text-align: end; color: var(--bk-ink); }
	.tl__n--late { color: var(--bk-ink-2); }
	.tl__q { font-size: 32px; font-weight: 600; color: var(--bk-amber); line-height: 1; }
	.tl__text { display: grid; }
	.tl__when { font-weight: 600; }
	.tl__what { color: var(--bk-ink); }
	.stacks { display: grid; gap: var(--bk-s4); }
	.stack { display: grid; gap: 0; }
	.stack--thread { border-inline-start: 1px solid var(--bk-ink); padding-inline-start: var(--bk-s3); }
	.stack--thread .card + .card { margin-block-start: -1px; border-start-start-radius: 0; border-start-end-radius: 0; }
	.stack--thread .card:not(:last-child) { border-end-start-radius: 0; border-end-end-radius: 0; }
	.stack__why { display: flex; align-items: center; gap: 8px; padding-block-end: var(--bk-s2); }
	.stack__dot { width: 7px; height: 7px; border-radius: 50%; background: var(--bk-ink); margin-inline-start: calc(-1 * var(--bk-s3) - 4px); }
	.card { background: var(--bk-surface); border: 1px solid var(--bk-rule); border-radius: var(--bk-radius); }
	.card--flag { border-inline-start: 4px solid var(--bk-red); }
	.card--old { background: transparent; }
	.card__link, .card__body { display: grid; gap: 6px; padding: var(--bk-s3) var(--bk-s4); color: var(--bk-ink); text-decoration: none; border-radius: inherit; }
	.card__link:hover { background: var(--bk-teal-wash); }
	.card__top { display: flex; justify-content: space-between; align-items: baseline; gap: var(--bk-s3); }
	.card__type { font-weight: 600; font-size: 19px; letter-spacing: -0.01em; }
	.card__amount { font-weight: 600; font-variant-numeric: tabular-nums; white-space: nowrap; }
	.card__chips { display: flex; flex-wrap: wrap; gap: 6px; padding-block-start: 4px; }
	.card__body--work { grid-template-columns: 56px 1fr; align-items: center; gap: var(--bk-s3); }
	.card__thumb { width: 56px; aspect-ratio: 210 / 297; object-fit: cover; object-position: top; border: 1px solid var(--bk-rule); border-radius: 4px; }
	.ask { border: 1.5px dashed var(--bk-ink-2); border-radius: var(--bk-radius); padding: var(--bk-s3) var(--bk-s4); margin-block-end: var(--bk-s4); display: grid; gap: var(--bk-s3); }
	.ask__btns { display: flex; gap: var(--bk-s2); flex-wrap: wrap; }
	[aria-disabled='true'] { opacity: 0.5; pointer-events: none; }
	@media (max-width: 960px) {
		.timeline, .threads { grid-column: 1 / -1; }
		.tl__link { grid-template-columns: 64px 1fr; padding-inline-start: var(--bk-s3); }
	}
</style>
