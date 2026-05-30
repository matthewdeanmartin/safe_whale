"""Tests for data models."""

from datetime import datetime

from safe_whale.models import CatalogEntry, Profile, RunConfig, RunResult


def test_run_config_defaults():
    cfg = RunConfig(package_spec="httpie", entrypoint="http")
    assert cfg.read_only is True
    assert cfg.non_root is True
    assert cfg.memory_mb == 1024
    assert cfg.engine == "docker"


def test_run_config_display_name():
    cfg = RunConfig(package_spec="httpie==3.2.2", entrypoint="http")
    assert cfg.display_name() == "httpie==3.2.2"


def test_run_config_display_name_empty():
    cfg = RunConfig(package_spec="", entrypoint="mybin")
    assert cfg.display_name() == "mybin"


def test_catalog_entry_defaults():
    entry = CatalogEntry(name="ruff", entrypoint="ruff", description="Fast linter")
    assert entry.ecosystem == "pypi"
    assert entry.apt_packages == []


def test_run_result():
    cfg = RunConfig(package_spec="ruff", entrypoint="ruff")
    result = RunResult(
        config=cfg,
        timestamp=datetime.now(),
        exit_code=0,
        stdout="ok\n",
        stderr="",
    )
    assert result.exit_code == 0


def test_profile():
    cfg = RunConfig(package_spec="black", entrypoint="black")
    profile = Profile(name="my-black", config=cfg)
    assert profile.name == "my-black"
    assert profile.config.package_spec == "black"
