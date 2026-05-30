"""Storage environment override tests."""

from pathlib import Path

import pytest


def test_data_dir_can_be_overridden_by_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import safe_whale.storage as storage_mod

    override = tmp_path / "override"
    monkeypatch.setenv("$SAFE_WHALE_DATA_DIR", str(override))

    assert storage_mod._data_dir() == override
    assert override.exists()
