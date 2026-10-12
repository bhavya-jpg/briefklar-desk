<script lang="ts">
	import type { Evidence } from '#lib/api.ts';

	// The page image with a highlight layer. Spans named in `active` glow teal and scroll into view;
	// clicking a span reports its id so the matching sentence can pulse.
	let { pages, evidence, active = [], onpick = () => {}, scan = false }: {
		pages: { id: string; url: string; width: number; height: number }[];
		evidence: Evidence[];
		active?: string[];
		onpick?: (id: string) => void;
		scan?: boolean;
	} = $props();

	let root: HTMLElement | undefined = $state();

	$effect(() => {
		if (!active.length || !root) return;
		const target = root.querySelector<HTMLElement>(`[data-span="${active[0]}"]`);
		const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
		target?.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: reduced ? 'auto' : 'smooth' });
	});
</script>

<div class="pages" bind:this={root}>
	{#each pages as page, index (page.id)}
		<div class="sheet" style:aspect-ratio="{page.width} / {page.height}">
			<img src={page.url} alt="Page {index + 1} of the letter" width={page.width} height={page.height} />
			{#if scan}<span class="scan" aria-hidden="true"></span>{/if}
			{#each evidence.filter((e) => e.page === index && e.bbox) as item (item.id)}
				{@const [x0, y0, x1, y1] = item.bbox!}
				<button
					type="button"
					class="span"
					class:on={active.includes(item.id)}
					data-span={item.id}
					style:left="{x0 * 100}%"
					style:top="{y0 * 100}%"
					style:width="{(x1 - x0) * 100}%"
					style:height="{(y1 - y0) * 100}%"
					aria-label="Source on page {index + 1}: {item.text}"
					aria-pressed={active.includes(item.id)}
					onclick={() => onpick(item.id)}
				></button>
			{/each}
		</div>
	{/each}
</div>

<style>
	.pages { display: grid; gap: var(--bk-s3); }
	.sheet { position: relative; background: #fff; border: 1px solid var(--bk-rule); border-radius: 6px; overflow: hidden; }
	img { width: 100%; height: 100%; object-fit: contain; }
	.span { position: absolute; padding: 0; margin: -3px; box-sizing: content-box; border: 3px solid transparent; background: transparent; border-radius: 3px; cursor: pointer;
		transition: background var(--bk-fast) var(--bk-ease), box-shadow var(--bk-fast) var(--bk-ease); }
	.span:hover, .span:focus-visible { background: rgba(15, 110, 106, 0.1); outline-offset: 0; }
	.span.on { background: rgba(15, 110, 106, 0.18); box-shadow: 0 0 0 1px #0f6e6a; }
	.scan { position: absolute; inset-inline: 0; top: 0; height: 2px; background: #0f6e6a; opacity: 0.7; animation: scan 900ms linear infinite; }
	@keyframes scan { from { transform: translateY(0); } to { transform: translateY(60vh); } }
	@media (prefers-reduced-motion: reduce) { .scan { display: none; } }
</style>
