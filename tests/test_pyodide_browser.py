"""Tests for browser-hosted Pyodide scaffolding."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from safe_whale.pyodide_browser import (
    DEMO_ARGS,
    DEMO_CODE,
    DEMO_PACKAGE,
    BrowserPyodideConfig,
    create_browser_pyodide_app,
    open_browser_pyodide_app,
)


def test_create_browser_pyodide_app_writes_terminal_scaffold(tmp_path: Path) -> None:
    app = create_browser_pyodide_app(
        BrowserPyodideConfig(
            code="print('hello')",
            package_spec=DEMO_PACKAGE,
            cli_args="--version",
            name="Rich demo",
        ),
        root=tmp_path,
    )

    html = app.index_path.read_text(encoding="utf-8")

    assert app.index_path.exists()
    assert app.directory.parent == tmp_path
    assert app.url.startswith("file:///")
    assert app.runtime == "pyodide"
    assert "Browser-hosted Pyodide runs Python in WebAssembly" in html
    assert "micropip.install(packages)" in html
    assert "SAFE_WHALE_ARGS" in html
    assert "print('hello')" in html
    assert DEMO_PACKAGE in html


def test_create_browser_pyscript_app_writes_package_demo(tmp_path: Path) -> None:
    app = create_browser_pyodide_app(
        BrowserPyodideConfig(
            code=DEMO_CODE,
            package_spec=DEMO_PACKAGE,
            cli_args=DEMO_ARGS,
            name="PyScript demo",
            runtime="pyscript",
        ),
        root=tmp_path,
    )

    html = app.index_path.read_text(encoding="utf-8")

    assert app.runtime == "pyscript"
    assert "https://pyscript.net/releases/2026.3.1/core.js" in html
    assert '<script type="py" target="output"' in html
    assert f"&quot;{DEMO_PACKAGE}&quot;" in html
    assert "snowballstemmer demo" in html
    assert "SAFE_WHALE_ARGS = [" in html


def test_open_browser_pyodide_app_uses_file_uri(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app = create_browser_pyodide_app(BrowserPyodideConfig(code="print(1)"), root=tmp_path)
    open_mock = Mock(return_value=True)
    monkeypatch.setattr("safe_whale.pyodide_browser.webbrowser.open", open_mock)

    assert open_browser_pyodide_app(app) is True
    open_mock.assert_called_once_with(app.url)
