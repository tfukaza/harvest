"""Sanity tests for the service registry."""

from __future__ import annotations

import asyncio

from harvest.services import Service, ServiceRegistry


class MockService(Service):
    """Minimal service implementation for registry tests."""

    def __init__(self, name: str = "mock_service") -> None:
        super().__init__(name)

    async def start(self) -> None:
        self.is_running = True

    async def stop(self) -> None:
        self.is_running = False

    def health_check(self) -> dict[str, str]:
        return {"status": "healthy" if self.is_running else "stopped"}

    def get_capabilities(self) -> list[str]:
        return ["mock_capability"]


def test_service_registry_registers_and_discovers_services() -> None:
    async def run_test() -> None:
        registry = ServiceRegistry()
        service = MockService()

        await registry.register_service("test_service", service, {"version": "1.0.0"})

        assert registry.get_service_count() == 1
        assert registry.discover_service("test_service") is service
        assert registry.list_services()["test_service"]["metadata"]["version"] == "1.0.0"

        await registry.shutdown()

    asyncio.run(run_test())


def test_service_registry_starts_and_stops_services() -> None:
    async def run_test() -> None:
        registry = ServiceRegistry()
        service = MockService()

        await registry.register_service("test_service", service)
        await registry.start_service("test_service")
        assert service.is_running is True
        assert registry.get_running_service_count() == 1

        await registry.stop_service("test_service")
        assert service.is_running is False
        assert registry.get_running_service_count() == 0

        await registry.shutdown()

    asyncio.run(run_test())