<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '#lib/api.ts';
	import { app } from '#lib/state.svelte.ts';

	let cases = $state<Awaited<ReturnType<typeof api.cases>>>([]);
	let languages = $state<Record<string, string>>({});
	onMount(async () => {
		try {
			[cases, languages] = await Promise.all([
				api.cases(),
				api.languages().then((r) => Object.fromEntries(r.languages.map((l) => [l.code, l.native])))
			]);
		} catch {
			/* the layout shows the connection error */
		}
	});

	const steps = [
		['Photograph', 'Every letter the client brought, in one go.'],
		['Order', 'Deadlines computed by Swiss rules. Reminders linked to what they became.'],
		['Act', 'A reply to sign, and a page to take home in their language.']
	];
	const link = (c: (typeof cases)[number]) => (c.status === 'capturing' ? `/case/${c.id}/capture` : `/case/${c.id}`);
</script>

<svelte:head><title>Briefklar Desk</title></svelte:head>

<div class="bk-page">
	<section class="hero bk-grid">
		<div class="hero__text">
			<p class="bk-eyebrow">Help desk</p>
			<h1 class="hero__title">A bag of letters,<br />put in order.</h1>
			<p class="hero__lede bk-measure">
				Photograph what the client brought. Briefklar reads each letter, works out every deadline and prepares what
				happens next. Nothing leaves this device.
			</p>
		</div>
	</section>

	<section class="strip" aria-label="How it works">
		{#each steps as [title, text], index}
			<div class="step bk-rise" style:--i={index}>
				<span class="step__n" aria-hidden="true">{index + 1}</span>
				<h2 class="step__title">{title}</h2>
				<p class="bk-small">{text}</p>
			</div>
		{/each}
	</section>

	<section class="recent" aria-labelledby="recent-h">
		<h2 id="recent-h" class="recent__h">Open cases</h2>
		{#if cases.length === 0}
			<p class="bk-small">No case is open. Cases live in memory only and are wiped when you end them, or after two hours.</p>
		{:else}
			<ul class="recent__list">
				{#each cases as c}
					<li>
						<a href={link(c)}>
							<span lang={c.client_language}>{languages[c.client_language] ?? c.client_language}</span>
							<span class="bk-small">{c.letters} {c.letters === 1 ? 'letter' : 'letters'} · {c.status}{c.demo ? ' · demo' : ''}</span>
						</a>
					</li>
				{/each}
			</ul>
		{/if}
	</section>
</div>

<div class="bk-action bk-noprint">
	<a class="bk-btn bk-btn--primary bk-btn--large" href="/case/new">New case</a>
</div>

<style>
	.hero { padding-block: var(--bk-s7) var(--bk-s6); }
	.hero__text { grid-column: 1 / span 9; display: grid; gap: var(--bk-s4); }
	.hero__title { font-size: var(--bk-size-display); line-height: 1.02; }
	.hero__lede { font-size: 20px; color: var(--bk-ink-2); }
	.strip { display: grid; grid-template-columns: repeat(3, 1fr); border-block: 1px solid var(--bk-rule); }
	.step { padding: var(--bk-s5) var(--bk-s4) var(--bk-s5) 0; display: grid; gap: var(--bk-s2); align-content: start; }
	.step + .step { padding-inline-start: var(--bk-s4); border-inline-start: 1px solid var(--bk-rule); }
	.step__n { font-size: var(--bk-size-small); font-weight: 600; color: var(--bk-teal); font-variant-numeric: tabular-nums; }
	.step__title { font-size: var(--bk-size-h2); }
	.recent { padding-block-start: var(--bk-s6); display: grid; gap: var(--bk-s3); }
	.recent__h { font-size: var(--bk-size-body); }
	.recent__list { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--bk-s2); max-width: 560px; }
	.recent__list a { display: flex; justify-content: space-between; align-items: center; gap: var(--bk-s3); min-height: 52px; padding: 10px 16px;
		background: var(--bk-surface); border: 1px solid var(--bk-rule); border-radius: var(--bk-radius); color: var(--bk-ink); text-decoration: none; font-weight: 600; }
	.recent__list a:hover { border-color: var(--bk-teal); }
	@media (max-width: 960px) {
		.hero { padding-block: var(--bk-s5); }
		.hero__text { grid-column: 1 / -1; }
		.strip { grid-template-columns: 1fr; }
		.step + .step { padding-inline-start: 0; border-inline-start: 0; border-block-start: 1px solid var(--bk-rule); }
	}
</style>
