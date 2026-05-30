"""PyPI metadata enrichment with a small JSON cache."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from safe_whale.models import CatalogEntry
from safe_whale.storage import _data_dir

PYPI_JSON_URL = "https://pypi.org/pypi/{name}/json"


class MetadataError(RuntimeError):
    """Raised when fresh metadata cannot be fetched or parsed."""


def metadata_cache_dir() -> Path:
    """Return the persistent metadata cache directory."""
    path = _data_dir() / "metadata"
    path.mkdir(parents=True, exist_ok=True)
    return path


def enrich_catalog_entry(
    entry: CatalogEntry,
    ttl_seconds: int,
    *,
    timeout_seconds: float = 5.0,
) -> CatalogEntry:
    """Return a copy of entry enriched from cached or freshly fetched PyPI JSON."""
    cached = _load_cached_payload(entry.name)
    if cached is not None and _cache_is_fresh(cached, ttl_seconds):
        return _entry_from_payload(entry, cached["payload"], "cached")

    try:
        payload = fetch_pypi_json(entry.name, timeout_seconds=timeout_seconds)
    except MetadataError:
        if cached is not None:
            return _entry_from_payload(entry, cached["payload"], "stale")
        raise

    _save_cached_payload(entry.name, payload)
    return _entry_from_payload(entry, payload, "fetched")


def fetch_pypi_json(name: str, *, timeout_seconds: float = 5.0) -> dict[str, Any]:
    """Fetch raw PyPI JSON metadata for a project."""
    normalized = normalize_project_name(name)
    request = Request(
        PYPI_JSON_URL.format(name=normalized),
        headers={"Accept": "application/json", "User-Agent": "safe-whale/0.1 metadata"},
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise MetadataError(str(exc)) from exc
    if not isinstance(data, dict):
        raise MetadataError("PyPI returned an unexpected metadata payload.")
    return data


def normalize_project_name(name: str) -> str:
    """Normalize a Python project name for cache filenames and PyPI URLs."""
    return re.sub(r"[-_.]+", "-", name.strip().lower())


def _cache_path(name: str) -> Path:
    return metadata_cache_dir() / f"{normalize_project_name(name)}.json"


def _load_cached_payload(name: str) -> dict[str, Any] | None:
    path = _cache_path(name)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("payload"), dict):
        return None
    return data


def _save_cached_payload(name: str, payload: dict[str, Any]) -> None:
    data = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    _cache_path(name).write_text(json.dumps(data, indent=2), encoding="utf-8")


def _cache_is_fresh(data: dict[str, Any], ttl_seconds: int) -> bool:
    fetched_at = data.get("fetched_at")
    if not isinstance(fetched_at, str):
        return False
    try:
        timestamp = datetime.fromisoformat(fetched_at)
    except ValueError:
        return False
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - timestamp
    return age.total_seconds() <= ttl_seconds


def _entry_from_payload(entry: CatalogEntry, payload: dict[str, Any], status: str) -> CatalogEntry:
    info = payload.get("info", {})
    releases = payload.get("releases", {})
    if not isinstance(info, dict):
        info = {}
    if not isinstance(releases, dict):
        releases = {}

    latest_version = _str(info.get("version"))
    release_files = releases.get(latest_version, [])
    if not isinstance(release_files, list):
        release_files = []

    summary = _str(info.get("summary"))
    project_urls = _string_dict(info.get("project_urls"))
    home_page = _str(info.get("home_page"))
    if home_page and "Homepage" not in project_urls:
        project_urls["Homepage"] = home_page

    return replace(
        entry,
        description=summary or entry.description,
        latest_version=latest_version,
        release_date=_release_date(release_files),
        license=_str(info.get("license")),
        requires_python=_str(info.get("requires_python")),
        classifiers=_string_list(info.get("classifiers")),
        keywords=_merge_unique(entry.keywords, _keywords(info.get("keywords"))),
        project_urls={**entry.project_urls, **project_urls},
        distribution_files=_distribution_files(release_files),
        metadata_status=status,
    )


def _release_date(files: list[Any]) -> str:
    dates = []
    for item in files:
        if isinstance(item, dict):
            date = _str(item.get("upload_time_iso_8601")) or _str(item.get("upload_time"))
            if date:
                dates.append(date)
    return max(dates) if dates else ""


def _distribution_files(files: list[Any]) -> list[str]:
    results: list[str] = []
    for item in files:
        if not isinstance(item, dict):
            continue
        filename = _str(item.get("filename"))
        packagetype = _str(item.get("packagetype"))
        python_version = _str(item.get("python_version"))
        label_parts = [part for part in (packagetype, python_version) if part]
        if filename:
            results.append(f"{filename} ({', '.join(label_parts)})" if label_parts else filename)
    return results[:8]


def _keywords(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if not isinstance(value, str):
        return []
    return [part for part in re.split(r"[,;\s]+", value) if part]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _string_dict(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(val) for key, val in value.items() if str(key) and str(val)}


def _merge_unique(first: list[str], second: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for value in [*first, *second]:
        normalized = value.lower()
        if normalized not in seen:
            seen.add(normalized)
            merged.append(value)
    return merged


def _str(value: object) -> str:
    return value if isinstance(value, str) else ""
