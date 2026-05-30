"""Persistent storage: profiles, Dockerfiles, and run history."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path

from platformdirs import user_data_dir

from safe_whale.models import ManagedAsset, Profile, RunConfig, RunResult


def _data_dir() -> Path:
    override = os.environ.get("$SAFE_WHALE_DATA_DIR")
    if override:
        p = Path(override).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        return p
    p = Path(user_data_dir("safe-whale", "matthewdeanmartin"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def dockerfiles_dir() -> Path:
    """Directory where generated Dockerfiles are stored, one per profile."""
    p = _data_dir() / "dockerfiles"
    p.mkdir(parents=True, exist_ok=True)
    return p


def pyodide_apps_dir() -> Path:
    """Directory where generated browser-hosted Pyodide apps are stored."""
    p = _data_dir() / "pyodide_apps"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _profiles_path() -> Path:
    return _data_dir() / "profiles.json"


def _history_path() -> Path:
    return _data_dir() / "history.jsonl"


def _managed_assets_path() -> Path:
    return _data_dir() / "managed_assets.json"


# ── Serialization helpers ─────────────────────────────────────────────────────


def _config_to_dict(cfg: RunConfig) -> dict[str, object]:
    return {
        "package_spec": cfg.package_spec,
        "entrypoint": cfg.entrypoint,
        "cli_args": cfg.cli_args,
        "apt_packages": cfg.apt_packages,
        "engine": cfg.engine,
        "interaction": cfg.interaction,
        "read_only": cfg.read_only,
        "no_new_privs": cfg.no_new_privs,
        "cap_drop_all": cfg.cap_drop_all,
        "tmpfs_tmp": cfg.tmpfs_tmp,
        "block_network": cfg.block_network,
        "non_root": cfg.non_root,
        "limit_pids": cfg.limit_pids,
        "memory_mb": cfg.memory_mb,
        "cpus": cfg.cpus,
        "mount_dir": cfg.mount_dir,
        "stdin_file": cfg.stdin_file,
    }


def config_digest(cfg: RunConfig) -> str:
    """Return a stable digest for config fields that affect wrapper behavior."""
    data = _config_to_dict(cfg)
    data.pop("cli_args", None)
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha1(encoded, usedforsecurity=False).hexdigest()


def _config_from_dict(d: dict[str, object]) -> RunConfig:
    apt_packages = d.get("apt_packages", [])
    normalized_apt_packages = [str(pkg) for pkg in apt_packages] if isinstance(apt_packages, list) else []

    return RunConfig(
        package_spec=str(d.get("package_spec", "")),
        entrypoint=str(d.get("entrypoint", "")),
        cli_args=str(d.get("cli_args", "")),
        apt_packages=normalized_apt_packages,
        engine=str(d.get("engine", "docker")),
        interaction=str(d.get("interaction", "immediate")),
        read_only=bool(d.get("read_only", True)),
        no_new_privs=bool(d.get("no_new_privs", True)),
        cap_drop_all=bool(d.get("cap_drop_all", True)),
        tmpfs_tmp=bool(d.get("tmpfs_tmp", True)),
        block_network=bool(d.get("block_network", False)),
        non_root=bool(d.get("non_root", True)),
        limit_pids=bool(d.get("limit_pids", True)),
        memory_mb=_int_from_object(d.get("memory_mb"), 1024),
        cpus=_float_from_object(d.get("cpus"), 1.0),
        mount_dir=str(d.get("mount_dir", "")),
        stdin_file=str(d.get("stdin_file", "")),
    )


def _datetime_from_object(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _asset_to_dict(asset: ManagedAsset) -> dict[str, object]:
    return {
        "asset_id": asset.asset_id,
        "asset_type": asset.asset_type,
        "engine": asset.engine,
        "name": asset.name,
        "location": asset.location,
        "source": asset.source,
        "created_at": asset.created_at.isoformat(),
        "last_used_at": asset.last_used_at.isoformat() if asset.last_used_at else "",
        "state": asset.state,
        "safe_to_delete": asset.safe_to_delete,
    }


def _asset_from_dict(data: dict[str, object]) -> ManagedAsset:
    return ManagedAsset(
        asset_id=str(data.get("asset_id", "")),
        asset_type=str(data.get("asset_type", "")),
        engine=str(data.get("engine", "")),
        name=str(data.get("name", "")),
        location=str(data.get("location", "")),
        source=str(data.get("source", "")),
        created_at=_datetime_from_object(data.get("created_at")) or datetime.now(),
        last_used_at=_datetime_from_object(data.get("last_used_at")),
        state=str(data.get("state", "tracked")),
        safe_to_delete=bool(data.get("safe_to_delete", True)),
    )


def _int_from_object(value: object, default: int) -> int:
    if isinstance(value, (int, float, bool)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    try:
        return int(str(value)) if value is not None else default
    except (TypeError, ValueError):
        return default


def _float_from_object(value: object, default: float) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    try:
        return float(str(value)) if value is not None else default
    except (TypeError, ValueError):
        return default


def _legacy_dockerfile_path_for(profile_name: str) -> Path:
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in profile_name) or "profile"
    return dockerfiles_dir() / f"{safe_name}.Dockerfile"


def _dockerfile_filename(profile_name: str) -> str:
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in profile_name) or "profile"
    digest = hashlib.sha1(profile_name.encode("utf-8"), usedforsecurity=False).hexdigest()[:10]
    return f"{safe_name}-{digest}.Dockerfile"


# ── Profiles ──────────────────────────────────────────────────────────────────


def load_profiles() -> list[Profile]:
    """Load all saved profiles from disk."""
    path = _profiles_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        profiles = []
        for item in data:
            raw_tags = item.get("tags", [])
            tags = [str(tag) for tag in raw_tags] if isinstance(raw_tags, list) else []
            raw_commands = item.get("commands", [])
            commands = [str(cmd) for cmd in raw_commands] if isinstance(raw_commands, list) else []
            profiles.append(
                Profile(
                    name=str(item["name"]),
                    config=_config_from_dict(item["config"]),
                    created_at=datetime.fromisoformat(item.get("created_at", datetime.now().isoformat())),
                    notes=str(item.get("notes", "")),
                    usage_pattern=str(item.get("usage_pattern", "")),
                    tags=tags,
                    commands=commands,
                    launcher_name=str(item.get("launcher_name", "")),
                    launcher_installed=bool(item.get("launcher_installed", False)),
                    launcher_updated_at=_datetime_from_object(item.get("launcher_updated_at")),
                    launcher_config_digest=str(item.get("launcher_config_digest", "")),
                    preferred_action=str(item.get("preferred_action", "")),
                )
            )
        return profiles
    except (OSError, json.JSONDecodeError, KeyError, ValueError):
        return []


def save_profiles(profiles: list[Profile]) -> None:
    """Persist the profiles list to disk."""
    data = [
        {
            "name": p.name,
            "config": _config_to_dict(p.config),
            "created_at": p.created_at.isoformat(),
            "notes": p.notes,
            "usage_pattern": p.usage_pattern,
            "tags": p.tags,
            "commands": p.commands,
            "launcher_name": p.launcher_name,
            "launcher_installed": p.launcher_installed,
            "launcher_updated_at": p.launcher_updated_at.isoformat() if p.launcher_updated_at else "",
            "launcher_config_digest": p.launcher_config_digest,
            "preferred_action": p.preferred_action,
        }
        for p in profiles
    ]
    _profiles_path().write_text(json.dumps(data, indent=2), encoding="utf-8")


def save_profile(profile: Profile) -> None:
    """Add or update a profile by name, and write its Dockerfile."""
    from safe_whale.container import generate_dockerfile  # avoid circular at module level

    profiles = load_profiles()
    previous = next((p for p in profiles if p.name == profile.name), None)
    if previous and not profile.launcher_name:
        same_launcher_config = previous.launcher_config_digest == config_digest(profile.config)
        profile.launcher_name = previous.launcher_name
        profile.launcher_updated_at = previous.launcher_updated_at
        profile.launcher_config_digest = previous.launcher_config_digest
        profile.launcher_installed = previous.launcher_installed and same_launcher_config
    profiles = [p for p in profiles if p.name != profile.name]
    profiles.append(profile)
    save_profiles(profiles)

    # Write the Dockerfile so users can inspect / version-control it
    dockerfile_path = dockerfile_path_for(profile.name)
    dockerfile_path.write_text(generate_dockerfile(profile.config), encoding="utf-8")
    upsert_managed_asset(
        ManagedAsset(
            asset_id=f"dockerfile:{profile.name}",
            asset_type="dockerfile",
            engine="",
            name=dockerfile_path.name,
            location=str(dockerfile_path),
            source=profile.name,
            state="present",
        )
    )

    legacy_path = _legacy_dockerfile_path_for(profile.name)
    if legacy_path != dockerfile_path and legacy_path.exists():
        legacy_path.unlink()


def dockerfile_path_for(profile_name: str) -> Path:
    """Return the Dockerfile path for a saved profile."""
    return dockerfiles_dir() / _dockerfile_filename(profile_name)


def delete_profile(name: str) -> None:
    """Remove a profile by name and its Dockerfile if present."""
    profiles = [p for p in load_profiles() if p.name != name]
    save_profiles(profiles)
    for dockerfile_path in [dockerfile_path_for(name), _legacy_dockerfile_path_for(name)]:
        if dockerfile_path.exists():
            dockerfile_path.unlink()
    remove_managed_asset(f"dockerfile:{name}")


# ── History ───────────────────────────────────────────────────────────────────


def append_history(result: RunResult) -> None:
    """Append a run result to the history log."""
    record = {
        "timestamp": result.timestamp.isoformat(),
        "exit_code": result.exit_code,
        "command": result.command,
        "package_spec": result.config.package_spec,
        "engine": result.config.engine,
    }
    with _history_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def load_history(limit: int = 100) -> list[dict[str, object]]:
    """Return the most recent `limit` history entries, newest first."""
    path = _history_path()
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    records = []
    for line in reversed(lines[-limit * 2 :]):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
        if len(records) >= limit:
            break
    return records


# ── Managed assets ────────────────────────────────────────────────────────────


def load_managed_assets() -> list[ManagedAsset]:
    """Load safe-whale-managed asset inventory."""
    path = _managed_assets_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    assets: list[ManagedAsset] = []
    for item in data:
        if isinstance(item, dict):
            asset = _asset_from_dict(item)
            if asset.asset_id:
                assets.append(asset)
    return assets


def save_managed_assets(assets: list[ManagedAsset]) -> None:
    """Persist safe-whale-managed asset inventory."""
    _managed_assets_path().write_text(
        json.dumps([_asset_to_dict(asset) for asset in assets], indent=2),
        encoding="utf-8",
    )


def upsert_managed_asset(asset: ManagedAsset) -> None:
    """Add or replace an asset by id."""
    assets = [existing for existing in load_managed_assets() if existing.asset_id != asset.asset_id]
    assets.append(asset)
    save_managed_assets(assets)


def remove_managed_asset(asset_id: str) -> None:
    """Remove an asset from the inventory."""
    save_managed_assets([asset for asset in load_managed_assets() if asset.asset_id != asset_id])
