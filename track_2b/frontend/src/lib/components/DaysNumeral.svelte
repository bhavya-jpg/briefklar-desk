<script lang="ts">
	import { onMount, untrack } from 'svelte';

	// Large days-left numeral. Counts down once from the period length to the value (600 ms, ease-out).
	let { days, from = null, size = 56 }: { days: number; from?: number | null; size?: number } = $props();
	let shown = $state(untrack(() => days));

	onMount(() => {
		const start = from ?? days;
		const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
		if (reduced || start === days) return;
		const began = performance.now();
		let frame = 0;
		const tick = (now: number) => {
			const t = Math.min(1, (now - began) / 600);
			shown = Math.round(start + (days - start) * (1 - Math.pow(1 - t, 3)));
			if (t < 1) frame = requestAnimationFrame(tick);
		};
		frame = requestAnimationFrame(tick);
		return () => cancelAnimationFrame(frame);
	});
	$effect(() => {
		shown = days;
	});
</script>

<span class="numeral" style:font-size="{size}px" aria-hidden="true">{shown}</span>

<style>
	.numeral { font-weight: 600; line-height: 1; letter-spacing: -0.03em; font-variant-numeric: tabular-nums; }
</style>
