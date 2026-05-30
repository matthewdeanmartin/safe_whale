"""Tests for the safe-whale argparse CLI surface."""

from __future__ import annotations

from pathlib import Path

import pytest

from safe_whale.cli import build_parser, main
from safe_whale.storage import load_profiles


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import safe_whale.settings as settings_mod
    import safe_whale.storage as storage_mod

    monkeypatch.setattr(storage_mod, "_data_dir", lambda: tmp_path)
    monkeypatch.setattr(settings_mod, "_data_dir", lambda: tmp_path)


def test_parser_has_pipx_compatible_commands() -> None:
    parser = build_parser()
    help_text = parser.format_help()

    for command in [
        "install",
        "install-all",
        "inject",
        "upgrade",
        "upgrade-all",
        "uninstall",
        "uninstall-all",
        "reinstall",
        "reinstall-all",
        "list",
        "run",
        "runpip",
        "ensurepath",
        "environment",
        "completions",
        "help",
    ]:
        assert command in help_text


def test_help_unknown_topic_returns_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["help", "nope"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "unknown help topic" in captured.err


def test_run_dry_run_prints_container_plan(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["run", "--dry-run", "--engine", "docker", "ruff", "--", "--version"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "dry-run: run" in output
    assert "docker build" in output
    assert "docker run" in output
    assert "--version" in output
    assert "--network none" not in output


def test_run_dry_run_with_spec_uses_app_as_entrypoint(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["run", "--dry-run", "--engine", "docker", "--spec", "rich-cli", "rich", "--", "--help"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert 'RUN pip install --no-cache-dir --root-user-action=ignore "rich-cli"' in output
    assert 'ENTRYPOINT ["rich"]' in output
    assert "--help" in output


def test_global_dry_run_applies_to_subcommands(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["--dry-run", "run", "--engine", "docker", "ruff"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "dry-run: run" in output


def test_install_dry_run_does_not_save_profile(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["install", "--dry-run", "--engine", "docker", "ruff"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "dry-run: install" in output
    assert load_profiles() == []


def test_install_name_requires_single_package(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["install", "--name", "tools", "ruff", "black"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--name" in captured.err
    assert load_profiles() == []


def test_install_all_dry_run_accepts_safe_whale_options(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    metadata = tmp_path / "pipx-list.json"
    metadata.write_text(
        '{"venvs": {"ruff": {"metadata": {"main_package": {"package_or_url": "ruff"}}}}}',
        encoding="utf-8",
    )

    exit_code = main(["install-all", "--dry-run", "--engine", "docker", "--block-network", str(metadata)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "dry-run: install" in output
    assert "--network none" in output


def test_install_all_missing_file_returns_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["install-all", "missing.json"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "metadata file not found" in captured.err


def test_install_skip_build_saves_profile_and_wrapper(tmp_path: Path) -> None:
    wrapper_dir = tmp_path / "bin"

    exit_code = main(
        [
            "install",
            "--skip-build",
            "--engine",
            "docker",
            "--wrapper-dir",
            str(wrapper_dir),
            "ruff",
        ]
    )

    profiles = load_profiles()
    assert exit_code == 0
    assert len(profiles) == 1
    assert profiles[0].name == "ruff"
    assert profiles[0].launcher_installed is True
    assert any(wrapper_dir.iterdir())


def test_profiles_json_lists_installed_profile(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    wrapper_dir = tmp_path / "bin"
    assert main(["install", "--skip-build", "--wrapper-dir", str(wrapper_dir), "ruff"]) == 0

    exit_code = main(["profiles", "--json"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert '"name": "ruff"' in output
    assert '"package_spec": "ruff"' in output


def test_list_catalog_json(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["list", "--catalog", "--query", "ruff", "--json"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert '"name": "ruff"' in output
    assert '"entrypoint": "ruff"' in output


def test_uninstall_dry_run_preserves_profile(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    wrapper_dir = tmp_path / "bin"
    assert main(["install", "--skip-build", "--wrapper-dir", str(wrapper_dir), "ruff"]) == 0

    exit_code = main(["uninstall", "--dry-run", "ruff"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "would uninstall ruff" in output
    assert len(load_profiles()) == 1


def test_reinstall_dry_run_requires_installed_profile(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["reinstall", "--dry-run", "ruff"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "not installed" in captured.err


def test_reinstall_all_dry_run_with_no_profiles_is_ok(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["reinstall-all", "--dry-run"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "nothing installed" in output


def test_cleanup_dry_run_lists_requested_asset(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["cleanup", "--dry-run", "wrapper:ruff"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "would delete wrapper:ruff" in output


def test_install_discovers_multiple_commands_and_uninstall_removes_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wrapper_dir = tmp_path / "bin"

    from datetime import datetime

    import safe_whale.cli as cli_mod
    import safe_whale.discovery as discovery_mod
    import safe_whale.runner as runner_mod
    from safe_whale.discovery import DiscoveredCommand
    from safe_whale.models import RunResult

    def fake_build(config: object, **_kwargs: object) -> RunResult:
        return RunResult(
            config=config,  # type: ignore[arg-type]
            timestamp=datetime.now(),
            exit_code=0,
            stdout="",
            stderr="",
            image_ready=True,
        )

    def fake_discover(_cfg: object, **_kwargs: object) -> list[DiscoveredCommand]:
        return [
            DiscoveredCommand("http", "console_scripts", "httpie:main"),
            DiscoveredCommand("https", "console_scripts", "httpie:main"),
        ]

    monkeypatch.setattr(runner_mod, "run_container", fake_build)
    monkeypatch.setattr(cli_mod, "_detect_engines", lambda: ["docker"])
    monkeypatch.setattr(discovery_mod, "discover_entrypoints", fake_discover)

    exit_code = main(["install", "--wrapper-dir", str(wrapper_dir), "httpie"])
    assert exit_code == 0

    profiles = load_profiles()
    assert profiles[0].commands == ["http", "https"]
    names = {path.name for path in wrapper_dir.iterdir()}
    # Each command yields a .cmd + .ps1 on win32, or a bare file on posix.
    assert any(name.startswith("http") for name in names)
    assert any(name.startswith("https") for name in names)

    assert main(["uninstall", "httpie"]) == 0
    assert load_profiles() == []
    assert not any(wrapper_dir.iterdir())


def test_install_yes_does_not_prompt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wrapper_dir = tmp_path / "bin"

    def explode(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("install --yes must not call input()")

    monkeypatch.setattr("builtins.input", explode)
    # Even if a TTY is reported, --yes suppresses prompting.
    monkeypatch.setattr("sys.stdin.isatty", lambda: True, raising=False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True, raising=False)

    exit_code = main(["install", "--skip-build", "--yes", "--wrapper-dir", str(wrapper_dir), "ruff"])
    assert exit_code == 0


def test_unsupported_pipx_command_is_recognized(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["inject", "--dry-run", "ruff", "requests"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "recognized" in output


def test_unsupported_pipx_command_without_dry_run_fails(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["inject", "ruff", "requests"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "does not map" in captured.err
