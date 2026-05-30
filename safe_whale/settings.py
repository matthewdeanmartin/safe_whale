"""Application-level settings for the safe-whale UI."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from safe_whale.storage import _data_dir


@dataclass
class AppSettings:
    """Small persisted settings record for v2 UI state."""

    wrapper_dir: str = ""
    help_panel_visible: bool = False
    catalog_cache_ttl: int = 86_400
    last_selected_tab: str = "Catalog"
    preferred_search_mode: str = "fuzzy"


def _settings_path() -> Path:
    return _data_dir() / "settings.json"


def load_settings() -> AppSettings:
    """Load app settings, returning defaults if no settings exist yet."""
    path = _settings_path()
    if not path.exists():
        return AppSettings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AppSettings()
    if not isinstance(data, dict):
        return AppSettings()
    return AppSettings(
        wrapper_dir=str(data.get("wrapper_dir", "")),
        help_panel_visible=bool(data.get("help_panel_visible", False)),
        catalog_cache_ttl=_int_from_object(data.get("catalog_cache_ttl"), 86_400),
        last_selected_tab=str(data.get("last_selected_tab", "Catalog")),
        preferred_search_mode=str(data.get("preferred_search_mode", "fuzzy")),
    )


def save_settings(settings: AppSettings) -> None:
    """Persist app settings."""
    data = {
        "wrapper_dir": settings.wrapper_dir,
        "help_panel_visible": settings.help_panel_visible,
        "catalog_cache_ttl": settings.catalog_cache_ttl,
        "last_selected_tab": settings.last_selected_tab,
        "preferred_search_mode": settings.preferred_search_mode,
    }
    _settings_path().write_text(json.dumps(data, indent=2), encoding="utf-8")


def _int_from_object(value: object, default: int) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default
