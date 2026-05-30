"""Discover the console-script commands a package exposes.

pipx reads a package's ``console_scripts`` / ``gui_scripts`` entry points with
``importlib.metadata`` against the installed distribution (see
``pipx/venv_inspect.py::get_apps_from_entry_points``) and exposes one launcher per
command. safe-whale installs into a container image rather than a host venv, so the
equivalent is to run the same ``importlib.metadata`` query *inside the built image*
and parse its JSON output.

Discovery is best-effort: any failure (no engine, build error, parse error) returns
an empty list so callers fall back to the single declared entrypoint.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import subprocess
import textwrap
from typing import Any

from safe_whale.container import base_project, build_run_argv, image_tag
from safe_whale.models import RunConfig
from safe_whale.storage import _data_dir

LOG = logging.getLogger(__name__)

# Runs inside the container. Reads the installed distribution's entry points and
# prints the console/gui scripts as JSON. Mirrors pipx's group filtering.
_PROBE_SCRIPT = textwrap.dedent("""
    import importlib.metadata as m, json, sys

    name = sys.argv[1]
    groups = {"console_scripts", "gui_scripts"}
    out = []
    try:
        dist = m.distribution(name)
    except Exception:
        print("[]")
        sys.exit(0)
    seen = set()
    for ep in dist.entry_points:
        if ep.group not in groups:
            continue
        if ep.name in seen:
            continue
        seen.add(ep.name)
        out.append({"name": ep.name, "group": ep.group, "value": ep.value})
    print(json.dumps(out))
    """).strip()


@dataclass(frozen=True)
class DiscoveredCommand:
    """A console/gui script a package installs."""

    name: str
    group: str
    target: str


def discover_entrypoints(
    cfg: RunConfig,
    *,
    timeout_seconds: float = 60.0,
    use_cache: bool = True,
) -> list[DiscoveredCommand]:
    """Return the console/gui scripts the package in ``cfg`` exposes.

    Builds the image if needed, then runs a probe container. Returns ``[]`` on any
    failure so callers can fall back to the single declared entrypoint.
    """
    tag = image_tag(cfg)
    if use_cache:
        cached = load_cached_entrypoints(tag)
        if cached is not None:
            return cached

    from safe_whale.runner import run_container  # avoid import cycle

    build = run_container(cfg, build_only=True)
    if not build.image_ready:
        LOG.debug("discovery skipped: image build failed for %s", tag)
        return []

    commands = _probe_image(cfg, tag, timeout_seconds=timeout_seconds)
    if use_cache and commands:
        save_cached_entrypoints(tag, commands)
    return commands


def _probe_image(cfg: RunConfig, tag: str, *, timeout_seconds: float) -> list[DiscoveredCommand]:
    argv = _probe_argv(cfg, tag)
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        LOG.debug("discovery probe failed to run: %s", exc)
        return []
    if proc.returncode != 0:
        LOG.debug("discovery probe exited %s: %s", proc.returncode, proc.stderr.strip())
        return []
    return _parse_probe_output(proc.stdout)


def _probe_argv(cfg: RunConfig, tag: str) -> list[str]:
    """Build a hardened ``run`` argv that overrides the entrypoint with python.

    Reuses build_run_argv for the hardening flags, then strips the trailing image
    tag/args and re-appends an ``--entrypoint python`` override plus the probe.
    Network is always blocked for the probe; no mounts or stdin are used.
    """
    probe_cfg = RunConfig(
        package_spec=cfg.package_spec,
        entrypoint=cfg.entrypoint,
        cli_args="",
        apt_packages=list(cfg.apt_packages),
        engine=cfg.engine,
        interaction="immediate",
        read_only=cfg.read_only,
        no_new_privs=cfg.no_new_privs,
        cap_drop_all=cfg.cap_drop_all,
        tmpfs_tmp=cfg.tmpfs_tmp,
        block_network=True,
        non_root=cfg.non_root,
        limit_pids=cfg.limit_pids,
        memory_mb=cfg.memory_mb,
        cpus=cfg.cpus,
        mount_dir="",
        stdin_file="",
    )
    hardened = build_run_argv(probe_cfg, tag)
    # hardened ends with [..., tag]; insert the entrypoint override before tag and
    # append the python probe command after it.
    tag_index = hardened.index(tag)
    flags = hardened[:tag_index]
    return [
        *flags,
        "--entrypoint",
        "python",
        tag,
        "-c",
        _PROBE_SCRIPT,
        base_project(cfg.package_spec) or cfg.package_spec,
    ]


def _parse_probe_output(stdout: str) -> list[DiscoveredCommand]:
    text = stdout.strip()
    if not text:
        return []
    # The probe prints a single JSON line; tolerate leading build/runtime noise by
    # scanning for the last line that parses as a JSON list.
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line.startswith("["):
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        return _commands_from_payload(data)
    return []


def _commands_from_payload(data: Any) -> list[DiscoveredCommand]:
    if not isinstance(data, list):
        return []
    commands: list[DiscoveredCommand] = []
    seen: set[str] = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        commands.append(
            DiscoveredCommand(
                name=name,
                group=str(item.get("group", "console_scripts")),
                target=str(item.get("value", "")),
            )
        )
    return sorted(commands, key=lambda command: command.name)


# ── Cache ──────────────────────────────────────────────────────────────────────


def entrypoints_cache_dir() -> Path:
    """Return the persistent entry-point discovery cache directory."""
    path = _data_dir() / "entrypoints"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cache_path(tag: str) -> Path:
    return entrypoints_cache_dir() / f"{tag}.json"


def load_cached_entrypoints(tag: str) -> list[DiscoveredCommand] | None:
    """Return cached commands for an image tag, or ``None`` if not cached."""
    path = _cache_path(tag)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return _commands_from_payload(data.get("commands"))


def save_cached_entrypoints(tag: str, commands: list[DiscoveredCommand]) -> None:
    """Persist discovered commands for an image tag."""
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "commands": [{"name": command.name, "group": command.group, "value": command.target} for command in commands],
    }
    _cache_path(tag).write_text(json.dumps(payload, indent=2), encoding="utf-8")
