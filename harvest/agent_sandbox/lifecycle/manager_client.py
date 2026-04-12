"""Client for parent agents to manage child agents through the sandbox event bus.

A parent agent holds one ``AgentManagerClient`` instance. It exposes
blocking methods that dispatch lifecycle requests onto the shared
:class:`~harvest.agent_sandbox.events.helpers.SyncEventBus` and wait for
responses, hiding the event plumbing from the agent thread.
"""


import logging
import uuid
from collections import defaultdict

from harvest.agent_sandbox.events.helpers import (
    SyncEventBus,
    dispatch_and_wait,
)
from harvest.agent_sandbox.lifecycle.events import (
    AgentStatusChanged,
    AgentStopped,
    CreateAgentRequest,
    CreateAgentResponse,
    GetAgentStatusRequest,
    GetAgentStatusResponse,
    ShutdownAgentRequest,
    ShutdownAgentResponse,
)
from harvest.events.base import HarvestEvent

logger = logging.getLogger(__name__)


class AgentManagerClient:
    """High-level client that parent agents use to create, query, and
    shut down child agents via the sandbox event bus."""

    def __init__(self, parent_id: str, sandbox_bus: SyncEventBus) -> None:
        self._parent_id = parent_id
        self._bus = sandbox_bus
        self._child_ids: set[str] = set()
        self._child_events: dict[str, list] = defaultdict(list)

        # Subscribe to lifecycle events for children
        self._bus.on(AgentStopped, self._on_child_stopped)
        self._bus.on(AgentStatusChanged, self._on_child_status_changed)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request(
        self,
        request: HarvestEvent,
        response_types: tuple[type[HarvestEvent], ...],
        timeout: float = 10.0,
    ) -> HarvestEvent | None:
        """Dispatch a lifecycle request and block for a matching response."""
        rid = getattr(request, "request_id", "")
        return dispatch_and_wait(
            bus=self._bus,
            request=request,
            response_types=response_types,
            filter_fn=lambda e: getattr(e, "request_id", None) == rid,
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_agent(
        self,
        agent_id: str,
        model: str = "",
        policy_name: str = "",
        policy_dict: dict | None = None,
        system_prompt: str = "",
    ) -> dict:
        """Request child agent creation. Blocks up to 10 s."""
        raw = self._request(
            CreateAgentRequest(
                parent_id=self._parent_id, agent_id=agent_id,
                request_id=uuid.uuid4().hex, model=model,
                policy_name=policy_name, policy_dict=policy_dict or {},
                system_prompt=system_prompt, source=self._parent_id,
            ),
            response_types=(CreateAgentResponse,),
        )
        if raw is None:
            return {"error": "timeout"}
        assert isinstance(raw, CreateAgentResponse)
        if raw.status == "created":
            self._child_ids.add(agent_id)
            return {"status": "created", "agent_id": agent_id}
        return {"error": raw.error or "unknown"}

    def shutdown_agent(self, agent_id: str) -> dict:
        """Request shutdown of a child agent or self."""
        if agent_id != self._parent_id and agent_id not in self._child_ids:
            return {"error": "not_your_agent"}
        raw = self._request(
            ShutdownAgentRequest(
                parent_id=self._parent_id, agent_id=agent_id,
                request_id=uuid.uuid4().hex, source=self._parent_id,
            ),
            response_types=(ShutdownAgentResponse,),
        )
        if raw is None:
            return {"error": "timeout"}
        assert isinstance(raw, ShutdownAgentResponse)
        if raw.status == "stopped":
            self._child_ids.discard(agent_id)
            return {"status": "stopped", "agent_id": agent_id}
        return {"error": raw.error or "unknown"}

    def get_child_status(self, agent_id: str) -> dict:
        """Query the current status of a child agent."""
        if agent_id not in self._child_ids:
            return {"error": "not_your_agent"}
        raw = self._request(
            GetAgentStatusRequest(
                parent_id=self._parent_id, agent_id=agent_id,
                request_id=uuid.uuid4().hex, source=self._parent_id,
            ),
            response_types=(GetAgentStatusResponse,),
        )
        if raw is None:
            return {"error": "timeout"}
        assert isinstance(raw, GetAgentStatusResponse)
        if raw.error:
            return {"error": raw.error}
        return {"agent_id": agent_id, "status": raw.agent_status}

    def list_children(self) -> list[str]:
        """Return a list of living child agent IDs."""
        return list(self._child_ids)

    def drain_child_events(self, agent_id: str) -> list[dict]:
        """Return and clear buffered lifecycle events for *agent_id*.

        Each event is returned as a plain dict with ``type``, ``agent_id``,
        and any extra fields from the original event.
        """
        events = self._child_events.pop(agent_id, [])
        return events

    # ------------------------------------------------------------------
    # Internal event handlers
    # ------------------------------------------------------------------

    def _on_child_stopped(self, event: AgentStopped) -> None:
        """Buffer a stop event and remove the child from tracking."""
        if event.agent_id in self._child_ids:
            self._child_events[event.agent_id].append(
                {
                    "type": "AgentStopped",
                    "agent_id": event.agent_id,
                    "final_status": event.final_status,
                    "reason": event.reason,
                }
            )
            self._child_ids.discard(event.agent_id)

    def _on_child_status_changed(self, event: AgentStatusChanged) -> None:
        """Buffer a status-change event if it concerns one of our children."""
        if event.agent_id in self._child_ids:
            self._child_events[event.agent_id].append(
                {
                    "type": "AgentStatusChanged",
                    "agent_id": event.agent_id,
                    "old_status": event.old_status,
                    "new_status": event.new_status,
                    "reason": event.reason,
                }
            )

    # ------------------------------------------------------------------
    # Teardown
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Unsubscribe from the sandbox bus."""
        self._bus.off(AgentStopped, self._on_child_stopped)
        self._bus.off(AgentStatusChanged, self._on_child_status_changed)
