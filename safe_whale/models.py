"""Core data models for safe-whale."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

USAGE_PATTERNS = ("single_run_cli", "wrapper_cli", "pipe_filter", "tui_terminal")


def usage_pattern_for_interaction(interaction: str) -> str:
    """Return the default v2 usage pattern for a v1 interaction mode."""
    if interaction == "interactive":
        return "tui_terminal"
    if interaction == "pipe":
        return "pipe_filter"
    return "single_run_cli"


def preferred_action_for_usage_pattern(usage_pattern: str) -> str:
    """Return the default UI action for a usage pattern."""
    if usage_pattern == "single_run_cli":
        return "run_in_app"
    if usage_pattern == "tui_terminal":
        return "open_terminal"
    return "install_wrapper"


@dataclass
class CatalogEntry:
    """A known Python CLI tool that can be run in a container."""

    name: str
    entrypoint: str
    description: str
    apt_packages: list[str] = field(default_factory=list)
    example_args: str = ""
    ecosystem: str = "pypi"
    interaction: str = "immediate"  # "immediate" | "interactive" | "pipe"
    usage_pattern: str = ""
    tags: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    classifiers: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    project_urls: dict[str, str] = field(default_factory=dict)
    latest_version: str = ""
    release_date: str = ""
    requires_python: str = ""
    license: str = ""
    distribution_files: list[str] = field(default_factory=list)
    wrapper_recommended: bool = False
    metadata_status: str = "bundled"  # "bundled" | "cached" | "fetched" | "stale"

    def __post_init__(self) -> None:
        if not self.usage_pattern:
            self.usage_pattern = usage_pattern_for_interaction(self.interaction)
        if self.usage_pattern in {"wrapper_cli", "pipe_filter", "tui_terminal"}:
            self.wrapper_recommended = True

    def preferred_action(self) -> str:
        """Return the preferred action for this catalog entry."""
        return preferred_action_for_usage_pattern(self.usage_pattern)


@dataclass
class RunConfig:
    """Full configuration for a container run."""

    package_spec: str
    entrypoint: str
    cli_args: str = ""
    apt_packages: list[str] = field(default_factory=list)
    engine: str = "docker"
    interaction: str = "immediate"
    # Security knobs
    read_only: bool = True
    no_new_privs: bool = True
    cap_drop_all: bool = True
    tmpfs_tmp: bool = True
    block_network: bool = False
    non_root: bool = True
    limit_pids: bool = True
    memory_mb: int = 1024
    cpus: float = 1.0
    mount_dir: str = ""
    stdin_file: str = ""

    def display_name(self) -> str:
        """Return a short human-readable name for this config."""
        return self.package_spec or self.entrypoint or "(unnamed)"


@dataclass
class RunResult:
    """The outcome of a container run."""

    config: RunConfig
    timestamp: datetime
    exit_code: int | None
    stdout: str
    stderr: str
    command: str = ""
    image_ready: bool = False


@dataclass
class Profile:
    """A saved, named run configuration."""

    name: str
    config: RunConfig
    created_at: datetime = field(default_factory=datetime.now)
    notes: str = ""
    usage_pattern: str = ""
    tags: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    launcher_name: str = ""
    launcher_installed: bool = False
    launcher_updated_at: datetime | None = None
    launcher_config_digest: str = ""
    preferred_action: str = ""

    def __post_init__(self) -> None:
        if not self.usage_pattern:
            self.usage_pattern = usage_pattern_for_interaction(self.config.interaction)
        if not self.preferred_action:
            self.preferred_action = preferred_action_for_usage_pattern(self.usage_pattern)


@dataclass
class ManagedAsset:
    """A safe-whale-created artifact that can be shown in Cleanup."""

    asset_id: str
    asset_type: str
    engine: str
    name: str
    location: str
    source: str
    created_at: datetime = field(default_factory=datetime.now)
    last_used_at: datetime | None = None
    state: str = "tracked"
    safe_to_delete: bool = True
