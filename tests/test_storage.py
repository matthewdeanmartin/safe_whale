"""Tests for profile and history storage."""

from datetime import datetime
from pathlib import Path

import pytest

from safe_whale.models import Profile, RunConfig, RunResult
from safe_whale.storage import (
    _config_from_dict,
    _config_to_dict,
    append_history,
    delete_profile,
    dockerfile_path_for,
    load_managed_assets,
    load_history,
    load_profiles,
    save_profile,
    upsert_managed_asset,
)


def _cfg() -> RunConfig:
    return RunConfig(package_spec="httpie", entrypoint="http")


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect storage to a temp directory for each test."""
    import safe_whale.storage as storage_mod

    df_dir = tmp_path / "dockerfiles"
    df_dir.mkdir()
    monkeypatch.setattr(storage_mod, "_data_dir", lambda: tmp_path)
    monkeypatch.setattr(storage_mod, "dockerfiles_dir", lambda: df_dir)


class TestConfigRoundtrip:
    def test_roundtrip(self):
        cfg = _cfg()
        cfg.stdin_file = r"C:\tmp\input.txt"
        d = _config_to_dict(cfg)
        restored = _config_from_dict(d)
        assert restored.package_spec == cfg.package_spec
        assert restored.engine == cfg.engine
        assert restored.read_only == cfg.read_only
        assert restored.stdin_file == cfg.stdin_file


class TestProfiles:
    def test_empty_on_first_load(self):
        assert load_profiles() == []

    def test_save_and_load(self):
        p = Profile(name="test", config=_cfg())
        save_profile(p)
        loaded = load_profiles()
        assert len(loaded) == 1
        assert loaded[0].name == "test"

    def test_overwrite_by_name(self):
        save_profile(Profile(name="x", config=_cfg()))
        cfg2 = _cfg()
        cfg2.cli_args = "--version"
        save_profile(Profile(name="x", config=cfg2))
        loaded = load_profiles()
        assert len(loaded) == 1
        assert loaded[0].config.cli_args == "--version"

    def test_delete_profile(self):
        save_profile(Profile(name="del-me", config=_cfg()))
        delete_profile("del-me")
        assert load_profiles() == []

    def test_delete_nonexistent_is_noop(self):
        delete_profile("does-not-exist")

    def test_profile_dockerfiles_do_not_collide_when_names_sanitize_same(self):
        first = Profile(name="My Profile", config=_cfg())
        second_cfg = _cfg()
        second_cfg.cli_args = "--version"
        second = Profile(name="My_Profile", config=second_cfg)

        save_profile(first)
        save_profile(second)

        first_path = dockerfile_path_for(first.name)
        second_path = dockerfile_path_for(second.name)

        assert first_path != second_path
        assert first_path.exists()
        assert second_path.exists()
        assert "httpie" in first_path.read_text(encoding="utf-8")
        assert "httpie" in second_path.read_text(encoding="utf-8")

    def test_deleting_one_colliding_name_preserves_the_other_dockerfile(self):
        first = Profile(name="My Profile", config=_cfg())
        second = Profile(name="My_Profile", config=_cfg())

        save_profile(first)
        save_profile(second)
        second_path = dockerfile_path_for(second.name)

        delete_profile(first.name)

        assert load_profiles() == [second]
        assert second_path.exists()

    def test_overwriting_profile_marks_launcher_stale_when_config_changes(self):
        from safe_whale.storage import config_digest

        profile = Profile(name="x", config=_cfg(), launcher_name="x", launcher_installed=True)
        profile.launcher_config_digest = config_digest(profile.config)
        save_profile(profile)

        cfg2 = _cfg()
        cfg2.block_network = True
        save_profile(Profile(name="x", config=cfg2))

        loaded = load_profiles()[0]
        assert loaded.launcher_name == "x"
        assert loaded.launcher_installed is False


class TestHistory:
    def test_empty_on_first_load(self):
        assert load_history() == []

    def test_append_and_load(self):
        result = RunResult(
            config=_cfg(),
            timestamp=datetime.now(),
            exit_code=0,
            stdout="ok",
            stderr="",
            command="docker run ...",
        )
        append_history(result)
        records = load_history()
        assert len(records) == 1
        assert records[0]["exit_code"] == 0

    def test_history_newest_first(self):
        for i in range(3):
            r = RunResult(
                config=_cfg(),
                timestamp=datetime.now(),
                exit_code=i,
                stdout="",
                stderr="",
                command=f"cmd{i}",
            )
            append_history(r)
        records = load_history()
        assert records[0]["exit_code"] == 2


class TestManagedAssets:
    def test_save_profile_tracks_dockerfile_asset(self):
        save_profile(Profile(name="asset-profile", config=_cfg()))

        assets = load_managed_assets()

        assert any(asset.asset_id == "dockerfile:asset-profile" for asset in assets)

    def test_upsert_managed_asset_replaces_by_id(self):
        from safe_whale.models import ManagedAsset

        upsert_managed_asset(
            ManagedAsset(
                asset_id="image:docker:one",
                asset_type="image",
                engine="docker",
                name="one",
                location="one",
                source="one",
            )
        )
        upsert_managed_asset(
            ManagedAsset(
                asset_id="image:docker:one",
                asset_type="image",
                engine="docker",
                name="two",
                location="two",
                source="two",
            )
        )

        assets = load_managed_assets()
        assert len(assets) == 1
        assert assets[0].name == "two"
