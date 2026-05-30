"""Tests for runner helpers — no Docker required."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch


def test_find_wt_uses_shutil_which_when_available() -> None:
    """If shutil.which finds wt, return 'wt' (not the full path)."""
    if sys.platform != "win32":
        return  # Windows-only test

    from safe_whale.runner import _find_wt

    with patch("shutil.which", return_value="wt"):
        assert _find_wt() == "wt"


def test_find_wt_falls_back_to_appx_alias(tmp_path: Path) -> None:
    """When shutil.which misses wt, fall back to the AppX alias path."""
    if sys.platform != "win32":
        return  # Windows-only test

    from safe_whale.runner import _find_wt

    fake_wt = tmp_path / "wt.exe"
    fake_wt.write_bytes(b"")  # create a file so .exists() returns True

    with (
        patch("shutil.which", return_value=None),
        patch.dict(os.environ, {"LOCALAPPDATA": str(tmp_path / "AppData" / "Local")}),
    ):
        # Alias won't exist at fake LOCALAPPDATA — should return None
        assert _find_wt() is None

    # Now put a wt.exe at the expected alias location
    alias_dir = tmp_path / "AppData" / "Local" / "Microsoft" / "WindowsApps"
    alias_dir.mkdir(parents=True)
    (alias_dir / "wt.exe").write_bytes(b"")

    with (
        patch("shutil.which", return_value=None),
        patch.dict(os.environ, {"LOCALAPPDATA": str(tmp_path / "AppData" / "Local")}),
    ):
        result = _find_wt()
        assert result is not None
        assert result.endswith("wt.exe")


def test_find_wt_returns_none_when_neither_found(tmp_path: Path) -> None:
    """Returns None when wt is not on PATH and not in the AppX alias location."""
    if sys.platform != "win32":
        return  # Windows-only test

    from safe_whale.runner import _find_wt

    with (
        patch("shutil.which", return_value=None),
        patch.dict(os.environ, {"LOCALAPPDATA": str(tmp_path)}),
    ):
        assert _find_wt() is None


def test_find_wt_real_system() -> None:
    """On this Windows machine, wt.exe should be discoverable via AppX alias."""
    if sys.platform != "win32":
        return

    from safe_whale.runner import _find_wt

    result = _find_wt()
    # On a system with Windows Terminal installed, it must be found.
    localappdata = os.environ.get("LOCALAPPDATA", "")
    appx_alias = Path(localappdata) / "Microsoft" / "WindowsApps" / "wt.exe"
    if appx_alias.exists():
        assert result is not None, (
            f"wt.exe exists at {appx_alias} but _find_wt() returned None — "
            "shutil.which and AppX fallback both failed"
        )
