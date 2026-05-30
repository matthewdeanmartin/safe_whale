"""Tests for the swappable prompting layer."""

from __future__ import annotations

import sys
from collections.abc import Iterator

import pytest

from safe_whale.prompts import (
    IOPrompter,
    NoninteractivePrompter,
    get_prompter,
    should_prompt,
)


def _feed_input(monkeypatch: pytest.MonkeyPatch, answers: list[str]) -> None:
    iterator: Iterator[str] = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(iterator))


def test_io_confirm_uses_default_on_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    _feed_input(monkeypatch, [""])
    assert IOPrompter().confirm("ok?", default=True) is True


def test_io_confirm_parses_yes_no(monkeypatch: pytest.MonkeyPatch) -> None:
    _feed_input(monkeypatch, ["n"])
    assert IOPrompter().confirm("ok?", default=True) is False
    _feed_input(monkeypatch, ["yes"])
    assert IOPrompter().confirm("ok?", default=False) is True


def test_io_confirm_reprompts_on_garbage(monkeypatch: pytest.MonkeyPatch) -> None:
    _feed_input(monkeypatch, ["maybe", "y"])
    assert IOPrompter().confirm("ok?", default=False) is True


def test_io_choose_by_number_and_default(monkeypatch: pytest.MonkeyPatch) -> None:
    options = ["single_run_cli", "wrapper_cli", "tui_terminal"]
    _feed_input(monkeypatch, ["3"])
    assert IOPrompter().choose("kind?", options, default="single_run_cli") == "tui_terminal"
    _feed_input(monkeypatch, [""])
    assert IOPrompter().choose("kind?", options, default="wrapper_cli") == "wrapper_cli"


def test_noninteractive_returns_defaults() -> None:
    prompter = NoninteractivePrompter()
    assert prompter.confirm("q", default=True) is True
    assert prompter.choose("q", ["a", "b"], default="b") == "b"
    prompter.note("ignored")  # should not raise


def test_should_prompt_false_when_assume_yes() -> None:
    assert should_prompt(assume_yes=True) is False


def test_should_prompt_respects_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    assert should_prompt() is True
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    assert should_prompt() is False


def test_get_prompter_noninteractive_without_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    assert isinstance(get_prompter(), NoninteractivePrompter)
