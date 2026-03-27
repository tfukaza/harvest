<script lang="ts">
  import { marked } from "marked";
  import type { AgentInfo, ActivityEntry, AgentMemory, AgentTodo } from "./types";

  interface Props {
    agent: AgentInfo;
    onClose: () => void;
  }

  let { agent, onClose }: Props = $props();

  marked.setOptions({ breaks: true, gfm: true });

  // Accordion state
  let memoriesOpen = $state(false);
  let todosOpen = $state(false);
  let expandedMemory: string | null = $state(null);

  // Track which paired entries are expanded (by pair index)
  let expandedPairs = $state(new Set<number>());

  // Pair tool_call + tool_result together, keep other entries as-is
  interface PairedEntry {
    type: "thinking" | "tool" | "text" | "summary";
    timestamp: string;
    content?: string;
    // For tool pairs
    call?: ActivityEntry;
    result?: ActivityEntry;
    // For summary (compaction)
    tokens_before?: number;
    tokens_after?: number;
  }

  let pairedEntries: PairedEntry[] = $derived.by(() => {
    const raw = agent.activity ?? [];
    // Build a lookup: tool_call_id → tool_result entry
    const resultMap = new Map<string, ActivityEntry>();
    for (const e of raw) {
      if (e.type === "tool_result" && e.tool_call_id) {
        resultMap.set(e.tool_call_id, e);
      }
    }
    // Track which results have been consumed by a call
    const consumedResults = new Set<string>();

    const out: PairedEntry[] = [];
    for (const e of raw) {
      if (e.type === "tool_call") {
        const result = e.tool_call_id ? resultMap.get(e.tool_call_id) : undefined;
        if (result) consumedResults.add(e.tool_call_id!);
        out.push({ type: "tool", timestamp: e.timestamp, call: e, result });
      } else if (e.type === "tool_result") {
        // Skip results that were already paired with their call
        if (e.tool_call_id && consumedResults.has(e.tool_call_id)) continue;
        // Orphan result — show it standalone
        out.push({ type: "tool", timestamp: e.timestamp, result: e });
      } else if (e.type === "thinking") {
        out.push({ type: "thinking", timestamp: e.timestamp, content: e.content });
      } else if (e.type === "text") {
        out.push({ type: "text", timestamp: e.timestamp, content: e.content });
      } else {
        out.push({ type: "summary", timestamp: e.timestamp, content: e.content, tokens_before: e.tokens_before, tokens_after: e.tokens_after });
      }
    }
    return out;
  });

  // Draggable width
  let sidebarWidth = $state(380);
  let dragging = $state(false);

  function onDragStart(e: MouseEvent) {
    e.preventDefault();
    dragging = true;
    const startX = e.clientX;
    const startWidth = sidebarWidth;

    function onMouseMove(e: MouseEvent) {
      const delta = startX - e.clientX;
      sidebarWidth = Math.max(280, Math.min(700, startWidth + delta));
    }
    function onMouseUp() {
      dragging = false;
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    }
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  }

  // Auto-scroll activity log
  let activityPane: HTMLDivElement | undefined = $state(undefined);
  $effect(() => {
    agent.activity?.length;
    if (activityPane) {
      requestAnimationFrame(() => {
        activityPane!.scrollTop = activityPane!.scrollHeight;
      });
    }
  });

  let hasMemory = $derived(
    (agent.cognitive_tools ?? []).includes("memory")
  );
  let hasTodo = $derived(
    (agent.cognitive_tools ?? []).includes("todo")
  );

  function statusColor(status: string): string {
    switch (status) {
      case "active": return "bg-emerald-500";
      case "rate_limited": return "bg-amber-400";
      case "crashed":
      case "unrecoverable": return "bg-red-500";
      case "stopped": return "bg-gray-400";
      default: return "bg-emerald-500/50";
    }
  }

  function statusLabel(agent: AgentInfo): string {
    const alive = agent.thread_alive ? "online" : "offline";
    return `${agent.status} / ${alive}`;
  }

  function formatTime(ts: string): string {
    try {
      return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    } catch {
      return ts;
    }
  }

  function renderContent(content: string): string {
    return marked.parse(content, { async: false }) as string;
  }

  function parseToolArgs(args: string): Record<string, unknown> | null {
    try {
      return JSON.parse(args);
    } catch {
      return null;
    }
  }

  function formatToolResult(content: string): string {
    try {
      const parsed = JSON.parse(content);
      return JSON.stringify(parsed, null, 2);
    } catch {
      return content;
    }
  }

  function togglePair(i: number) {
    const s = new Set(expandedPairs);
    if (s.has(i)) s.delete(i); else s.add(i);
    expandedPairs = s;
  }
