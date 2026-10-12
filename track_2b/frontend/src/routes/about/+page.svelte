<script lang="ts">
	import { onMount } from 'svelte';
	import { api, type Language } from '#lib/api.ts';
	import Light from '#lib/components/Light.svelte';

	type Summary = {
		provenance: { model_outputs: string; note: string };
		letters: number;
		cases: number;
		systems: Record<string, { status: string; label: string; metrics?: Record<string, number | null> }>;
	};
	let languages = $state<Language[]>([]);
	let summary = $state<Summary | null>(null);

	onMount(() => {
		api.languages().then((r) => (languages = r.languages)).catch(() => {});
		fetch('/api/eval').then((r) => (r.ok ? r.json() : null)).then((s) => (summary = s)).catch(() => {});
		const observer = new IntersectionObserver(
			(entries) => {
				for (const entry of entries) if (entry.isIntersecting) entry.target.classList.add('in');
			},
			{ threshold: 0.2 }
		);
		document.querySelectorAll('.reveal').forEach((el) => observer.observe(el));
		return () => observer.disconnect();
	});

	const numbers = [
		['10', 'days to object to a payment order. After that, the creditor can go on to seizure.'],
		['13', 'client languages, each with a simple-German twin for the counsellor.'],
		['0', 'bytes leave the building. The model runs on the help desk’s own machine.']
	];
	const steps = [
		['Photograph', 'The counsellor photographs every letter in the bag. Pages are cropped and straightened on the device.'],
		['Order', 'Apertus reads each letter. Code, not the model, computes each deadline under Swiss rules and links reminders to the payment order they became.'],
		['Act', 'An objection ready to sign, a one-page handout in the client’s language, a German note for the file. Then the case is wiped.']
	];
	const signs = [
		'The sender presents itself as a Swiss authority, but the account is abroad.',
		'The letter cites a legal basis that does not fit the situation.',
		'The phone number on the letter differs from the official directory.',
		'Payment is demanded through gift cards or a cash transfer.'
	];
	const modes = [
		['Air-gapped workstation', 'One machine with one GPU. Weights are on disk. No network at runtime.', 'primary'],
		['On-premise server', 'The same containers on an office server. Browsers on the office network.', ''],
		['Sovereign Swiss cloud', 'Point one setting at a Swiss-hosted Apertus endpoint. Nothing else changes.', '']
	];
	const metricRows = [
		['deadline_accuracy', 'Deadline, exact date'],
		['letter_type_accuracy', 'Letter type'],
		['red_flag_recall', 'Warning signs, recall'],
		['triage_tau', 'Triage order (Kendall τ)']
	];
	const fmt = (v: number | null | undefined) => (v === null || v === undefined ? '–' : v.toFixed(2));
</script>

<svelte:head><title>About · Briefklar Desk</title></svelte:head>

