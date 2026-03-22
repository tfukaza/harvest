<script lang="ts">
  import { wsState } from "$lib/ws";
  import { log } from "$lib/logger";
  import { marked } from "marked";
  import type { SandboxSnapshot, MessageInfo } from "$lib/types";

  // Configure marked for inline rendering (no wrapping <p> tags for single-line messages)
  marked.setOptions({ breaks: true, gfm: true });

  // Known agent IDs and channel IDs for highlighting
  let agentIds: Set<string> = $derived(
    new Set(sandbox ? sandbox.agents.map((a) => a.agent_id) : [])
  );
  let channelIds: Set<string> = $derived(
    new Set(sandbox ? sandbox.channels.map((c) => c.channel_id) : [])
  );

  function renderMarkdown(content: string): string {
    let html = marked.parse(content, { async: false }) as string;
    // Highlight @mentions
    html = html.replace(/@([\w-]+)/g, (match, name) => {
      if (name === "here") {
        return `<span class="mention mention-known">@here</span>`;
      }
      if (agentIds.has(name)) {
        return `<span class="mention mention-known">@${name}</span>`;
      }
      return `<span class="mention">@${name}</span>`;
    });
    // Highlight #channel references
    html = html.replace(/#([\w-]+)/g, (match, name) => {
      if (channelIds.has(name)) {
        return `<span class="channel-ref">#${name}</span>`;
      }
      return match;
    });
    return html;
  }

  let state = $derived($wsState);

  // Currently selected channel (null = all messages)
  let selectedChannel: string | null = $state(null);

  // First sandbox
  let sandbox: SandboxSnapshot | null = $derived(
    state.sandboxes.length > 0 ? state.sandboxes[0] : null
  );

  // Messages filtered by selected channel
  let messages: MessageInfo[] = $derived(
    sandbox
      ? selectedChannel
        ? sandbox.recent_messages.filter((m) => m.channel_id === selectedChannel)
        : sandbox.recent_messages
      : []
  );

  // Group consecutive messages by sender (Slack-style)
  interface MessageGroup {
    sender_id: string;
    channel_id: string;
    messages: { content: string; timestamp: string; message_id: string; reply_to?: string }[];
  }

  const GROUP_GAP_MS = 1000; // split into new group if messages are >1s apart

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

  /** Resolve reply_to short IDs to "sender:shortid" labels */
  function replyLabel(replyTo: string): string {
    if (!replyTo || !sandbox) return "";
    const ids = replyTo.split(",").map(s => s.trim());
    const parts: string[] = [];
    for (const rid of ids) {
      const match = sandbox.recent_messages.find(m => m.message_id.startsWith(rid));
      parts.push(match ? `${match.sender_id}:${rid}` : rid);
    }
    return parts.join(", ");
  }

  $effect(() => {
    if (sandbox) {
      log.renderUpdate(
        sandbox.sandbox_id,
        sandbox.agents.length,
        sandbox.channels.length,
        sandbox.recent_messages.length
      );
    }
  });

  // Auto-scroll to bottom on new messages
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

  // Deterministic avatar color from ID
  const COLORS = ["bg-orange-500", "bg-emerald-600", "bg-sky-500", "bg-rose-500", "bg-violet-500", "bg-amber-500", "bg-blue-500", "bg-green-600"];
  function avatarColor(id: string): string {
    let hash = 0;
    for (const ch of id) hash = ((hash << 5) - hash + ch.charCodeAt(0)) | 0;
    return COLORS[Math.abs(hash) % COLORS.length];
  }

  function isSystem(id: string): boolean {
    return id === "system" || id === "moderator";
  }

  // Typing indicator: collect agent names currently typing in visible channels
  let typingAgents: string[] = $derived.by(() => {
    const typing = state.typing;
    if (!typing || typing.size === 0) return [];
    const agents = new Set<string>();
    if (selectedChannel) {
      const set = typing.get(selectedChannel);
      if (set) set.forEach((a) => agents.add(a));
    } else {
      typing.forEach((set) => set.forEach((a) => agents.add(a)));
    }
    return [...agents].sort();
  });

  function typingText(agents: string[]): string {
    if (agents.length === 0) return "";
    if (agents.length === 1) return `${agents[0]} is typing`;
    if (agents.length === 2) return `${agents[0]} and ${agents[1]} are typing`;
    return `${agents.slice(0, -1).join(", ")}, and ${agents[agents.length - 1]} are typing`;
  }
</script>

