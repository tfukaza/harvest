"""Resource contract for generalized runtime inputs and capabilities."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Resource(ABC):
    """Defines a generalized runtime resource distinct from broker execution.

    A resource can expose data, artifacts, or other runtime inputs. It advertises
    capabilities and lifecycle state, while the runtime decides how those
    capabilities are surfaced to agents.
    """

    @property
    @abstractmethod
    def resource_id(self) -> str:
        """Return the stable identifier for this resource."""

    @abstractmethod
    def get_capabilities(self) -> list[str]:
        """Return the capabilities exposed by this resource."""

    @abstractmethod
    async def start(self) -> None:
        """Start the resource lifecycle."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the resource lifecycle."""

    @abstractmethod
    def health_check(self) -> dict[str, Any]:
        """Return resource health information."""