<div class="about">
	<section class="hero">
		<div class="hero__copy">
			<h1>Every letter.<br />Every deadline.<br /><span class="accent">In their language.</span></h1>
			<p class="hero__sub">The letter co-pilot Swiss help desks are allowed to use.</p>
			<div class="hero__btns">
				<a class="bk-btn bk-btn--primary bk-btn--large" href="#run">Run it in your office</a>
				<a class="bk-btn bk-btn--large" href="#numbers">See the numbers</a>
			</div>
		</div>
		<div class="pile" aria-hidden="true">
			{#each [['2', 'Warning signs', true], ['9', 'Payment order', false], ['13', 'School notice', false], ['21', 'Invoice', false], ['34', 'Tax assessment', false]] as [n, label, flag], i}
				<div class="pile__card" class:pile__card--flag={flag} style:--i={i}>
					<span class="pile__n">{n}</span><span>{label}</span>
				</div>
			{/each}
		</div>
	</section>

	<section class="big">
		{#each numbers as [n, text]}
			<div class="big__row reveal">
				<span class="big__n">{n}</span>
				<p>{text}</p>
			</div>
		{/each}
	</section>

	<section class="block">
		<p class="bk-eyebrow reveal">How it works</p>
		<div class="steps">
			{#each steps as [title, text], i}
				<div class="reveal" style:--i={i}>
					<span class="steps__n">0{i + 1}</span>
					<h2>{title}</h2>
					<p>{text}</p>
				</div>
			{/each}
		</div>
	</section>

	<section class="block warn">
		<p class="bk-eyebrow reveal">Warning signs</p>
		<h2 class="warn__h reveal">Some letters only look official. Briefklar shows why, line by line.</h2>
		<ol class="warn__list">
			{#each signs as sign, i}
				<li class="reveal" style:--i={i}>{sign}</li>
			{/each}
		</ol>
		<p class="bk-small bk-measure reveal">It lists evidence and the official contact from a local directory. It never says a letter is fake or genuine: that call stays with the counsellor.</p>
	</section>

	<section class="block" id="numbers">
		<p class="bk-eyebrow reveal">Measured, not claimed</p>
		<h2 class="reveal">Swiss Letters Bench: 150 synthetic letters, 20 case bundles, gold computed by code.</h2>
		{#if summary}
			<p class="bk-banner reveal">{summary.provenance.note}</p>
			<div class="table-wrap reveal">
				<table>
					<thead>
						<tr><th scope="col">System</th>{#each metricRows as [, label]}<th scope="col">{label}</th>{/each}</tr>
					</thead>
					<tbody>
						{#each Object.entries(summary.systems) as [key, system]}
							<tr class:ours={key === 'BK'}>
								<th scope="row">{key} · {system.label}</th>
								{#each metricRows as [metric]}
									<td>{system.status === 'ok' ? fmt(system.metrics?.[metric]) : 'not run'}</td>
								{/each}
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			<p class="bk-small reveal">Subset shown: {summary.letters} letters in {summary.cases} cases (data/bench_small).</p>
		{:else}
			<p class="bk-banner reveal">No evaluation has been run on this build yet.</p>
		{/if}
		<div class="lights reveal">
			{#each languages as language}
				<div class="lights__tile">
					<span class="lights__native" lang={language.code} dir={language.dir}>{language.native}</span>
					<Light light={language.light} />
				</div>
			{/each}
		</div>
		<p class="bk-small bk-measure reveal">A language is green only when its back-translation score is high and native speakers rated it. A language nobody checked can never be green.</p>
	</section>

	<section class="block sovereign">
		<p class="bk-eyebrow reveal">Sovereign by design</p>
		<div class="sovereign__grid">
			<svg class="reveal" viewBox="0 0 420 260" role="img" aria-label="A closed box: browser, orchestrator, tools and Apertus run inside the help desk. No arrow leaves the box.">
				<rect x="10" y="10" width="400" height="240" rx="14" fill="none" stroke="currentColor" stroke-width="2" />
				<text x="28" y="40" font-size="13" font-weight="600" fill="currentColor">Help desk · no network at runtime</text>
				{#each [['Browser', 34, 70], ['Orchestrator', 164, 70], ['Apertus 1.5 8B', 294, 70], ['OCR · QR', 34, 160], ['Deadline rules', 164, 160], ['Directory', 294, 160]] as [label, x, y]}
					<rect x={x} y={y} width="100" height="56" rx="8" fill="var(--bk-surface)" stroke="currentColor" stroke-width="1" />
					<text x={Number(x) + 50} y={Number(y) + 33} font-size="12" text-anchor="middle" fill="currentColor">{label}</text>
				{/each}
				<path d="M134 98h30M264 98h30M214 126v34M84 160v-34M344 160v-34" stroke="var(--bk-teal)" stroke-width="2" fill="none" />
			</svg>
			<ul class="modes">
				{#each modes as [title, text, tag], i}
					<li class="reveal" style:--i={i}>
						<h3>{title}{#if tag}<span class="bk-chip bk-chip--teal">{tag}</span>{/if}</h3>
						<p>{text}</p>
					</li>
				{/each}
			</ul>
		</div>
	</section>

	<section class="block" id="run">
		<p class="bk-eyebrow reveal">Open</p>
		<h2 class="reveal">One command. One GPU. No licence fees.</h2>
		<pre class="reveal"><code>make run        # replay mode, no GPU: the demo case from cached answers
make gpu-up     # local vLLM with Apertus 1.5 8B + the app</code></pre>
		<p class="bk-measure reveal">Code under Apache-2.0. Dataset under CDLA-Permissive-2.0. Report under CC-BY-4.0. Fonts under the SIL Open Font Licence, served from this machine.</p>
		<p class="bk-small bk-measure reveal">Briefklar explains letters. It does not give legal advice, and it does not replace the counsellor.</p>
	</section>
</div>

<style>
	.about { padding-inline: 72px; max-width: 1560px; margin-inline: auto; padding-block-end: var(--bk-s7); }
	.hero { min-height: calc(100vh - 80px); display: grid; grid-template-columns: 7fr 5fr; gap: var(--bk-s5); align-items: center; padding-block: var(--bk-s6); }
	.hero h1 { font-size: clamp(44px, 7.4vw, 112px); line-height: 0.98; letter-spacing: -0.035em; }
	.accent { color: var(--bk-teal); }
	.hero__sub { font-size: clamp(19px, 1.8vw, 26px); color: var(--bk-ink-2); margin-block: var(--bk-s4) var(--bk-s5); max-width: 28ch; }
	.hero__btns { display: flex; gap: var(--bk-s3); flex-wrap: wrap; }
	.pile { position: relative; height: 420px; }
	.pile__card { position: absolute; inset-inline: 0; top: calc(var(--i) * 78px); display: flex; align-items: center; gap: var(--bk-s3); height: 66px; padding-inline: var(--bk-s4);
		background: var(--bk-surface); border: 1px solid var(--bk-rule); border-radius: var(--bk-radius); font-weight: 600;
		animation: assemble 8s var(--bk-ease) infinite; animation-delay: calc(var(--i) * 120ms); }
	.pile__card--flag { border-inline-start: 4px solid var(--bk-red); }
	.pile__n { font-size: 32px; letter-spacing: -0.03em; font-variant-numeric: tabular-nums; min-width: 48px; }
	@keyframes assemble {
		0% { opacity: 0; transform: translate(calc((var(--i) - 2) * 26px), calc((2 - var(--i)) * 70px)) rotate(calc((var(--i) - 2) * 5deg)); }
		8%, 14% { opacity: 1; transform: translate(calc((var(--i) - 2) * 26px), calc((2 - var(--i)) * 70px)) rotate(calc((var(--i) - 2) * 5deg)); }
		26%, 92% { opacity: 1; transform: none; }
		100% { opacity: 0; transform: none; }
	}
	.big { border-block-start: 1px solid var(--bk-rule); }
	.big__row { display: grid; grid-template-columns: 5fr 7fr; gap: var(--bk-s5); align-items: center; min-height: 62vh; border-block-end: 1px solid var(--bk-rule); }
	.big__n { font-size: clamp(120px, 24vw, 360px); font-weight: 600; line-height: 0.85; letter-spacing: -0.06em; font-variant-numeric: tabular-nums; }
	.big__row p { font-size: clamp(22px, 2.6vw, 40px); line-height: 1.15; letter-spacing: -0.02em; max-width: 20ch; text-wrap: balance; }
	.block { padding-block: var(--bk-s7); display: grid; gap: var(--bk-s4); }
	.block > h2 { font-size: clamp(28px, 3.6vw, 56px); line-height: 1.05; letter-spacing: -0.03em; max-width: 22ch; }
	.steps { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--bk-s5); }
	.steps > div { display: grid; gap: var(--bk-s2); align-content: start; border-block-start: 2px solid var(--bk-ink); padding-block-start: var(--bk-s3); }
	.steps__n { font-size: var(--bk-size-small); font-weight: 600; color: var(--bk-teal); }
	.steps h2 { font-size: clamp(28px, 3vw, 44px); letter-spacing: -0.03em; }
	.steps p { color: var(--bk-ink-2); }
	.warn__h { font-size: clamp(28px, 3.6vw, 56px); line-height: 1.05; letter-spacing: -0.03em; max-width: 22ch; }
	.warn__list { list-style: none; margin: var(--bk-s3) 0; padding: 0; display: grid; gap: var(--bk-s2); max-width: 760px; counter-reset: sign; }
	.warn__list li { counter-increment: sign; padding: var(--bk-s3) var(--bk-s4); background: var(--bk-red-wash); border-inline-start: 4px solid var(--bk-red); border-radius: var(--bk-radius); font-size: 20px; }
	.table-wrap { overflow-x: auto; }
	table { border-collapse: collapse; width: 100%; max-width: 980px; font-variant-numeric: tabular-nums; }
	th, td { text-align: start; padding: 12px 16px 12px 0; border-block-end: 1px solid var(--bk-rule); font-weight: 500; }
	thead th { font-size: var(--bk-size-small); color: var(--bk-ink-2); font-weight: 600; }
	tbody th { font-weight: 600; }
	tr.ours th, tr.ours td { color: var(--bk-teal); font-weight: 600; }
	.lights { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: var(--bk-s2); margin-block-start: var(--bk-s4); }
	.lights__tile { display: grid; gap: 4px; padding: var(--bk-s3); background: var(--bk-surface); border: 1px solid var(--bk-rule); border-radius: var(--bk-radius); }
	.lights__native { font-size: 20px; font-weight: 600; }
	.sovereign__grid { display: grid; grid-template-columns: 6fr 6fr; gap: var(--bk-s6); align-items: center; }
	.sovereign svg { width: 100%; height: auto; color: var(--bk-ink); }
	.modes { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--bk-s4); }
	.modes h3 { font-size: var(--bk-size-h2); display: flex; gap: var(--bk-s2); align-items: center; flex-wrap: wrap; letter-spacing: -0.01em; }
	.modes p { color: var(--bk-ink-2); }
	pre { margin: 0; padding: var(--bk-s4); background: var(--bk-ink); color: var(--bk-paper); border-radius: var(--bk-radius); overflow-x: auto; font-family: var(--bk-font-mono); font-size: 15px; line-height: 1.7; }
	.reveal { opacity: 0; transform: translateY(24px); transition: opacity var(--bk-slow) var(--bk-ease), transform var(--bk-slow) var(--bk-ease); transition-delay: calc(var(--i, 0) * 80ms); }
	:global(.reveal.in) { opacity: 1; transform: none; }
	@media (prefers-reduced-motion: reduce) {
		.reveal { opacity: 1; transform: none; transition: none; }
		.pile__card { animation: none; }
	}
	@media (max-width: 960px) {
		.about { padding-inline: var(--bk-s3); }
		.hero { grid-template-columns: 1fr; min-height: 0; }
		.pile { height: 400px; }
		.big__row { grid-template-columns: 1fr; min-height: 0; padding-block: var(--bk-s6); gap: var(--bk-s3); }
		.steps, .sovereign__grid { grid-template-columns: 1fr; }
	}
</style>
