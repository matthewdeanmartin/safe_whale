"""Tests for managed cleanup."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from safe_whale.cleanup import delete_managed_asset, list_cleanup_assets
from safe_whale.models import ManagedAsset
from safe_whale.storage import load_managed_assets, upsert_managed_asset


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import safe_whale.storage as storage_mod

    monkeypatch.setattr(storage_mod, "_data_dir", lambda: tmp_path)


def test_list_cleanup_assets_refreshes_file_state(tmp_path: Path) -> None:
    wrapper = tmp_path / "tool.cmd"
    wrapper.write_text("@echo off\n", encoding="utf-8")
    upsert_managed_asset(
        ManagedAsset(
            asset_id="wrapper:tool",
            asset_type="wrapper",
            engine="docker",
            name="tool",
            location=str(wrapper),
            source="tool",
        )
    )

    assets = list_cleanup_assets()

    assert assets[0].state == "present"


def test_delete_managed_file_asset(tmp_path: Path) -> None:
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM scratch\n", encoding="utf-8")
    upsert_managed_asset(
        ManagedAsset(
            asset_id="dockerfile:tool",
            asset_type="dockerfile",
            engine="",
            name="Dockerfile",
            location=str(dockerfile),
            source="tool",
        )
    )

    result = delete_managed_asset("dockerfile:tool")

    assert result == "deleted"
    assert not dockerfile.exists()
    assert load_managed_assets() == []


def test_delete_managed_image_asset_runs_rmi(monkeypatch: pytest.MonkeyPatch) -> None:
    run = Mock(return_value=Mock(returncode=0))
    monkeypatch.setattr("safe_whale.cleanup.subprocess.run", run)
    upsert_managed_asset(
        ManagedAsset(
            asset_id="image:docker:safe-whale-demo",
            asset_type="image",
            engine="docker",
            name="safe-whale-demo",
            location="safe-whale-demo",
            source="demo",
        )
    )

    result = delete_managed_asset("image:docker:safe-whale-demo")

    assert result == "deleted"
    run.assert_called_with(
        ["docker", "rmi", "safe-whale-demo"], capture_output=True, text=True, timeout=60, check=False
    )
