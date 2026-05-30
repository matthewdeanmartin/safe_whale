"""Command-line entry point for safe-whale."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from datetime import datetime
import importlib.util
import json
import logging
import os
from pathlib import Path
import shlex
import sys
from typing import cast

from safe_whale.__about__ import __version__
from safe_whale.catalog import get_by_name, search
from safe_whale.container import base_project, build_display_command, generate_dockerfile, image_tag
from safe_whale.encoding import configure_utf8_stdio
from safe_whale.models import Profile, RunConfig

LOG = logging.getLogger(__name__)
Handler = Callable[[argparse.Namespace], int]
CommandParsers = dict[str, argparse.ArgumentParser]


def main(argv: Sequence[str] | None = None) -> int:
    """Parse CLI arguments and launch the requested safe-whale surface."""
    configure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    _normalize_common_args(args)
    _configure_logging(args)

    if getattr(args, "diagnostics", False):
        _run_diagnostics()
        return 0

    handler_obj = getattr(args, "handler", None)
    if handler_obj is None:
        return _launch_gui(args)
    handler = cast(Handler, handler_obj)
    return handler(args)


def build_parser() -> argparse.ArgumentParser:
    """Build the pipx-shaped argparse interface."""
    common = argparse.ArgumentParser(add_help=False)
    _add_common_options(common)

    parser = argparse.ArgumentParser(
        prog="safe-whale",
        description="Run Python CLI tools safely in Docker containers, with a pipx-like CLI.",
        parents=[common],
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="Print detected engines and storage location, then exit.",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    command_parsers: CommandParsers = {}

    run_parser = _add_subparser(subparsers, command_parsers, "run", common, "Build if needed, then run an app")
    _add_run_options(run_parser)
    run_parser.set_defaults(handler=_cmd_run)

    install_parser = _add_subparser(subparsers, command_parsers, "install", common, "Install package-backed wrapper(s)")
    _add_install_options(install_parser)
    install_parser.set_defaults(handler=_cmd_install)

    build_cmd = _add_subparser(subparsers, command_parsers, "build", common, "Build a package image")
    _add_build_options(build_cmd)
    build_cmd.set_defaults(handler=_cmd_build)

    list_parser = _add_subparser(subparsers, command_parsers, "list", common, "List installed profiles")
    list_parser.add_argument("--json", action="store_true", help="Output machine-readable JSON.")
    list_parser.add_argument("--short", action="store_true", help="Only show profile names.")
    list_parser.add_argument(
        "--catalog", action="store_true", help="List catalog entries instead of installed profiles."
    )
    list_parser.add_argument("--query", default="", help="Filter catalog entries or profiles by text.")
    list_parser.set_defaults(handler=_cmd_list)

    uninstall_parser = _add_subparser(
        subparsers, command_parsers, "uninstall", common, "Uninstall profile(s), wrappers, and images"
    )
    uninstall_parser.add_argument("packages", nargs="+", help="Installed profile or package name(s) to remove.")
    uninstall_parser.add_argument(
        "--keep-images", action="store_true", help="Remove profile/wrapper records but keep images."
    )
    uninstall_parser.set_defaults(handler=_cmd_uninstall)

    uninstall_all = _add_subparser(
        subparsers, command_parsers, "uninstall-all", common, "Uninstall every installed profile"
    )
    uninstall_all.add_argument(
        "--keep-images", action="store_true", help="Remove profile/wrapper records but keep images."
    )
    uninstall_all.set_defaults(handler=_cmd_uninstall_all)

    reinstall = _add_subparser(subparsers, command_parsers, "reinstall", common, "Rebuild installed profile image(s)")
    reinstall.add_argument("packages", nargs="+", help="Installed profile or package name(s) to rebuild.")
    reinstall.set_defaults(handler=_cmd_reinstall)

    reinstall_all = _add_subparser(
        subparsers, command_parsers, "reinstall-all", common, "Rebuild every installed profile image"
    )
    reinstall_all.set_defaults(handler=_cmd_reinstall_all)

    upgrade = _add_subparser(
        subparsers, command_parsers, "upgrade", common, "Rebuild profile image(s) from latest specs"
    )
    upgrade.add_argument("packages", nargs="+", help="Installed profile or package name(s) to rebuild.")
    upgrade.add_argument("--include-injected", action="store_true", help=argparse.SUPPRESS)
    upgrade.add_argument("--force", "-f", action="store_true", help="Force rebuild.")
    _add_ignored_pip_options(upgrade)
    upgrade.set_defaults(handler=_cmd_reinstall)

    upgrade_all = _add_subparser(subparsers, command_parsers, "upgrade-all", common, "Rebuild every profile image")
    upgrade_all.add_argument("--include-injected", action="store_true", help=argparse.SUPPRESS)
    _add_ignored_pip_options(upgrade_all)
    upgrade_all.set_defaults(handler=_cmd_reinstall_all)

    profiles = _add_subparser(subparsers, command_parsers, "profiles", common, "List saved safe-whale profiles")
    profiles.add_argument("--json", action="store_true", help="Output machine-readable JSON.")
    profiles.set_defaults(handler=_cmd_profiles)

    cleanup = _add_subparser(subparsers, command_parsers, "cleanup", common, "List or delete safe-whale managed assets")
    cleanup.add_argument("asset_ids", nargs="*", help="Specific asset ids to delete.")
    cleanup.add_argument("--all", action="store_true", help="Delete all safe-to-delete assets.")
    cleanup.set_defaults(handler=_cmd_cleanup)

    environment = _add_subparser(
        subparsers, command_parsers, "environment", common, "Print safe-whale environment variables and paths"
    )
    environment.set_defaults(handler=_cmd_environment)

    ensurepath = _add_subparser(subparsers, command_parsers, "ensurepath", common, "Show PATH setup for wrappers")
    ensurepath.set_defaults(handler=_cmd_ensurepath)

    completions = _add_subparser(subparsers, command_parsers, "completions", common, "Print shell completion guidance")
    completions.set_defaults(handler=_cmd_completions)

    install_all = _add_subparser(
        subparsers, command_parsers, "install-all", common, "Install packages from pipx list --json metadata"
    )
    install_all.add_argument("spec_metadata_file", help="Spec metadata file generated from pipx list --json.")
    _add_safe_whale_config_options(install_all)
    _add_install_behavior_options(install_all)
    install_all.set_defaults(handler=_cmd_install_all)

    for unsupported_name, help_text in {
        "inject": "Recognized for pipx compatibility; package injection is not a container concept yet",
        "uninject": "Recognized for pipx compatibility; package injection is not a container concept yet",
        "pin": "Recognized for pipx compatibility; pin by installing an explicit package spec",
        "unpin": "Recognized for pipx compatibility; pin by installing an explicit package spec",
        "runpip": "Recognized for pipx compatibility; safe-whale has no managed venv pip",
        "interpreter": "Recognized for pipx compatibility; safe-whale uses container Python images",
        "upgrade-shared": "Recognized for pipx compatibility; safe-whale has no shared venv libraries",
    }.items():
        unsupported = _add_subparser(subparsers, command_parsers, unsupported_name, common, help_text)
        unsupported.add_argument("args", nargs="*", help=argparse.SUPPRESS)
        unsupported.set_defaults(handler=_cmd_unsupported)

    help_parser = _add_subparser(subparsers, command_parsers, "help", common, "Show help for safe-whale or a command")
    help_parser.add_argument("topic", nargs="?", help="Optional command to show help for.")
    help_parser.set_defaults(handler=lambda args: _cmd_help(args, parser, command_parsers))

    return parser


def _add_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    command_parsers: CommandParsers,
    name: str,
    common: argparse.ArgumentParser,
    help_text: str,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(name, help=help_text, description=help_text, parents=[common])
    command_parsers[name] = parser
    return parser


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Show what safe-whale would do without changing files, building images, or running containers.",
    )
    parser.add_argument(
        "--log-level",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"],
        default=argparse.SUPPRESS,
        help="Set logging level explicitly.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="count",
        default=argparse.SUPPRESS,
        help="Increase logging verbosity; equivalent to --log-level INFO, then DEBUG.",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="count",
        default=argparse.SUPPRESS,
        help="Decrease logging verbosity; provided for pipx CLI compatibility.",
    )
    parser.add_argument(
        "--engine",
        metavar="ENGINE",
        help="Container engine to use (docker, podman, nerdctl, finch). Auto-detected if omitted.",
        default=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Do not record run history.",
    )


def _add_run_options(parser: argparse.ArgumentParser) -> None:
    _add_safe_whale_config_options(parser)
    _add_ignored_pip_options(parser)
    parser.add_argument("--spec", help="Package spec to install before running the app, pipx-style.")
    parser.add_argument("--args", dest="cli_args", default="", help="Arguments to pass to the app.")
    parser.add_argument("app", help="Package or app to run.")
    parser.add_argument("app_args", nargs=argparse.REMAINDER, help="Arguments forwarded to the app.")


def _add_install_options(parser: argparse.ArgumentParser) -> None:
    _add_safe_whale_config_options(parser)
    _add_install_behavior_options(parser)
    parser.add_argument("--suffix", default="", help="Suffix for profile and wrapper names.")
    parser.add_argument("package_spec", nargs="+", help="Package name(s) or pip installation spec(s).")


def _add_install_behavior_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--name", help="Profile name for a single installed package.")
    parser.add_argument("--wrapper-dir", help="Directory where command wrappers should be installed.")
    parser.add_argument("--launcher-name", help="Wrapper command name for a single installed package.")
    parser.add_argument("--no-wrapper", action="store_true", help="Save/build only; do not install a wrapper.")
    parser.add_argument(
        "--skip-build", action="store_true", help="Save/install wrapper without building the image first."
    )
    parser.add_argument("--force", "-f", action="store_true", help="Overwrite existing profile/wrapper metadata.")
    parser.add_argument(
        "--yes",
        "-y",
        dest="assume_yes",
        action="store_true",
        help="Do not prompt; accept defaults and any flags given.",
    )
    parser.add_argument(
        "--no-input",
        dest="assume_yes",
        action="store_true",
        help="Alias for --yes; never prompt interactively.",
    )
    _add_ignored_pip_options(parser)


def _add_build_options(parser: argparse.ArgumentParser) -> None:
    _add_safe_whale_config_options(parser)
    _add_ignored_pip_options(parser)
    parser.add_argument("--args", dest="cli_args", default="", help="Default arguments stored in the image config.")
    parser.add_argument("package_spec", help="Package name or pip installation spec.")


def _add_safe_whale_config_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--entrypoint", help="Executable inside the package image. Defaults to catalog entry/name.")
    parser.add_argument(
        "--apt", "--apt-package", action="append", default=[], help="APT package to install in the image."
    )
    parser.add_argument(
        "--interaction",
        choices=["immediate", "interactive", "pipe"],
        default="immediate",
        help="How the tool interacts with stdio.",
    )
    parser.add_argument("--stdin-file", default="", help="File to feed to stdin in pipe mode.")
    parser.add_argument("--mount", dest="mount_dir", default="", help="Bind mount as host_path:container_path[:ro|rw].")
    parser.add_argument("--memory", "--memory-mb", dest="memory_mb", type=int, default=1024, help="Memory limit in MB.")
    parser.add_argument("--cpus", type=float, default=1.0, help="CPU quota passed to the container engine.")
    parser.add_argument("--network", action="store_true", help="Allow runtime network access.")
    parser.add_argument("--block-network", action="store_true", help="Disable runtime network access.")
    parser.add_argument("--read-only", dest="read_only", action="store_true", default=True, help="Run read-only.")
    parser.add_argument(
        "--writable", dest="read_only", action="store_false", help="Allow writes to the container rootfs."
    )
    parser.add_argument("--non-root", dest="non_root", action="store_true", default=True, help="Run as uid 10001.")
    parser.add_argument("--root", dest="non_root", action="store_false", help="Run as root inside the container.")
    parser.add_argument(
        "--no-new-privs",
        dest="no_new_privs",
        action="store_true",
        default=True,
        help="Set no-new-privileges.",
    )
    parser.add_argument(
        "--allow-new-privs",
        dest="no_new_privs",
        action="store_false",
        help="Do not set no-new-privileges.",
    )
    parser.add_argument("--cap-drop-all", dest="cap_drop_all", action="store_true", default=True, help="Drop all caps.")
    parser.add_argument("--keep-caps", dest="cap_drop_all", action="store_false", help="Do not drop capabilities.")
    parser.add_argument("--tmpfs-tmp", dest="tmpfs_tmp", action="store_true", default=True, help="Mount tmpfs at /tmp.")
    parser.add_argument("--no-tmpfs-tmp", dest="tmpfs_tmp", action="store_false", help="Do not add tmpfs mounts.")
    parser.add_argument(
        "--limit-pids", dest="limit_pids", action="store_true", default=True, help="Limit process count."
    )
    parser.add_argument("--no-limit-pids", dest="limit_pids", action="store_false", help="Do not set a PID limit.")


def _add_ignored_pip_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--include-deps", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--include-apps", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--system-site-packages", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--python", help=argparse.SUPPRESS)
    parser.add_argument("--fetch-python", choices=["always", "missing", "never"], help=argparse.SUPPRESS)
    parser.add_argument("--fetch-missing-python", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--preinstall", action="append", default=[], help=argparse.SUPPRESS)
    parser.add_argument("--index-url", "-i", help=argparse.SUPPRESS)
    parser.add_argument("--editable", "-e", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--pip-args", default="", help=argparse.SUPPRESS)
    parser.add_argument("--backend", choices=["pip", "uv"], help=argparse.SUPPRESS)
    parser.add_argument("--global", dest="global_", action="store_true", help=argparse.SUPPRESS)


def _cmd_run(args: argparse.Namespace) -> int:
    package_spec = str(args.spec or args.app)
    app_args = _remainder_to_args(args.app_args)
    cli_args = _combine_cli_args(str(args.cli_args), app_args)
    cfg = _config_from_args(args, package_spec=package_spec, cli_args=cli_args, app_name=str(args.app))

    if args.dry_run:
        _print_plan("run", cfg)
        return 0

    from safe_whale.runner import run_container
    from safe_whale.storage import append_history

    result = run_container(cfg, on_output=lambda line: print(line, end=""))
    if not args.no_history:
        append_history(result)
    return int(result.exit_code or 0)


def _cmd_install(args: argparse.Namespace) -> int:
    package_specs = [str(item) for item in args.package_spec]
    if (args.name or args.launcher_name) and len(package_specs) != 1:
        print("Error: --name and --launcher-name can only be used with one package.", file=sys.stderr)
        return 2
    results = [_install_one(args, package_spec) for package_spec in package_specs]
    return 0 if all(code == 0 for code in results) else 1


def _cmd_install_all(args: argparse.Namespace) -> int:
    path = Path(str(args.spec_metadata_file))
    if not path.exists():
        print(f"Error: metadata file not found: {path}", file=sys.stderr)
        return 2
    try:
        specs = _package_specs_from_pipx_metadata(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Error: could not read metadata file: {exc}", file=sys.stderr)
        return 2
    if not specs:
        print("No package specs found in metadata file.")
        return 0
    args.package_spec = specs
    args.name = None
    args.launcher_name = None
    return _cmd_install(args)


def _install_one(args: argparse.Namespace, package_spec: str) -> int:
    profile_name = _profile_name_for(args, package_spec)
    cfg = _config_from_args(args, package_spec=package_spec, cli_args="")
    cfg = _interactive_setup(args, cfg)
    profile = Profile(name=profile_name, config=cfg, launcher_name=str(args.launcher_name or ""))
    wrapper_dir = _resolve_wrapper_dir(args)

    if args.dry_run:
        _print_plan("install", cfg, profile_name=profile_name, wrapper_dir=wrapper_dir)
        return 0

    from safe_whale.launchers import install_launchers
    from safe_whale.runner import run_container
    from safe_whale.storage import save_profile

    save_profile(profile)
    if not args.skip_build:
        result = run_container(cfg, on_output=lambda line: print(line, end=""), build_only=True)
        if result.exit_code != 0:
            return int(result.exit_code or 1)
        profile.commands = _discover_profile_commands(args, cfg)
    if not args.no_wrapper:
        if args.launcher_name and len(profile.commands) > 1:
            # An explicit single launcher name cannot disambiguate several commands.
            profile.commands = [str(args.launcher_name)]
        profile, infos = install_launchers(profile, str(wrapper_dir))
        save_profile(profile)
        names = ", ".join(sorted({info.name for info in infos}))
        print(f"installed {profile.name} wrapper(s) [{names}] at {wrapper_dir}")
    else:
        save_profile(profile)
        print(f"saved {profile.name}")
    return 0


def _interactive_setup(args: argparse.Namespace, cfg: RunConfig) -> RunConfig:
    """Ask the user about tool type and read-only filesystem when interactive.

    Skipped entirely under --yes/--no-input or when there is no TTY. Questions the
    user already answered via explicit flags are not asked again.
    """
    from safe_whale.models import (
        USAGE_PATTERNS,
        preferred_action_for_usage_pattern,
        usage_pattern_for_interaction,
    )
    from safe_whale.prompts import get_prompter, should_prompt

    from dataclasses import replace

    assume_yes = bool(getattr(args, "assume_yes", False))
    if args.dry_run or not should_prompt(assume_yes=assume_yes):
        return cfg
    prompter = get_prompter(assume_yes=assume_yes)

    if not _flag_was_given("--interaction"):
        current = usage_pattern_for_interaction(cfg.interaction)
        chosen = prompter.choose(
            "What kind of tool is this?",
            list(USAGE_PATTERNS),
            default=current,
        )
        cfg = replace(cfg, interaction=_interaction_for_usage_pattern(chosen))
        if chosen == "tui_terminal":
            prompter.note("TUI apps need a real terminal; safe-whale will install a wrapper to launch one.")
        prompter.note(f"Preferred action: {preferred_action_for_usage_pattern(chosen)}.")

    if not _read_only_flag_given():
        read_only = prompter.confirm(
            "Run with a read-only root filesystem? (safer; some tools need to write)",
            default=cfg.read_only,
        )
        cfg = replace(cfg, read_only=read_only)
        if not read_only:
            prompter.note("Filesystem will be writable inside the container — less isolated.")

    return cfg


def _interaction_for_usage_pattern(usage_pattern: str) -> str:
    if usage_pattern == "tui_terminal":
        return "interactive"
    if usage_pattern == "pipe_filter":
        return "pipe"
    return "immediate"


def _flag_was_given(flag: str) -> bool:
    return any(token == flag or token.startswith(flag + "=") for token in sys.argv[1:])


def _read_only_flag_given() -> bool:
    return any(token in {"--read-only", "--writable"} for token in sys.argv[1:])


def _discover_profile_commands(args: argparse.Namespace, cfg: RunConfig) -> list[str]:
    """Discover all console-script commands the package exposes (best-effort)."""
    from safe_whale.discovery import discover_entrypoints

    commands = [command.name for command in discover_entrypoints(cfg)]
    if not commands:
        return [str(args.launcher_name) if args.launcher_name else cfg.entrypoint]
    return commands


def _cmd_build(args: argparse.Namespace) -> int:
    cfg = _config_from_args(args, package_spec=str(args.package_spec), cli_args=str(args.cli_args))
    if args.dry_run:
        _print_plan("build", cfg)
        return 0

    from safe_whale.runner import run_container

    result = run_container(cfg, on_output=lambda line: print(line, end=""), build_only=True)
    return int(result.exit_code or 0)


def _cmd_list(args: argparse.Namespace) -> int:
    if args.catalog:
        entries = search(str(args.query or ""))
        if args.json:
            print(json.dumps([entry.__dict__ for entry in entries], indent=2, default=str))
        else:
            for entry in entries:
                print(entry.name if args.short else f"{entry.name}\t{entry.entrypoint}\t{entry.usage_pattern}")
        return 0
    return _cmd_profiles(args)


def _cmd_profiles(args: argparse.Namespace) -> int:
    from safe_whale.storage import load_profiles

    profiles = load_profiles()
    query = str(getattr(args, "query", "") or "").lower()
    if query:
        profiles = [profile for profile in profiles if query in profile.name.lower()]
    if args.json:
        print(json.dumps([_profile_to_dict(profile) for profile in profiles], indent=2))
        return 0
    if not profiles:
        print("nothing installed")
        return 0
    for profile in profiles:
        if getattr(args, "short", False):
            print(profile.name)
        else:
            launcher = f" wrapper={profile.launcher_name}" if profile.launcher_name else ""
            print(f"{profile.name}\t{profile.config.package_spec}\tentrypoint={profile.config.entrypoint}{launcher}")
    return 0


def _cmd_uninstall(args: argparse.Namespace) -> int:
    from safe_whale.storage import load_profiles

    profiles = load_profiles()
    targets = [_find_profile(profiles, str(package)) for package in args.packages]
    missing = [str(package) for package, profile in zip(args.packages, targets, strict=True) if profile is None]
    if missing:
        print(f"Error: not installed: {', '.join(missing)}", file=sys.stderr)
        return 1
    for profile in targets:
        if profile is not None:
            _uninstall_profile(profile, keep_images=bool(args.keep_images), dry_run=bool(args.dry_run))
    return 0


def _cmd_uninstall_all(args: argparse.Namespace) -> int:
    from safe_whale.storage import load_profiles

    profiles = load_profiles()
    if not profiles:
        print("nothing installed")
        return 0
    for profile in profiles:
        _uninstall_profile(profile, keep_images=bool(args.keep_images), dry_run=bool(args.dry_run))
    return 0


def _cmd_reinstall(args: argparse.Namespace) -> int:
    from safe_whale.storage import load_profiles

    profiles = load_profiles()
    targets = [_find_profile(profiles, str(package)) for package in args.packages]
    missing = [str(package) for package, profile in zip(args.packages, targets, strict=True) if profile is None]
    if missing:
        print(f"Error: not installed: {', '.join(missing)}", file=sys.stderr)
        return 1
    return _rebuild_profiles([profile for profile in targets if profile is not None], dry_run=bool(args.dry_run))


def _cmd_reinstall_all(args: argparse.Namespace) -> int:
    from safe_whale.storage import load_profiles

    profiles = load_profiles()
    if not profiles:
        print("nothing installed")
        return 0
    return _rebuild_profiles(profiles, dry_run=bool(args.dry_run))


def _cmd_cleanup(args: argparse.Namespace) -> int:
    from safe_whale.cleanup import delete_managed_asset, delete_unused_assets, list_cleanup_assets

    assets = list_cleanup_assets()
    if args.all:
        if args.dry_run:
            for asset in assets:
                if asset.safe_to_delete:
                    print(f"would delete {asset.asset_id}")
            return 0
        for asset_id, result in delete_unused_assets().items():
            print(f"{asset_id}: {result}")
        return 0
    if args.asset_ids:
        for asset_id in args.asset_ids:
            if args.dry_run:
                print(f"would delete {asset_id}")
            else:
                print(f"{asset_id}: {delete_managed_asset(str(asset_id))}")
        return 0
    for asset in assets:
        print(f"{asset.asset_id}\t{asset.asset_type}\t{asset.state}\t{asset.location}")
    return 0


def _cmd_environment(args: argparse.Namespace) -> int:
    from safe_whale.container import detect_engines
    from safe_whale.settings import load_settings
    from safe_whale.storage import _data_dir, dockerfiles_dir

    settings = load_settings()
    print(f"SAFE_WHALE_HOME={_data_dir()}")
    print(f"SAFE_WHALE_BIN_DIR={_resolve_wrapper_dir(args)}")
    print(f"configured_wrapper_dir={settings.wrapper_dir or '(not set)'}")
    print(f"dockerfiles_dir={dockerfiles_dir()}")
    print(f"detected_engines={','.join(detect_engines()) or '(none found)'}")
    return 0


def _cmd_ensurepath(args: argparse.Namespace) -> int:
    wrapper_dir = _resolve_wrapper_dir(args)
    on_path = _directory_on_path(wrapper_dir)
    if on_path:
        print(f"{wrapper_dir} is already on PATH")
        return 0
    print(f"{wrapper_dir} is not on PATH")
    if sys.platform == "win32":
        print(f'Add it with: setx PATH "%PATH%;{wrapper_dir}"')
    else:
        print(f'Add it with: export PATH="{wrapper_dir}:$PATH"')
    if args.dry_run:
        print("dry-run: PATH was not modified")
    return 0


def _cmd_completions(args: argparse.Namespace) -> int:
    del args
    print("Shell completion scripts are not bundled yet.")
    print("The argparse command surface is stable enough for generated completions in a future release.")
    return 0


def _cmd_help(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    command_parsers: CommandParsers,
) -> int:
    topic = str(args.topic or "")
    if not topic:
        parser.print_help()
        return 0
    command_parser = command_parsers.get(topic)
    if command_parser is None:
        print(f"Error: unknown help topic: {topic}", file=sys.stderr)
        return 2
    command_parser.print_help()
    return 0


def _cmd_unsupported(args: argparse.Namespace) -> int:
    command = str(args.command)
    if args.dry_run:
        print(f"dry-run: {command} is recognized but has no safe-whale action yet")
        return 0
    print(
        f"safe-whale recognizes '{command}' for pipx CLI compatibility, "
        "but this operation does not map to container-backed tools yet.",
        file=sys.stderr,
    )
    return 2


def _rebuild_profiles(profiles: list[Profile], dry_run: bool) -> int:
    if dry_run:
        for profile in profiles:
            _print_plan("rebuild", profile.config, profile_name=profile.name)
        return 0

    from safe_whale.runner import run_container

    exit_codes: list[int] = []
    for profile in profiles:
        print(f"rebuilding {profile.name}")
        result = run_container(profile.config, on_output=lambda line: print(line, end=""), build_only=True)
        exit_codes.append(int(result.exit_code or 0))
    return 0 if all(code == 0 for code in exit_codes) else 1


def _uninstall_profile(profile: Profile, keep_images: bool, dry_run: bool) -> None:
    from safe_whale.cleanup import delete_managed_asset
    from safe_whale.storage import delete_profile, load_managed_assets

    wrapper_prefix = f"wrapper:{profile.name}"
    wrapper_ids = sorted(
        asset.asset_id
        for asset in load_managed_assets()
        if asset.asset_id == wrapper_prefix or asset.asset_id.startswith(wrapper_prefix + ":")
    )
    asset_ids = [*wrapper_ids, f"dockerfile:{profile.name}"]
    if not keep_images:
        asset_ids.append(f"image:{profile.config.engine}:{image_tag(profile.config)}")
    if dry_run:
        print(f"would uninstall {profile.name}")
        for asset_id in asset_ids:
            print(f"would delete {asset_id}")
        return
    for asset_id in asset_ids:
        delete_managed_asset(asset_id)
    delete_profile(profile.name)
    print(f"uninstalled {profile.name}")


def _find_profile(profiles: list[Profile], value: str) -> Profile | None:
    normalized = value.lower()
    for profile in profiles:
        names = {
            profile.name.lower(),
            profile.config.package_spec.lower(),
            base_project(profile.config.package_spec).lower(),
            profile.config.entrypoint.lower(),
        }
        if normalized in names:
            return profile
    return None


def _config_from_args(
    args: argparse.Namespace,
    *,
    package_spec: str,
    cli_args: str,
    app_name: str = "",
) -> RunConfig:
    engines = _detect_engines()
    engine = str(args.engine or (engines[0] if engines else "docker"))
    entrypoint = str(args.entrypoint or _default_entrypoint(package_spec, app_name))
    block_network = bool(args.block_network)
    if args.network:
        block_network = False
    return RunConfig(
        package_spec=package_spec,
        entrypoint=entrypoint,
        cli_args=cli_args,
        apt_packages=[str(item) for item in args.apt],
        engine=engine,
        interaction=str(args.interaction),
        read_only=bool(args.read_only),
        no_new_privs=bool(args.no_new_privs),
        cap_drop_all=bool(args.cap_drop_all),
        tmpfs_tmp=bool(args.tmpfs_tmp),
        block_network=block_network,
        non_root=bool(args.non_root),
        limit_pids=bool(args.limit_pids),
        memory_mb=int(args.memory_mb),
        cpus=float(args.cpus),
        mount_dir=str(args.mount_dir),
        stdin_file=str(args.stdin_file),
    )


def _detect_engines() -> list[str]:
    from safe_whale.container import detect_engines

    return detect_engines()


def _default_entrypoint(package_spec: str, app_name: str = "") -> str:
    if app_name and package_spec != app_name:
        return app_name
    entry = get_by_name(base_project(package_spec))
    if entry is not None:
        return entry.entrypoint
    return base_project(package_spec) or package_spec


def _profile_name_for(args: argparse.Namespace, package_spec: str) -> str:
    base = str(args.name or base_project(package_spec) or package_spec)
    suffix = str(getattr(args, "suffix", "") or "")
    return f"{base}{suffix}"


def _resolve_wrapper_dir(args: argparse.Namespace) -> Path:
    from safe_whale.settings import load_settings

    explicit = getattr(args, "wrapper_dir", None)
    if explicit:
        return Path(str(explicit)).expanduser()
    env_dir = os.environ.get("SAFE_WHALE_BIN_DIR")
    if env_dir:
        return Path(env_dir).expanduser()
    settings_dir = load_settings().wrapper_dir
    if settings_dir:
        return Path(settings_dir).expanduser()
    if sys.platform == "win32":
        root = os.environ.get("LOCALAPPDATA")
        return (Path(root) if root else Path.home() / "AppData" / "Local") / "safe-whale" / "bin"
    return Path.home() / ".local" / "bin"


def _print_plan(
    action: str,
    cfg: RunConfig,
    *,
    profile_name: str = "",
    wrapper_dir: Path | None = None,
) -> None:
    tag = image_tag(cfg)
    print(f"dry-run: {action}")
    if profile_name:
        print(f"profile: {profile_name}")
    if wrapper_dir is not None:
        print(f"wrapper_dir: {wrapper_dir}")
    print("\n# Dockerfile")
    print(generate_dockerfile(cfg))
    print("# Build command")
    print(shlex.join([cfg.engine, "build", "-t", tag, "<build-context>"]))
    print("\n# Run command")
    print(build_display_command(cfg, tag))


def _combine_cli_args(option_args: str, remainder_args: str) -> str:
    parts = []
    if option_args:
        parts.append(option_args)
    if remainder_args:
        parts.append(remainder_args)
    return " ".join(parts)


def _remainder_to_args(values: list[str]) -> str:
    cleaned = list(values)
    if cleaned and cleaned[0] == "--":
        cleaned = cleaned[1:]
    return shlex.join(cleaned)


def _profile_to_dict(profile: Profile) -> dict[str, object]:
    return {
        "name": profile.name,
        "package_spec": profile.config.package_spec,
        "entrypoint": profile.config.entrypoint,
        "commands": profile.commands,
        "launcher_name": profile.launcher_name,
        "launcher_installed": profile.launcher_installed,
        "created_at": profile.created_at.isoformat(),
    }


def _package_specs_from_pipx_metadata(data: object) -> list[str]:
    if not isinstance(data, dict):
        return []
    venvs = data.get("venvs", {})
    if not isinstance(venvs, dict):
        return []
    specs: list[str] = []
    for name, raw in venvs.items():
        spec = str(name)
        if isinstance(raw, dict):
            metadata = raw.get("metadata", {})
            if isinstance(metadata, dict):
                main_package = metadata.get("main_package", {})
                if isinstance(main_package, dict):
                    spec = str(main_package.get("package_or_url") or main_package.get("package") or name)
        specs.append(spec)
    return specs


def _directory_on_path(directory: Path) -> bool:
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


def _configure_logging(args: argparse.Namespace) -> None:
    level_name = str(args.log_level or "")
    if not level_name:
        verbose = int(args.verbose or 0)
        quiet = int(args.quiet or 0)
        if verbose >= 2:
            level_name = "DEBUG"
        elif verbose == 1:
            level_name = "INFO"
        elif quiet >= 2:
            level_name = "CRITICAL"
        elif quiet == 1:
            level_name = "ERROR"
        else:
            level_name = "WARNING"
    logging.basicConfig(level=getattr(logging, level_name), format="%(levelname)s:%(name)s:%(message)s")
    LOG.debug("logging configured at %s", level_name)


def _normalize_common_args(args: argparse.Namespace) -> None:
    defaults: dict[str, object] = {
        "dry_run": False,
        "log_level": None,
        "verbose": 0,
        "quiet": 0,
        "engine": None,
        "no_history": False,
    }
    for name, value in defaults.items():
        if not hasattr(args, name):
            setattr(args, name, value)


def _launch_gui(args: argparse.Namespace) -> int:
    """Launch the Tkinter GUI when no subcommand is supplied."""
    if importlib.util.find_spec("tkinter") is None:
        print(
            "Error: Tkinter is not available in this Python installation.\n"
            "On Debian/Ubuntu: sudo apt-get install python3-tk\n"
            "On Fedora: sudo dnf install python3-tkinter\n"
            "On macOS: install Python from python.org (includes Tk)\n"
            "On Windows: re-run the Python installer and ensure 'tcl/tk' is checked.",
            file=sys.stderr,
        )
        return 1

    from safe_whale.ui.main_window import MainWindow  # pylint: disable=import-outside-toplevel

    app = MainWindow(
        preferred_engine=args.engine,
        no_history=args.no_history,
        dry_run=args.dry_run,
    )
    try:
        app.mainloop()
    except KeyboardInterrupt:
        app.destroy()
    return 0


def _run_diagnostics() -> None:
    from safe_whale.container import detect_engines  # pylint: disable=import-outside-toplevel
    from safe_whale.storage import _data_dir  # pylint: disable=import-outside-toplevel

    engines = detect_engines()
    print(f"safe-whale {__version__}")
    print(f"Detected engines: {', '.join(engines) if engines else '(none found)'}")
    print("Browser Python:   PyScript and Pyodide scaffolds")
    print(f"Data directory:   {_data_dir()}")
    print(f"Timestamp:        {datetime.now().isoformat(timespec='seconds')}")


if __name__ == "__main__":
    sys.exit(main())
