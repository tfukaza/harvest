"""Service event types for event-driven agent ↔ SandboxServiceRouter communication.

These events flow on the per-sandbox SyncEventBus. Agents dispatch request
events and block for the matching response. SandboxServiceRouter subscribes
to request events, executes the routing logic, and dispatches responses.
"""


from pydantic import Field

from harvest.events.base import HarvestEvent


# -- Data fetch --------------------------------------------------------------


class FetchDataRequest(HarvestEvent):
    """Agent requests a data fetch from a service."""

    agent_id: str
    request_id: str
    service_id: str
    query_type: str
    params: dict = Field(default_factory=dict)


class FetchDataResponse(HarvestEvent):
    """Service router returns fetch results."""

    agent_id: str
    request_id: str
    payload: dict = Field(default_factory=dict)
    error: str = ""


# -- Action execution --------------------------------------------------------


class ExecuteActionRequest(HarvestEvent):
    """Agent requests an action execution on a service."""

    agent_id: str
    request_id: str
    service_id: str
    command_type: str
    params: dict = Field(default_factory=dict)


class ExecuteActionResponse(HarvestEvent):
    """Service router returns action results."""

    agent_id: str
    request_id: str
    payload: dict = Field(default_factory=dict)
    error: str = ""


# -- Event notifications -----------------------------------------------------


class ReadNotificationsRequest(HarvestEvent):
    """Agent requests pending event notifications."""

    agent_id: str
    request_id: str


class ReadNotificationsResponse(HarvestEvent):
    """Service router returns pending notifications."""

    agent_id: str
    request_id: str
    notifications: list[dict] = Field(default_factory=list)


# -- Tool discovery ----------------------------------------------------------


class DiscoverToolsRequest(HarvestEvent):
    """Agent requests the service tool catalogue or a specific tool's full spec."""

    agent_id: str
    request_id: str
    tool_name: str = ""  # empty = list all, non-empty = get full spec


class DiscoverToolsResponse(HarvestEvent):
    """Service router returns tool catalogue or full spec."""

    agent_id: str
    request_id: str
    tools: list[dict] = Field(default_factory=list)
    error: str = ""
