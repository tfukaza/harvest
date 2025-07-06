import asyncio
from typing import Callable, Dict, List, Any, Optional
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)


class EventBus:
    """
    Event bus system for decoupled communication between services.
    Supports both synchronous and asynchronous event handling.
    """

    def __init__(self):
        self._event_handlers: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = asyncio.Lock()

    def publish(self, event_type: str, data: dict) -> None:
        """
        Publish an event to all subscribers.

        Note that individual handlers maybe asynchronous, but this function as a whole runs them synchronously.

        Args:
            event_type: Type of event being published
            data: Event data payload
        """
        if event_type not in self._event_handlers:
            logger.debug(f"No handlers for event type: {event_type}")
            return

        handlers = self._event_handlers[event_type].copy()

        for handler_info in handlers:
            try:
                if not self._matches_filters(data, handler_info['filters']):
                    continue

                handler = handler_info['callback']
                if asyncio.iscoroutinefunction(handler):
                    asyncio.create_task(handler(data))
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"Error in event handler for {event_type}: {e}")

    async def publish_async(self, event_type: str, data: dict) -> None:
        """
        Publish an event asynchronously to all subscribers.

        Args:
            event_type: Type of event being published
            data: Event data payload
        """
        async with self._lock:
            if event_type not in self._event_handlers:
                logger.debug(f"No handlers for event type: {event_type}")
                return

            handlers = self._event_handlers[event_type].copy()

        # Execute handlers concurrently
        tasks = []
        for handler_info in handlers:
            try:
                if not self._matches_filters(data, handler_info['filters']):
                    continue

                handler = handler_info['callback']
                if asyncio.iscoroutinefunction(handler):
                    tasks.append(handler(data))
                else:
                    tasks.append(asyncio.create_task(asyncio.to_thread(handler, data)))
            except Exception as e:
                logger.error(f"Error preparing handler for {event_type}: {e}")

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def subscribe(self, event_type: str, callback: Callable, filters: Optional[dict] = None) -> str:
        """
        Subscribe to an event type with optional filtering.

        Args:
            event_type: Type of event to subscribe to
            callback: Function to call when event occurs
            filters: Optional filters for event data.
               This is a dictionary where keys are field names and values are expected values.
               The callback will only be called if the event data matches all filters.

        Returns:
            Subscription ID for later unsubscription
        """
        subscription_id = str(uuid4())

        handler_info = {
            'id': subscription_id,
            'callback': callback,
            'filters': filters or {}
        }

        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []

        self._event_handlers[event_type].append(handler_info)

        logger.debug(f"Subscribed to {event_type} with ID: {subscription_id}")
        return subscription_id

    def unsubscribe(self, subscription_id: str) -> None:
        """
        Unsubscribe from events using subscription ID.

        Args:
            subscription_id: ID returned from subscribe()
        """
        for event_type, handlers in self._event_handlers.items():
            self._event_handlers[event_type] = [
                h for h in handlers if h['id'] != subscription_id
            ]

            # Clean up empty event types
            if not self._event_handlers[event_type]:
                del self._event_handlers[event_type]
                break

        logger.debug(f"Unsubscribed: {subscription_id}")

    def get_subscription_count(self, event_type: Optional[str] = None) -> int:
        """
        Get the number of subscriptions for an event type or all events.

        Args:
            event_type: Optional event type to count, if None counts all

        Returns:
            Number of subscriptions
        """
        if event_type:
            return len(self._event_handlers.get(event_type, []))

        return sum(len(handlers) for handlers in self._event_handlers.values())

    def clear_all_subscriptions(self) -> None:
        """Clear all event subscriptions."""
        self._event_handlers.clear()
        logger.info("All event subscriptions cleared")

    def _matches_filters(self, data: dict, filters: dict) -> bool:
        """
        Check if event data matches subscription filters.

        Args:
            data: Event data
            filters: Filter criteria

        Returns:
            True if data matches all filters
        """
        if not filters:
            return True

        for key, expected_value in filters.items():
            if key not in data or data[key] != expected_value:
                return False

        return True
