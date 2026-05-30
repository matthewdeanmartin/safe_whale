"""Tests for launcher wrapper generation."""

from __future__ import annotations

import os
from pathlib import Path
import sys

import pytest
from safe_whale.launchers import (
    directory_on_path,
    generate_powershell_wrapper,
    generate_wrapper,
    install_launcher,
    install_launchers,
    launcher_info,
    launcher_infos,
    launcher_path,
    safe_launcher_name,
)
from safe_whale.models import Profile, RunConfig
from safe_whale.storage import config_digest



@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import safe_whale.storage as storage_mod

    monkeypatch.setattr(storage_mod, "_data_dir", lambda: tmp_path)


def test_safe_launcher_name() -> None:
    assert safe_launcher_name("My Tool!") == "my-tool"
    assert safe_launcher_name("...") == "safe-whale-tool"


def test_generate_posix_wrapper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    cfg = RunConfig(package_spec="ruff", entrypoint="ruff", cli_args="--help")
    wrapper = generate_wrapper(cfg)

    assert wrapper.startswith("#!/bin/sh")
    assert "docker run" in wrapper
    assert "--help" not in wrapper
    assert '"$@"' in wrapper


def test_generate_windows_wrapper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    cfg = RunConfig(package_spec="ruff", entrypoint="ruff", cli_args="--help")
    wrapper = generate_wrapper(cfg)

    assert wrapper.startswith("@echo off")
    assert "docker run" in wrapper
    assert "--help" not in wrapper
    assert "%*" in wrapper


def test_install_launcher_updates_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    profile = Profile(name="Ruff Format", config=RunConfig(package_spec="ruff", entrypoint="ruff"))

    updated = install_launcher(profile, str(tmp_path))

    # Wrappers are named after the command (entrypoint), pipx-style, not the profile.
    path = launcher_path(tmp_path, "ruff")
    assert path.exists()
    assert updated.launcher_name == "ruff"
    assert updated.launcher_installed is True
    assert updated.launcher_updated_at is not None
    assert updated.launcher_config_digest == config_digest(updated.config)


def test_directory_on_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ.get("PATH", ""))
    assert directory_on_path(tmp_path)


def test_install_launchers_writes_one_wrapper_per_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    profile = Profile(
        name="httpie",
        config=RunConfig(package_spec="httpie", entrypoint="http"),
        commands=["http", "https"],
    )

    updated, infos = install_launchers(profile, str(tmp_path))

    assert (tmp_path / "http").exists()
    assert (tmp_path / "https").exists()
    assert {info.command for info in infos} == {"http", "https"}
    # The primary launcher name is the first command.
    assert updated.launcher_name == "http"
    statuses = {info.command: info.status for info in launcher_infos(updated, str(tmp_path))}
    assert statuses == {"http": "ok", "https": "ok"}


def test_install_launchers_writes_ps1_on_windows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    profile = Profile(
        name="httpie",
        config=RunConfig(package_spec="httpie", entrypoint="http"),
        commands=["http"],
    )

    install_launchers(profile, str(tmp_path))

    assert (tmp_path / "http.cmd").exists()
    assert (tmp_path / "http.ps1").exists()


def test_generate_powershell_wrapper_forwards_args(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    cfg = RunConfig(package_spec="ruff", entrypoint="ruff", cli_args="--help")
    wrapper = generate_powershell_wrapper(cfg)

    assert "docker" in wrapper
    assert "@args" in wrapper
    assert "--help" not in wrapper


def test_launcher_info_detects_stale_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    profile = Profile(name="ruff", config=RunConfig(package_spec="ruff", entrypoint="ruff"))
    installed = install_launcher(profile, str(tmp_path))
    installed.config.block_network = True

    info = launcher_info(installed, str(tmp_path))

    assert info.status == "needs rebuild"
