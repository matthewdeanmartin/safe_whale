"""UTF-8 stdio configuration helper."""

from __future__ import annotations

import io
import sys


def configure_utf8_stdio() -> None:
    """Reconfigure stdout/stderr to UTF-8 with error replacement on Windows."""
    if sys.platform == "win32":
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    else:
        if isinstance(sys.stdout, io.TextIOWrapper):
            sys.stdout.reconfigure(errors="replace")
        if isinstance(sys.stderr, io.TextIOWrapper):
            sys.stderr.reconfigure(errors="replace")
