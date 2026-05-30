"""Contextual help text for the notebook UI."""

from __future__ import annotations

HELP_TOPICS: dict[str, str] = {
    "Catalog": (
        "Catalog\n\n"
        "Search the bundled package index, choose a tool, inspect its metadata, "
        "then run it in the output panel or open it in a real terminal when it needs a TTY."
    ),
    "Profiles": (
        "Profiles\n\n"
        "Saved profiles are reusable run recipes. v2 groups them by usage pattern so one-shot "
        "tools, pipe filters, and terminal apps can expose the right default action."
    ),
    "Launchers": (
        "Launchers\n\n"
        "Phase 3 will create pipx-style wrapper commands here. Pick a wrapper directory, keep "
        "it on PATH, and safe-whale can launch container-backed tools from your shell."
    ),
    "Cleanup": (
        "Cleanup\n\n"
        "This tab is reserved for safe-whale-managed images, containers, Dockerfiles, caches, "
        "and wrappers. It should only touch assets safe-whale created or tracked."
    ),
    "Activity": (
        "Activity\n\n"
        "Run and build history appears here so recent commands and failures are visible without "
        "digging through JSON files."
    ),
    "Browser Python": (
        "Browser Python\n\n"
        "Generate a browser-hosted PyScript or direct Pyodide scaffold. The default demo installs "
        "snowballstemmer and runs it in the browser sandbox, but this is not a normal Linux "
        "container and cannot run Tkinter, TUI apps, native wheels, subprocess-heavy tools, "
        "or browser-hosted servers."
    ),
    "Search": (
        "Catalog Search\n\n"
        "Search matches package names, descriptions, tags, aliases, classifiers, and keywords. "
        "Exact mode only matches names and aliases."
    ),
    "Usage Pattern": (
        "Usage Patterns\n\n"
        "single_run_cli runs well in the output panel. wrapper_cli and pipe_filter prefer shell "
        "wrappers. tui_terminal needs a real terminal because curses-style apps cannot render "
        "correctly into a text output pipe."
    ),
    "Security": (
        "Security Options\n\n"
        "These flags harden docker run after the image has already been built. Read-only mode, "
        "non-root execution, no-new-privileges, dropped capabilities, and PID limits are safe "
        "defaults for most CLI tools."
    ),
    "Output": (
        "Output\n\n"
        "Build and run logs stream here for one-shot commands. Interactive terminal apps are "
        "built here first, then opened outside the GUI."
    ),
}


def topic_text(topic: str) -> str:
    """Return help text for a topic."""
    return HELP_TOPICS.get(topic, HELP_TOPICS["Catalog"])
