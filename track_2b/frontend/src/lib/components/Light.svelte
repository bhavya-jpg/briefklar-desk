<script lang="ts">
	import type { Light } from '#lib/api.ts';
	let { light }: { light: Light } = $props();
	const text: Record<Light, string> = {
		green: 'Checked: good',
		amber: 'Use with care',
		red: 'Weak: use simple German',
		unmeasured: 'Not measured yet'
	};
</script>

<!-- Shape and text carry the meaning, not colour alone. -->
<span class="light light--{light}">
	<span class="light__dot" aria-hidden="true"></span>{text[light]}
</span>

<style>
	.light { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; color: var(--bk-ink-2); }
	.light__dot { width: 10px; height: 10px; border-radius: 50%; border: 2px solid var(--bk-ink-2); background: transparent; flex: none; }
	.light--green .light__dot { background: var(--bk-green); border-color: var(--bk-green); }
	.light--amber .light__dot { background: var(--bk-amber); border-color: var(--bk-amber); border-radius: 2px; }
	.light--red .light__dot { background: var(--bk-red); border-color: var(--bk-red); border-radius: 0; transform: rotate(45deg); }
</style>
