/**
 * Canvas layout computation for Phase 14.
 *
 * Computes positions for agents, channels, sandbox boundary, and external
 * nodes from a SandboxSnapshot. All rendering is done by SandboxCanvas.svelte;
 * this module is pure layout math.
 */

import type { SandboxSnapshot, AgentInfo, ChannelInfo, ExternalNodeInfo } from "./types";

export interface Point {
  x: number;
  y: number;
}

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface AgentNode {
  kind: "agent";
  id: string;
  label: string;
  status: AgentInfo["status"];
  thread_alive: boolean;
  cx: number;
  cy: number;
  w: number;
  h: number;
  /** policy-permitted external service IDs */
  allowedDataSources: string[];
  allowedActions: string[];
  allowedEventSources: string[];
}

export interface ChannelNode {
  kind: "channel";
  id: string;
  label: string;
  cx: number;
  cy: number;
  r: number;
  memberIds: string[];
}

export interface ExternalNode {
  kind: "external";
  id: string;
  label: string;
  nodeKind: "data_source" | "action" | "event_source";
  cx: number;
  cy: number;
  w: number;
  h: number;
}

export interface EntryPoint {
  /** Position on sandbox boundary wall where all blue data-flow lines meet */
  x: number;
  y: number;
}

export interface CanvasLayout {
  boundary: Rect;
  entryPoint: EntryPoint;
  agents: AgentNode[];
  channels: ChannelNode[];
  externals: ExternalNode[];
  /** Subscription edges: agent → channel */
  subscriptionEdges: Array<{ agentId: string; channelId: string }>;
  /** Hierarchy edges: parent → child (dashed gray) */
  hierarchyEdges: Array<{ parentId: string; childId: string }>;
  /**
   * Data-flow edges: agent → entry point → external node (blue)
   * direction: "inbound" = DataSource/EventSource, "outbound" = Action
   */
  dataFlowEdges: Array<{
    agentId: string;
    externalId: string;
    label: string;
    direction: "inbound" | "outbound";
  }>;
}

const AGENT_W = 120;
const AGENT_H = 44;
const CHANNEL_R = 22;
const EXT_W = 130;
const EXT_H = 38;

const BOUNDARY_PAD_X = 48;
const BOUNDARY_PAD_Y = 48;
const BOUNDARY_TOP_PAD = 32; // extra top for label

const AGENT_ROW_GAP = 20;
const AGENT_COL_GAP = 30;

const EXT_GAP = 18; // gap between external node and sandbox boundary
const EXT_SPACING = 14; // vertical spacing between external nodes on same side

/**
 * Compute a full canvas layout from a sandbox snapshot.
 * The sandbox boundary is positioned at the center-left of the canvas;
 * DataSources go to the left, Actions to the right, EventSources below.
 */
