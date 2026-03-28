"""Concrete BasicSandbox implementation for hosting multiple agents."""


import enum
import json
import logging
import random
import threading
from pathlib import Path
from typing import Any

from harvest.core.agent import Agent
from harvest.agent_sandbox.chat import ChatRouter
from harvest.agent_sandbox.config import AgentSandboxConfig
from harvest.agent_sandbox.endpoints import DeliveryMode, GroupChatDefinition, SandboxEndpoint
from harvest.agent_sandbox.hibernation import EventSource, InboxEventSource, WakeEvent
from harvest.agent_sandbox.processors import MessageProcessor
from harvest.agent_sandbox.sandbox import AgentSandbox
from harvest.agent_sandbox.event_helpers import SyncEventBus
from harvest.agent_sandbox.sandbox_gateway import SandboxGateway
from harvest.agent_sandbox.service_router import SandboxServiceRouter
from harvest.agent_sandbox.system_prompt_builder import SystemPromptBuilder
from harvest.events.event_bus import EventBus
from harvest.interfaces.tool_definition import InterfaceTool
from harvest.core.policy import AgentPolicy, ChildPolicyMode
from harvest.core.policy_registry import PolicyRegistry
from harvest.storage.schema.chat import ChatStore

logger = logging.getLogger(__name__)


HIBERNATION_POLL_MIN = 2.0   # seconds
HIBERNATION_POLL_MAX = 8.0   # seconds
WAKE_DEBOUNCE = 0.5          # seconds — pause after wake signal to batch messages


class AgentStatus(enum.Enum):
    """Observable status of an agent in the sandbox."""

    IDLE = "idle"
    ACTIVE = "active"
    RATE_LIMITED = "rate_limited"
    CRASHED = "crashed"
    STOPPED = "stopped"
    UNRECOVERABLE = "unrecoverable"


class _AgentHandle:
    """Internal bookkeeping for a registered agent."""

    def __init__(self, agent: Agent, policy: AgentPolicy | None = None) -> None:
        self.agent = agent
        self.policy = policy
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.wake_signal = threading.Event()
        self.event_sources: list[EventSource] = []
        self._status: AgentStatus = AgentStatus.IDLE
        self._status_callbacks: list[Any] = []

    @property
    def status(self) -> AgentStatus:
        return self._status

    @status.setter
    def status(self, value: AgentStatus) -> None:
        old = self._status
        self._status = value
        if old != value:
            for cb in self._status_callbacks:
                try:
                    cb(value)
                except Exception:
                    pass

    def on_status_changed(self, callback: Any) -> None:
        """Register a callback for status changes. Called with (AgentStatus,)."""
        self._status_callbacks.append(callback)


def _build_identity_footer(agent_id: str) -> str:
    """Build the identity and communication footer appended to every agent's system prompt."""
    return (
        f"\n\n---\n"
        f"Your agent ID is `{agent_id}`. Other agents and the system "
        f"refer to you as @{agent_id}. When you see a message from "
        f"@{agent_id}, that is *you* — do not respond to your own "
        f"messages. When another agent or the moderator mentions "
        f"@{agent_id} in their message, they are addressing you "
        f"directly and you should respond.\n\n"
        f"**How communication works — READ THIS CAREFULLY:**\n"
        f"- To send a message that other agents or users can see, you "
        f"MUST call the `send_message` tool with the appropriate "
        f"channel_id. Plain text responses (i.e. responding without "
        f"calling a tool) are NOT visible to anyone — they disappear "
        f"into the void.\n"
        f"- `think` is your PRIVATE scratchpad for internal reasoning. "
        f"No one else can see it. Use it for planning, analysis, and "
        f"working through problems before acting.\n"
        f"- If you want to communicate, use `send_message`. If you want "
        f"to reason privately, use `think`. Never use plain text "
        f"responses when you intend to communicate — they will not be "
        f"delivered.\n\n"
        f"**How you receive messages:**\n"
        f"When you wake up, new messages are already delivered to you "
        f"in your wake prompt — you do NOT need to call `read_messages` "
        f"to see them. The messages shown at the start of your turn are "
        f"your inbox. You should read them, then act (think, research, "
        f"send a reply, etc.).\n"
        f"- Do NOT call `read_messages` repeatedly to poll for new "
        f"messages. Other agents cannot respond while your turn is "
        f"running, so polling will always return empty results.\n"
        f"- Use `read_messages` only when you need to check a channel "
        f"you are NOT currently being notified about (e.g. reading "
        f"history from a different channel), or when a wake notification "
        f"says \"N new messages in #channel\" without showing content.\n"
        f"- After you send a message, STOP and yield your turn. The "
        f"other agent will respond, and you will wake up again with "
        f"their reply delivered to you automatically.\n\n"
        f"**When to respond vs. stay quiet:** Not every message "
        f"requires a response from you. Use your judgment:\n"
        f"- If a message mentions you by name (@{agent_id}) or uses "
        f"@here, you are being addressed — respond.\n"
        f"- If a message is directed at someone else by name "
        f"(e.g. \"@bob what do you think?\"), let that person "
        f"respond. Do not jump in unless you have something "
        f"genuinely relevant to add.\n"
        f"- If a message is a general statement to the channel "
        f"with no specific @mention, respond only if you have "
        f"something meaningful to contribute.\n"
        f"- Messages from @admin are from a human operator "
        f"with authority over all agents. Treat admin messages "
        f"with the highest priority and urgency. If @admin gives "
        f"you an instruction, follow it immediately and to the "
        f"best of your ability — admin directives override your "
        f"normal conversation flow. Still follow the addressing "
        f"rules: respond if addressed, stay quiet if someone "
        f"else is.\n\n"
        f"**Seed prompts / channel topics:** Messages marked as "
        f"[channel-topic] or with sender \"system\" and "
        f"is_seed_prompt=true describe the channel's topic. They were "
        f"set by the system, not sent by another agent — do not "
        f"address \"system\" as a participant. However, you should "
        f"still engage with the topic: discuss it, act on it, or "
        f"respond to it in the channel as appropriate.\n\n"
        f"**Message awareness:** When you read messages, pay attention "
        f"to the `sender` field on each message. Messages where "
        f"`sender` equals your own agent ID (`{agent_id}`) are "
        f"messages *you* sent — do not respond to them or treat "
        f"them as new input. Only respond to messages from other "
        f"agents or users.\n\n"
        f"**Tool-call limit:** Keep your tool usage efficient. When "
        f"you wake up, read your inbox, send your replies, then stop. "
        f"Do not loop or poll — you will wake again when new messages "
        f"arrive."
    )


