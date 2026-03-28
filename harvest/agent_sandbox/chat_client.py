"""Client for agents to communicate with ChatRouter via the sandbox event bus.

Agents use ``ChatRouterClient`` instead of calling ChatRouter methods directly.
Every operation dispatches a request event onto the shared ``SyncEventBus`` and
blocks the calling thread until a matching response arrives (or a timeout fires).
"""


import logging
import uuid
from typing import Any

from harvest.agent_sandbox.chat_events import (
    AddAgentToChannelRequest,
    AddAgentToChannelResponse,
    ChatMessageDelivered,
    CreateChannelRequest,
    CreateChannelResponse,
    LeaveChannelRequest,
    LeaveChannelResponse,
    ListChannelsRequest,
    ListChannelsResponse,
    ReadMessagesRequest,
    ReadMessagesResponse,
    ReleaseStake,
    RequestStake,
    SendChatMessage,
    StakeGranted,
    StakeQueued,
)
from harvest.agent_sandbox.event_helpers import SyncEventBus, dispatch_and_wait
from harvest.events.base import HarvestEvent

logger = logging.getLogger(__name__)


class ChatRouterClient:
    """Event-bus client that agents use to talk to the ChatRouter.

    All methods block until a response event is received or the timeout
    expires.  The caller (agent thread) is parked via ``dispatch_and_wait``
    which subscribes *before* dispatching, eliminating response-race bugs.
    """

    def __init__(self, agent_id: str, sandbox_bus: SyncEventBus) -> None:
        self._agent_id = agent_id
        self._bus = sandbox_bus

    # -- internal helpers ----------------------------------------------------

    def _request(
        self,
        request: HarvestEvent,
        response_types: tuple[type[HarvestEvent], ...],
        timeout: float = 10.0,
        match_field: str = "request_id",
        match_value: str | None = None,
        id_field: str = "agent_id",
    ) -> HarvestEvent | None:
        """Dispatch a request and block for a matching response.

        Builds the standard filter that matches ``match_field`` and
        ``id_field`` (the agent owning this client).
        """
        expected = match_value or getattr(request, match_field, "")
        return dispatch_and_wait(
            bus=self._bus,
            request=request,
            response_types=response_types,
            filter_fn=lambda e: (
                getattr(e, match_field, None) == expected
                and getattr(e, id_field, None) == self._agent_id
            ),
            timeout=timeout,
        )

    # -- public API ----------------------------------------------------------

    def send_message(self, channel_id: str, content: str, reply_to: str = "") -> dict:
        """Full send flow: request stake -> send -> auto-release on delivery."""
        request_id = uuid.uuid4().hex

        # 1. Request the write stake.
        stake_resp = self._request(
            RequestStake(agent_id=self._agent_id, channel_id=channel_id, request_id=request_id),
            response_types=(StakeGranted, StakeQueued),
            timeout=10.0,
        )
        if stake_resp is None:
            return {"error": "stake_timeout"}

        # 2a. Queued — return immediately, no retry loop.
        if isinstance(stake_resp, StakeQueued):
            return {
                "status": "stake_queued",
                "channel_id": channel_id,
                "queue_position": stake_resp.position,
                "hint": "StakeGranted will arrive later on the bus.",
            }

        # 2b. Granted — send the message and wait for delivery ACK.
        message_id = uuid.uuid4().hex
        delivery = self._request(
            SendChatMessage(
                sender_id=self._agent_id, channel_id=channel_id,
                content=content, message_id=message_id, reply_to=reply_to,
            ),
            response_types=(ChatMessageDelivered,),
            timeout=10.0,
            match_field="message_id",
            match_value=message_id,
            id_field="sender_id",
        )
        if delivery is None:
            return {"error": "delivery_timeout"}
        if isinstance(delivery, ChatMessageDelivered) and delivery.error:
            return {"error": delivery.error}
        return {"status": "sent", "channel_id": channel_id}

    def acquire_channel_lock(self, channel_id: str) -> dict:
        """Request the write lock on a channel. Returns immediately.

        Returns ``{"status": "granted"}`` if acquired, or
        ``{"status": "queued", "position": N}`` if another agent holds it.
        """
        request_id = uuid.uuid4().hex
        resp = self._request(
            RequestStake(agent_id=self._agent_id, channel_id=channel_id, request_id=request_id),
            response_types=(StakeGranted, StakeQueued),
            timeout=10.0,
        )
        if resp is None:
            return {"error": "lock_timeout"}
        if isinstance(resp, StakeQueued):
            return {
                "status": "queued",
                "channel_id": channel_id,
                "position": resp.position,
                "hint": "The channel is locked by another agent. You will "
                "be notified when it's your turn. Wait before composing "
                "your message.",
            }
        return {"status": "granted", "channel_id": channel_id}

    def release_channel_lock(self, channel_id: str) -> dict:
        """Release a previously acquired channel lock without sending."""
        self._bus.dispatch(ReleaseStake(
            agent_id=self._agent_id,
            channel_id=channel_id,
        ))
        return {"status": "released", "channel_id": channel_id}

    def send_message_locked(self, channel_id: str, content: str, reply_to: str = "") -> dict:
        """Send a message on a channel where the lock is already held.

        Skips stake acquisition — the caller must have already acquired
        the lock via :meth:`acquire_channel_lock`.
        """
        message_id = uuid.uuid4().hex
        delivery = self._request(
            SendChatMessage(
                sender_id=self._agent_id, channel_id=channel_id,
                content=content, message_id=message_id, reply_to=reply_to,
            ),
            response_types=(ChatMessageDelivered,),
            timeout=10.0,
            match_field="message_id",
            match_value=message_id,
            id_field="sender_id",
        )
        if delivery is None:
            return {"error": "delivery_timeout"}
        if isinstance(delivery, ChatMessageDelivered) and delivery.error:
            return {"error": delivery.error}
        return {"status": "sent", "channel_id": channel_id}

    def read_messages(self, channel_id: str = "", history: bool = False) -> dict:
        """Fire ``ReadMessagesRequest`` and block for ``ReadMessagesResponse``."""
        resp = self._request(
            ReadMessagesRequest(agent_id=self._agent_id, request_id=uuid.uuid4().hex,
                                channel_id=channel_id, history=history),
            response_types=(ReadMessagesResponse,),
            timeout=5.0,
        )
        if resp is None:
            return {"error": "read_timeout"}
        return {"messages": resp.messages}  # type: ignore[union-attr]

    def list_channels(self, channel_type: str = "") -> list[dict]:
        """Fire ``ListChannelsRequest`` and block for ``ListChannelsResponse``."""
        resp = self._request(
            ListChannelsRequest(agent_id=self._agent_id, request_id=uuid.uuid4().hex,
                                channel_type=channel_type),
            response_types=(ListChannelsResponse,),
            timeout=5.0,
        )
        if resp is None:
            return []
        return resp.channels  # type: ignore[union-attr]

    def add_agent_to_channel(self, agent_id: str, channel_id: str) -> dict:
        """Request adding an agent to a channel. Blocks until response."""
        resp = self._request(
            AddAgentToChannelRequest(requester_id=self._agent_id, agent_id=agent_id,
                                     channel_id=channel_id, request_id=uuid.uuid4().hex),
            response_types=(AddAgentToChannelResponse,),
            timeout=10.0,
            id_field="requester_id",
        )
        if resp is None:
            return {"error": "add_agent_timeout"}
        resp_typed: AddAgentToChannelResponse = resp  # type: ignore[assignment]
        if resp_typed.error:
            return {"error": resp_typed.error}
        return {
            "status": resp_typed.status,
            "agent_id": resp_typed.agent_id,
            "channel_id": resp_typed.channel_id,
        }

    def create_channel(
        self,
        channel_id: str,
        channel_type: str = "group",
        member_ids: list[str] | None = None,
        description: str = "",
    ) -> dict:
        """Request creating a new channel. Blocks until response."""
        resp = self._request(
            CreateChannelRequest(
                requester_id=self._agent_id, request_id=uuid.uuid4().hex,
                channel_id=channel_id, channel_type=channel_type,
                member_ids=member_ids or [], description=description,
            ),
            response_types=(CreateChannelResponse,),
            timeout=10.0,
            id_field="requester_id",
        )
        if resp is None:
            return {"error": "create_channel_timeout"}
        resp_typed: CreateChannelResponse = resp  # type: ignore[assignment]
        if resp_typed.error:
            return {"error": resp_typed.error}
        return {"status": resp_typed.status, "channel_id": resp_typed.channel_id}

    def leave_channel(self, channel_id: str) -> dict:
        """Request leaving a channel. Blocks until response."""
        resp = self._request(
            LeaveChannelRequest(
                agent_id=self._agent_id, request_id=uuid.uuid4().hex,
                channel_id=channel_id,
            ),
            response_types=(LeaveChannelResponse,),
            timeout=10.0,
        )
        if resp is None:
            return {"error": "leave_channel_timeout"}
        resp_typed: LeaveChannelResponse = resp  # type: ignore[assignment]
        if resp_typed.error:
            return {"error": resp_typed.error}
        return {"status": resp_typed.status, "channel_id": resp_typed.channel_id}

    def peek_inbox(self) -> list[dict]:
        """Convenience: read messages with no channel filter."""
        result = self.read_messages()
        return result.get("messages", [])

    def close(self) -> None:
        """Cleanup (no-op for now)."""
