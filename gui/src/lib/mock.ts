/**
 * Mock data for frontend development without a running backend.
 *
 * Usage: append ?mock=<scenario> to the dev URL.
 *   ?mock=trading    — Phase 13 sandbox with agents + external nodes (default)
 *   ?mock=simple     — minimal: one agent, one channel
 *   ?mock=hierarchy  — parent/child agent hierarchy
 *   ?mock=true       — alias for "trading"
 */

import type {
  SnapshotMessage,
  DeltaMessage,
  TypingMessage,
  ServerMessage,
  SandboxSnapshot,
} from "./types";

// ---------------------------------------------------------------------------
// Scenario: trading
// A Phase 13 sandbox with analyst/trader/orchestrator agents, three channels,
// and Alpaca DataSource + Action + EventSource external nodes.
// ---------------------------------------------------------------------------

const tradingSnapshot: SandboxSnapshot = {
  sandbox_id: "trading-sandbox",
  display_name: "Trading Sandbox",
  snapshot_timestamp: new Date().toISOString(),
  typing: {},
  external_nodes: [
    {
      node_id: "alpaca-market-data",
      node_type: "alpaca_market_data",
      kind: "data_source",
      capabilities: ["price", "candles", "quotes", "snapshot"],
    },
    {
      node_id: "news-feed",
      node_type: "http_data_source",
      kind: "data_source",
      capabilities: ["headlines", "search"],
    },
    {
      node_id: "alpaca-orders",
      node_type: "alpaca_orders",
      kind: "action",
      capabilities: ["place_order", "cancel_order", "get_positions"],
    },
    {
      node_id: "market-ticks",
      node_type: "market_tick_stream",
      kind: "event_source",
      capabilities: ["price_alert", "tick_stream"],
    },
    {
      node_id: "earnings-calendar",
      node_type: "http_webhook",
      kind: "event_source",
      capabilities: ["earnings_release", "dividend_announcement"],
    },
  ],
  agent_relationships: [],
  agents: [
    {
      agent_id: "orchestrator",
      agent_type: "OrchestratorAgent",
      thread_alive: true,
      status: "idle",
      policy_summary: {
        allowed_data_sources: ["alpaca-market-data", "news-feed"],
        allowed_actions: ["alpaca-orders"],
        allowed_event_sources: ["market-ticks", "earnings-calendar"],
      },
      cognitive_tools: ["think", "memory", "todo"],
      context_tokens: 18200,
      context_limit: 128000,
      compaction_threshold: 0.75,
      activity: [
        { type: "thinking", timestamp: new Date(Date.now() - 60000).toISOString(), content: "I need to coordinate the analyst and trader agents. Let me check the current market conditions first and then delegate tasks." },
        { type: "tool_call", timestamp: new Date(Date.now() - 55000).toISOString(), tool_name: "send_message", tool_args: '{"channel_id":"research","content":"@analyst Please provide a market analysis for AAPL, MSFT, and NVDA."}', tool_call_id: "tc_001" },
        { type: "tool_result", timestamp: new Date(Date.now() - 54000).toISOString(), content: '{"status":"sent","message_id":"msg_abc123"}', tool_call_id: "tc_001" },
        { type: "tool_call", timestamp: new Date(Date.now() - 50000).toISOString(), tool_name: "save_memory", tool_args: '{"name":"session_goal","description":"Current trading session objective","content":"Monitor tech sector: AAPL, MSFT, NVDA. Risk tolerance: moderate."}', tool_call_id: "tc_002" },
        { type: "tool_result", timestamp: new Date(Date.now() - 49000).toISOString(), content: '{"status":"saved","name":"session_goal","total_memories":1}', tool_call_id: "tc_002" },
        { type: "text", timestamp: new Date(Date.now() - 45000).toISOString(), content: "I've delegated the market analysis to the analyst and saved our session goals. Waiting for results." },
      ],
      memories: [
        { name: "session_goal", description: "Current trading session objective", content: "Monitor tech sector: AAPL, MSFT, NVDA. Risk tolerance: moderate. Focus on earnings momentum plays." },
        { name: "risk_limits", description: "Position sizing and risk management rules", content: "Max 5% per position. Stop loss at 2% below entry. Take profit at 3:1 reward/risk ratio." },
      ],
      todos: [
        { id: "a1b2c3d4", task: "Wait for analyst market report", done: false },
        { id: "e5f6g7h8", task: "Review trading signals", done: false },
        { id: "i9j0k1l2", task: "Set up initial watchlist", done: true },
      ],
    },
    {
      agent_id: "analyst",
      agent_type: "AnalystAgent",
      thread_alive: true,
      status: "active",
      policy_summary: {
        allowed_data_sources: ["alpaca-market-data", "news-feed"],
        allowed_actions: [],
        allowed_event_sources: ["market-ticks"],
      },
      cognitive_tools: ["think", "memory"],
      context_tokens: 42500,
      context_limit: 128000,
      compaction_threshold: 0.75,
      activity: [
        { type: "thinking", timestamp: new Date(Date.now() - 40000).toISOString(), content: "The orchestrator wants analysis on AAPL, MSFT, and NVDA. Let me fetch the latest price data and recent news for each." },
        { type: "tool_call", timestamp: new Date(Date.now() - 38000).toISOString(), tool_name: "query_data_source", tool_args: '{"source":"alpaca-market-data","query":"AAPL,MSFT,NVDA","params":{"type":"snapshot"}}', tool_call_id: "tc_010" },
        { type: "tool_result", timestamp: new Date(Date.now() - 36000).toISOString(), content: '{"AAPL":{"price":178.52,"change":"+1.2%","volume":"52M"},"MSFT":{"price":415.80,"change":"+0.8%","volume":"28M"},"NVDA":{"price":890.25,"change":"+3.5%","volume":"67M"}}', tool_call_id: "tc_010" },
        { type: "tool_call", timestamp: new Date(Date.now() - 34000).toISOString(), tool_name: "query_data_source", tool_args: '{"source":"news-feed","query":"AAPL MSFT NVDA tech earnings","params":{"type":"headlines"}}', tool_call_id: "tc_011" },
        { type: "tool_result", timestamp: new Date(Date.now() - 32000).toISOString(), content: '{"headlines":["NVDA surges on AI chip demand forecast","Apple Vision Pro sales beat estimates","Microsoft Azure revenue up 29%"]}', tool_call_id: "tc_011" },
        { type: "thinking", timestamp: new Date(Date.now() - 30000).toISOString(), content: "NVDA shows the strongest momentum with +3.5% and positive AI demand news. AAPL and MSFT are also up. The tech sector looks strong today. Let me compile my analysis." },
        { type: "tool_call", timestamp: new Date(Date.now() - 28000).toISOString(), tool_name: "send_message", tool_args: '{"channel_id":"research","content":"**Market Analysis Report**\\n\\n- **NVDA** $890.25 (+3.5%) - Strong buy signal. AI chip demand forecast driving momentum.\\n- **AAPL** $178.52 (+1.2%) - Moderate buy. Vision Pro sales beating estimates.\\n- **MSFT** $415.80 (+0.8%) - Hold. Azure growth solid but priced in."}', tool_call_id: "tc_012" },
        { type: "tool_result", timestamp: new Date(Date.now() - 27000).toISOString(), content: '{"status":"sent","message_id":"msg_def456"}', tool_call_id: "tc_012" },
      ],
      memories: [
        { name: "nvda_signal", description: "NVDA trading signal from latest analysis", content: "Strong buy signal based on AI chip demand forecast. Price $890.25, up 3.5%. Volume 67M above average." },
      ],
      todos: [],
    },
    {
      agent_id: "trader",
      agent_type: "TraderAgent",
      thread_alive: true,
      status: "idle",
      policy_summary: {
        allowed_data_sources: ["alpaca-market-data"],
        allowed_actions: ["alpaca-orders"],
        allowed_event_sources: ["market-ticks", "earnings-calendar"],
      },
      cognitive_tools: ["think", "todo"],
      context_tokens: 3100,
      context_limit: 128000,
      compaction_threshold: 0.75,
      activity: [
        { type: "thinking", timestamp: new Date(Date.now() - 20000).toISOString(), content: "Waiting for trading signals from the analyst. I'll prepare my order execution plan once the analysis comes in." },
      ],
      memories: [],
      todos: [
        { id: "x1y2z3w4", task: "Await analyst report before placing orders", done: false },
      ],
    },
  ],
  channels: [
    {
      channel_id: "general",
      channel_type: "broadcast",
      title: "General",
      member_ids: ["orchestrator", "analyst", "trader"],
      publisher_ids: ["orchestrator", "analyst", "trader"],
      subscriber_ids: ["orchestrator", "analyst", "trader"],
    },
    {
      channel_id: "research",
      channel_type: "broadcast",
      title: "Research",
      member_ids: ["orchestrator", "analyst"],
      publisher_ids: ["analyst"],
      subscriber_ids: ["orchestrator", "analyst"],
    },
    {
      channel_id: "trades",
      channel_type: "broadcast",
      title: "Trades",
      member_ids: ["orchestrator", "trader"],
      publisher_ids: ["trader"],
      subscriber_ids: ["orchestrator", "trader"],
    },
  ],
  recent_messages: [
    {
      message_id: "msg-t-001",
      channel_id: "general",
      sender_id: "system",
      content: "Trading sandbox initialized",
      timestamp: ts(-120),
    },
    {
      message_id: "msg-t-002",
      channel_id: "general",
      sender_id: "orchestrator",
      content: "Good morning. Markets open in 30 minutes. @analyst please prepare the daily brief.",
      timestamp: ts(-110),
    },
    {
      message_id: "msg-t-003",
      channel_id: "research",
      sender_id: "analyst",
      content: "Pulling overnight data from `alpaca-market-data` and `news-feed`...",
      timestamp: ts(-100),
    },
    {
      message_id: "msg-t-004",
      channel_id: "research",
      sender_id: "analyst",
      content:
        "**AAPL** — up 1.4% pre-market after strong earnings beat.\n**NVDA** — down 0.8%, no news.\nSentiment index: **positive**.",
      timestamp: ts(-90),
    },
    {
      message_id: "msg-t-005",
      channel_id: "general",
      sender_id: "orchestrator",
      content: "@trader review the #research brief. AAPL looks like a candidate.",
      timestamp: ts(-80),
    },
    {
      message_id: "msg-t-006",
      channel_id: "trades",
      sender_id: "trader",
      content: "Checking AAPL position limits before placing order...",
      timestamp: ts(-70),
    },
    {
      message_id: "msg-t-007",
      channel_id: "trades",
      sender_id: "trader",
      content: "Order placed via `alpaca-orders`: BUY 50 AAPL @ market. Request ID: `req-0042`.",
      timestamp: ts(-60),
    },
    {
      message_id: "msg-t-008",
      channel_id: "trades",
      sender_id: "trader",
      content: "Order filled. Avg price $187.32. Position updated.",
      timestamp: ts(-55),
    },
  ],
};

