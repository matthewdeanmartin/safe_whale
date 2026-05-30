"""Managed cleanup for safe-whale-owned assets."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import subprocess

from safe_whale.models import ManagedAsset
from safe_whale.storage import load_managed_assets, remove_managed_asset, save_managed_assets


def list_cleanup_assets() -> list[ManagedAsset]:
    """Return tracked assets with filesystem state refreshed."""
    refreshed = [_refresh_asset_state(asset) for asset in load_managed_assets()]
    save_managed_assets(refreshed)
    return sorted(refreshed, key=lambda asset: (asset.asset_type, asset.source, asset.name))


def delete_managed_asset(asset_id: str) -> str:
    """Delete one tracked safe-whale asset and remove it from inventory."""
    asset = next((item for item in load_managed_assets() if item.asset_id == asset_id), None)
    if asset is None:
        return "already removed"
    if not asset.safe_to_delete:
        return "not eligible"

    if asset.asset_type == "image":
        _delete_image(asset)
    elif asset.asset_type in {"wrapper", "dockerfile"}:
        _delete_file(asset)
    else:
        return "unsupported"

    remove_managed_asset(asset.asset_id)
    return "deleted"


def delete_unused_assets() -> dict[str, str]:
    """Delete all tracked assets currently marked safe to delete."""
    results: dict[str, str] = {}
    for asset in list_cleanup_assets():
        if asset.safe_to_delete:
            results[asset.asset_id] = delete_managed_asset(asset.asset_id)
    return results


def _refresh_asset_state(asset: ManagedAsset) -> ManagedAsset:
    if asset.asset_type in {"wrapper", "dockerfile"}:
        state = "present" if Path(asset.location).exists() else "missing"
        return replace(asset, state=state)
    if asset.asset_type == "image":
        state = "tracked"
        if asset.engine:
            try:
                probe = subprocess.run(
                    [asset.engine, "image", "inspect", asset.location],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                state = "present" if probe.returncode == 0 else "missing"
            except (FileNotFoundError, subprocess.TimeoutExpired):
                state = "missing"
        return replace(asset, state=state)
    return asset


def _delete_image(asset: ManagedAsset) -> None:
    if not asset.engine:
        return
    try:
        subprocess.run([asset.engine, "rmi", asset.location], capture_output=True, text=True, timeout=60, check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return


def _delete_file(asset: ManagedAsset) -> None:
    path = Path(asset.location)
    if path.exists() and path.is_file():
        path.unlink()