</script>

<!-- Right sidebar panel -->
<aside
  class="bg-white border-l border-gray-200 flex flex-col h-full overflow-hidden shrink-0 relative"
  style="width: {sidebarWidth}px"
>
  <!-- Drag handle on left edge -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div
    class="drag-handle"
    class:drag-active={dragging}
    onmousedown={onDragStart}
  ></div>

  <!-- ============ SECTION: Agent Status ============ -->
  <div class="px-4 py-3 shrink-0">
    <div class="flex items-center gap-2">
      <span class="w-2.5 h-2.5 rounded-full shrink-0 {statusColor(agent.status)}"></span>
      <div class="flex-1 min-w-0">
        <h2 class="text-[14px] font-bold truncate">{agent.agent_id}</h2>
        <p class="text-[11px] text-gray-400">{statusLabel(agent)} &middot; {agent.agent_type}</p>
      </div>
      <button
        class="w-7 h-7 flex items-center justify-center rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600 shrink-0"
        onclick={onClose}
        aria-label="Close sidebar"
      >&times;</button>
    </div>

    <!-- Context window usage bar -->
    {#if (agent.context_limit ?? 0) > 0}
      {@const tokens = agent.context_tokens ?? 0}
      {@const limit = agent.context_limit ?? 0}
      {@const pct = Math.min(100, (tokens / limit) * 100)}
      {@const compactAt = (agent.compaction_threshold ?? 0.75) * 100}
      {@const isWarning = pct >= compactAt}
      <div class="mt-2.5">
        <div class="flex items-center justify-between text-[10px] text-gray-500 mb-0.5">
          <span>Context: <strong>{tokens.toLocaleString()}</strong> / {limit.toLocaleString()} tokens</span>
          <span class="{isWarning ? 'text-amber-600 font-semibold' : ''}">{pct.toFixed(0)}%</span>
        </div>
        <div class="relative w-full h-1.5 bg-gray-100 rounded-full overflow-hidden">
          <div
            class="absolute inset-y-0 left-0 rounded-full transition-all duration-300 {isWarning ? 'bg-amber-400' : 'bg-blue-400'}"
            style="width: {pct}%"
          ></div>
          <div
            class="absolute top-0 bottom-0 w-px bg-red-400"
            style="left: {compactAt}%"
            title="Compaction threshold ({compactAt}%)"
          ></div>
        </div>
        <div class="flex items-center justify-end mt-0.5">
          <span class="text-[9px] text-gray-400">compacts at {compactAt}%</span>
        </div>
      </div>
    {:else}
      <div class="mt-2 text-[10px] text-gray-400">Context usage: waiting for first step...</div>
    {/if}
  </div>

  <!-- ============ SECTION: Memory & Todo ============ -->
  {#if hasMemory || hasTodo}
    <div class="section-divider"></div>

    {#if hasMemory}
      <div class="border-b border-gray-100">
        <button
          class="flex items-center gap-2 w-full text-left px-4 py-2 hover:bg-gray-50 text-[12px] font-semibold text-gray-600 uppercase tracking-wide"
          onclick={() => memoriesOpen = !memoriesOpen}
        >
          <span class="text-[10px] transition-transform duration-150 {memoriesOpen ? 'rotate-90' : ''}"
            style="display:inline-block">&#9654;</span>
          Memories
          <span class="ml-auto text-[11px] font-normal text-gray-400 normal-case">{(agent.memories ?? []).length}</span>
        </button>
        {#if memoriesOpen}
          <div class="px-4 pb-2 max-h-[200px] overflow-y-auto">
            {#if (agent.memories ?? []).length === 0}
              <p class="text-[11px] text-gray-400 italic py-1">No memories saved</p>
            {:else}
              {#each agent.memories ?? [] as mem}
                <button
                  class="w-full text-left rounded px-2 py-1.5 hover:bg-gray-50 mb-0.5"
                  onclick={() => expandedMemory = expandedMemory === mem.name ? null : mem.name}
                >
                  <div class="flex items-center gap-1.5">
                    <span class="text-[10px] transition-transform duration-150 {expandedMemory === mem.name ? 'rotate-90' : ''}"
                      style="display:inline-block">&#9654;</span>
                    <span class="text-[12px] font-medium text-gray-700 truncate">{mem.name}</span>
                  </div>
                  <p class="text-[11px] text-gray-400 ml-4 truncate">{mem.description}</p>
                  {#if expandedMemory === mem.name}
                    <div class="mt-1.5 ml-4 p-2 bg-gray-50 rounded text-[11px] text-gray-600 whitespace-pre-wrap break-words max-h-[120px] overflow-y-auto">
                      {mem.content}
                    </div>
                  {/if}
                </button>
              {/each}
            {/if}
          </div>
        {/if}
      </div>
    {/if}

    {#if hasTodo}
      <div class="border-b border-gray-100">
        <button
          class="flex items-center gap-2 w-full text-left px-4 py-2 hover:bg-gray-50 text-[12px] font-semibold text-gray-600 uppercase tracking-wide"
          onclick={() => todosOpen = !todosOpen}
        >
          <span class="text-[10px] transition-transform duration-150 {todosOpen ? 'rotate-90' : ''}"
            style="display:inline-block">&#9654;</span>
          To-do list
          {#if (agent.todos ?? []).length > 0}
            {@const pending = (agent.todos ?? []).filter(t => !t.done).length}
            <span class="ml-auto text-[11px] font-normal text-gray-400 normal-case">
              {pending} pending / {(agent.todos ?? []).length} total
            </span>
          {:else}
            <span class="ml-auto text-[11px] font-normal text-gray-400 normal-case">0</span>
          {/if}
        </button>
        {#if todosOpen}
          <div class="px-4 pb-2 max-h-[200px] overflow-y-auto">
            {#if (agent.todos ?? []).length === 0}
              <p class="text-[11px] text-gray-400 italic py-1">No tasks</p>
            {:else}
              {#each agent.todos ?? [] as todo}
                <div class="flex items-start gap-2 py-1 px-1">
                  {#if todo.done}
                    <span class="mt-0.5 text-[12px] text-emerald-500">&#10003;</span>
                  {:else}
                    <span class="mt-0.5 w-3 h-3 rounded-full border border-gray-300 shrink-0 inline-block"></span>
                  {/if}
                  <span class="text-[12px] {todo.done ? 'text-gray-400 line-through' : 'text-gray-700'}">{todo.task}</span>
                  <span class="ml-auto text-[9px] text-gray-400 font-mono shrink-0">{todo.id}</span>
                </div>
              {/each}
            {/if}
          </div>
        {/if}
      </div>
    {/if}
  {/if}

  <!-- ============ SECTION: Activity Log ============ -->
  <div class="section-divider"></div>
  <div class="px-4 py-2 shrink-0">
    <h3 class="text-[12px] font-semibold text-gray-600 uppercase tracking-wide">Activity Log</h3>
  </div>

  <div class="flex-1 overflow-y-auto px-3 py-1" bind:this={activityPane}>
    {#if pairedEntries.length === 0}
      <div class="flex items-center justify-center h-full">
        <p class="text-[12px] text-gray-400 italic">No activity yet</p>
      </div>
    {:else}
      {#each pairedEntries as entry, i}
        {#if entry.type === "thinking"}
          <div class="activity-entry">
            <div class="flex items-center gap-1.5 mb-0.5">
              <span class="activity-icon">&#128161;</span>
              <span class="text-[10px] text-purple-500 font-semibold uppercase">Thinking</span>
              <span class="text-[9px] text-gray-400 ml-auto">{formatTime(entry.timestamp)}</span>
            </div>
            <div class="ml-5 text-[12px] text-gray-600 bg-white border border-gray-100 rounded px-2.5 py-2 whitespace-pre-wrap break-words leading-relaxed max-h-[200px] overflow-y-auto">
              {entry.content}
            </div>
          </div>

        {:else if entry.type === "tool"}
          <!-- Paired tool call + result as one entry -->
          <!-- svelte-ignore a11y_click_events_have_key_events -->
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <div class="activity-entry cursor-pointer" onclick={() => togglePair(i)}>
            <!-- Compact one-line summary -->
            <div class="flex items-center gap-1.5">
              <span class="terminal-icon" aria-hidden="true">&gt;</span>
              <span class="text-[11px] text-gray-700 font-mono">{entry.call?.tool_name ?? "tool"}</span>
              {#if entry.result}
                <span class="text-[9px] text-emerald-600 font-medium">OK</span>
              {:else}
                <span class="text-[9px] text-amber-500 font-medium">...</span>
              {/if}
              <span class="text-[9px] text-gray-400 ml-auto shrink-0">{formatTime(entry.timestamp)}</span>
            </div>

            <!-- Expanded: args + result -->
            {#if expandedPairs.has(i)}
              <div class="ml-5 mt-1.5 space-y-1.5">
                <!-- Args -->
                {#if entry.call?.tool_args}
                  {@const parsed = parseToolArgs(entry.call.tool_args ?? "")}
                  <div>
                    <div class="text-[9px] text-gray-400 font-semibold uppercase mb-0.5">Arguments</div>
                    <div class="text-[11px] bg-white border border-gray-100 rounded px-2.5 py-1.5 max-h-[200px] overflow-y-auto">
                      {#if parsed}
                        {#each Object.entries(parsed) as [key, val]}
                          <div class="mb-0.5">
                            <span class="text-gray-500 font-mono">{key}:</span>
                            <span class="text-gray-700 break-words whitespace-pre-wrap">{typeof val === "string" ? val : JSON.stringify(val)}</span>
                          </div>
                        {/each}
                      {:else}
                        <pre class="text-gray-600 whitespace-pre-wrap break-words font-mono">{entry.call.tool_args}</pre>
                      {/if}
                    </div>
                  </div>
                {/if}
                <!-- Result -->
                {#if entry.result}
                  <div>
                    <div class="text-[9px] text-gray-400 font-semibold uppercase mb-0.5">Result</div>
                    <div class="text-[11px] bg-white border border-gray-100 rounded px-2.5 py-1.5 max-h-[200px] overflow-y-auto">
                      <pre class="text-gray-600 whitespace-pre-wrap break-words font-mono">{formatToolResult(entry.result.content ?? "")}</pre>
                    </div>
                  </div>
                {/if}
              </div>
            {/if}
          </div>

        {:else if entry.type === "text"}
          <div class="activity-entry">
            <div class="flex items-center gap-1.5 mb-0.5">
              <span class="activity-icon">&#128172;</span>
              <span class="text-[10px] text-gray-600 font-semibold uppercase">Response</span>
              <span class="text-[9px] text-gray-400 ml-auto">{formatTime(entry.timestamp)}</span>
            </div>
            <div class="ml-5 text-[12px] text-gray-700 bg-white border border-gray-100 rounded px-2.5 py-2 prose prose-sm max-w-none prose-p:my-0.5 prose-pre:my-1 prose-pre:bg-gray-100 prose-pre:rounded prose-code:text-[11px] max-h-[200px] overflow-y-auto">
              {@html renderContent(entry.content ?? "")}
            </div>
          </div>

        {:else if entry.type === "summary"}
          <div class="activity-entry">
            <div class="flex flex-col items-center gap-1 px-2 py-2">
              <div class="flex items-center gap-2 w-full">
                <div class="flex-1 h-px bg-amber-300"></div>
                <span class="text-[10px] text-amber-600 font-semibold whitespace-nowrap">Context Compacted</span>
                <div class="flex-1 h-px bg-amber-300"></div>
              </div>
              {#if (entry.tokens_before ?? 0) > 0}
                {@const before = entry.tokens_before ?? 0}
                {@const after = entry.tokens_after ?? 0}
                {@const saved = before - after}
                {@const pctSaved = before > 0 ? ((saved / before) * 100).toFixed(0) : "0"}
                <div class="text-[10px] text-gray-500 flex items-center gap-2">
                  <span>{before.toLocaleString()} &rarr; {after.toLocaleString()} tokens</span>
                  <span class="text-emerald-600 font-medium">&minus;{saved.toLocaleString()} ({pctSaved}%)</span>
                </div>
              {/if}
            </div>
          </div>
        {/if}
      {/each}
    {/if}
  </div>
</aside>

<style>
  .section-divider {
    height: 4px;
    background: #f3f4f6;
    flex-shrink: 0;
  }
  .activity-entry {
    padding: 6px 0;
    margin-bottom: 4px;
  }
  .activity-entry + .activity-entry {
    border-top: 1px solid #f0f0f0;
    padding-top: 10px;
  }
  .activity-icon {
    font-size: 12px;
    width: 16px;
    text-align: center;
    flex-shrink: 0;
  }
  .terminal-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 16px;
    border-radius: 3px;
    background: #1e1e1e;
    color: #e0e0e0;
    font-family: monospace;
    font-size: 10px;
    font-weight: bold;
    flex-shrink: 0;
    line-height: 1;
  }
  .drag-handle {
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 4px;
    cursor: col-resize;
    z-index: 10;
    background: transparent;
    transition: background 0.15s;
  }
  .drag-handle:hover,
  .drag-active {
    background: #3b82f6;
  }
</style>