class BasicSandbox(AgentSandbox):
    """First concrete agent sandbox with per-agent threading.

    Hosts multiple agents, owns the ChatRouter, enforces policies,
    and mediates between agents and the framework.
    """

    def __init__(
        self,
        config: AgentSandboxConfig,
        policy_registry: PolicyRegistry | None = None,
        event_bus: EventBus | None = None,
        chat_store: ChatStore | None = None,
    ) -> None:
        """Initialize the sandbox.

        Args:
            config: Sandbox configuration.
            policy_registry: Optional shared policy registry.
            event_bus: Optional framework event bus for integration.
            chat_store: Optional ChatStore for message persistence.
        """
        self._config = config
        self._agents: dict[str, _AgentHandle] = {}
        self._lock = threading.Lock()
        self._resources: dict[str, Any] = {}
        self._tools: dict[str, Any] = {}
        self._policy_registry = policy_registry
        self._last_dispatch_results: dict[str, Any] = {}
        self._event_bus = event_bus
        self._running = False
        self._status_callbacks: list[Any] = []  # (agent_id, AgentStatus) -> None

        # Per-sandbox synchronous event bus and gateway for isolation
        self._sandbox_bus = SyncEventBus(name=f"sandbox-{config.runner_id}")
        self._gateway: SandboxGateway | None = None
        if event_bus is not None:
            self._gateway = SandboxGateway(
                sandbox_id=config.runner_id,
                orchestrator_bus=event_bus,
                sandbox_bus=self._sandbox_bus,
            )
            self._gateway.start()

        self._chat_router = ChatRouter(store=chat_store, sandbox_bus=self._sandbox_bus)
        self._service_router = SandboxServiceRouter(
            sandbox_id=config.runner_id,
            event_bus=event_bus,
            sandbox_bus=self._sandbox_bus,
        )

        # Per-agent system prompt builders and injection tracking
        self._prompt_builders: dict[str, SystemPromptBuilder] = {}
        # Per-agent set of tool names already injected (for idempotency)
        self._injected_tool_names: dict[str, set[str]] = {}

        # Phase 18: lifecycle tracking
        self._parent_map: dict[str, str] = {}  # agent_id → parent_id
        self._agent_policies: dict[str, AgentPolicy] = {}
        self._shutdown_reasons: dict[str, str] = {}  # agent_id → reason

        # Subscribe to lifecycle request events on sandbox bus
        self._wire_lifecycle_handlers()

        # Register the event notification callback so the router can push
        # structured event-arrival notifications into the system prompt.
        self._service_router.register_event_notification_callback(
            self._add_event_notification
        )

    @property
    def config(self) -> AgentSandboxConfig:
        """Return the sandbox configuration."""
        return self._config

    @property
    def chat_router(self) -> ChatRouter:
        """Access the sandbox's ChatRouter."""
        return self._chat_router

    @property
    def service_router(self) -> SandboxServiceRouter:
        """Access the sandbox's SandboxServiceRouter."""
        return self._service_router

    # -- Agent management --

    def register_agent(
        self,
        agent_id: str,
        agent: Agent,
        *,
        policy: AgentPolicy | None = None,
    ) -> None:
        """Register an agent with the sandbox and wire all integrations.

        The :class:`~harvest.agent.Agent` base class provides stub
        attributes (``_tools``, ``_tool_map``, ``_chat_client``, etc.)
        with safe defaults, so wiring methods work for both full
        :class:`HarvestAgent` instances and minimal test stubs.

        Wiring steps:

        1. Sets ``agent.agent_id`` and ``agent._sandbox``.
        2. Wires the event-driven chat client (skipped if ``_chat_client``
           is already set).
        3. Attaches a dynamic system-prompt function backed by a
           :class:`SystemPromptBuilder`.
        4. Wires interface tools, discovery tool, generic service tools,
           and cognitive tools.
        5. Subscribes the agent to ``EVENT_SOURCE`` services.
        6. Subscribes to :class:`NewChatMessage` for wake-on-message.
        7. Dispatches an :class:`AgentStarted` lifecycle event.
        8. Starts the agent thread if the sandbox is already running.

        Args:
            agent_id: Unique identifier for the agent.
            agent: The agent instance.
            policy: Optional policy governing the agent.

        Raises:
            ValueError: If the agent_id is already registered.
        """
        with self._lock:
            if agent_id in self._agents:
                raise ValueError(f"Agent already registered: {agent_id}")
            handle = _AgentHandle(agent, policy)
            self._agents[agent_id] = handle

            self._wire_agent_prompt(agent_id, agent)
            self._wire_agent_chat(agent_id, agent, policy)
            self._wire_agent_tools(agent_id, agent, policy)
            self._wire_agent_events(agent_id, handle, policy)

            # Track policy for service routing
            if policy is not None:
                self._agent_policies[agent_id] = policy

            # Start agent thread if sandbox is running
            if self._running:
                self._start_agent_thread(agent_id, handle)

    # -- Agent wiring helpers (called from register_agent) --

    def _wire_agent_prompt(self, agent_id: str, agent: Agent) -> None:
        """Set agent identity and attach a dynamic SystemPromptBuilder."""
        builder = SystemPromptBuilder()
        self._prompt_builders[agent_id] = builder
        self._injected_tool_names[agent_id] = set()

        agent.agent_id = agent_id
        agent._sandbox = self

        # Inject a persistent "context" section with the current date/time.
        # This is rebuilt on each prompt build so agents always see an
        # up-to-date clock.
        def _make_prompt_fn(_aid: str, _agent: Agent) -> Any:
            def _prompt_fn() -> str:
                from harvest.util.date import utc_current_time, get_local_timezone
                import datetime as _dt
                now_utc = utc_current_time()
                try:
                    local_tz = get_local_timezone()
                    now_local = now_utc.astimezone(local_tz)
                    time_str = (
                        f"Current date and time: {now_local.strftime('%A, %B %d, %Y at %H:%M')} "
                        f"({local_tz}) / {now_utc.strftime('%Y-%m-%d %H:%M')} UTC"
                    )
                except Exception:
                    time_str = f"Current date and time: {now_utc.strftime('%A, %B %d, %Y at %H:%M')} UTC"
                self._prompt_builders[_aid].set("context", time_str)
                return self._prompt_builders[_aid].build(_agent.base_system_prompt)
            return _prompt_fn
        agent._system_prompt_fn = _make_prompt_fn(agent_id, agent)

    def _wire_agent_chat(self, agent_id: str, agent: Agent, policy: AgentPolicy | None) -> None:
        """Wire the event-driven chat client (skipped if already wired)."""
        if agent._chat_client is None:
            agent._wire_chat_client(self._sandbox_bus, policy)
            self._chat_router.register_agent(agent_id)

    def _wire_agent_tools(self, agent_id: str, agent: Agent, policy: AgentPolicy | None) -> None:
        """Register interface, discovery, service, and cognitive tools."""
        interface_tool_pairs = self._service_router.wire_agent_tools(agent_id, policy)

        for tool_spec, tool_callable in interface_tool_pairs:
            agent._tools.append(tool_spec)
            agent._tool_map[tool_spec["function"]["name"]] = tool_callable

        # Register the discover_tools callable
        discovery_spec, discovery_callable = self._service_router.make_discovery_tool(
            agent_id, policy, inject_callback=self._inject_tool_spec
        )
        agent._tools.append(discovery_spec)
        agent._tool_map[discovery_spec["function"]["name"]] = discovery_callable

        # Wire service router generic tools (fetch_data, execute_action, read_event_notifications)
        tool_specs, tool_map = self._service_router.make_service_tools(
            agent_id, policy,
            clear_notifications_callback=self._clear_event_notifications,
        )
        agent._tools.extend(tool_specs)
        agent._tool_map.update(tool_map)

        # Wire cognitive tools based on policy
        if policy is not None:
            cognitive = getattr(policy, 'cognitive_tools', frozenset())
            if cognitive:
                agent._wire_cognitive_tools(cognitive)

    def _wire_agent_events(
        self,
        agent_id: str,
        handle: _AgentHandle,
        policy: AgentPolicy | None,
    ) -> None:
        """Register event sources, wake callbacks, and lifecycle events."""
        # Inbox event source for hibernation
        handle.event_sources.append(InboxEventSource(self._chat_router))

        # Wake callback for external events
        self._service_router.register_agent_wake_callback(
            agent_id,
            wake_fn=handle.wake_signal.set,
        )

        # Subscribe to EVENT_SOURCE services granted by policy
        if policy is not None:
            from harvest.interfaces.service import ServiceRole
            all_services = set(self._service_router.list_services())
            for perm in policy.allowed_services:
                svc = self._service_router.get_service(perm.service_id)
                if svc is None:
                    continue
                if ServiceRole.EVENT_SOURCE not in svc.roles:
                    continue
                if perm.roles is not None and ServiceRole.EVENT_SOURCE not in perm.roles:
                    continue
                if perm.service_id in all_services:
                    self._service_router.subscribe_agent(agent_id, perm.service_id)

        # Wake on new chat messages
        from harvest.agent_sandbox.chat_events import NewChatMessage

        def _on_new_chat(
            event: Any,
            _handle: _AgentHandle = handle,
            _agent_id: str = agent_id,
        ) -> None:
            if _agent_id not in getattr(event, 'recipient_ids', []):
                return
            if getattr(event, 'sender_id', '') == _agent_id:
                return
            _handle.wake_signal.set()
            if _handle.status == AgentStatus.ACTIVE:
                self._add_inbox_notification(
                    _agent_id,
                    getattr(event, 'channel_id', ''),
                    getattr(event, 'sender_id', ''),
                )

        self._sandbox_bus.on(NewChatMessage, _on_new_chat)

        # Status change callbacks
        def _on_status(new_status: AgentStatus, _aid: str = agent_id) -> None:
            for cb in self._status_callbacks:
                try:
                    cb(_aid, new_status)
                except Exception:
                    pass

        handle.on_status_changed(_on_status)
        self._dispatch_status_callback(agent_id, handle)

        # Dispatch AgentStarted event
        from harvest.agent_sandbox.lifecycle_events import AgentStarted
        self._sandbox_bus.dispatch(AgentStarted(
            agent_id=agent_id,
            parent_id=self._parent_map.get(agent_id, ""),
            policy_name=handle.policy.name if handle.policy else "",
        ))

    def on_status_changed(self, callback: Any) -> None:
        """Register a callback for agent status changes.

        Args:
            callback: Called with (agent_id: str, status: AgentStatus).
        """
        self._status_callbacks.append(callback)

    def list_agents(self) -> list[str]:
        """Return the identifiers of all hosted agents."""
        with self._lock:
            return list(self._agents.keys())

    def remove_agent(self, agent_id: str) -> None:
        """Remove an agent from the sandbox.

        Args:
            agent_id: Agent to remove.

        Raises:
            KeyError: If agent not found.
        """
        with self._lock:
            handle = self._agents.pop(agent_id)
            handle.status = AgentStatus.STOPPED
            handle.stop_event.set()

        self._service_router.unregister_agent(agent_id)
        self._prompt_builders.pop(agent_id, None)
        self._injected_tool_names.pop(agent_id, None)
        self._agent_policies.pop(agent_id, None)
        handle.agent.shutdown()

        if handle.thread is not None and handle.thread.is_alive():
            handle.thread.join(timeout=5.0)

        # Dispatch AgentStopped event
        from harvest.agent_sandbox.lifecycle_events import AgentStopped
        reason = self._shutdown_reasons.pop(agent_id, "")
        self._sandbox_bus.dispatch(AgentStopped(
            agent_id=agent_id,
            final_status=handle.status.value,
            reason=reason,
        ))

    def get_agent(self, agent_id: str) -> Agent:
        """Get an agent by ID.

        Args:
            agent_id: Agent ID.

        Returns:
            The agent instance.

        Raises:
            KeyError: If agent not found.
        """
        with self._lock:
            return self._agents[agent_id].agent

    def get_agent_handle(self, agent_id: str) -> _AgentHandle:
        """Get internal agent handle (for monitoring).

        Args:
            agent_id: Agent ID.

        Returns:
            The _AgentHandle instance.

        Raises:
            KeyError: If agent not found.
        """
        with self._lock:
            return self._agents[agent_id]

    # -- Runtime contract --

    def bind_resource(self, resource_id: str, resource: Any) -> None:
        """Bind a resource to the sandbox."""
        self._resources[resource_id] = resource

    def bind_tool(self, tool_name: str, tool: Any) -> None:
        """Bind a tool to the sandbox."""
        self._tools[tool_name] = tool

    def publish_event(self, event_type: str, payload: dict[str, Any]) -> None:
        """Publish a framework-facing event."""
        if self._event_bus is not None:
            from harvest.events.base import HarvestEvent
            event = HarvestEvent(source=self._config.runner_id)
            self._event_bus.dispatch(event)

    def handle_event(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Fan out a framework event to all hosted agents by calling each agent's ``step()``.

        Iterates over every registered agent, filters by the agent's policy
        ``event_subscriptions`` (if any), constructs a JSON-encoded event
        envelope (with ``event_type``, ``payload``, and ``timestamp``), and
        passes it to ``agent.step()``.  Results (or errors) are collected
        per agent and stored in ``self._last_dispatch_results``.

        Args:
            event_type: The event type string.
            payload: Event payload.

        Returns:
            Dict mapping ``agent_id`` to the corresponding ``step()`` output,
            or ``{"error": ...}`` if the agent raised an exception.
        """
        import datetime as dt

        translated = json.dumps({
            "event_type": event_type,
            "payload": payload,
            "timestamp": dt.datetime.now(dt.UTC).isoformat(),
        })

        results: dict[str, Any] = {}
        with self._lock:
            handles = list(self._agents.items())

        for agent_id, handle in handles:
            # Filter by policy event subscriptions
            if handle.policy and handle.policy.event_subscriptions:
                subs = handle.policy.event_subscriptions
                if subs.allowed_event_types is not None and event_type not in subs.allowed_event_types:
                    continue
            try:
                output = handle.agent.step(translated)
                results[agent_id] = output
            except Exception as e:
                results[agent_id] = {"error": str(e)}
                logger.exception("Error in agent %s during event fan-out", agent_id)

        self._last_dispatch_results = results
        return results

    async def start(self) -> None:
        """Start the sandbox and spin up agent threads."""
        with self._lock:
            self._running = True
            for agent_id, handle in self._agents.items():
                self._start_agent_thread(agent_id, handle)

    async def stop(self) -> None:
        """Stop all agents and clean up."""
        with self._lock:
            self._running = False
            handles = list(self._agents.items())

        for agent_id, handle in handles:
            handle.stop_event.set()
            handle.agent.shutdown()
            if handle.thread is not None and handle.thread.is_alive():
                handle.thread.join(timeout=5.0)

        with self._lock:
            self._agents.clear()

        if self._gateway is not None:
            self._gateway.stop()

    def health_check(self) -> dict[str, Any]:
        """Return sandbox health information."""
        with self._lock:
            agent_info = {}
            for aid, handle in self._agents.items():
                agent_info[aid] = {
                    "thread_alive": handle.thread.is_alive() if handle.thread else False,
                    "status": handle.status.value,
                }
            return {
                "running": self._running,
                "agent_count": len(self._agents),
                "agents": agent_info,
                "last_dispatch_results": self._last_dispatch_results,
            }

    # -- AgentSandbox contract --

    def register_processor(self, processor_id: str, processor: MessageProcessor) -> None:
        """Register a processor (delegates to ChatRouter channel creation)."""

    def list_processors(self) -> list[str]:
        """List processor channels."""
        from harvest.agent_sandbox.channels import ProcessorChannel
        return [
            ch.channel_id
            for ch in self._chat_router.list_channels()
            if isinstance(ch, ProcessorChannel)
        ]

    def remove_processor(self, processor_id: str) -> None:
        """Remove a processor channel."""
        self._chat_router.remove_channel(processor_id)

    def register_group_chat(self, group_chat: GroupChatDefinition) -> None:
        """Register a group chat (delegates to ChatRouter)."""
        from harvest.agent_sandbox.channels import GroupChannel
        channel = GroupChannel(
            channel_id=group_chat.address.endpoint_id,
            member_ids=group_chat.member_ids,
            description=group_chat.description,
        )
        self._chat_router.create_channel(channel)

    def list_group_chats(self) -> list[str]:
        """List group chat channels."""
        from harvest.agent_sandbox.channels import GroupChannel
        return [
            ch.channel_id
            for ch in self._chat_router.list_channels()
            if isinstance(ch, GroupChannel)
        ]

    def remove_group_chat(self, group_chat_id: str) -> None:
        """Remove a group chat channel."""
        self._chat_router.remove_channel(group_chat_id)

    def list_endpoints(self) -> list[SandboxEndpoint]:
        """Return the currently known sandbox endpoints."""
        return []

    def get_supported_delivery_modes(self) -> list[DeliveryMode]:
        """Return supported delivery modes."""
        from harvest.agent_sandbox.endpoints import DeliveryMode as DM
        return [DM.PUSH, DM.PULL]

    # -- Event source management --

    def add_event_source(self, agent_id: str, source: EventSource) -> None:
        """Register an additional event source for a hibernating agent.

        Args:
            agent_id: Target agent.
            source: EventSource to add.

        Raises:
            KeyError: If agent not found.
        """
        with self._lock:
            handle = self._agents[agent_id]
            handle.event_sources.append(source)

    # -- System prompt injection callbacks -----------------------------------

    def _inject_tool_spec(self, agent_id: str, tool: InterfaceTool) -> None:
        """Append a tool spec block to the 'tool_specs' system prompt section.

        Idempotent — already-injected tools are skipped.

        # TODO (future phase): Replace this with a proper memory system.
        # Tool signatures are high-value persistent knowledge that should be
        # saved to agent memory and reloaded into the system prompt on each
        # invocation, making them durable across sessions and restarts — not
        # just within a single run. The SystemPromptBuilder.append() call here
        # is the correct architectural slot; the future implementation reads
        # from memory instead of from in-process builder state.
        """
        builder = self._prompt_builders.get(agent_id)
        if builder is None:
            return
        injected = self._injected_tool_names.get(agent_id)
        if injected is None:
            return
        if tool.name not in injected:
            # First injection: prepend the "Available Tools" header
            if not injected:
                builder.append("tool_specs", "## Available Tools\n")
            builder.append("tool_specs", tool.to_system_prompt_block())
            injected.add(tool.name)

    def _add_event_notification(
        self, agent_id: str, source_id: str, event_type: str
    ) -> None:
        """Append an event arrival notification to the 'event_notifications' section."""
        builder = self._prompt_builders.get(agent_id)
        if builder is None:
            return
        block = (
            f"## Pending Event Notification\n\n"
            f"A new event has arrived from source '{source_id}' "
            f"(type: '{event_type}'). Call read_event_notifications() to read it."
        )
        builder.append("event_notifications", block)

    def _clear_event_notifications(self, agent_id: str) -> None:
        """Clear the 'event_notifications' section after the agent reads events."""
        builder = self._prompt_builders.get(agent_id)
        if builder is None:
            return
        builder.clear("event_notifications")

    def _add_inbox_notification(
        self, agent_id: str, channel_id: str, sender_id: str,
    ) -> None:
        """Append an inbox notification to the system prompt.

        Called when a new chat message arrives for an agent that is currently
        in an active step(). The notification appears in the system prompt on
        the next LLM call iteration, so the agent can decide to read it.
        """
        builder = self._prompt_builders.get(agent_id)
        if builder is None:
            return

        # Respect notification mode: for MENTION channels, only inject if
        # the agent was explicitly mentioned (we don't have message content
        # here, so we always inject — the agent can check via read_messages).
        block = (
            f"**New message** from @{sender_id} in #{channel_id}. "
            f"Call read_messages(channel_id=\"{channel_id}\") to see it."
        )
        builder.append_auto_clear("inbox_notifications", block)

    def _clear_inbox_notifications(self, agent_id: str) -> None:
        """Clear inbox notifications after the agent reads messages."""
        builder = self._prompt_builders.get(agent_id)
        if builder is None:
            return
        builder.clear("inbox_notifications")

    # -- Lifecycle event handlers (Phase 18) -----------------------------------

    def _wire_lifecycle_handlers(self) -> None:
        """Subscribe to lifecycle request events on the sandbox bus."""
        from harvest.agent_sandbox.lifecycle_events import (
            CreateAgentRequest,
            GetAgentStatusRequest,
            ShutdownAgentRequest,
        )
        self._sandbox_bus.on(CreateAgentRequest, self._handle_create_agent)
        self._sandbox_bus.on(ShutdownAgentRequest, self._handle_shutdown_agent)
        self._sandbox_bus.on(GetAgentStatusRequest, self._handle_get_status)

    def _handle_create_agent(self, event: Any) -> None:
        """Validate policy and create a child agent."""
        from harvest.agent_sandbox.lifecycle_events import CreateAgentResponse

        try:
            # Resolve policy
            parent_policy = self._agent_policies.get(event.parent_id)
            if parent_policy is None:
                self._sandbox_bus.dispatch(CreateAgentResponse(
                    parent_id=event.parent_id, agent_id=event.agent_id,
                    request_id=event.request_id, status="error",
                    error="parent_policy_not_found",
                ))
                return

            if not parent_policy.can_create_agents:
                self._sandbox_bus.dispatch(CreateAgentResponse(
                    parent_id=event.parent_id, agent_id=event.agent_id,
                    request_id=event.request_id, status="error",
                    error="not_permitted",
                ))
                return

            # Resolve child policy based on parent's child_policy_mode
            child_policy: AgentPolicy | None = None
            mode = parent_policy.child_policy_mode

            if mode == ChildPolicyMode.CLONE:
                # Child gets a copy of parent's policy
                child_policy = AgentPolicy(
                    name=f"{parent_policy.name}-clone-{event.agent_id}",
                    allowed_tools=parent_policy.allowed_tools,
                    can_send_messages=parent_policy.can_send_messages,
                    can_create_channel=parent_policy.can_create_channel,
                    can_create_agents=parent_policy.can_create_agents,
                    child_policy_mode=parent_policy.child_policy_mode,
                    allowed_child_policies=parent_policy.allowed_child_policies,
                )
            elif mode == ChildPolicyMode.PREDEFINED:
                if not event.policy_name:
                    self._sandbox_bus.dispatch(CreateAgentResponse(
                        parent_id=event.parent_id, agent_id=event.agent_id,
                        request_id=event.request_id, status="error",
                        error="PREDEFINED mode requires policy_name",
                    ))
                    return
                if event.policy_name not in parent_policy.allowed_child_policies:
                    self._sandbox_bus.dispatch(CreateAgentResponse(
                        parent_id=event.parent_id, agent_id=event.agent_id,
                        request_id=event.request_id, status="error",
                        error=f"policy_not_in_allowed:{event.policy_name}",
                    ))
                    return
                if not self._policy_registry:
                    self._sandbox_bus.dispatch(CreateAgentResponse(
                        parent_id=event.parent_id, agent_id=event.agent_id,
                        request_id=event.request_id, status="error",
                        error="no_policy_registry",
                    ))
                    return
                try:
                    child_policy = self._policy_registry.get(event.policy_name)
                except KeyError:
                    self._sandbox_bus.dispatch(CreateAgentResponse(
                        parent_id=event.parent_id, agent_id=event.agent_id,
                        request_id=event.request_id, status="error",
                        error=f"policy_not_found:{event.policy_name}",
                    ))
                    return
            elif mode == ChildPolicyMode.DEFINE:
                if not event.policy_dict:
                    self._sandbox_bus.dispatch(CreateAgentResponse(
                        parent_id=event.parent_id, agent_id=event.agent_id,
                        request_id=event.request_id, status="error",
                        error="DEFINE mode requires policy_dict",
                    ))
                    return
                pd = event.policy_dict
                child_policy = AgentPolicy(
                    name=pd.get("name", f"custom-{event.agent_id}"),
                    allowed_tools=frozenset(pd.get("allowed_tools", [])),
                    can_send_messages=pd.get("can_send_messages", True),
                    can_create_channel=pd.get("can_create_channel", False),
                    can_create_agents=pd.get("can_create_agents", False),
                    child_policy_mode=ChildPolicyMode(pd.get("child_policy_mode", "none")),
                    allowed_child_policies=tuple(pd.get("allowed_child_policies", [])),
                )
            else:
                # Fallback: try policy_name from registry
                if event.policy_name and self._policy_registry:
                    try:
                        child_policy = self._policy_registry.get(event.policy_name)
                    except KeyError:
                        self._sandbox_bus.dispatch(CreateAgentResponse(
                            parent_id=event.parent_id, agent_id=event.agent_id,
                            request_id=event.request_id, status="error",
                            error=f"policy_not_found:{event.policy_name}",
                        ))
                        return

            # Create the agent
            from harvest.harvest_agent import HarvestAgent, HarvestAgentConfig

            # Resolve model: use parent's if not specified
            parent_handle = self._agents.get(event.parent_id)
            model = event.model
            if not model and parent_handle and hasattr(parent_handle.agent, 'config'):
                model = parent_handle.agent.config.model

            identity_footer = _build_identity_footer(event.agent_id)
            system_prompt = (event.system_prompt or "You are an agent.").rstrip() + identity_footer

            config = HarvestAgentConfig(
                model=model or "anthropic/claude-haiku-4-5-20251001",
                system_prompt=system_prompt,
            )
            agent = HarvestAgent(config=config, agent_id=event.agent_id)

            # Track parent
            self._parent_map[event.agent_id] = event.parent_id

            # Register the child agent
            self.register_agent(event.agent_id, agent, policy=child_policy)

            self._sandbox_bus.dispatch(CreateAgentResponse(
                parent_id=event.parent_id, agent_id=event.agent_id,
                request_id=event.request_id, status="created",
            ))
        except Exception as exc:
            logger.exception("Failed to create agent %s", event.agent_id)
            self._sandbox_bus.dispatch(CreateAgentResponse(
                parent_id=event.parent_id, agent_id=event.agent_id,
                request_id=event.request_id, status="error",
                error=str(exc),
            ))

    def _handle_shutdown_agent(self, event: Any) -> None:
        """Validate ownership and remove the agent."""
        from harvest.agent_sandbox.lifecycle_events import ShutdownAgentResponse

        is_self_shutdown = (event.parent_id == event.agent_id)

        if not is_self_shutdown:
            # Check parent owns this agent
            actual_parent = self._parent_map.get(event.agent_id)
            if actual_parent != event.parent_id:
                self._sandbox_bus.dispatch(ShutdownAgentResponse(
                    parent_id=event.parent_id, agent_id=event.agent_id,
                    request_id=event.request_id, status="error",
                    error="not_your_agent",
                ))
                return

        if event.agent_id not in self._agents:
            self._sandbox_bus.dispatch(ShutdownAgentResponse(
                parent_id=event.parent_id, agent_id=event.agent_id,
                request_id=event.request_id, status="error",
                error="agent_not_found",
            ))
            return

        # Set reason for the AgentStopped event
        reason = "task_complete" if is_self_shutdown else "parent_shutdown"
        self._shutdown_reasons[event.agent_id] = reason

        try:
            self.remove_agent(event.agent_id)
            self._sandbox_bus.dispatch(ShutdownAgentResponse(
                parent_id=event.parent_id, agent_id=event.agent_id,
                request_id=event.request_id, status="stopped",
            ))
        except Exception as exc:
            logger.exception("Failed to shutdown agent %s", event.agent_id)
            self._sandbox_bus.dispatch(ShutdownAgentResponse(
                parent_id=event.parent_id, agent_id=event.agent_id,
                request_id=event.request_id, status="error",
                error=str(exc),
            ))

    def _handle_get_status(self, event: Any) -> None:
        """Return the agent's current status."""
        from harvest.agent_sandbox.lifecycle_events import GetAgentStatusResponse

        handle = self._agents.get(event.agent_id)
        if handle is None:
            self._sandbox_bus.dispatch(GetAgentStatusResponse(
                parent_id=event.parent_id, agent_id=event.agent_id,
                request_id=event.request_id, error="agent_not_found",
            ))
            return

        self._sandbox_bus.dispatch(GetAgentStatusResponse(
            parent_id=event.parent_id, agent_id=event.agent_id,
            request_id=event.request_id, agent_status=handle.status.value,
        ))

    def _dispatch_status_callback(self, agent_id: str, handle: _AgentHandle) -> None:
        """Wire status changes to dispatch AgentStatusChanged on the sandbox bus."""
        from harvest.agent_sandbox.lifecycle_events import AgentStatusChanged

        def _on_bus_status(new_status: AgentStatus, _aid: str = agent_id) -> None:
            # We need old_status — capture it via closure
            pass  # actual dispatch happens below

        # Hook into the existing status setter callback
        _prev_status = [handle.status]

        def _status_bus_cb(new_status: AgentStatus, _aid: str = agent_id) -> None:
            old = _prev_status[0]
            _prev_status[0] = new_status
            if old != new_status:
                self._sandbox_bus.dispatch(AgentStatusChanged(
                    agent_id=_aid,
                    old_status=old.value,
                    new_status=new_status.value,
                ))

        handle.on_status_changed(_status_bus_cb)

    def get_agent_policy(self, agent_id: str) -> AgentPolicy | None:
        """Return the policy for an agent, or None."""
        return self._agent_policies.get(agent_id)

    # -- Internal --

    def _start_agent_thread(self, agent_id: str, handle: _AgentHandle) -> None:
        """Create and start a daemon thread for the agent."""
        thread = threading.Thread(
            target=self._agent_loop,
            args=(agent_id, handle),
            name=f"agent-{agent_id}",
            daemon=True,
        )
        handle.thread = thread
        thread.start()

    def _agent_loop(self, agent_id: str, handle: _AgentHandle) -> None:
        """Agent lifecycle loop: hibernate, poll for events, run LLM step.

        After start() is called the agent enters this loop.  It sleeps for
        a random interval between HIBERNATION_POLL_MIN and HIBERNATION_POLL_MAX
        seconds (or until wake_signal is set), then polls all registered
        EventSources.  The jitter serves two purposes: it throttles API
        requests to avoid bursts, and it staggers agent wake-ups so they
        don't all respond simultaneously to the same message.
        """
        logger.info("Agent %s entering hibernation loop", agent_id)

        while not handle.stop_event.is_set():
            # --- Hibernation phase (jittered sleep) ---
            handle.status = AgentStatus.IDLE
            jitter = random.uniform(HIBERNATION_POLL_MIN, HIBERNATION_POLL_MAX)
            handle.wake_signal.wait(timeout=jitter)
            handle.wake_signal.clear()

            if handle.stop_event.is_set():
                break

            # --- Debounce: brief pause to let additional messages accumulate ---
            # Without this, an agent woken by a single message may miss
            # others that arrive milliseconds later, leading to separate
            # step() calls (and duplicate-looking replies) for messages
            # that should have been batched together.
            handle.stop_event.wait(timeout=WAKE_DEBOUNCE)
            if handle.stop_event.is_set():
                break

            # --- Poll phase ---
            all_events: list[WakeEvent] = []
            for source in handle.event_sources:
                try:
                    events = source.poll(agent_id)
                    all_events.extend(events)
                except Exception:
                    logger.exception(
                        "Event source %s failed for agent %s",
                        type(source).__name__,
                        agent_id,
                    )

            if not all_events:
                continue

            # Filter wake events by policy subscription
            if handle.policy and handle.policy.event_subscriptions:
                subs = handle.policy.event_subscriptions
                if subs.allowed_wake_sources is not None:
                    all_events = [e for e in all_events if e.source_type in subs.allowed_wake_sources]
            if not all_events:
                continue

            # --- Wake phase: format events and restart LLM loop ---
            logger.info(
                "Agent %s woke with %d event(s): %s",
                agent_id,
                len(all_events),
                [(e.source_type, e.payload.get("sender_id", "")) for e in all_events],
            )
            prompt = self._format_wake_events(all_events)
            logger.debug(
                "Agent %s wake prompt:\n%s", agent_id, prompt,
            )
            logger.info("Agent %s calling step()", agent_id)
            handle.status = AgentStatus.ACTIVE
            max_retries = 8
            for attempt in range(max_retries):
                try:
                    handle.agent.step(prompt)
                    logger.info("Agent %s step() returned", agent_id)
                    break
                except Exception as exc:
                    from harvest.agent_sandbox.llm_errors import (
                        LLMErrorKind,
                        classify_llm_error,
                    )
                    kind = classify_llm_error(exc)

                    if kind == LLMErrorKind.UNRECOVERABLE:
                        # These errors will not resolve with retries — shut
                        # the agent down immediately with a clear message.
                        logger.error(
                            "Agent %s encountered an unrecoverable LLM error and is "
                            "shutting down: %s",
                            agent_id, exc,
                        )
                        handle.status = AgentStatus.UNRECOVERABLE
                        handle.stop_event.set()
                        break

                    if kind == LLMErrorKind.RETRYABLE and attempt < max_retries - 1:
                        # Exponential backoff: 10s, 20s, 40s, 80s, 160s, ...
                        backoff = 10.0 * (2 ** attempt) + random.uniform(0, 5)
                        logger.warning(
                            "Agent %s hit retryable LLM error (attempt %d/%d), "
                            "retrying in %.0fs: %s",
                            agent_id, attempt + 1, max_retries, backoff,
                            str(exc)[:200],
                        )
                        handle.status = AgentStatus.RATE_LIMITED
                        # Use interruptible wait so stop_event can break out
                        handle.stop_event.wait(timeout=backoff)
                        if handle.stop_event.is_set():
                            break
                        handle.status = AgentStatus.ACTIVE
                        continue

                    # Unknown error or retries exhausted — crash the agent.
                    logger.exception("Agent %s step() failed on wake", agent_id)
                    handle.status = AgentStatus.CRASHED
                    handle.stop_event.set()  # exit the hibernation loop
                    break

            # Release any channel stakes the agent still holds
            # (e.g. got channel_updated but decided not to send)
            self._chat_router._cleanup_stakes_for_agent(agent_id)

        logger.info("Agent %s exited hibernation loop", agent_id)

    @staticmethod
    def _format_wake_events(events: list[WakeEvent]) -> str:
        """Format wake events into a Slack-style prompt for agent.step().

        Mention events (DMs, @here, @name) show full message content:
            ``@sender in #channel: content``

        Ambient events (group messages without a mention) show a soft
        summary, like Slack bolding a channel name without a red badge:
            ``N new messages in #channel``

        Non-inbox events use a generic JSON fallback.
        """
        mention_parts: list[str] = []
        ambient_counts: dict[str, int] = {}
        non_inbox_parts: list[str] = []

        for event in events:
            if event.source_type != "inbox":
                non_inbox_parts.append(
                    f"[event:{event.source_type}] {json.dumps(event.payload)}"
                )
                continue

            mention_type = event.payload.get("mention_type", "mention")
            if mention_type == "mention":
                sender = event.payload.get("sender_id", "unknown")
                content = event.payload.get("content", "")
                channel_id = event.payload.get("channel_id", "")
                msg_id = event.payload.get("message_id", "")
                short_id = msg_id[:8] if msg_id else ""
                # Seed messages use a distinct format so agents know
                # this is a scenario prompt, not a real participant.
                from harvest.agent_sandbox.chat import ChatRouter
                if sender == ChatRouter.SEED_SENDER_ID:
                    mention_parts.append(
                        f"[channel-topic] #{channel_id} (this topic was set by "
                        f"the system, not by another agent — but you should "
                        f"still engage with it): {content}"
                    )
                else:
                    ts = event.timestamp.strftime("%H:%M:%S") if event.timestamp else ""
                    mention_parts.append(
                        f"[msg:{short_id} {ts}] @{sender} in #{channel_id}: {content}"
                    )
            else:
                channel_id = event.payload.get("channel_id", "")
                ambient_counts[channel_id] = ambient_counts.get(channel_id, 0) + 1

        parts: list[str] = []
        parts.extend(mention_parts)
        for channel_id, count in ambient_counts.items():
            noun = "message" if count == 1 else "messages"
            parts.append(f"{count} new {noun} in #{channel_id}")
        parts.extend(non_inbox_parts)

        return "\n".join(parts)

    # -- Manifest loading --

    @classmethod
    def from_manifest(
        cls,
        path: str | Path,
        *,
        registry: PolicyRegistry | None = None,
        event_bus: EventBus | None = None,
        chat_store: ChatStore | None = None,
    ) -> BasicSandbox:
        """Create and fully wire a BasicSandbox from a YAML manifest.

        Args:
            path: Path to the YAML manifest file.
            registry: Optional shared PolicyRegistry.
            event_bus: Optional framework EventBus.
            chat_store: Optional ChatStore for persistence.

        Returns:
            A ready-but-not-started BasicSandbox.
        """
        from harvest.agent_sandbox.manifest import load_manifest

        manifest = load_manifest(path, registry=registry)

        config = AgentSandboxConfig(
            runner_id=manifest.name,
            display_name=manifest.name,
        )

        # Merge manifest policies into registry
        merged_registry = PolicyRegistry()
        if registry is not None:
            for name in registry.list_policies():
                merged_registry.register(registry.get(name))
        for name, policy in manifest.policies.items():
            merged_registry.register(policy)

        sandbox = cls(
            config=config,
            policy_registry=merged_registry,
            event_bus=event_bus,
            chat_store=chat_store,
        )

        # Instantiate and register manifest services
        import os as _os

        _SERVICE_TYPE_MAP: dict[str, type] = {}

        def _get_service_class(service_type: str) -> type | None:
            """Lazy-load service classes to avoid circular imports."""
            if not _SERVICE_TYPE_MAP:
                from harvest.services.perplexity import PerplexityService
                from harvest.services.newsapi import NewsAPIService
                from harvest.services.tavily import TavilyService
                _SERVICE_TYPE_MAP["perplexity"] = PerplexityService
                _SERVICE_TYPE_MAP["newsapi"] = NewsAPIService
                _SERVICE_TYPE_MAP["tavily"] = TavilyService
            return _SERVICE_TYPE_MAP.get(service_type)

        for svc_id, svc_entry in manifest.services.items():
            svc_cls = _get_service_class(svc_entry.service_type)
            if svc_cls is None:
                logger.warning(
                    "Unknown service type '%s' for service '%s', skipping",
                    svc_entry.service_type, svc_id,
                )
                continue
            # Unwrap nested "config" key if present (manifest parser
            # collects all non-"type" keys, including the "config" dict).
            raw_config = svc_entry.config
            if "config" in raw_config and isinstance(raw_config["config"], dict):
                raw_config = raw_config["config"]
            # Resolve ${ENV_VAR} references in config values
            resolved_config: dict[str, Any] = {}
            for k, v in raw_config.items():
                if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
                    env_var = v[2:-1]
                    resolved_config[k] = _os.environ.get(env_var, "")
                else:
                    resolved_config[k] = v
            # Map common manifest aliases to constructor parameter names
            if "model" in resolved_config and "default_model" not in resolved_config:
                resolved_config["default_model"] = resolved_config.pop("model")
            try:
                svc_instance = svc_cls(**resolved_config)
                sandbox._service_router.register_service(svc_instance)
                logger.info("Registered service '%s' (type=%s)", svc_id, svc_entry.service_type)
            except Exception:
                logger.exception("Failed to instantiate service '%s'", svc_id)

        # Register agents
        from harvest.harvest_agent import HarvestAgent, HarvestAgentConfig

        for agent_id, entry in manifest.agents.items():
            policy = manifest.policies.get(entry.policy_name)
            if policy is None and merged_registry is not None:
                try:
                    policy = merged_registry.get(entry.policy_name)
                except KeyError:
                    pass

            # Inject identity footer so the agent knows its own name
            identity_footer = _build_identity_footer(agent_id)
            config_kwargs: dict[str, Any] = {
                "model": entry.model,
                "system_prompt": entry.system_prompt.rstrip() + identity_footer,
                "api_base": entry.api_base,
                "api_key_env": entry.api_key_env,
            }
            if entry.tool_call_loop_cap is not None:
                config_kwargs["tool_call_loop_cap"] = entry.tool_call_loop_cap
            if entry.context_limit is not None:
                config_kwargs["context_limit"] = entry.context_limit
            agent_config = HarvestAgentConfig(**config_kwargs)
            agent = HarvestAgent(
                config=agent_config,
                agent_id=agent_id,
                policy=policy,
            )
            sandbox.register_agent(agent_id, agent, policy=policy)

        # Create channels
        from harvest.agent_sandbox.channels import (
            AggregationProcessorChannel,
            ChannelType,
            DMChannel,
            GatedProcessorChannel,
            GroupChannel,
        )

        for channel_id, entry in manifest.channels.items():
            if entry.channel_type == ChannelType.DM:
                channel = DMChannel(
                    channel_id=channel_id,
                    member_ids=list(entry.member_ids),
                )
            elif entry.channel_type == ChannelType.GROUP:
                channel = GroupChannel(
                    channel_id=channel_id,
                    member_ids=list(entry.member_ids),
                    description=entry.description,
                    notification_mode=entry.notification_mode,
                )
            elif entry.channel_type == ChannelType.PROCESSOR_GATED:
                channel = GatedProcessorChannel(
                    channel_id=channel_id,
                    publisher_ids=list(entry.publisher_ids),
                    subscriber_ids=list(entry.subscriber_ids),
                    description=entry.description,
                )
            elif entry.channel_type == ChannelType.PROCESSOR_AGGREGATION:
                channel = AggregationProcessorChannel(
                    channel_id=channel_id,
                    publisher_ids=list(entry.publisher_ids),
                    subscriber_ids=list(entry.subscriber_ids),
                    batch_threshold=entry.batch_threshold,
                    description=entry.description,
                )
            else:
                continue

            sandbox._chat_router.create_channel(channel)

        return sandbox
