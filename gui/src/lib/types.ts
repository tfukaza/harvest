export interface ActivityEntry {
  type: "thinking" | "tool_call" | "tool_result" | "text" | "summary";
  timestamp: string;
  content?: string;
  tool_name?: string;
  tool_args?: string;
  tool_call_id?: string;
  tokens_before?: number;
  tokens_after?: number;
}

export interface AgentMemory {
  name: string;
  description: string;
  content: string;
}

export interface AgentTodo {
  id: string;
  task: string;
  done: boolean;
}

export interface AgentInfo {
  agent_id: string;
  agent_type: string;
  thread_alive: boolean;
  policy_summary: Record<string, unknown> | null;
  status: "idle" | "active" | "rate_limited" | "crashed";
  activity?: ActivityEntry[];
  memories?: AgentMemory[];
  todos?: AgentTodo[];
  cognitive_tools?: string[];
  context_tokens?: number;
  context_limit?: number;
  compaction_threshold?: number;
}

export interface ChannelInfo {
  channel_id: string;
  channel_type: string;
  title: string;
  member_ids: string[];
  publisher_ids: string[];
  subscriber_ids: string[];
}

export interface MessageInfo {
  message_id: string;
  channel_id: string;
  sender_id: string;
  content: string;
  timestamp: string;
  reply_to?: string;
}

// Phase 13 external interface nodes registered to a sandbox
export interface ExternalNodeInfo {
  node_id: string;       // stable service ID, e.g. "alpaca-market-data"
  node_type: string;     // implementation class, e.g. "alpaca_market_data"
  kind: "data_source" | "action" | "event_source";
  capabilities: string[];
}

// Agent parent/child relationship for hierarchy rendering
export interface AgentRelationship {
  parent_id: string;
  child_id: string;
}

export interface SandboxSnapshot {
  sandbox_id: string;
  display_name: string;
  agents: AgentInfo[];
  channels: ChannelInfo[];
  recent_messages: MessageInfo[];
  typing: Record<string, string[]>;
  snapshot_timestamp: string;
  // Phase 13 external interface nodes (optional; absent when backend not yet updated)
  external_nodes?: ExternalNodeInfo[];
  // Agent hierarchy edges (optional)
  agent_relationships?: AgentRelationship[];
}

export interface DeltaMessageEntry {
  sandbox_id: string;
  message_id: string;
  channel_id: string;
  sender_id: string;
  content: string;
  timestamp: string;
  reply_to?: string;
}

export interface SnapshotMessage {
  type: "snapshot";
  timestamp: string;
  sandboxes: SandboxSnapshot[];
}

export interface DeltaMessage {
  type: "delta";
  timestamp: string;
  messages: DeltaMessageEntry[];
}

export interface TypingMessage {
  type: "typing";
  sandbox_id: string;
  channel_id: string;
  agent_id: string;
  active: boolean;
}

export interface AgentStatusMessage {
  type: "agent_status";
  sandbox_id: string;
  agent_id: string;
  status: "idle" | "active" | "rate_limited" | "crashed";
}

export interface AdminQueuedMessage {
  type: "admin_queued";
  sandbox_id: string;
  channel_id: string;
  message_id: string;
}

export interface AdminBlockedMessage {
  type: "admin_blocked";
  reason: string;
}

/** Message sent from the frontend to inject a human message into a channel. */
export interface AdminSendMessage {
  type: "admin_send";
  sandbox_id: string;
  channel_id: string;
  content: string;
}

export type ServerMessage = SnapshotMessage | DeltaMessage | TypingMessage | AgentStatusMessage | AdminQueuedMessage | AdminBlockedMessage;
