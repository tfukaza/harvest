"""Aggregation processor for channel-based chat system."""


import threading

from harvest.agent_sandbox.chat.messages import SandboxMessage


class AggregationProcessor:
    """Backs AggregationProcessorChannel.

    Buffers messages until count threshold, then releases batch to
    subscriber inboxes.
    """

    def __init__(self, batch_threshold: int = 1) -> None:
        """Initialize the aggregation processor.

        Args:
            batch_threshold: Number of messages required before release.
        """
        self._batch_threshold = batch_threshold
        self._buffer: list[SandboxMessage] = []
        self._lock = threading.Lock()

    @property
    def batch_threshold(self) -> int:
        """Return the configured batch threshold."""
        return self._batch_threshold

    def accept_message(self, msg: SandboxMessage) -> list[SandboxMessage]:
        """Accept a message, returning released batch if threshold met.

        Args:
            msg: The incoming message.

        Returns:
            Released batch if threshold met, otherwise empty list.
        """
        with self._lock:
            self._buffer.append(msg)
            if len(self._buffer) >= self._batch_threshold:
                released = list(self._buffer)
                self._buffer.clear()
                return released
            return []

    def flush(self) -> list[SandboxMessage]:
        """Return all buffered messages regardless of threshold.

        Returns:
            All buffered messages.
        """
        with self._lock:
            released = list(self._buffer)
            self._buffer.clear()
            return released
