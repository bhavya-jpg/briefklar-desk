<script lang="ts">
	import { STAGES, STAGE_STRING } from '#lib/api.ts';

	// The five reading steps, in the client's language, ticking one by one.
	let { stage, strings, language, lang, dir }: {
		stage: string | null;
		strings: Record<string, string>;
		language: string;
		lang: string;
		dir: 'ltr' | 'rtl';
	} = $props();
	const current = $derived(stage ? STAGES.indexOf(stage as (typeof STAGES)[number]) : -1);
</script>

<ol class="stages" {lang} {dir}>
	{#each STAGES as name, index}
		<li class:done={index < current} class:now={index === current}>
			<span class="tick" aria-hidden="true">{index < current ? '✓' : ''}</span>
			{strings[STAGE_STRING[name]].replace('{language}', language)}
		</li>
	{/each}
</ol>

<style>
	.stages { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; font-size: var(--bk-size-small); color: var(--bk-ink-2); }
	li { display: flex; align-items: center; gap: 8px; transition: color var(--bk-base) var(--bk-ease); }
	.tick { width: 16px; height: 16px; border-radius: 50%; border: 1.5px solid var(--bk-rule); display: inline-grid; place-items: center; font-size: 10px; flex: none;
		transition: background var(--bk-base) var(--bk-ease), border-color var(--bk-base) var(--bk-ease); }
	.done { color: var(--bk-ink); }
	.done .tick { background: var(--bk-teal); border-color: var(--bk-teal); color: var(--bk-on-teal); }
	.now { color: var(--bk-ink); font-weight: 600; }
	.now .tick { border-color: var(--bk-teal); }
</style>
