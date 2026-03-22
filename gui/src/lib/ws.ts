import { writable, type Readable } from "svelte/store";
import type { SnapshotMessage, DeltaMessage, TypingMessage, AgentStatusMessage, ServerMessage, SandboxSnapshot } from "./types";
import { log } from "./logger";

function getWsUrl(): string {
  if (typeof window !== "undefined") {
    const params = new URLSearchParams(window.location.search);
    const override = params.get("ws");
    if (override) return override;
  }
  return "ws://localhost:8100/ws";
}

interface WsState {
  connected: boolean;
  sandboxes: SandboxSnapshot[];
  lastUpdate: string | null;
  typing: Map<string, Set<string>>; // channel_id → set of agent_ids
}

const initial: WsState = { connected: false, sandboxes: [], lastUpdate: null, typing: new Map() };
const store = writable<WsState>(initial);

let ws: WebSocket | null = null;
let reconnectAttempt = 0;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let isFirstSnapshot = true;
// Auto-expire timers for typing indicators (safety net)
const typingTimers = new Map<string, ReturnType<typeof setTimeout>>();

function connect() {
  const url = getWsUrl();
  log.wsConnecting(url);
  ws = new WebSocket(url);

  ws.onopen = () => {
    log.wsConnected(url);
    reconnectAttempt = 0;
    isFirstSnapshot = true;
    store.update((s) => ({ ...s, connected: true }));
  };

  ws.onclose = (ev) => {
    log.wsDisconnected(ev.code, ev.reason);
    store.update((s) => ({ ...s, connected: false }));
    scheduleReconnect();
  };

  ws.onerror = (ev) => {
    log.wsError(ev);
  };

  ws.onmessage = (ev) => {
    const raw = ev.data as string;
    let msg: ServerMessage;
    try {
      msg = JSON.parse(raw);
    } catch (err) {
      log.wsParseError(raw, err);
      return;
    }

    log.wsMessageReceived(msg.type, raw.length);

    if (msg.type === "snapshot") {
      applySnapshot(msg);
    } else if (msg.type === "delta") {
      applyDelta(msg);
    } else if (msg.type === "typing") {
      applyTyping(msg);
    } else if (msg.type === "agent_status") {
      applyAgentStatus(msg);
    }
  };
}

function applySnapshot(msg: SnapshotMessage) {
  if (!isFirstSnapshot) {
    log.resyncDetected();
  }
  isFirstSnapshot = false;

  const agentCount = msg.sandboxes.reduce((n, s) => n + s.agents.length, 0);
  const channelCount = msg.sandboxes.reduce((n, s) => n + s.channels.length, 0);
  const messageCount = msg.sandboxes.reduce((n, s) => n + s.recent_messages.length, 0);
  log.snapshotApplied(msg.sandboxes.length, agentCount, channelCount, messageCount);

  // Rebuild typing state from snapshot
  const newTyping = new Map<string, Set<string>>();
  for (const sandbox of msg.sandboxes) {
    if (sandbox.typing) {
      for (const [channelId, agentIds] of Object.entries(sandbox.typing)) {
        const existing = newTyping.get(channelId) ?? new Set<string>();
        for (const aid of agentIds) existing.add(aid);
        newTyping.set(channelId, existing);
      }
    }
  }

  store.set({
    connected: true,
    sandboxes: msg.sandboxes,
    lastUpdate: msg.timestamp,
    typing: newTyping,
  });
}

function applyDelta(msg: DeltaMessage) {
  store.update((state) => {
    const updated = { ...state, lastUpdate: msg.timestamp };
    for (const entry of msg.messages) {
      const sandbox = updated.sandboxes.find((s) => s.sandbox_id === entry.sandbox_id);
      if (sandbox) {
        // Dedup by message_id — skip if already present
        const existing = new Set(sandbox.recent_messages.map((m) => m.message_id));
        if (existing.has(entry.message_id)) continue;
        sandbox.recent_messages = [
          ...sandbox.recent_messages,
          {
            message_id: entry.message_id,
            channel_id: entry.channel_id,
            sender_id: entry.sender_id,
            content: entry.content,
            timestamp: entry.timestamp,
            reply_to: entry.reply_to,
          },
        ];
      }
    }
    const totalMessages = updated.sandboxes.reduce((n, s) => n + s.recent_messages.length, 0);
    log.deltaApplied(msg.messages.length, totalMessages);
    return updated;
  });
}

const TYPING_EXPIRE_MS = 10_000;

function applyTyping(msg: TypingMessage) {
  store.update((state) => {
    const typing = new Map(state.typing);
    const key = `${msg.channel_id}:${msg.agent_id}`;

    if (msg.active) {
      const agents = new Set(typing.get(msg.channel_id) ?? []);
      agents.add(msg.agent_id);
      typing.set(msg.channel_id, agents);

      // Auto-expire after 10s
      const existing = typingTimers.get(key);
      if (existing) clearTimeout(existing);
      typingTimers.set(key, setTimeout(() => {
        typingTimers.delete(key);
        applyTyping({ type: "typing", sandbox_id: msg.sandbox_id, channel_id: msg.channel_id, agent_id: msg.agent_id, active: false });
      }, TYPING_EXPIRE_MS));
    } else {
      const agents = typing.get(msg.channel_id);
      if (agents) {
        const updated = new Set(agents);
        updated.delete(msg.agent_id);
        if (updated.size > 0) {
          typing.set(msg.channel_id, updated);
        } else {
          typing.delete(msg.channel_id);
        }
      }
      const timer = typingTimers.get(key);
      if (timer) {
        clearTimeout(timer);
        typingTimers.delete(key);
      }
    }

    return { ...state, typing };
  });
}

function applyAgentStatus(msg: AgentStatusMessage) {
  store.update((state) => {
    const sandbox = state.sandboxes.find((s) => s.sandbox_id === msg.sandbox_id);
    if (sandbox) {
      const agent = sandbox.agents.find((a) => a.agent_id === msg.agent_id);
      if (agent) {
        agent.status = msg.status;
      }
    }
    return { ...state };
  });
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  reconnectAttempt++;
  const delay = Math.min(1000 * Math.pow(2, reconnectAttempt - 1), 10000);
  log.wsReconnecting(reconnectAttempt, delay);
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connect();
  }, delay);
}

export function initWs() {
  connect();
}

export const wsState: Readable<WsState> = { subscribe: store.subscribe };
