"""Phase 1 contract tests for the Resource abstraction."""

from __future__ import annotations

from abc import ABC


def test_resource_contract_exists() -> None:
    """Phase 1 should introduce a Resource contract."""
    from harvest.resource import Resource

    assert issubclass(Resource, ABC)


def test_resource_contract_exposes_capabilities() -> None:
    """Resource should advertise capabilities through a typed contract."""
    from harvest.resource import Resource

    assert hasattr(Resource, "resource_id")
    assert hasattr(Resource, "get_capabilities")


def test_resource_contract_has_lifecycle_methods() -> None:
    """Resource should have an explicit lifecycle."""
    from harvest.resource import Resource

    assert hasattr(Resource, "start")
    assert hasattr(Resource, "stop")
    assert hasattr(Resource, "health_check")


def test_resource_contract_is_distinct_from_broker() -> None:
    """Resource should be introduced as a separate abstraction from Broker."""
    from harvest.broker._base import Broker
    from harvest.resource import Resource

    assert Resource is not Broker
