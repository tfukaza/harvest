<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import type { SandboxSnapshot } from "./types";
  import { computeLayout } from "./canvas";
  import type { CanvasLayout, AgentNode, ChannelNode, ExternalNode, Point } from "./canvas";

  interface Props {
    snapshot: SandboxSnapshot | null;
    selectedAgentId?: string | null;
    onAgentClick?: (agentId: string) => void;
    onChannelClick?: (channelId: string) => void;
  }

  let { snapshot, selectedAgentId = null, onAgentClick, onChannelClick }: Props = $props();

  let canvasEl: HTMLCanvasElement | undefined = $state(undefined);
  let containerEl: HTMLDivElement | undefined = $state(undefined);
  let canvasW = $state(800);
  let canvasH = $state(600);
  let layout: CanvasLayout | null = $state(null);

  // Recompute layout when snapshot or canvas size changes
  $effect(() => {
    if (!snapshot) { layout = null; return; }
    layout = computeLayout(snapshot, canvasW, canvasH);
  });

  // Redraw whenever layout or selection changes
  $effect(() => {
    if (canvasEl && layout) {
      draw(canvasEl, layout, selectedAgentId);
    } else if (canvasEl) {
      clearCanvas(canvasEl);
    }
  });

  // -------------------------------------------------------------------------
  // Resize observer
  // -------------------------------------------------------------------------
  let resizeObserver: ResizeObserver | null = null;

  onMount(() => {
    if (!containerEl) return;
    resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        canvasW = entry.contentRect.width;
        canvasH = entry.contentRect.height;
      }
    });
    resizeObserver.observe(containerEl);
    canvasW = containerEl.clientWidth;
    canvasH = containerEl.clientHeight;
  });

  onDestroy(() => {
    resizeObserver?.disconnect();
  });

  // -------------------------------------------------------------------------
  // Hit testing for clicks
  // -------------------------------------------------------------------------
  function getCanvasPos(ev: MouseEvent): Point {
    if (!canvasEl) return { x: 0, y: 0 };
    const rect = canvasEl.getBoundingClientRect();
    const dpr = window.devicePixelRatio ?? 1;
    return {
      x: (ev.clientX - rect.left) * (canvasEl.width / rect.width),
      y: (ev.clientY - rect.top) * (canvasEl.height / rect.height),
    };
  }

  function hitAgent(pt: Point, node: AgentNode): boolean {
    return (
      pt.x >= node.cx - node.w / 2 &&
      pt.x <= node.cx + node.w / 2 &&
      pt.y >= node.cy - node.h / 2 &&
      pt.y <= node.cy + node.h / 2
    );
  }

  function hitChannel(pt: Point, node: ChannelNode): boolean {
    const dx = pt.x - node.cx;
    const dy = pt.y - node.cy;
    return Math.sqrt(dx * dx + dy * dy) <= node.r + 8; // 8px tolerance
  }

  function handleClick(ev: MouseEvent) {
    if (!layout) return;
    const pt = getCanvasPos(ev);
    for (const agent of layout.agents) {
      if (hitAgent(pt, agent)) {
        onAgentClick?.(agent.id);
        return;
      }
    }
    for (const ch of layout.channels) {
      if (hitChannel(pt, ch)) {
        onChannelClick?.(ch.id);
        return;
      }
    }
  }

  function handleMouseMove(ev: MouseEvent) {
    if (!layout || !canvasEl) return;
    const pt = getCanvasPos(ev);
    let cursor = "default";
    for (const agent of layout.agents) {
      if (hitAgent(pt, agent)) { cursor = "pointer"; break; }
    }
    if (cursor === "default") {
      for (const ch of layout.channels) {
        if (hitChannel(pt, ch)) { cursor = "pointer"; break; }
      }
    }
    canvasEl.style.cursor = cursor;
  }

  // -------------------------------------------------------------------------
  // Drawing
  // -------------------------------------------------------------------------

  // Colors
  const C_GRAY = "#9ca3af";          // agent / channel / subscription / boundary
  const C_GRAY_DARK = "#6b7280";     // agent label
  const C_GRAY_FILL = "transparent"; // agent fill (unfilled boundary)
  const C_AGENT_FILL = "#f9fafb";    // very light fill for agents
  const C_AGENT_SELECTED = "#dbeafe"; // selected agent fill
  const C_AGENT_BORDER = "#9ca3af";
  const C_BOUNDARY = "#d1d5db";      // sandbox boundary
  const C_BLUE = "#3b82f6";          // data-flow lines
  const C_BLUE_LABEL = "#1d4ed8";
  const C_EXT_FILL = "#f0f9ff";      // external node fill
  const C_EXT_BORDER = "#93c5fd";
  const C_STATUS_ACTIVE = "#22c55e";
  const C_STATUS_IDLE = "#9ca3af";
  const C_STATUS_RL = "#f59e0b";
  const C_STATUS_CRASH = "#ef4444";
  const FONT = "13px Inter, system-ui, sans-serif";
  const FONT_SMALL = "11px Inter, system-ui, sans-serif";
  const FONT_LABEL = "bold 13px Inter, system-ui, sans-serif";
  const BOUNDARY_R = 16;
  const AGENT_R = 8;
  const EXT_R = 6;

  function clearCanvas(canvas: HTMLCanvasElement) {
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }

  function agentStatusColor(status: AgentNode["status"]): string {
    switch (status) {
      case "active": return C_STATUS_ACTIVE;
      case "rate_limited": return C_STATUS_RL;
      case "crashed": return C_STATUS_CRASH;
      default: return C_STATUS_IDLE;
    }
  }

  function draw(canvas: HTMLCanvasElement, layout: CanvasLayout, selAgentId: string | null) {
    const dpr = window.devicePixelRatio ?? 1;
    if (canvas.width !== Math.round(canvasW * dpr) || canvas.height !== Math.round(canvasH * dpr)) {
      canvas.width = Math.round(canvasW * dpr);
      canvas.height = Math.round(canvasH * dpr);
    }
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.save();
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, canvasW, canvasH);

    // -- 1. Gray subscription edges (agent → channel) --
    ctx.save();
    ctx.strokeStyle = C_GRAY;
    ctx.lineWidth = 1;
    ctx.globalAlpha = 0.5;
    for (const edge of layout.subscriptionEdges) {
      const agent = layout.agents.find((a) => a.id === edge.agentId);
      const ch = layout.channels.find((c) => c.id === edge.channelId);
      if (!agent || !ch) continue;
      ctx.beginPath();
      ctx.moveTo(agent.cx, agent.cy);
      ctx.lineTo(ch.cx, ch.cy);
      ctx.stroke();
    }
    ctx.restore();

    // -- 2. Gray dashed hierarchy edges (parent → child) --
    ctx.save();
    ctx.strokeStyle = C_GRAY;
    ctx.lineWidth = 1.5;
    ctx.setLineDash([5, 4]);
    ctx.globalAlpha = 0.7;
    for (const edge of layout.hierarchyEdges) {
      const parent = layout.agents.find((a) => a.id === edge.parentId);
      const child = layout.agents.find((a) => a.id === edge.childId);
      if (!parent || !child) continue;
      ctx.beginPath();
      ctx.moveTo(parent.cx, parent.cy);
      ctx.lineTo(child.cx, child.cy);
      ctx.stroke();
    }
    ctx.restore();

    // -- 3. Blue data-flow edges --
    // Group by externalId to deduplicate the external→entryPoint segment
    const extEdgesSeen = new Set<string>();
    ctx.save();
    ctx.strokeStyle = C_BLUE;
    ctx.lineWidth = 1.5;
    ctx.globalAlpha = 0.7;

    for (const edge of layout.dataFlowEdges) {
      const agent = layout.agents.find((a) => a.id === edge.agentId);
      if (!agent) continue;
      // Agent → entry point
      ctx.beginPath();
      ctx.moveTo(agent.cx, agent.cy);
      ctx.lineTo(layout.entryPoint.x, layout.entryPoint.y);
      ctx.stroke();
    }

    // External → entry point (one per unique externalId)
    for (const edge of layout.dataFlowEdges) {
      if (extEdgesSeen.has(edge.externalId)) continue;
      extEdgesSeen.add(edge.externalId);
      const ext = layout.externals.find((n) => n.id === edge.externalId);
      if (!ext) continue;
      ctx.beginPath();
      ctx.moveTo(ext.cx, ext.cy);
      ctx.lineTo(layout.entryPoint.x, layout.entryPoint.y);
      ctx.stroke();
    }
    ctx.restore();

    // Data-flow arrows (subtle arrowhead at external node end for direction)
    for (const edge of layout.dataFlowEdges) {
      if (!extEdgesSeen.has(edge.externalId + "_arrow")) {
        extEdgesSeen.add(edge.externalId + "_arrow");
        const ext = layout.externals.find((n) => n.id === edge.externalId);
        if (ext) {
          drawArrowhead(ctx, layout.entryPoint, { x: ext.cx, y: ext.cy }, edge.direction, C_BLUE);
        }
      }
    }

    // -- 4. Sandbox boundary --
    const { boundary } = layout;
    ctx.save();
    ctx.strokeStyle = C_BOUNDARY;
    ctx.lineWidth = 1.5;
    ctx.setLineDash([]);
    roundRect(ctx, boundary.x, boundary.y, boundary.w, boundary.h, BOUNDARY_R);
    ctx.stroke();
    ctx.restore();

    // Sandbox label
    ctx.save();
    ctx.font = FONT_LABEL;
    ctx.fillStyle = C_GRAY_DARK;
    ctx.textAlign = "left";
    ctx.fillText(
      snapshot?.display_name ?? snapshot?.sandbox_id ?? "",
      boundary.x + 14,
      boundary.y + 18
    );
    ctx.restore();

    // Entry point dot on boundary wall
    ctx.save();
    ctx.beginPath();
    ctx.arc(layout.entryPoint.x, layout.entryPoint.y, 5, 0, Math.PI * 2);
    ctx.fillStyle = C_BLUE;
    ctx.fill();
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.restore();

    // Entry point label
    ctx.save();
    ctx.font = FONT_SMALL;
    ctx.fillStyle = C_BLUE_LABEL;
    ctx.textAlign = "right";
    ctx.fillText("bus", layout.entryPoint.x - 8, layout.entryPoint.y + 4);
    ctx.restore();

    // -- 5. Channel rings --
    for (const ch of layout.channels) {
      ctx.save();
      ctx.strokeStyle = C_GRAY;
      ctx.lineWidth = 1.5;
      ctx.globalAlpha = 0.8;
      ctx.beginPath();
      ctx.arc(ch.cx, ch.cy, ch.r, 0, Math.PI * 2);
      ctx.stroke();
      // Channel label below ring
      ctx.globalAlpha = 1;
      ctx.font = FONT_SMALL;
      ctx.fillStyle = C_GRAY_DARK;
      ctx.textAlign = "center";
      ctx.fillText(`#${ch.label}`, ch.cx, ch.cy + ch.r + 13);
      ctx.restore();
    }

    // -- 6. Agent nodes --
    for (const agent of layout.agents) {
      const isSelected = agent.id === selAgentId;
      ctx.save();

      // Drop shadow for selected
      if (isSelected) {
        ctx.shadowColor = "rgba(59,130,246,0.35)";
        ctx.shadowBlur = 10;
      }

      // Fill
      roundRect(ctx, agent.cx - agent.w / 2, agent.cy - agent.h / 2, agent.w, agent.h, AGENT_R);
      ctx.fillStyle = isSelected ? C_AGENT_SELECTED : C_AGENT_FILL;
      ctx.fill();

      // Border
      ctx.strokeStyle = isSelected ? C_BLUE : C_AGENT_BORDER;
      ctx.lineWidth = isSelected ? 2 : 1;
      ctx.stroke();

      ctx.shadowBlur = 0;
      ctx.shadowColor = "transparent";

      // Status dot
      const dotR = 4;
      ctx.beginPath();
      ctx.arc(agent.cx - agent.w / 2 + 10, agent.cy, dotR, 0, Math.PI * 2);
      ctx.fillStyle = agentStatusColor(agent.status);
      ctx.fill();

      // Label
      ctx.font = FONT;
      ctx.fillStyle = isSelected ? "#1d4ed8" : C_GRAY_DARK;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(agent.label, agent.cx + 4, agent.cy);
      ctx.restore();
    }

    // -- 7. External nodes --
    for (const ext of layout.externals) {
      ctx.save();
      roundRect(ctx, ext.cx - ext.w / 2, ext.cy - ext.h / 2, ext.w, ext.h, EXT_R);
      ctx.fillStyle = C_EXT_FILL;
      ctx.fill();
      ctx.strokeStyle = C_EXT_BORDER;
      ctx.lineWidth = 1;
      ctx.stroke();

      // Kind badge color strip at left edge
      const badgeColor =
        ext.nodeKind === "data_source"
          ? "#60a5fa"
          : ext.nodeKind === "action"
          ? "#34d399"
          : "#a78bfa"; // event_source = purple
      ctx.fillStyle = badgeColor;
      roundRectLeft(ctx, ext.cx - ext.w / 2, ext.cy - ext.h / 2, 5, ext.h, EXT_R);
      ctx.fill();

      // Label
      ctx.font = FONT_SMALL;
      ctx.fillStyle = "#1e40af";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(ext.label, ext.cx + 2, ext.cy, ext.w - 14);
      ctx.restore();
    }

    ctx.restore(); // outer dpr scale
  }

  // -------------------------------------------------------------------------
  // Drawing helpers
  // -------------------------------------------------------------------------

  function roundRect(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    w: number,
    h: number,
    r: number
  ) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.arcTo(x + w, y, x + w, y + r, r);
    ctx.lineTo(x + w, y + h - r);
    ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
    ctx.lineTo(x + r, y + h);
    ctx.arcTo(x, y + h, x, y + h - r, r);
    ctx.lineTo(x, y + r);
    ctx.arcTo(x, y, x + r, y, r);
    ctx.closePath();
  }

  /** Left-side rounded rect (only left corners rounded) for badge strip */
  function roundRectLeft(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    w: number,
    h: number,
    r: number
  ) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w, y);
    ctx.lineTo(x + w, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.arcTo(x, y + h, x, y + h - r, r);
    ctx.lineTo(x, y + r);
    ctx.arcTo(x, y, x + r, y, r);
    ctx.closePath();
  }

  function drawArrowhead(
    ctx: CanvasRenderingContext2D,
    from: Point,
    to: Point,
    direction: "inbound" | "outbound",
    color: string
  ) {
    // Arrow tip is at the external node side
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    const len = Math.sqrt(dx * dx + dy * dy);
    if (len < 1) return;
    const ux = dx / len;
    const uy = dy / len;

    // For inbound: arrow points from external toward entry (tip at entry point end)
    // For outbound: arrow points from entry toward external (tip at external end)
    const tipX = direction === "outbound" ? to.x : from.x;
    const tipY = direction === "outbound" ? to.y : from.y;
    // Direction the arrowhead points
    const ax = direction === "outbound" ? ux : -ux;
    const ay = direction === "outbound" ? uy : -uy;

    const arrowLen = 8;
    const arrowW = 4;

    ctx.save();
    ctx.fillStyle = color;
    ctx.globalAlpha = 0.8;
    ctx.beginPath();
    ctx.moveTo(tipX, tipY);
    ctx.lineTo(tipX - arrowLen * ax + arrowW * ay, tipY - arrowLen * ay - arrowW * ax);
    ctx.lineTo(tipX - arrowLen * ax - arrowW * ay, tipY - arrowLen * ay + arrowW * ax);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  }
