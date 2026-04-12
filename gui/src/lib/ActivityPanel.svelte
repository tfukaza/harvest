<script lang="ts">
  import { marked } from "marked";
  import type { SandboxSnapshot, MessageInfo, AgentInfo } from "./types";
  import { sendAdminMessage, wsState } from "./ws";
  import AgentDetailSidebar from "./AgentDetailSidebar.svelte";

  interface Props {
    snapshot: SandboxSnapshot | null;
    connected: boolean;
    lastUpdate: string | null;
    typing: Map<string, Set<string>>;
    /** Agent to pre-select / highlight in the panel */
    selectedAgentId?: string | null;
    /** Channel to pre-select in the panel */
    selectedChannelId?: string | null;
    /** Whether the panel is visible */
    open: boolean;
    onToggle: () => void;
  }

  let {
    snapshot,
    connected,
    lastUpdate,
    typing,
    selectedAgentId = null,
    selectedChannelId = null,
    open,
    onToggle,
  }: Props = $props();

  marked.setOptions({ breaks: true, gfm: true });

  // Known IDs for mention/channel highlighting
  let agentIds: Set<string> = $derived(
    new Set(snapshot ? snapshot.agents.map((a) => a.agent_id) : [])
  );
  let channelIds: Set<string> = $derived(
    new Set(snapshot ? snapshot.channels.map((c) => c.channel_id) : [])
  );

  // Currently selected channel (null = all messages)
  // Sync with parent-provided selectedChannelId
  let selectedChannel: string | null = $state(null);
  $effect(() => {
    if (selectedChannelId !== null) selectedChannel = selectedChannelId;
  });
  // Also filter by agent when one is selected in canvas
  let filterAgentId: string | null = $state(null);
  $effect(() => {
    filterAgentId = selectedAgentId ?? null;
  });

  function renderMarkdown(content: string): string {
    let html = marked.parse(content, { async: false }) as string;
    html = html.replace(/@([\w-]+)/g, (match, name) => {
      if (name === "here") return `<span class="mention mention-known">@here</span>`;
      if (agentIds.has(name)) return `<span class="mention mention-known">@${name}</span>`;
      return `<span class="mention">@${name}</span>`;
    });
    html = html.replace(/#([\w-]+)/g, (match, name) => {
      if (channelIds.has(name)) return `<span class="channel-ref">#${name}</span>`;
      return match;
    });
    return html;
  }

  let messages: MessageInfo[] = $derived(
    snapshot
      ? snapshot.recent_messages.filter((m) => {
          if (selectedChannel && m.channel_id !== selectedChannel) return false;
          if (filterAgentId && m.sender_id !== filterAgentId && m.sender_id !== "system") return false;
          // Hide internal system nudge messages
          if (m.content.startsWith("[system:")) return false;
          return true;
        })
      : []
  );

  interface MessageGroup {
    sender_id: string;
    channel_id: string;
    messages: { content: string; timestamp: string; message_id: string; reply_to?: string }[];
  }

  const GROUP_GAP_MS = 1000;

  let groupedMessages: MessageGroup[] = $derived.by(() => {
    const groups: MessageGroup[] = [];
    for (const msg of messages) {
      const last = groups[groups.length - 1];
      let sameGroup = false;
      if (last && last.sender_id === msg.sender_id && last.channel_id === msg.channel_id) {
        const prevTs = new Date(last.messages[last.messages.length - 1].timestamp).getTime();
        const curTs = new Date(msg.timestamp).getTime();
        sameGroup = Math.abs(curTs - prevTs) <= GROUP_GAP_MS;
      }
      if (sameGroup) {
        last!.messages.push({ content: msg.content, timestamp: msg.timestamp, message_id: msg.message_id, reply_to: msg.reply_to });
      } else {
        groups.push({
          sender_id: msg.sender_id,
          channel_id: msg.channel_id,
          messages: [{ content: msg.content, timestamp: msg.timestamp, message_id: msg.message_id, reply_to: msg.reply_to }],
        });
      }
    }
    return groups;
  });

  function shortId(id: string): string {
    return id.slice(0, 8);
  }

  function replyLabel(replyTo: string): string {
    if (!replyTo || !snapshot) return "";
    const ids = replyTo.split(",").map((s) => s.trim());
    const parts: string[] = [];
    for (const rid of ids) {
      const match = snapshot.recent_messages.find((m) => m.message_id.startsWith(rid));
      parts.push(match ? `${match.sender_id}:${rid}` : rid);
    }
    return parts.join(", ");
  }

  let messagePane: HTMLDivElement | undefined = $state(undefined);
  $effect(() => {
    messages.length;
    if (messagePane) {
      requestAnimationFrame(() => {
        messagePane!.scrollTop = messagePane!.scrollHeight;
      });
    }
  });

  function formatTime(ts: string): string {
    try {
      return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    } catch {
      return ts;
    }
  }

  const COLORS = ["bg-orange-500", "bg-emerald-600", "bg-sky-500", "bg-rose-500", "bg-violet-500", "bg-amber-500", "bg-blue-500", "bg-green-600"];
  function avatarColor(id: string): string {
    let hash = 0;
    for (const ch of id) hash = ((hash << 5) - hash + ch.charCodeAt(0)) | 0;
    return COLORS[Math.abs(hash) % COLORS.length];
  }

  function isSystem(id: string): boolean {
    return id === "system" || id === "moderator";
  }

  let typingAgents: string[] = $derived.by(() => {
    const t = typing;
    if (!t || t.size === 0) return [];
    const agents = new Set<string>();
    if (selectedChannel) {
      const set = t.get(selectedChannel);
      if (set) set.forEach((a) => agents.add(a));
    } else {
      t.forEach((set) => set.forEach((a) => agents.add(a)));
    }
    return [...agents].sort();
  });

  function typingText(agents: string[]): string {
    if (agents.length === 0) return "";
    if (agents.length === 1) return `${agents[0]} is typing`;
    if (agents.length === 2) return `${agents[0]} and ${agents[1]} are typing`;
    return `${agents.slice(0, -1).join(", ")}, and ${agents[agents.length - 1]} are typing`;
  }

  // Agent detail sidebar
  let detailAgentId: string | null = $state(null);
  let detailAgent: AgentInfo | null = $derived(
    detailAgentId && snapshot
      ? snapshot.agents.find((a) => a.agent_id === detailAgentId) ?? null
      : null
  );

  function handleAgentClick(agentId: string) {
    // If clicking the same agent, toggle the detail panel
    if (detailAgentId === agentId) {
      detailAgentId = null;
    } else {
      detailAgentId = agentId;
    }
    // Also set filter
    filterAgentId = filterAgentId === agentId ? null : agentId;
  }

  // Admin mode
  let adminMode: boolean = $state(false);
  let adminInput: string = $state("");
  let adminStatusMsg: string = $state("");

  let adminStatus = $derived($wsState.adminStatus);
  $effect(() => {
    if (adminStatus) {
      if (adminStatus.status === "queued") {
        adminStatusMsg = "Queued";
      } else {
        adminStatusMsg = `Blocked: ${adminStatus.reason ?? "unknown"}`;
      }
      setTimeout(() => { adminStatusMsg = ""; }, 3000);
    }
  });

  function handleAdminSend() {
    if (!snapshot || !adminInput.trim()) {
      console.warn("[admin] send aborted: no snapshot or empty input", { hasSnapshot: !!snapshot, input: adminInput });
      return;
    }
    const channel = selectedChannel ?? (snapshot.channels[0]?.channel_id ?? "");
    if (!channel) {
      console.warn("[admin] send aborted: no channel selected and no channels available");
      return;
    }
    const content = adminInput.trim();
    console.log("[admin] handleAdminSend ->", { sandbox_id: snapshot.sandbox_id, channel, content });
    const sent = sendAdminMessage(snapshot.sandbox_id, channel, content);
    if (sent) {
      console.log("[admin] message handed to WebSocket successfully");
      // Optimistically add the message to the chat immediately so it
      // appears without waiting for the next sync cycle.
      const optimisticId = `admin-${Date.now().toString(36)}`;
      snapshot.recent_messages = [
        ...snapshot.recent_messages,
        {
          message_id: optimisticId,
          sender_id: "admin",
          channel_id: channel,
          content,
          timestamp: new Date().toISOString(),
        },
      ];
      adminInput = "";
    } else {
      console.warn("[admin] sendAdminMessage returned false (WebSocket not open)");
      adminStatusMsg = "Not connected";
    }
  }

  function handleAdminKeydown(e: KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleAdminSend();
    }
  }
