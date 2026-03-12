"""Sanity tests for storage surfaces that remain in the architecture."""

from __future__ import annotations

from pathlib import Path

from harvest.services.central_storage_service import CentralStorageService
from harvest.storage._base import LocalAlgorithmStorage


def test_local_algorithm_storage_uses_algorithm_directory(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    storage = LocalAlgorithmStorage("test_algo")

    assert Path("algorithms").exists()
    assert str(storage.db_engine.url) == "sqlite:///algorithms/test_algo.db"


def test_central_storage_service_exposes_shared_storage_capabilities(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    service = CentralStorageService()

    assert Path("shared").exists()
    assert service.service_name == "central_storage"
    assert "shared_database_access" in service.get_capabilities()
