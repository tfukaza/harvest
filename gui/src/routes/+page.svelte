<script lang="ts">
  import { onMount } from "svelte";
  import { fade } from "svelte/transition";
  import { wsState } from "$lib/ws";
  import SandboxCanvas from "$lib/SandboxCanvas.svelte";
  import ActivityPanel from "$lib/ActivityPanel.svelte";
  import type { SandboxSnapshot } from "$lib/types";

  let wsData = $derived($wsState);

  // First sandbox (matches previous behaviour)
  let sandbox: SandboxSnapshot | null = $derived(
    wsData.sandboxes.length > 0 ? wsData.sandboxes[0] : null
  );

  // View toggle — persisted across page refreshes
  type ViewMode = "graph" | "slack";
  let viewMode = $state<ViewMode>("graph");

  onMount(() => {
    const saved = localStorage.getItem("harvest_view_mode");
    if (saved === "graph" || saved === "slack") viewMode = saved;
  });

  function setViewMode(mode: ViewMode) {
    viewMode = mode;
    localStorage.setItem("harvest_view_mode", mode);
  }

  // Selected agent / channel (shared across both views)
  let selectedAgentId: string | null = $state(null);
  let selectedChannelId: string | null = $state(null);

  function handleAgentClick(agentId: string) {
    selectedAgentId = selectedAgentId === agentId ? null : agentId;
    selectedChannelId = null;
  }

  function handleChannelClick(channelId: string) {
    selectedChannelId = selectedChannelId === channelId ? null : channelId;
    selectedAgentId = null;
  }
</script>

<div class="flex flex-col h-screen overflow-hidden bg-[#fafafa] text-[#1d1c1d]">

  <!-- ===== Header ===== -->
  <header class="flex items-center gap-3 px-4 py-2.5 bg-white border-b border-gray-200 shrink-0 z-10">
    <!-- Harvest wordmark -->
    <span class="font-bold text-[16px] tracking-tight text-gray-800 select-none">Harvest</span>

    {#if sandbox}
      <span class="text-gray-300 select-none">·</span>
      <span class="text-[14px] text-gray-600 font-medium truncate">
        {sandbox.display_name || sandbox.sandbox_id}
      </span>
      <!-- Sandbox stats chips -->
      <div class="flex items-center gap-2 ml-1">
        <span class="text-[11px] text-gray-400 bg-gray-100 rounded px-1.5 py-px">{sandbox.agents.length} agent{sandbox.agents.length === 1 ? '' : 's'}</span>
        <span class="text-[11px] text-gray-400 bg-gray-100 rounded px-1.5 py-px">{sandbox.channels.length} channel{sandbox.channels.length === 1 ? '' : 's'}</span>
        {#if (sandbox.external_nodes ?? []).length > 0}
          <span class="text-[11px] text-blue-500 bg-blue-50 rounded px-1.5 py-px">{sandbox.external_nodes!.length} external</span>
        {/if}
      </div>
    {:else}
      <span class="text-[13px] text-gray-400 italic">No sandbox connected</span>
    {/if}

    <!-- Right side: view toggle + connection status -->
    <div class="ml-auto flex items-center gap-3 shrink-0">
      <!-- Segmented pill toggle -->
      <div class="flex items-center bg-gray-100 rounded-full p-0.5 gap-0.5">
        <button
          class="flex items-center gap-1.5 px-3 py-1 rounded-full text-[12px] font-medium transition-all duration-150
            {viewMode === 'graph'
              ? 'bg-white text-gray-800 shadow-sm'
              : 'text-gray-500 hover:text-gray-700'}"
          onclick={() => setViewMode("graph")}
        >
          <svg width="12" height="12" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="8" cy="3" r="2" fill="currentColor"/>
            <circle cx="3" cy="13" r="2" fill="currentColor"/>
            <circle cx="13" cy="13" r="2" fill="currentColor"/>
            <line x1="8" y1="5" x2="3" y2="11" stroke="currentColor" stroke-width="1.5"/>
            <line x1="8" y1="5" x2="13" y2="11" stroke="currentColor" stroke-width="1.5"/>
          </svg>
          Graph
        </button>
        <button
          class="flex items-center gap-1.5 px-3 py-1 rounded-full text-[12px] font-medium transition-all duration-150
            {viewMode === 'slack'
              ? 'bg-white text-gray-800 shadow-sm'
              : 'text-gray-500 hover:text-gray-700'}"
          onclick={() => setViewMode("slack")}
        >
          <svg width="12" height="12" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M2 2h12a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H5l-3 2V3a1 1 0 0 1 1-1z" fill="currentColor" fill-opacity="0.15" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
          </svg>
          Slack
        </button>
      </div>

      <!-- Connection status -->
      <div class="flex items-center gap-1.5">
        <span class="w-2 h-2 rounded-full {wsData.connected ? 'bg-emerald-500' : 'bg-red-400'}"></span>
        <span class="text-[12px] text-gray-400">{wsData.connected ? 'connected' : 'disconnected'}</span>
      </div>
    </div>
  </header>

  <!-- ===== Main content (full-width, toggled) ===== -->
  <div class="flex-1 relative min-h-0">
    {#if viewMode === "graph"}
      <div class="absolute inset-0" transition:fade={{ duration: 150 }}>
        <SandboxCanvas
          snapshot={sandbox}
          selectedAgentId={selectedAgentId}
          onAgentClick={handleAgentClick}
          onChannelClick={handleChannelClick}
        />
      </div>
    {:else}
      <div class="absolute inset-0" transition:fade={{ duration: 150 }}>
        <ActivityPanel
          snapshot={sandbox}
          connected={wsData.connected}
          lastUpdate={wsData.lastUpdate}
          typing={wsData.typing}
          selectedAgentId={selectedAgentId}
          selectedChannelId={selectedChannelId}
          open={true}
          onToggle={() => setViewMode("graph")}
        />
      </div>
    {/if}
  </div>
</div>
