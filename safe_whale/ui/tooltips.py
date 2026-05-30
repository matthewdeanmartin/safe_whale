"""Small Tkinter tooltip helper."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class Tooltip:
    """Attach a delayed tooltip to a widget."""

    def __init__(self, widget: tk.Widget, text: str, delay_ms: int = 500) -> None:
        self._widget = widget
        self._text = text
        self._delay_ms = delay_ms
        self._after_id: str | None = None
        self._tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event: tk.Event[tk.Widget]) -> None:
        self._cancel()
        self._after_id = self._widget.after(self._delay_ms, self._show)

    def _show(self) -> None:
        if self._tip is not None:
            return
        x = self._widget.winfo_rootx() + 16
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 8
        tip = tk.Toplevel(self._widget)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{x}+{y}")
        frame = ttk.Frame(tip, relief="solid", borderwidth=1)
        frame.pack()
        ttk.Label(frame, text=self._text, padding=(8, 4), wraplength=320).pack()
        self._tip = tip

    def _hide(self, _event: tk.Event[tk.Widget] | None = None) -> None:
        self._cancel()
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None

    def _cancel(self) -> None:
        if self._after_id is not None:
            self._widget.after_cancel(self._after_id)
            self._after_id = None


def add_tooltip(widget: tk.Widget, text: str) -> tk.Widget:
    """Attach a tooltip and return the widget for compact call sites."""
    Tooltip(widget, text)
    return widget
