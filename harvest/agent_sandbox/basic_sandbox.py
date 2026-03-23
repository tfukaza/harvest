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
from harvest.agent_sandbox.event_helpers import SyncEventBus
from harvest.agent_sandbox.sandbox_gateway import SandboxGateway
from harvest.agent_sandbox.service_router import SandboxServiceRouter
from harvest.agent_sandbox.system_prompt_builder import SystemPromptBuilder
from harvest.events.event_bus import EventBus
from harvest.interfaces.tool_definition import InterfaceTool
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

            # Wire agent identity
            if hasattr(agent, 'agent_id'):
                agent.agent_id = agent_id
            if hasattr(agent, '_sandbox'):
                agent._sandbox = self

            # Wire agent to chat: prefer event-driven client, fall back to direct.
            # If the agent was already wired (e.g. chat_router passed to constructor),
            # skip re-wiring to avoid overwriting existing tools.
            already_wired = (
                hasattr(agent, '_chat_router') and agent._chat_router is not None
            )
            if not already_wired and hasattr(agent, '_wire_chat_client'):
                agent._wire_chat_client(self._sandbox_bus, policy)
                # Still register with ChatRouter for inbox/channel tracking
                self._chat_router.register_agent(agent_id)
            elif not already_wired and hasattr(agent, '_chat_router'):
                agent._chat_router = self._chat_router
                agent._wire_chat_router(self._chat_router, policy)

            # Initialise per-agent system prompt builder and inject tracker
            self._prompt_builders[agent_id] = SystemPromptBuilder()
            self._injected_tool_names[agent_id] = set()

            # Wire the dynamic system prompt provider so the builder's output
            # is used on every LLM invocation.
            if hasattr(agent, '_system_prompt_fn') and hasattr(agent, 'base_system_prompt'):
                def _make_prompt_fn(_aid: str, _agent: Any) -> Any:
                    def _prompt_fn() -> str:
                        return self._prompt_builders[_aid].build(_agent.base_system_prompt)
                    return _prompt_fn
                agent._system_prompt_fn = _make_prompt_fn(agent_id, agent)

            # Auto-register interface tools from permitted services (no spec injection)
            interface_tool_pairs = self._service_router.wire_agent_tools(agent_id, policy)
            if hasattr(agent, '_tools') and hasattr(agent, '_tool_map'):
                for tool_spec, tool_callable in interface_tool_pairs:
                    agent._tools.append(tool_spec)
                    agent._tool_map[tool_spec["function"]["name"]] = tool_callable

            # Register the discover_tools callable
            discovery_spec, discovery_callable = self._service_router.make_discovery_tool(
                agent_id, policy, inject_callback=self._inject_tool_spec
            )
            if hasattr(agent, '_tools') and hasattr(agent, '_tool_map'):
                agent._tools.append(discovery_spec)
                agent._tool_map[discovery_spec["function"]["name"]] = discovery_callable

            # Wire service router generic tools (fetch_data, execute_action, read_event_notifications)
            if hasattr(agent, '_wire_service_router'):
                # Use the updated make_service_tools with clear_notifications_callback
                tool_specs, tool_map = self._service_router.make_service_tools(
                    agent_id, policy,
                    clear_notifications_callback=self._clear_event_notifications,
                )
                agent._tools.extend(tool_specs)
                agent._tool_map.update(tool_map)

            # Auto-register inbox event source for hibernation
            handle.event_sources.append(InboxEventSource(self._chat_router))

            # Register wake callback with service router so external events
            # can interrupt the agent's hibernation sleep.
            self._service_router.register_agent_wake_callback(
                agent_id,
                wake_fn=handle.wake_signal.set,
            )

            # Subscribe agent to any EVENT_SOURCE services granted by its policy.
            if policy is not None:
                from harvest.interfaces.service import ServiceRole
                all_services = set(self._service_router.list_services())
                for perm in policy.allowed_services:
                    svc = self._service_router._services.get(perm.service_id)
                    if svc is None:
                        continue
                    if ServiceRole.EVENT_SOURCE not in svc.roles:
                        continue
                    if perm.roles is not None and ServiceRole.EVENT_SOURCE not in perm.roles:
                        continue
                    if perm.service_id in all_services:
                        self._service_router.subscribe_agent(agent_id, perm.service_id)

            # Wire wake signal so new messages interrupt hibernation sleep.
            # Subscribe to NewChatMessage on the sandbox bus (event-driven).
            from harvest.agent_sandbox.chat_events import NewChatMessage

            def _wake_on_new_chat(
                event: Any,
                _handle: _AgentHandle = handle,
                _agent_id: str = agent_id,
            ) -> None:
                if _agent_id in getattr(event, 'recipient_ids', []):
                    _handle.wake_signal.set()

            self._sandbox_bus.on(NewChatMessage, _wake_on_new_chat)

            # Also keep legacy callback for backward compatibility
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

            # Dispatch lifecycle events on sandbox bus
            self._dispatch_status_callback(agent_id, handle)

            # Dispatch AgentStarted event
            from harvest.agent_sandbox.lifecycle_events import AgentStarted
            self._sandbox_bus.dispatch(AgentStarted(
                agent_id=agent_id,
                parent_id=self._parent_map.get(agent_id, ""),
                policy_name=policy.name if policy else "",
            ))

            # Track policy for service routing
            if policy is not None:
                self._agent_policies[agent_id] = policy

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

            # Resolve child policy
            child_policy: AgentPolicy | None = None
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

            identity_footer = (
                f"\n\n---\n"
                f"Your agent ID is `{event.agent_id}`. Other agents refer to you "
                f"as @{event.agent_id}."
            )
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
                        f"[scenario-prompt] #{channel_id}: {content}"
                    )
                else:
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
                api_base=entry.api_base,
                api_key_env=entry.api_key_env,
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