// ---------------------------------------------------------------------------
// Scenario: simple
// One agent, one channel. Good for testing minimal layout.
// ---------------------------------------------------------------------------

const simpleSnapshot: SandboxSnapshot = {
  sandbox_id: "simple-sandbox",
  display_name: "Simple Sandbox",
  snapshot_timestamp: new Date().toISOString(),
  typing: {},
  external_nodes: [],
  agent_relationships: [],
  agents: [
    {
      agent_id: "agent-1",
      agent_type: "BaseAgent",
      thread_alive: true,
      status: "idle",
      policy_summary: null,
    },
  ],
  channels: [
    {
      channel_id: "main",
      channel_type: "broadcast",
      title: "Main",
      member_ids: ["agent-1"],
      publisher_ids: ["agent-1"],
      subscriber_ids: ["agent-1"],
    },
  ],
  recent_messages: [
    {
      message_id: "msg-s-001",
      channel_id: "main",
      sender_id: "system",
      content: "Simple sandbox initialized",
      timestamp: ts(-30),
    },
    {
      message_id: "msg-s-002",
      channel_id: "main",
      sender_id: "agent-1",
      content: "Hello. I am the only agent in this sandbox.",
      timestamp: ts(-20),
    },
  ],
};

// ---------------------------------------------------------------------------
// Scenario: hierarchy
// A supervisor with two worker agents. Tests parent/child rendering.
// ---------------------------------------------------------------------------

