"""Launcher wrapper generation for saved profiles.

Like pipx, a single installed package may expose several console-script commands.
``install_launchers`` writes one wrapper per command in ``profile.commands`` (falling
back to a single wrapper when no commands were discovered). On Windows each command
gets a ``.cmd`` (resolved via PATHEXT when typed bare) plus an optional ``.ps1``
companion for PowerShell users.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
import os
from pathlib import Path
import shlex
import stat
import subprocess
import sys

from safe_whale.container import build_run_argv, image_tag
from safe_whale.models import ManagedAsset, Profile, RunConfig
from safe_whale.storage import config_digest, upsert_managed_asset


@dataclass
class LauncherInfo:
    """Status for a generated launcher wrapper."""

    name: str
    path: Path
    exists: bool
    on_path: bool
    status: str
    command: str = ""


def install_launchers(profile: Profile, wrapper_dir: str) -> tuple[Profile, list[LauncherInfo]]:
    """Write a wrapper for every command the profile exposes.

    Returns the updated profile (with launcher bookkeeping refreshed) and one
    LauncherInfo per generated command.
    """
    directory = Path(wrapper_dir)
    directory.mkdir(parents=True, exist_ok=True)
    if not directory.is_dir():
        raise NotADirectoryError(wrapper_dir)

    commands = profile_commands(profile)
    primary = commands[0]
    updated_at = datetime.now()
    infos: list[LauncherInfo] = []

    for command in commands:
        launcher_name = safe_launcher_name(command)
        path = launcher_path(directory, launcher_name)
        cmd_cfg = replace(profile.config, entrypoint=command)
        path.write_text(generate_wrapper(cmd_cfg), encoding="utf-8")
        if sys.platform != "win32":
            path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        else:
            ps1_path = directory / f"{launcher_name}.ps1"
            ps1_path.write_text(generate_powershell_wrapper(cmd_cfg), encoding="utf-8")
            _record_wrapper_asset(profile, f"{command}-ps1", launcher_name, ps1_path, updated_at)
        _record_wrapper_asset(profile, command, launcher_name, path, updated_at)
        infos.append(LauncherInfo(launcher_name, path, True, directory_on_path(directory), "ok", command))

    updated = replace(
        profile,
        launcher_name=safe_launcher_name(primary),
        launcher_installed=True,
        launcher_updated_at=updated_at,
        launcher_config_digest=config_digest(profile.config),
    )
    return updated, infos


def install_launcher(profile: Profile, wrapper_dir: str) -> Profile:
    """Write or update wrappers for a profile and return an updated profile.

    Thin back-compatible wrapper over :func:`install_launchers`.
    """
    updated, _infos = install_launchers(profile, wrapper_dir)
    return updated


def profile_commands(profile: Profile) -> list[str]:
    """Return the command names a profile should install wrappers for."""
    if profile.commands:
        return list(dict.fromkeys(profile.commands))
    fallback = profile.launcher_name or profile.config.entrypoint or profile.name
    return [fallback]


def launcher_infos(profile: Profile, wrapper_dir: str) -> list[LauncherInfo]:
    """Return wrapper status for each command the profile exposes."""
    return [_command_info(profile, command, wrapper_dir) for command in profile_commands(profile)]


def launcher_info(profile: Profile, wrapper_dir: str) -> LauncherInfo:
    """Return wrapper status for a profile's primary command (back-compat)."""
    launcher_name = profile.launcher_name or safe_launcher_name(profile_commands(profile)[0])
    return _command_info(profile, launcher_name, wrapper_dir)


def _command_info(profile: Profile, command: str, wrapper_dir: str) -> LauncherInfo:
    launcher_name = safe_launcher_name(command)
    directory = Path(wrapper_dir) if wrapper_dir else Path()
    path = launcher_path(directory, launcher_name) if wrapper_dir else Path()
    exists = bool(wrapper_dir) and path.exists()
    on_path = bool(wrapper_dir) and directory_on_path(directory)
    if not wrapper_dir or not directory.exists():
        status = "wrapper dir unavailable"
    elif not exists:
        status = "missing target"
    elif not profile.launcher_installed or profile.launcher_config_digest != config_digest(profile.config):
        status = "needs rebuild"
    else:
        status = "ok"
    return LauncherInfo(launcher_name, path, exists, on_path, status, command)


def generate_wrapper(cfg: RunConfig) -> str:
    """Generate a platform-appropriate wrapper that forwards CLI args."""
    wrapper_cfg = replace(cfg, cli_args="")
    argv = build_run_argv(wrapper_cfg, image_tag(wrapper_cfg))
    if sys.platform == "win32":
        return _generate_windows_cmd(argv)
    return _generate_posix_script(argv)


def generate_powershell_wrapper(cfg: RunConfig) -> str:
    """Generate a PowerShell companion wrapper that forwards CLI args."""
    wrapper_cfg = replace(cfg, cli_args="")
    argv = build_run_argv(wrapper_cfg, image_tag(wrapper_cfg))
    return _generate_powershell(argv)


def launcher_path(directory: Path, name: str) -> Path:
    """Return the launcher path for the current platform."""
    suffix = ".cmd" if sys.platform == "win32" else ""
    return directory / f"{safe_launcher_name(name)}{suffix}"


def safe_launcher_name(name: str) -> str:
    """Return a filesystem-friendly launcher name."""
    cleaned = "".join(char if char.isalnum() or char in "-_." else "-" for char in name.strip().lower())
    cleaned = cleaned.strip("-._")
    return cleaned or "safe-whale-tool"


def directory_on_path(directory: Path) -> bool:
    """Return whether directory appears on PATH."""
    try:
        target = directory.resolve()
    except OSError:
        return False
    for raw in os.environ.get("PATH", "").split(os.pathsep):
        if not raw:
            continue
        try:
            if Path(raw).resolve() == target:
                return True
        except OSError:
            continue
    return False


def _record_wrapper_asset(
    profile: Profile,
    command: str,
    launcher_name: str,
    path: Path,
    timestamp: datetime,
) -> None:
    upsert_managed_asset(
        ManagedAsset(
            asset_id=f"wrapper:{profile.name}:{command}",
            asset_type="wrapper",
            engine=profile.config.engine,
            name=launcher_name,
            location=str(path),
            source=profile.name,
            created_at=timestamp,
            last_used_at=timestamp,
            state="present",
        )
    )


def _generate_windows_cmd(argv: list[str]) -> str:
    command = subprocess.list2cmdline(argv)
    return "\n".join(
        [
            "@echo off",
            "REM Generated by safe-whale. Reinstall from the safe-whale Launchers tab after profile changes.",
            f"{command} %*",
            "exit /b %ERRORLEVEL%",
            "",
        ]
    )


def _generate_powershell(argv: list[str]) -> str:
    quoted = ", ".join(f"'{a.replace(chr(39), chr(39) * 2)}'" for a in argv)
    return "\n".join(
        [
            "# Generated by safe-whale. Reinstall from the safe-whale Launchers tab after profile changes.",
            f"$cmd = @({quoted})",
            "& $cmd[0] @($cmd[1..($cmd.Length-1)]) @args",
            "exit $LASTEXITCODE",
            "",
        ]
    )


def _generate_posix_script(argv: list[str]) -> str:
    command = shlex.join(argv)
    return "\n".join(
        [
            "#!/bin/sh",
            "# Generated by safe-whale. Reinstall from the safe-whale Launchers tab after profile changes.",
            f'exec {command} "$@"',
            "",
        ]
    )
