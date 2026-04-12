const PREFIX = "[harvest]";

export const log = {
  // WebSocket lifecycle
  wsConnecting: (url: string) =>
    console.log(`${PREFIX} [ws] connecting to ${url}`),
  wsConnected: (url: string) =>
    console.log(`${PREFIX} [ws] connected to ${url}`),
  wsDisconnected: (code: number, reason: string) =>
    console.warn(`${PREFIX} [ws] disconnected code=${code} reason="${reason}"`),
  wsReconnecting: (attempt: number, delayMs: number) =>
    console.log(`${PREFIX} [ws] reconnecting attempt=${attempt} delay=${delayMs}ms`),
  wsError: (error: Event) =>
    console.error(`${PREFIX} [ws] error`, error),

  // Message protocol
  wsMessageReceived: (type: string, sizeBytes: number) =>
    console.log(`${PREFIX} [ws] received type="${type}" size=${sizeBytes}B`),
  wsParseError: (raw: string, error: unknown) =>
    console.error(`${PREFIX} [ws] parse error`, { raw: raw.slice(0, 200), error }),

  // Snapshot handling
  snapshotApplied: (sandboxCount: number, agentCount: number, channelCount: number, messageCount: number) =>
    console.log(`${PREFIX} [state] snapshot applied sandboxes=${sandboxCount} agents=${agentCount} channels=${channelCount} messages=${messageCount}`),
  deltaApplied: (newMessages: number, totalMessages: number) =>
    console.log(`${PREFIX} [state] delta applied new=${newMessages} total=${totalMessages}`),
  resyncDetected: () =>
    console.log(`${PREFIX} [state] periodic re-sync snapshot received`),

  // Render cycle
  renderUpdate: (sandboxId: string, agents: number, channels: number, messages: number) =>
    console.debug(`${PREFIX} [render] sandbox="${sandboxId}" agents=${agents} channels=${channels} messages=${messages}`),

  // State summaries
  stateSummary: (state: Record<string, unknown>) =>
    console.log(`${PREFIX} [state] current`, JSON.stringify(state, null, 2)),
};