const hierarchySnapshot: SandboxSnapshot = {
  sandbox_id: "hierarchy-sandbox",
  display_name: "Hierarchy Sandbox",
  snapshot_timestamp: new Date().toISOString(),
  typing: {},
  external_nodes: [
    {
      node_id: "task-api",
      node_type: "http_data_source",
      kind: "data_source",
      capabilities: ["get_tasks", "search_tasks"],
    },
  ],
  agent_relationships: [
    { parent_id: "supervisor", child_id: "worker-1" },
    { parent_id: "supervisor", child_id: "worker-2" },
  ],
  agents: [
    {
      agent_id: "supervisor",
      agent_type: "SupervisorAgent",
      thread_alive: true,
      status: "active",
      policy_summary: {
        allowed_data_sources: ["task-api"],
        allowed_actions: [],
        allowed_event_sources: [],
        can_create_agents: true,
      },
    },
    {
      agent_id: "worker-1",
      agent_type: "WorkerAgent",
      thread_alive: true,
      status: "active",
      policy_summary: {
        allowed_data_sources: ["task-api"],
        allowed_actions: [],
        allowed_event_sources: [],
      },
    },
    {
      agent_id: "worker-2",
      agent_type: "WorkerAgent",
      thread_alive: true,
      status: "idle",
      policy_summary: {
        allowed_data_sources: ["task-api"],
        allowed_actions: [],
        allowed_event_sources: [],
      },
    },
  ],
  channels: [
    {
      channel_id: "coordination",
      channel_type: "broadcast",
      title: "Coordination",
      member_ids: ["supervisor", "worker-1", "worker-2"],
      publisher_ids: ["supervisor", "worker-1", "worker-2"],
      subscriber_ids: ["supervisor", "worker-1", "worker-2"],
    },
    {
      channel_id: "results",
      channel_type: "broadcast",
      title: "Results",
      member_ids: ["supervisor", "worker-1", "worker-2"],
      publisher_ids: ["worker-1", "worker-2"],
      subscriber_ids: ["supervisor"],
    },
  ],
  recent_messages: [
    {
      message_id: "msg-h-001",
      channel_id: "coordination",
      sender_id: "system",
      content: "Hierarchy sandbox initialized",
      timestamp: ts(-60),
    },
    {
      message_id: "msg-h-002",
      channel_id: "coordination",
      sender_id: "supervisor",
      content: "Dispatching tasks. @worker-1 handle items 1–5. @worker-2 handle items 6–10.",
      timestamp: ts(-50),
    },
    {
      message_id: "msg-h-003",
      channel_id: "coordination",
      sender_id: "worker-1",
      content: "Acknowledged. Starting items 1–5.",
      timestamp: ts(-48),
    },
    {
      message_id: "msg-h-004",
      channel_id: "coordination",
      sender_id: "worker-2",
      content: "Acknowledged. Starting items 6–10.",
      timestamp: ts(-47),
    },
    {
      message_id: "msg-h-005",
      channel_id: "results",
      sender_id: "worker-1",
      content: "Items 1–3 complete. Item 4 has a data gap from `task-api`.",
      timestamp: ts(-30),
    },
    {
      message_id: "msg-h-006",
      channel_id: "coordination",
      sender_id: "supervisor",
      content: "@worker-1 skip item 4, continue with 5.",
      timestamp: ts(-28),
    },
  ],
};

