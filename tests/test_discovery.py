"""Tests for console-script discovery."""

from __future__ import annotations

from pathlib import Path

import pytest

import safe_whale.discovery as discovery_mod
from safe_whale.discovery import (
    DiscoveredCommand,
    _parse_probe_output,
    _probe_argv,
    discover_entrypoints,
    load_cached_entrypoints,
    save_cached_entrypoints,
)
from safe_whale.models import RunConfig, RunResult


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(discovery_mod, "_data_dir", lambda: tmp_path)


def test_parse_probe_output_extracts_commands() -> None:
    stdout = (
        "noise from build\n"
        '[{"name": "https", "group": "console_scripts", "value": "httpie.__main__:main"}, '
        '{"name": "http", "group": "console_scripts", "value": "httpie.__main__:main"}]\n'
    )
    commands = _parse_probe_output(stdout)
    assert [command.name for command in commands] == ["http", "https"]
    assert commands[0].group == "console_scripts"


def test_parse_probe_output_handles_empty_and_garbage() -> None:
    assert _parse_probe_output("") == []
    assert _parse_probe_output("not json at all") == []
    assert _parse_probe_output("[]") == []


def test_probe_argv_overrides_entrypoint_and_blocks_network() -> None:
    cfg = RunConfig(package_spec="httpie", entrypoint="http")
    argv = _probe_argv(cfg, "safe-whale-httpie-abc123")

    assert "--entrypoint" in argv
    assert argv[argv.index("--entrypoint") + 1] == "python"
    # network is forced off for the probe
    assert "none" in argv
    # the probe passes the base project name as the script argument
    assert argv[-1] == "httpie"
    assert "-c" in argv


def test_discover_returns_empty_when_build_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = RunConfig(package_spec="ruff", entrypoint="ruff")

    def fake_run_container(config: RunConfig, **_kwargs: object) -> RunResult:
        from datetime import datetime

        return RunResult(
            config=config,
            timestamp=datetime.now(),
            exit_code=1,
            stdout="",
            stderr="boom",
            image_ready=False,
        )

    import safe_whale.runner as runner_mod

    monkeypatch.setattr(runner_mod, "run_container", fake_run_container)
    assert discover_entrypoints(cfg) == []


def test_discover_uses_cache_without_building(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = RunConfig(package_spec="httpie", entrypoint="http")
    from safe_whale.container import image_tag

    save_cached_entrypoints(
        image_tag(cfg),
        [DiscoveredCommand("http", "console_scripts", "httpie:main")],
    )

    def explode(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("run_container should not be called when cache is warm")

    import safe_whale.runner as runner_mod

    monkeypatch.setattr(runner_mod, "run_container", explode)
    commands = discover_entrypoints(cfg)
    assert [command.name for command in commands] == ["http"]


def test_cache_round_trip() -> None:
    commands = [
        DiscoveredCommand("a", "console_scripts", "pkg:a"),
        DiscoveredCommand("b", "gui_scripts", "pkg:b"),
    ]
    save_cached_entrypoints("safe-whale-pkg-deadbeef", commands)
    loaded = load_cached_entrypoints("safe-whale-pkg-deadbeef")
    assert loaded is not None
    assert [command.name for command in loaded] == ["a", "b"]
    assert load_cached_entrypoints("safe-whale-missing-0") is None
