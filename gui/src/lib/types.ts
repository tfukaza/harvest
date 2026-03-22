export interface AgentInfo {
  agent_id: string;
  agent_type: string;
  thread_alive: boolean;
  policy_summary: Record<string, unknown> | null;
  status: "idle" | "active" | "rate_limited" | "crashed";
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

export interface SandboxSnapshot {
  sandbox_id: string;
  display_name: string;
  agents: AgentInfo[];
  channels: ChannelInfo[];
  recent_messages: MessageInfo[];
  typing: Record<string, string[]>;
  snapshot_timestamp: string;
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

export type ServerMessage = SnapshotMessage | DeltaMessage | TypingMessage | AgentStatusMessage;