// ---------------------------------------------------------------------------
// Scenario registry
// ---------------------------------------------------------------------------

const SCENARIOS: Record<string, SandboxSnapshot> = {
  trading: tradingSnapshot,
  simple: simpleSnapshot,
  hierarchy: hierarchySnapshot,
};

export function getMockScenario(name: string): string {
  if (name === "true" || name === "") return "trading";
  return name in SCENARIOS ? name : "trading";
}

function makeSnapshot(scenario: string): SnapshotMessage {
  const name = getMockScenario(scenario);
  const sandbox = SCENARIOS[name];
  return {
    type: "snapshot",
    timestamp: new Date().toISOString(),
    sandboxes: [{ ...sandbox, snapshot_timestamp: new Date().toISOString() }],
  };
}

// ---------------------------------------------------------------------------
// Simulated live delta stream
// Emits a new agent message every ~4 seconds to keep the UI feeling live.
// ---------------------------------------------------------------------------

const LIVE_MESSAGES: Array<{ sandbox_id: string; channel_id: string; sender_id: string; content: string }> = [
  { sandbox_id: "trading-sandbox", channel_id: "general", sender_id: "analyst", content: "Market tick received on `market-ticks`. Watching AAPL." },
  { sandbox_id: "trading-sandbox", channel_id: "research", sender_id: "analyst", content: "AAPL momentum still positive. No action recommended yet." },
  { sandbox_id: "trading-sandbox", channel_id: "general", sender_id: "orchestrator", content: "Earnings event on `earnings-calendar` for NVDA tomorrow. @trader flag for review." },
  { sandbox_id: "trading-sandbox", channel_id: "trades", sender_id: "trader", content: "NVDA flagged. Will monitor `market-ticks` for entry signal." },
  { sandbox_id: "hierarchy-sandbox", channel_id: "results", sender_id: "worker-2", content: "Items 6–10 complete. All passed." },
  { sandbox_id: "hierarchy-sandbox", channel_id: "coordination", sender_id: "supervisor", content: "Good. Preparing final summary." },
];