</script>

<!-- Panel (full-width view, toggled by header) -->
{#if open}
  <div
    class="flex flex-col w-full h-full bg-white overflow-hidden"
  >
    <!-- Slack-style left sidebar within panel -->
    <div class="flex h-full overflow-hidden">
      <!-- Mini nav: channels + agents -->
      <aside class="w-48 min-w-[160px] bg-[#3f0e40] text-[#cfc3cf] flex flex-col overflow-y-auto shrink-0">
        {#if snapshot}
          <div class="flex items-center gap-2 px-3 pt-3 pb-2">
            <h1 class="text-white text-[14px] font-bold truncate">{snapshot.display_name || snapshot.sandbox_id}</h1>
            <span class="w-2 h-2 rounded-full shrink-0 {connected ? 'bg-emerald-500' : 'bg-red-500'}"></span>
          </div>

          <!-- Agent filter chip if active -->
          {#if filterAgentId}
            <div class="mx-3 mb-1 flex items-center gap-1 bg-white/10 rounded px-2 py-1 text-[12px]">
              <span class="truncate">{filterAgentId}</span>
              <button class="ml-auto opacity-70 hover:opacity-100" onclick={() => filterAgentId = null} aria-label="Clear agent filter">×</button>
            </div>
          {/if}

          <div class="py-1">
            <h2 class="text-[11px] font-semibold uppercase tracking-wide text-[#9e8d9e] px-3 py-1">Channels</h2>
            <button
              class="flex items-center gap-1 w-full text-left px-4 py-1 text-[13px] hover:bg-white/[0.08] {selectedChannel === null ? 'bg-[#1264a3] text-white' : ''}"
              onclick={() => (selectedChannel = null)}
            >
              <span class="opacity-70">#</span> all
            </button>
            {#each snapshot.channels as ch}
              <button
                class="flex items-center gap-1 w-full text-left px-4 py-1 text-[13px] hover:bg-white/[0.08] {selectedChannel === ch.channel_id ? 'bg-[#1264a3] text-white' : ''}"
                onclick={() => (selectedChannel = ch.channel_id)}
              >
                <span class="opacity-70">#</span>
                <span class="truncate">{ch.channel_id}</span>
              </button>
            {/each}
          </div>

          <div class="py-1 mt-auto">
            <button
              class="flex items-center gap-2 w-full text-left px-4 py-1 text-[12px] hover:bg-white/[0.08] {adminMode ? 'text-amber-300' : 'text-[#9e8d9e]'}"
              onclick={() => (adminMode = !adminMode)}
              title="Toggle admin mode to inject messages"
            >
              <span class="text-[10px]">{adminMode ? "🔓" : "🔒"}</span>
              <span>Admin mode</span>
            </button>
          </div>

          <div class="py-1">
            <h2 class="text-[11px] font-semibold uppercase tracking-wide text-[#9e8d9e] px-3 py-1">Agents</h2>
            {#each snapshot.agents as agent}
              <button
                class="flex items-center gap-2 px-4 py-1 text-[13px] w-full text-left hover:bg-white/[0.08] {detailAgentId === agent.agent_id ? 'bg-[#1264a3] text-white' : filterAgentId === agent.agent_id ? 'bg-white/10' : ''}"
                onclick={() => handleAgentClick(agent.agent_id)}
              >
                <span
                  class="w-2 h-2 rounded-full shrink-0 {agent.status === 'crashed' ? 'bg-red-500' : agent.thread_alive ? (agent.status === 'rate_limited' ? 'bg-amber-400' : agent.status === 'active' ? 'bg-emerald-500' : 'bg-emerald-500/50') : 'bg-gray-500'}"
                  title="{agent.status ?? 'unknown'}"
                ></span>
                <span class="truncate">{agent.agent_id}</span>
                {#if agent.status === "active"}
                  <span class="ml-auto w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse shrink-0"></span>
                {/if}
              </button>
            {/each}
          </div>
        {:else}
          <div class="px-3 pt-3">
            <h1 class="text-white text-[14px] font-bold">Harvest</h1>
          </div>
          <p class="px-3 text-[12px] opacity-70">No sandbox</p>
        {/if}
      </aside>

      <!-- Message pane -->
      <main class="flex-1 flex flex-col min-w-0">
        <!-- Header -->
        <div class="flex items-center justify-between px-3 py-2 border-b border-gray-200 shrink-0">
          <h2 class="text-[14px] font-bold flex items-center gap-1 min-w-0">
            {#if selectedChannel}
              <span class="opacity-70">#</span>
              <span class="truncate">{selectedChannel}</span>
            {:else}
              <span class="truncate">All messages</span>
            {/if}
            {#if filterAgentId}
              <span class="text-[11px] text-blue-500 font-normal ml-1 shrink-0">· {filterAgentId}</span>
            {/if}
          </h2>
          {#if lastUpdate}
            <span class="text-[10px] text-gray-400 shrink-0 ml-1">{formatTime(lastUpdate)}</span>
          {/if}
        </div>

        <!-- Messages -->
        <div class="flex-1 overflow-y-auto py-3 min-w-0" bind:this={messagePane}>
          {#if messages.length === 0}
            <div class="flex flex-col items-center justify-center h-full text-gray-400 gap-1 px-4 text-center">
              <p class="text-sm">No messages yet</p>
            </div>
          {:else}
            {#each groupedMessages as group}
              {#if isSystem(group.sender_id)}
                {#each group.messages as msg}
                  <div class="flex items-center gap-2 px-3 py-3">
                    <div class="flex-1 h-px bg-gray-200"></div>
                    <span class="text-[11px] text-gray-400 italic whitespace-nowrap max-w-[60%] truncate">{msg.content}</span>
                    <div class="flex-1 h-px bg-gray-200"></div>
                  </div>
                {/each}
              {:else}
                <div class="flex gap-2 px-3 py-1 hover:bg-gray-50">
                  <div class="{avatarColor(group.sender_id)} w-7 h-7 rounded-md flex items-center justify-center text-white text-sm font-bold shrink-0 mt-0.5">
                    {group.sender_id.charAt(0).toUpperCase()}
                  </div>
                  <div class="min-w-0 flex-1">
                    <div class="flex items-baseline gap-1.5 mb-0.5 flex-wrap">
                      <span class="font-bold text-[13px]">{group.sender_id}</span>
                      {#if !selectedChannel}
                        <span class="text-[10px] text-[#1264a3] bg-sky-50 px-1 py-px rounded font-medium">#{group.channel_id}</span>
                      {/if}
                      <span class="text-[10px] text-gray-400">{formatTime(group.messages[0].timestamp)}</span>
                    </div>
                    {#each group.messages as msg}
                      <div class="text-[13px] leading-relaxed break-words min-w-0">
                        {#if msg.reply_to}
                          <div class="flex items-center gap-1 text-[11px] text-gray-400 mb-0.5">
                            <span class="text-orange-400">&larr;</span>
                            <span>replying to {replyLabel(msg.reply_to)}</span>
                          </div>
                        {/if}
                        <div class="prose prose-sm max-w-none prose-p:my-0.5 prose-pre:my-1 prose-pre:bg-gray-100 prose-pre:rounded prose-code:text-[12px] prose-code:before:content-none prose-code:after:content-none">
                          {@html renderMarkdown(msg.content)}
                        </div>
                        <span class="text-[9px] text-gray-400 font-mono ml-1 select-all">{shortId(msg.message_id)}</span>
                      </div>
                    {/each}
                  </div>
                </div>
              {/if}
            {/each}
          {/if}
        </div>

        <!-- Typing indicator -->
        {#if typingAgents.length > 0}
          <div class="typing-bar px-3 py-1 border-t border-gray-100 text-[11px] text-gray-500 italic shrink-0">
            <span>{@html typingText(typingAgents).replace(/([\w-]+)/g, (match) => {
              if (agentIds.has(match)) return `<span class="mention mention-known">${match}</span>`;
              return match;
            })}</span><span class="typing-dots">...</span>
          </div>
        {/if}

        <!-- Admin input bar -->
        {#if adminMode}
          <div class="admin-bar border-t-2 border-amber-300 bg-amber-50 px-3 py-2 shrink-0">
            <div class="flex items-center gap-1 mb-1">
              <span class="text-[10px] font-semibold text-amber-700 uppercase tracking-wide">Admin</span>
              {#if selectedChannel}
                <span class="text-[10px] text-amber-600">→ #{selectedChannel}</span>
              {:else if snapshot?.channels[0]}
                <span class="text-[10px] text-amber-600">→ #{snapshot.channels[0].channel_id}</span>
              {/if}
              {#if adminStatusMsg}
                <span class="ml-auto text-[10px] {adminStatusMsg.startsWith('Blocked') || adminStatusMsg === 'Not connected' ? 'text-red-500' : 'text-emerald-600'}">{adminStatusMsg}</span>
              {/if}
            </div>
            <div class="flex gap-1">
              <textarea
                bind:value={adminInput}
                onkeydown={handleAdminKeydown}
                rows="2"
                placeholder="Inject a message as admin (Enter to send, Shift+Enter for newline)…"
                class="flex-1 text-[12px] border border-amber-300 rounded px-2 py-1 resize-none focus:outline-none focus:ring-1 focus:ring-amber-400 bg-white"
              ></textarea>
              <button
                onclick={handleAdminSend}
                disabled={!adminInput.trim()}
                class="px-2 py-1 text-[11px] font-semibold bg-amber-500 text-white rounded hover:bg-amber-600 disabled:opacity-40 disabled:cursor-not-allowed"
              >Send</button>
            </div>
          </div>
        {/if}
      </main>

      <!-- Agent detail sidebar -->
      {#if detailAgent}
        <AgentDetailSidebar
          agent={detailAgent}
          onClose={() => detailAgentId = null}
        />
      {/if}
    </div>
  </div>
{/if}
