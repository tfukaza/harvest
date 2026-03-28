"""MockFullService: example Service with all three roles (DATA_SOURCE, ACTION, EVENT_SOURCE).

Used exclusively in tests and local development.
Validates that a single Service instance can register with all three roles.
"""


import json
import uuid
from typing import TYPE_CHECKING, Any

from harvest.interfaces.service import (
    ActionCommand,
    ActionResult,
    DataQuery,
    DataResult,
    Service,
    ServiceRole,
)
from harvest.interfaces.tool_definition import InterfaceTool, ToolArgument

if TYPE_CHECKING:
    from harvest.events.event_bus import EventBus


class MockFullService(Service):
    """A mock service fulfilling all three roles for multi-role testing.

    Roles:

    - ``DATA_SOURCE`` — returns mock data for ``"lookup"`` queries
    - ``ACTION`` — handles ``"notify"`` commands
    - ``EVENT_SOURCE`` — fires ``"tick"`` events when :meth:`fire_tick` is called

    Exposes tools for DATA_SOURCE and ACTION roles.
    EVENT_SOURCE follows the inbox model (no tools).
    """

    def __init__(self, service_id: str = "mock-full") -> None:
        self._service_id = service_id
        self._event_bus: EventBus | None = None
        self._started = False

    @property
    def service_id(self) -> str:
        return self._service_id

    @property
    def roles(self) -> frozenset[ServiceRole]:
        return frozenset({
            ServiceRole.DATA_SOURCE,
            ServiceRole.ACTION,
            ServiceRole.EVENT_SOURCE,
        })

    def get_capabilities(self) -> list[str]:
        return ["data_lookup", "notify_action", "tick_events"]

    async def fetch(self, query: DataQuery) -> DataResult:
        if query.query_type == "lookup":
            key = query.params.get("key", "unknown")
            return DataResult(
                request_id=query.request_id,
                source_id=self.service_id,
                payload={"key": key, "value": f"mock_value_for_{key}"},
            )
        return DataResult(
            request_id=query.request_id,
            source_id=self.service_id,
            payload={},
            error=f"unknown_query_type: '{query.query_type}'",
        )

    async def execute(self, command: ActionCommand) -> ActionResult:
        if command.command_type == "notify":
            message = command.params.get("message", "")
            return ActionResult(
                request_id=command.request_id,
                action_id=self.service_id,
                payload={"notified": True, "message": message, "id": str(uuid.uuid4())},
            )
        return ActionResult(
            request_id=command.request_id,
            action_id=self.service_id,
            payload={},
            error=f"unknown_command_type: '{command.command_type}'",
        )

    async def start(self, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus
        self._started = True

    async def stop(self) -> None:
        self._started = False
        self._event_bus = None

    def health_check(self) -> dict[str, Any]:
        return {"status": "healthy", "started": self._started}

    def get_tools(self, role: ServiceRole | None = None) -> list[InterfaceTool]:
        tools: list[InterfaceTool] = []

        include_ds = role is None or role == ServiceRole.DATA_SOURCE
        include_action = role is None or role == ServiceRole.ACTION

        if include_ds:
            def _lookup_handler(agent_id: str, key: str) -> str:
                if not hasattr(self, "_fetch_callback"):
                    return json.dumps({"error": "fetch_callback_not_bound"})
                return self._fetch_callback(
                    agent_id,
                    self._service_id,
                    "lookup",
                    {"key": key},
                )

            tools.append(
                InterfaceTool(
                    name="full_service_lookup",
                    short_description="Look up a value by key.",
                    full_description="Look up a value by key from the full mock service.",
                    arguments=[
                        ToolArgument(
                            name="key",
                            type="string",
                            description="The key to look up",
                            required=True,
                        ),
                    ],
                    returns_description="JSON with 'key' and 'value'.",
                    service_id=self._service_id,
                    service_type="data_source",
                    handler=_lookup_handler,
                )
            )

        if include_action:
            def _notify_handler(agent_id: str, message: str) -> str:
                if not hasattr(self, "_execute_callback"):
                    return json.dumps({"error": "execute_callback_not_bound"})
                return self._execute_callback(
                    agent_id,
                    self._service_id,
                    "notify",
                    {"message": message},
                )

            tools.append(
                InterfaceTool(
                    name="full_service_notify",
                    short_description="Send a notification message.",
                    full_description="Send a notification message through the full mock service.",
                    arguments=[
                        ToolArgument(
                            name="message",
                            type="string",
                            description="The notification message",
                            required=True,
                        ),
                    ],
                    returns_description="JSON with 'notified' and 'id'.",
                    service_id=self._service_id,
                    service_type="action",
                    handler=_notify_handler,
                )
            )

        return tools

    def fire_tick(self, value: float) -> None:
        """Manually fire a tick event for testing.

        Args:
            value: The tick value to include in the payload.
        """
        if self._event_bus is None:
            return

        from harvest.events.base import ExternalEventFired

        self._event_bus.dispatch(
            ExternalEventFired(
                source_id=self._service_id,
                event_type="tick",
                payload={"value": value},
            )
        )
