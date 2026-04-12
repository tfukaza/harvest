"""Gated processor for channel-based chat system."""


import threading

from harvest.agent_sandbox.chat.messages import SandboxMessage


class GatedProcessor:
    """Backs GatedProcessorChannel.

    Tracks which publishers have sent at least one message. When all
    publishers have contributed, opens the gate and releases all buffered
    messages. Once opened, the gate stays open — subsequent messages pass
    through immediately.
    """

    def __init__(self, publisher_ids: list[str]) -> None:
        """Initialize the gated processor.

        Args:
            publisher_ids: List of publisher agent IDs that must all send
                before the gate opens.
        """
        self._required_publishers: set[str] = set(publisher_ids)
        self._received_publishers: set[str] = set()
        self._buffer: list[SandboxMessage] = []
        self._gate_open = False
        self._lock = threading.Lock()

    @property
    def gate_open(self) -> bool:
        """Return whether the gate has been opened."""
        return self._gate_open

    def accept_message(self, msg: SandboxMessage) -> list[SandboxMessage]:
        """Accept a message, returning released batch if gate opens.

        Args:
            msg: The incoming message.

        Returns:
            Released batch if gate opens (or is already open), otherwise empty list.
        """
        with self._lock:
            if self._gate_open:
                return [msg]

            self._buffer.append(msg)
            self._received_publishers.add(msg.sender.endpoint_id)

            if self._required_publishers <= self._received_publishers:
                self._gate_open = True
                released = list(self._buffer)
                self._buffer.clear()
                return released

            return []

    def flush(self) -> list[SandboxMessage]:
        """Return buffered messages regardless of gate state.

        Returns:
            All buffered messages.
        """
        with self._lock:
            released = list(self._buffer)
            self._buffer.clear()
            return released