let liveIndex = 0;

function nextLiveMessage(sandboxId: string): DeltaMessage | null {
  const candidates = LIVE_MESSAGES.filter((m) => m.sandbox_id === sandboxId);
  if (candidates.length === 0) return null;
  const m = candidates[liveIndex % candidates.length];
  liveIndex++;
  return {
    type: "delta",
    timestamp: new Date().toISOString(),
    messages: [
      {
        sandbox_id: m.sandbox_id,
        message_id: `mock-delta-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        channel_id: m.channel_id,
        sender_id: m.sender_id,
        content: m.content,
        timestamp: new Date().toISOString(),
      },
    ],
  };
}

function nextTyping(sandboxId: string, scenario: string): TypingMessage | null {
  const sandbox = SCENARIOS[getMockScenario(scenario)];
  if (!sandbox || sandbox.agents.length === 0 || sandbox.channels.length === 0) return null;
  const agent = sandbox.agents[Math.floor(Math.random() * sandbox.agents.length)];
  const channel = sandbox.channels[Math.floor(Math.random() * sandbox.channels.length)];
  return {
    type: "typing",
    sandbox_id: sandboxId,
    channel_id: channel.channel_id,
    agent_id: agent.agent_id,
    active: true,
  };
}

const DELTA_INTERVAL_MS = 4000;
const TYPING_INTERVAL_MS = 6000;

export function startMockStream(scenario: string, dispatch: (msg: ServerMessage) => void): () => void {
  const name = getMockScenario(scenario);
  const sandbox = SCENARIOS[name];
  if (!sandbox) return () => {};

  const sandboxId = sandbox.sandbox_id;

  // Emit initial snapshot immediately
  dispatch(makeSnapshot(name));

  const deltaTimer = setInterval(() => {
    const msg = nextLiveMessage(sandboxId);
    if (msg) dispatch(msg);
  }, DELTA_INTERVAL_MS);

  const typingTimer = setInterval(() => {
    const msg = nextTyping(sandboxId, name);
    if (msg) {
      dispatch(msg);
      // Cancel the typing indicator after 2 seconds
      setTimeout(() => {
        dispatch({ ...msg, active: false });
      }, 2000);
    }
  }, TYPING_INTERVAL_MS);

  return () => {
    clearInterval(deltaTimer);
    clearInterval(typingTimer);
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Return an ISO timestamp offset by `secondsAgo` seconds from now. */
function ts(secondsAgo: number): string {
  return new Date(Date.now() + secondsAgo * 1000).toISOString();
}