<div class="flex h-screen bg-white text-[#1d1c1d]">

  <!-- ===== Sidebar ===== -->
  <aside class="w-64 min-w-[260px] bg-[#3f0e40] text-[#cfc3cf] flex flex-col overflow-y-auto">
    {#if sandbox}
      <!-- Header -->
      <div class="flex items-center gap-2 px-4 pt-4 pb-2">
        <h1 class="text-white text-[17px] font-bold truncate">{sandbox.display_name || sandbox.sandbox_id}</h1>
        <span class="w-2 h-2 rounded-full shrink-0 {state.connected ? 'bg-emerald-500' : 'bg-red-500'}"></span>
      </div>

      <!-- Channels -->
      <div class="py-2">
        <h2 class="text-[13px] font-semibold uppercase tracking-wide text-[#9e8d9e] px-4 py-1">Channels</h2>
        <button
          class="flex items-center gap-1 w-full text-left px-6 py-1 text-[15px] hover:bg-white/[0.08] {selectedChannel === null ? 'bg-[#1264a3] text-white' : ''}"
          onclick={() => (selectedChannel = null)}
        >
          <span class="opacity-70">#</span> all messages
        </button>
        {#each sandbox.channels as ch}
          <button
            class="flex items-center gap-1 w-full text-left px-6 py-1 text-[15px] hover:bg-white/[0.08] {selectedChannel === ch.channel_id ? 'bg-[#1264a3] text-white' : ''}"
            onclick={() => (selectedChannel = ch.channel_id)}
          >
            <span class="opacity-70">#</span> {ch.channel_id}
            <span class="ml-auto text-[11px] opacity-50">{ch.channel_type}</span>
          </button>
        {/each}
      </div>

      <!-- Agents -->
      <div class="py-2">
        <h2 class="text-[13px] font-semibold uppercase tracking-wide text-[#9e8d9e] px-4 py-1">Agents</h2>
        {#each sandbox.agents as agent}
          <div class="flex items-center gap-2 px-6 py-1 text-[15px]">
            <span class="w-2 h-2 rounded-full shrink-0 {agent.status === 'crashed' ? 'bg-red-500' : agent.thread_alive ? (agent.status === 'rate_limited' ? 'bg-amber-400' : agent.status === 'active' ? 'bg-emerald-500' : 'bg-emerald-500/50') : 'bg-gray-500'}" title="{agent.status ?? 'unknown'}"></span>
            {agent.agent_id}
          </div>
        {/each}
      </div>
    {:else}
      <div class="px-4 pt-4">
        <h1 class="text-white text-[17px] font-bold">Harvest</h1>
      </div>
      <p class="px-4 text-[13px] opacity-70">No sandboxes connected</p>
    {/if}
  </aside>

  <!-- ===== Main message pane ===== -->
  <main class="flex-1 flex flex-col min-w-0">
    <!-- Channel header -->
    <div class="flex items-center justify-between px-5 py-2.5 border-b border-gray-200 shrink-0">
      <h2 class="text-[17px] font-bold flex items-center gap-1">
        {#if selectedChannel}
          <span class="opacity-70">#</span> {selectedChannel}
        {:else}
          All messages
        {/if}
      </h2>
      {#if state.lastUpdate}
        <span class="text-xs text-gray-400">Updated {formatTime(state.lastUpdate)}</span>
      {/if}
    </div>

    <!-- Messages -->
    <div class="flex-1 overflow-y-auto py-4" bind:this={messagePane}>
      {#if messages.length === 0}
        <div class="flex flex-col items-center justify-center h-full text-gray-400">
          <p>No messages yet</p>
          <p class="text-sm text-gray-300">Messages will appear here as agents communicate</p>
        </div>
      {:else}
        {#each groupedMessages as group}
          {#if isSystem(group.sender_id)}
            <!-- System / seed messages as dividers -->
            {#each group.messages as msg}
              <div class="flex items-center gap-3 px-5 py-4">
                <div class="flex-1 h-px bg-gray-200"></div>
                <span class="text-[13px] text-gray-400 italic whitespace-nowrap max-w-[60%] truncate">{msg.content}</span>
                <div class="flex-1 h-px bg-gray-200"></div>
              </div>
            {/each}
          {:else}
            <!-- Agent message group -->
            <div class="flex gap-3 px-5 py-1.5 hover:bg-gray-50">
              <!-- Avatar -->
              <div class="{avatarColor(group.sender_id)} w-9 h-9 rounded-md flex items-center justify-center text-white text-base font-bold shrink-0 mt-0.5">
                {group.sender_id.charAt(0).toUpperCase()}
              </div>
              <!-- Content -->
              <div class="min-w-0 flex-1">
                <div class="flex items-baseline gap-2 mb-0.5">
                  <span class="font-bold text-[15px]">{group.sender_id}</span>
                  {#if !selectedChannel}
                    <span class="text-xs text-[#1264a3] bg-sky-50 px-1.5 py-px rounded font-medium">#{group.channel_id}</span>
                  {/if}
                  <span class="text-xs text-gray-400">{formatTime(group.messages[0].timestamp)}</span>
                </div>
                {#each group.messages as msg}
                  <div class="relative text-[15px] leading-relaxed break-words">
                    {#if msg.reply_to}
                      <div class="flex items-center gap-1 text-[12px] text-gray-400 mb-0.5">
                        <span class="text-orange-400">&larr;</span>
                        <span>replying to {replyLabel(msg.reply_to)}</span>
                      </div>
                    {/if}
                    <div class="prose prose-sm max-w-none prose-p:my-1 prose-pre:my-2 prose-pre:bg-gray-100 prose-pre:rounded prose-code:text-[13px] prose-code:before:content-none prose-code:after:content-none inline">
                      {@html renderMarkdown(msg.content)}
                    </div>
                    <span class="text-[10px] text-gray-400 font-mono ml-2 align-top select-all" title={msg.message_id}>{shortId(msg.message_id)}</span>
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
      <div class="typing-bar px-5 py-1.5 border-t border-gray-100 text-[13px] text-gray-500 italic shrink-0">
        <span>{@html typingText(typingAgents).replace(/([\w-]+)/g, (match) => {
          if (agentIds.has(match)) return `<span class="mention mention-known">${match}</span>`;
          return match;
        })}</span><span class="typing-dots">...</span>
      </div>
    {/if}
  </main>
</div>