</script>

<div
  bind:this={containerEl}
  class="relative w-full h-full overflow-hidden bg-[#fafafa]"
>
  {#if !snapshot}
    <div class="absolute inset-0 flex flex-col items-center justify-center text-gray-400 gap-2">
      <p class="text-lg font-medium">No sandbox connected</p>
      <p class="text-sm">Waiting for data…</p>
    </div>
  {:else}
    <canvas
      bind:this={canvasEl}
      style="width:{canvasW}px;height:{canvasH}px;"
      onclick={handleClick}
      onmousemove={handleMouseMove}
      class="block"
    ></canvas>

    <!-- Legend overlay (bottom-left) -->
    <div class="absolute bottom-3 left-3 flex flex-col gap-1 text-[11px] text-gray-500 bg-white/80 border border-gray-100 rounded px-2.5 py-2 shadow-sm select-none">
      <div class="flex items-center gap-1.5"><span class="inline-block w-3 h-3 rounded-sm bg-gray-100 border border-gray-300"></span> Agent</div>
      <div class="flex items-center gap-1.5"><svg width="14" height="14"><circle cx="7" cy="7" r="5" fill="none" stroke="#9ca3af" stroke-width="1.5"/></svg> Channel</div>
      <div class="flex items-center gap-1.5"><span class="inline-block w-6 border-t border-gray-400 border-dashed"></span> Hierarchy</div>
      <div class="flex items-center gap-1.5"><span class="inline-block w-6 border-t-2 border-blue-400"></span> Data flow</div>
    </div>
  {/if}
</div>
