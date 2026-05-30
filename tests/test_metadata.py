"""Tests for PyPI metadata enrichment."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from safe_whale.metadata import MetadataError, enrich_catalog_entry, normalize_project_name
from safe_whale.models import CatalogEntry


def _payload(version: str = "1.2.3") -> dict[str, object]:
    return {
        "info": {
            "summary": "Fetched summary",
            "version": version,
            "license": "MIT",
            "requires_python": ">=3.10",
            "classifiers": ["Programming Language :: Python :: 3"],
            "keywords": "http api, cli",
            "project_urls": {"Source": "https://example.test/source"},
        },
        "releases": {
            version: [
                {
                    "filename": f"demo-{version}-py3-none-any.whl",
                    "packagetype": "bdist_wheel",
                    "python_version": "py3",
                    "upload_time_iso_8601": "2026-05-01T12:00:00.000000Z",
                }
            ]
        },
    }


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect metadata cache to a temp directory."""
    import safe_whale.metadata as metadata_mod

    monkeypatch.setattr(metadata_mod, "_data_dir", lambda: tmp_path)


def test_normalize_project_name() -> None:
    assert normalize_project_name("Rich_CLI") == "rich-cli"


def test_enrich_fetches_and_caches_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    import safe_whale.metadata as metadata_mod

    calls = 0

    def fake_fetch(name: str, *, timeout_seconds: float = 5.0) -> dict[str, object]:
        nonlocal calls
        calls += 1
        assert name == "demo"
        return _payload()

    monkeypatch.setattr(metadata_mod, "fetch_pypi_json", fake_fetch)

    entry = CatalogEntry(name="demo", entrypoint="demo", description="Bundled")
    enriched = enrich_catalog_entry(entry, ttl_seconds=60)

    assert calls == 1
    assert enriched.description == "Fetched summary"
    assert enriched.latest_version == "1.2.3"
    assert enriched.release_date == "2026-05-01T12:00:00.000000Z"
    assert enriched.requires_python == ">=3.10"
    assert enriched.license == "MIT"
    assert enriched.metadata_status == "fetched"
    assert enriched.distribution_files == ["demo-1.2.3-py3-none-any.whl (bdist_wheel, py3)"]

    cached = enrich_catalog_entry(entry, ttl_seconds=60)
    assert calls == 1
    assert cached.metadata_status == "cached"


def test_enrich_uses_stale_cache_when_fetch_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import safe_whale.metadata as metadata_mod

    cache_dir = tmp_path / "metadata"
    cache_dir.mkdir()
    cache_file = cache_dir / "demo.json"
    cache_file.write_text(
        json.dumps(
            {
                "fetched_at": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
                "payload": _payload("2.0.0"),
            }
        ),
        encoding="utf-8",
    )

    def fake_fetch(_name: str, *, timeout_seconds: float = 5.0) -> dict[str, object]:
        raise MetadataError("offline")

    monkeypatch.setattr(metadata_mod, "fetch_pypi_json", fake_fetch)

    entry = CatalogEntry(name="demo", entrypoint="demo", description="Bundled")
    enriched = enrich_catalog_entry(entry, ttl_seconds=1)

    assert enriched.latest_version == "2.0.0"
    assert enriched.metadata_status == "stale"


def test_enrich_raises_without_cache_when_fetch_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    import safe_whale.metadata as metadata_mod

    def fake_fetch(_name: str, *, timeout_seconds: float = 5.0) -> dict[str, object]:
        raise MetadataError("offline")

    monkeypatch.setattr(metadata_mod, "fetch_pypi_json", fake_fetch)

    entry = CatalogEntry(name="demo", entrypoint="demo", description="Bundled")
    with pytest.raises(MetadataError):
        enrich_catalog_entry(entry, ttl_seconds=1)
