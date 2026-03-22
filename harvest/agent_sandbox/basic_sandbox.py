"""Concrete BasicSandbox implementation for hosting multiple agents."""

from __future__ import annotations

import enum
import json
import logging
import random
import threading
from pathlib import Path
from typing import Any

from harvest.agent import Agent
from harvest.agent_sandbox.chat import ChatRouter
from harvest.agent_sandbox.config import AgentSandboxConfig
from harvest.agent_sandbox.endpoints import DeliveryMode, GroupChatDefinition, SandboxEndpoint
from harvest.agent_sandbox.hibernation import EventSource, InboxEventSource, WakeEvent
from harvest.agent_sandbox.processors import MessageProcessor
from harvest.agent_sandbox.sandbox import AgentSandbox
from harvest.events.event_bus import EventBus
from harvest.policy import AgentPolicy, ChildPolicyMode
from harvest.policy_registry import PolicyRegistry
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
        self._chat_router = ChatRouter(store=chat_store)
        self._policy_registry = policy_registry
        self._last_dispatch_results: dict[str, Any] = {}
        self._event_bus = event_bus
        self._running = False
        self._status_callbacks: list[Any] = []  # (agent_id, AgentStatus) -> None

    @property
    def config(self) -> AgentSandboxConfig:
        """Return the sandbox configuration."""
        return self._config

    @property
    def chat_router(self) -> ChatRouter:
        """Access the sandbox's ChatRouter."""
        return self._chat_router

    # -- Agent management --

    def register_agent(
        self,
        agent_id: str,
        agent: Agent,
        *,
        policy: AgentPolicy | None = None,
    ) -> None:
        """Register an agent with the sandbox.

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

            # Wire agent to ChatRouter if it's a HarvestAgent
            if hasattr(agent, 'agent_id'):
                agent.agent_id = agent_id
            if hasattr(agent, '_sandbox'):
                agent._sandbox = self
            if hasattr(agent, '_chat_router') and agent._chat_router is None:
                agent._chat_router = self._chat_router
                agent._wire_chat_router(self._chat_router, policy)

            # Auto-register inbox event source for hibernation
            handle.event_sources.append(InboxEventSource(self._chat_router))

            # Wire wake signal so new messages interrupt hibernation sleep
            def _wake_on_message(
                channel_id: str,
                sender_id: str,
                recipient_ids: list[str],
                message_id: str,
                channel_type: str,
                content: str = "",
                reply_to: str = "",
                _handle: _AgentHandle = handle,
                _agent_id: str = agent_id,
            ) -> None:
                if _agent_id in recipient_ids:
                    _handle.wake_signal.set()

            self._chat_router.on_new_message(_wake_on_message)

            # Wire status change callbacks
            def _on_status(new_status: AgentStatus, _aid: str = agent_id) -> None:
                for cb in self._status_callbacks:
                    try:
                        cb(_aid, new_status)
                    except Exception:
                        pass

            handle.on_status_changed(_on_status)

            # Start agent thread if sandbox is running
            if self._running:
                self._start_agent_thread(agent_id, handle)

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
            handle.stop_event.set()

        handle.agent.shutdown()

        if handle.thread is not None and handle.thread.is_alive():
            handle.thread.join(timeout=5.0)

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
        """Fan out a framework event to all hosted agents.

        Args:
            event_type: The event type string.
            payload: Event payload.

        Returns:
            Dict of agent_id -> step() output.
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
                    exc_name = type(exc).__name__
                    is_rate_limit = "RateLimit" in exc_name or "429" in str(exc)
                    if is_rate_limit and attempt < max_retries - 1:
                        # Exponential backoff: 10s, 20s, 40s, 80s, 160s, ...
                        backoff = 10.0 * (2 ** attempt) + random.uniform(0, 5)
                        logger.warning(
                            "Agent %s hit rate limit (attempt %d/%d), retrying in %.0fs",
                            agent_id, attempt + 1, max_retries, backoff,
                        )
                        handle.status = AgentStatus.RATE_LIMITED
                        # Use interruptible wait so stop_event can break out
                        handle.stop_event.wait(timeout=backoff)
                        if handle.stop_event.is_set():
                            break
                        handle.status = AgentStatus.ACTIVE
                        continue
                    # Non-retryable error or retries exhausted — crash the agent
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
                mention_parts.append(
                    f"[msg:{short_id}] @{sender} in #{channel_id}: {content}"
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
            identity_footer = (
                f"\n\n---\n"
                f"Your agent ID is `{agent_id}`. Other agents and the system "
                f"refer to you as @{agent_id}. When you see a message from "
                f"@{agent_id}, that is *you* — do not respond to your own "
                f"messages. When another agent or the moderator mentions "
                f"@{agent_id} in their message, they are addressing you "
                f"directly and you should respond."
            )
            agent_config = HarvestAgentConfig(
                model=entry.model,
                system_prompt=entry.system_prompt.rstrip() + identity_footer,
            )
            agent = HarvestAgent(
                config=agent_config,
                agent_id=agent_id,
                chat_router=sandbox._chat_router,
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
