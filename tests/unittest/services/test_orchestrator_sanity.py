"""Sanity tests for the orchestrator surface."""



def test_orchestrator_exposes_resource_registration_methods() -> None:
    from harvest.domain.orchestrator import Orchestrator

    assert hasattr(Orchestrator, "register_resource")
    assert hasattr(Orchestrator, "get_resource")
    assert hasattr(Orchestrator, "list_resources")


def test_orchestrator_exposes_service_lifecycle_methods() -> None:
    from harvest.domain.orchestrator import Orchestrator

    assert hasattr(Orchestrator, "start")
    assert hasattr(Orchestrator, "start_services")
    assert hasattr(Orchestrator, "shutdown_services")