export function computeLayout(
  snapshot: SandboxSnapshot,
  canvasW: number,
  canvasH: number
): CanvasLayout {
  const agents = snapshot.agents;
  const channels = snapshot.channels;
  const externals = snapshot.external_nodes ?? [];

  // -------------------------------------------------------------------------
  // 1. Compute sandbox interior dimensions
  // -------------------------------------------------------------------------

  const cols = Math.max(1, Math.ceil(Math.sqrt(agents.length)));
  const rows = Math.ceil(agents.length / cols);

  const innerW =
    cols * AGENT_W + (cols - 1) * AGENT_COL_GAP;
  const innerH =
    rows * AGENT_H + (rows - 1) * AGENT_ROW_GAP +
    (channels.length > 0 ? CHANNEL_R * 2 + AGENT_ROW_GAP * 2 : 0);

  const boundaryW = innerW + BOUNDARY_PAD_X * 2;
  const boundaryH = innerH + BOUNDARY_PAD_Y * 2 + BOUNDARY_TOP_PAD;

  // -------------------------------------------------------------------------
  // 2. Classify external nodes
  // -------------------------------------------------------------------------
  const dataSources = externals.filter((n) => n.kind === "data_source");
  const actions = externals.filter((n) => n.kind === "action");
  const eventSources = externals.filter((n) => n.kind === "event_source");

  // Left column width for DataSources
  const leftColW = dataSources.length > 0 ? EXT_W + EXT_GAP * 2 : EXT_GAP;
  // Right column width for Actions
  const rightColW = actions.length > 0 ? EXT_W + EXT_GAP * 2 : EXT_GAP;
  // Bottom row height for EventSources
  const bottomRowH = eventSources.length > 0 ? EXT_H + EXT_GAP * 2 : EXT_GAP;

  // Total canvas area needed — we'll center everything
  const totalW = leftColW + boundaryW + rightColW;
  const totalH = boundaryH + bottomRowH;

  // Offset to center in canvas
  const offsetX = Math.max(0, (canvasW - totalW) / 2);
  const offsetY = Math.max(0, (canvasH - totalH) / 2);

  // -------------------------------------------------------------------------
  // 3. Sandbox boundary position
  // -------------------------------------------------------------------------
  const boundary: Rect = {
    x: offsetX + leftColW,
    y: offsetY,
    w: boundaryW,
    h: boundaryH,
  };

  // Entry point: mid-left wall of sandbox boundary
  const entryPoint: EntryPoint = {
    x: boundary.x,
    y: boundary.y + boundary.h / 2,
  };

  // -------------------------------------------------------------------------
  // 4. Agent node positions (grid inside boundary)
  // -------------------------------------------------------------------------
  const agentNodes: AgentNode[] = agents.map((a, i) => {
    const col = i % cols;
    const row = Math.floor(i / cols);
    const cx =
      boundary.x +
      BOUNDARY_PAD_X +
      col * (AGENT_W + AGENT_COL_GAP) +
      AGENT_W / 2;
    const cy =
      boundary.y +
      BOUNDARY_PAD_Y +
      BOUNDARY_TOP_PAD +
      row * (AGENT_H + AGENT_ROW_GAP) +
      AGENT_H / 2;

    const ps = a.policy_summary as Record<string, string[]> | null;
    return {
      kind: "agent",
      id: a.agent_id,
      label: a.agent_id,
      status: a.status,
      thread_alive: a.thread_alive,
      cx,
      cy,
      w: AGENT_W,
      h: AGENT_H,
      allowedDataSources: ps?.allowed_data_sources ?? [],
      allowedActions: ps?.allowed_actions ?? [],
      allowedEventSources: ps?.allowed_event_sources ?? [],
    };
  });

  // -------------------------------------------------------------------------
  // 5. Channel node positions (below agents, evenly spaced)
  // -------------------------------------------------------------------------
  const channelBaseY =
    boundary.y +
    BOUNDARY_PAD_Y +
    BOUNDARY_TOP_PAD +
    rows * (AGENT_H + AGENT_ROW_GAP) +
    AGENT_ROW_GAP;

  const channelSpacingX =
    channels.length > 1
      ? (boundaryW - BOUNDARY_PAD_X * 2) / (channels.length - 1)
      : 0;

  const channelNodes: ChannelNode[] = channels.map((ch, i) => {
    const cx =
      channels.length === 1
        ? boundary.x + boundaryW / 2
        : boundary.x + BOUNDARY_PAD_X + i * channelSpacingX;
    return {
      kind: "channel",
      id: ch.channel_id,
      label: ch.channel_id,
      cx,
      cy: channelBaseY + CHANNEL_R,
      r: CHANNEL_R,
      memberIds: ch.member_ids,
    };
  });

  // -------------------------------------------------------------------------
  // 6. External node positions
  // -------------------------------------------------------------------------
  function stackNodes(
    nodes: ExternalNodeInfo[],
    cx: number,
    startY: number
  ): ExternalNode[] {
    return nodes.map((n, i) => ({
      kind: "external" as const,
      id: n.node_id,
      label: n.node_id,
      nodeKind: n.kind,
      cx,
      cy: startY + i * (EXT_H + EXT_SPACING) + EXT_H / 2,
      w: EXT_W,
      h: EXT_H,
    }));
  }

  // Left: DataSources
  const dsStartY =
    boundary.y +
    (boundaryH - (dataSources.length * EXT_H + Math.max(0, dataSources.length - 1) * EXT_SPACING)) / 2;
  const dataSourceNodes = stackNodes(
    dataSources,
    offsetX + EXT_W / 2 + EXT_GAP,
    dsStartY
  );

  // Right: Actions
  const actStartY =
    boundary.y +
    (boundaryH - (actions.length * EXT_H + Math.max(0, actions.length - 1) * EXT_SPACING)) / 2;
  const actionNodes = stackNodes(
    actions,
    boundary.x + boundary.w + EXT_GAP + EXT_W / 2,
    actStartY
  );

  // Below: EventSources (centered, horizontal row)
  const evtTotalW =
    eventSources.length * EXT_W + Math.max(0, eventSources.length - 1) * EXT_SPACING;
  const evtStartX = boundary.x + (boundaryW - evtTotalW) / 2;
  const evtY = boundary.y + boundaryH + EXT_GAP + EXT_H / 2;
  const eventSourceNodes: ExternalNode[] = eventSources.map((n, i) => ({
    kind: "external",
    id: n.node_id,
    label: n.node_id,
    nodeKind: n.kind,
    cx: evtStartX + i * (EXT_W + EXT_SPACING) + EXT_W / 2,
    cy: evtY,
    w: EXT_W,
    h: EXT_H,
  }));

  const externalNodes = [...dataSourceNodes, ...actionNodes, ...eventSourceNodes];

  // -------------------------------------------------------------------------
  // 7. Subscription edges
  // -------------------------------------------------------------------------
  const subscriptionEdges: CanvasLayout["subscriptionEdges"] = [];
  for (const ch of channels) {
    for (const memberId of ch.member_ids) {
      subscriptionEdges.push({ agentId: memberId, channelId: ch.channel_id });
    }
  }

  // -------------------------------------------------------------------------
  // 8. Hierarchy edges
  // -------------------------------------------------------------------------
  const hierarchyEdges: CanvasLayout["hierarchyEdges"] =
    (snapshot.agent_relationships ?? []).map((r) => ({
      parentId: r.parent_id,
      childId: r.child_id,
    }));

  // -------------------------------------------------------------------------
  // 9. Data-flow edges (blue)
  // -------------------------------------------------------------------------
  const dataFlowEdges: CanvasLayout["dataFlowEdges"] = [];

  for (const agent of agentNodes) {
    for (const dsId of agent.allowedDataSources) {
      if (externalNodes.find((n) => n.id === dsId)) {
        dataFlowEdges.push({
          agentId: agent.id,
          externalId: dsId,
          label: dsId,
          direction: "inbound",
        });
      }
    }
    for (const actId of agent.allowedActions) {
      if (externalNodes.find((n) => n.id === actId)) {
        dataFlowEdges.push({
          agentId: agent.id,
          externalId: actId,
          label: actId,
          direction: "outbound",
        });
      }
    }
    for (const esId of agent.allowedEventSources) {
      if (externalNodes.find((n) => n.id === esId)) {
        dataFlowEdges.push({
          agentId: agent.id,
          externalId: esId,
          label: esId,
          direction: "inbound",
        });
      }
    }
  }

  return {
    boundary,
    entryPoint,
    agents: agentNodes,
    channels: channelNodes,
    externals: externalNodes,
    subscriptionEdges,
    hierarchyEdges,
    dataFlowEdges,
  };
}
