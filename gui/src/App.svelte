<script>
import { dataset_dev } from "svelte/internal";

	export let name;
	const positions = (async () => {
		const response = await fetch('127.0.0.1:11111/crypto_positions')
    	return await response.json()
	})()
</script>

<main>
	<h1>Hello {name}!!!</h1>
	{#await positions}
		<p>Loading...</p>
	{:then data}
		<p>data.message</p>
	{:catch error}
		<p>Error</p>
	{/await}
	<p></p>
</main>

<style>
	main {
		text-align: center;
		padding: 1em;
		max-width: 240px;
		margin: 0 auto;
	}

	h1 {
		color: #ff3e00;
		text-transform: uppercase;
		font-size: 4em;
		font-weight: 100;
	}

	@media (min-width: 640px) {
		main {
			max-width: none;
		}
	}
</style>