import datetime as dt
from typing import TYPE_CHECKING

from .service_interface import Service
from ..events.event_bus import EventBus
from ..events.events import PriceUpdateEvent
from ..definitions import TickerFrame, ChainInfo, ChainData, OptionData
from ..enum import Interval

if TYPE_CHECKING:
    from .central_storage_service import CentralStorageService


class MarketDataService(Service):
    """
    Service for managing market data feeds and distribution.
    Integrates with broker instances to fetch real-time and historical data.
    """

    def __init__(self, broker_instance):
        super().__init__("market_data")
        self.broker = broker_instance
        self.event_bus = None
        self.central_storage = None
        self.subscribers = set()
        self._active_feeds = {}
        self._is_running = False

    async def start(self) -> None:
        """Start the market data service"""
        self.is_running = True
        self._start_time = dt.datetime.utcnow().timestamp()

    async def stop(self) -> None:
        """Stop the market data service"""
        # Stop all active feeds
        for feed_id in list(self._active_feeds.keys()):
            await self.stop_data_feed(feed_id)
        
        self.is_running = False

    def health_check(self) -> dict[str, any]:  # type: ignore
        """Perform health check on the market data service"""
        return {
            "status": "healthy" if self.is_running else "stopped",
            "active_feeds": len(self._active_feeds),
            "broker_connected": self.broker is not None,
            "central_storage_connected": self.central_storage is not None,
            "event_bus_connected": self.event_bus is not None,
            "uptime_seconds": dt.datetime.utcnow().timestamp() - (self._start_time or 0)
        }

    def get_capabilities(self) -> list[str]:
        """Get list of service capabilities"""
        return [
            "real_time_data",
            "historical_data", 
            "option_chains",
            "market_data_distribution",
            "data_storage_integration"
        ]

    def set_event_bus(self, event_bus: EventBus) -> None:
        """Set the event bus for publishing market data events"""
        self.event_bus = event_bus

    def set_central_storage(self, central_storage: "CentralStorageService") -> None:
        """Set the central storage service for data persistence"""
        self.central_storage = central_storage

    async def start_data_feed(self, symbols: list[str], interval: Interval) -> str:
        """
        Start real-time data feed for symbols
        
        Args:
            symbols: List of symbols to track
            interval: Data update interval
            
        Returns:
            Feed ID for managing the feed
        """
        feed_id = f"feed_{len(self._active_feeds)}_{dt.datetime.utcnow().timestamp()}"
        
        # Implementation depends on broker type
        # This is a placeholder - actual implementation would start broker-specific data streams
        feed_config = {
            "symbols": symbols,
            "interval": interval,
            "active": True,
            "start_time": dt.datetime.utcnow()
        }
        
        self._active_feeds[feed_id] = feed_config
        
        # Start the actual data feed (broker-specific implementation)
        # await self._start_broker_feed(feed_id, symbols, interval)
        
        return feed_id

    async def stop_data_feed(self, feed_id: str) -> None:
        """Stop a specific data feed"""
        if feed_id in self._active_feeds:
            # Stop broker-specific feed
            # await self._stop_broker_feed(feed_id)
            
            del self._active_feeds[feed_id]

    def publish_price_update(self, symbol: str, price_data: TickerFrame) -> None:
        """
        Publish price update and store in central storage
        
        Args:
            symbol: Symbol that was updated
            price_data: Updated price data as TickerFrame
        """
        # Store in central storage
        if self.central_storage:
            self.central_storage.store_price_data(price_data)

        # Publish event
        if self.event_bus:
            # Create event data as dict for now
            event_data = {
                "symbol": symbol,
                "price_data": price_data,
                "timestamp": dt.datetime.utcnow()
            }
            self.event_bus.publish('price_update', event_data)

    async def fetch_chain_info(self, symbol: str) -> ChainInfo:
        """
        Fetch option chain information for a symbol
        
        Args:
            symbol: Stock symbol
            
        Returns:
            ChainInfo with expiration dates and metadata
        """
        if not self.broker:
            raise Exception("No broker instance available")
        
        return self.broker.fetch_chain_info(symbol)

    async def fetch_chain_data(self, symbol: str, expiration_date: dt.datetime) -> ChainData:
        """
        Fetch option chain data for specific expiration
        
        Args:
            symbol: Stock symbol
            expiration_date: Option expiration date
            
        Returns:
            ChainData with option contracts
        """
        if not self.broker:
            raise Exception("No broker instance available")
        
        return self.broker.fetch_chain_data(symbol, expiration_date)

    async def fetch_option_market_data(self, option_symbol: str) -> OptionData:
        """
        Fetch market data for a specific option
        
        Args:
            option_symbol: OCC format option symbol
            
        Returns:
            OptionData with current market information
        """
        if not self.broker:
            raise Exception("No broker instance available")
        
        return self.broker.fetch_option_market_data(option_symbol)

    async def get_historical_data(self, symbol: str, interval: Interval, 
                                start: dt.datetime | None = None, 
                                end: dt.datetime | None = None) -> TickerFrame:
        """
        Get historical market data
        
        Args:
            symbol: Symbol to fetch data for
            interval: Data interval
            start: Start date (optional)
            end: End date (optional)
            
        Returns:
            TickerFrame with historical data
        """
        if not self.broker:
            raise Exception("No broker instance available")
        
        # This would typically call broker's historical data method
        # For now, return empty TickerFrame as placeholder
        import polars as pl
        empty_df = pl.DataFrame({
            "timestamp": [],
            "symbol": [],
            "open": [],
            "high": [],
            "low": [],
            "close": [],
            "volume": []
        })
        return TickerFrame(empty_df)

    def add_subscriber(self, subscriber_id: str) -> None:
        """Add a subscriber for market data updates"""
        self.subscribers.add(subscriber_id)

    def remove_subscriber(self, subscriber_id: str) -> None:
        """Remove a subscriber"""
        self.subscribers.discard(subscriber_id)

    def get_active_feeds(self) -> dict:
        """Get information about currently active data feeds"""
        return self._active_feeds.copy()
