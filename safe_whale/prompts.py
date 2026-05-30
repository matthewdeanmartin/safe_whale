"""A tiny, swappable prompting layer for interactive CLI setup.

The CLI needs to ask the user a few questions during ``install`` (what kind of tool
this is, and — explicitly — whether the container should run with a read-only root
filesystem). This is intentionally the lightest possible wrapper around ``print`` /
``input`` so a prettier, accessible, or fully testable implementation can be swapped
in later behind the same ``Prompter`` protocol.

No GUI wiring lives here; the Tkinter app is unchanged.
"""

from __future__ import annotations

import sys
from typing import Protocol, runtime_checkable


@runtime_checkable
class Prompter(Protocol):
    """Minimal interactive question interface."""

    def confirm(self, question: str, *, default: bool) -> bool:
        """Ask a yes/no question; return the answer."""

    def choose(self, question: str, options: list[str], *, default: str) -> str:
        """Ask the user to pick one of ``options``; return the choice."""

    def note(self, message: str) -> None:
        """Show an informational message."""


class IOPrompter:
    """Default prompter built on ``print`` / ``input`` (single-shot)."""

    def confirm(self, question: str, *, default: bool) -> bool:
        suffix = " [Y/n] " if default else " [y/N] "
        while True:
            raw = input(question + suffix).strip().lower()
            if not raw:
                return default
            if raw in {"y", "yes"}:
                return True
            if raw in {"n", "no"}:
                return False
            print("Please answer 'y' or 'n'.")

    def choose(self, question: str, options: list[str], *, default: str) -> str:
        if not options:
            return default
        default_index = options.index(default) + 1 if default in options else 1
        print(question)
        for index, option in enumerate(options, start=1):
            marker = " (default)" if index == default_index else ""
            print(f"  {index}. {option}{marker}")
        while True:
            raw = input(f"Choose 1-{len(options)} [{default_index}]: ").strip()
            if not raw:
                return options[default_index - 1]
            if raw.isdigit() and 1 <= int(raw) <= len(options):
                return options[int(raw) - 1]
            if raw in options:
                return raw
            print(f"Please enter a number between 1 and {len(options)}.")

    def note(self, message: str) -> None:
        print(message)


class NoninteractivePrompter:
    """Prompter that never blocks; always returns the supplied default.

    Used when there is no TTY, when ``--yes`` / ``--no-input`` is passed, and in
    tests. ``note`` is suppressed by default to keep non-interactive output clean.
    """

    def __init__(self, *, echo_notes: bool = False) -> None:
        self._echo_notes = echo_notes

    def confirm(self, _question: str, *, default: bool) -> bool:
        return default

    def choose(self, _question: str, _options: list[str], *, default: str) -> str:
        return default

    def note(self, message: str) -> None:
        if self._echo_notes:
            print(message)


def should_prompt(*, assume_yes: bool = False) -> bool:
    """Return whether interactive prompting is appropriate.

    Requires both stdin and stdout to be a TTY, and ``--yes`` / ``--no-input`` not
    to have been requested. Mirrors how the CLI already branches on environment
    when deciding whether to launch the GUI.
    """
    if assume_yes:
        return False
    try:
        return bool(sys.stdin.isatty() and sys.stdout.isatty())
    except (ValueError, OSError):
        return False


def get_prompter(*, assume_yes: bool = False) -> Prompter:
    """Return the appropriate prompter for the current environment."""
    if should_prompt(assume_yes=assume_yes):
        return IOPrompter()
    return NoninteractivePrompter()
