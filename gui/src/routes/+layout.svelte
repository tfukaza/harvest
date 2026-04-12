<script>
  import { onMount } from "svelte";
  import { initWs } from "$lib/ws";
  import "../app.css";

  onMount(() => {
    initWs();
  });
</script>

<slot />
