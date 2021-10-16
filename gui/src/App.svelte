<script>

	export let name;
	const positions = (async () => {
		const response = await fetch('http://localhost:11111/api/crypto_positions');
    	const ret = await response.json();
		return ret;
	})()
</script>

<main>
	<h1>Hello {name}!!!</h1>
	{#await positions}
		<p>Loading...</p>
	{:then data}
		<ul>
		{#each data as position}
			<li>{position.symbol}</li>
		{/each}
		</ul>
	{:catch error}
		<p>Error: {error}</p>
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