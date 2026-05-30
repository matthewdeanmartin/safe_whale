"""Main application window for safe-whale."""

from __future__ import annotations

from contextlib import suppress
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, cast

from safe_whale.__about__ import __version__
from safe_whale.catalog import search
from safe_whale.cleanup import delete_managed_asset, delete_unused_assets, list_cleanup_assets
from safe_whale.container import build_display_command, detect_engines, generate_dockerfile, image_tag
from safe_whale.help import topic_text
from safe_whale.launchers import directory_on_path, install_launcher, launcher_info
from safe_whale.metadata import MetadataError, enrich_catalog_entry
from safe_whale.models import CatalogEntry, Profile, RunConfig, preferred_action_for_usage_pattern
from safe_whale.pyodide_browser import (
    DEMO_ARGS,
    DEMO_CODE,
    DEMO_PACKAGE,
    BrowserPyodideConfig,
    create_browser_pyodide_app,
    open_browser_pyodide_app,
)
from safe_whale.runner import run_container, run_in_terminal
from safe_whale.settings import AppSettings, load_settings, save_settings
from safe_whale.storage import (
    append_history,
    delete_profile,
    dockerfiles_dir,
    load_history,
    load_profiles,
    save_profile,
)
from safe_whale.ui.tooltips import add_tooltip


class MainWindow(tk.Tk):
    """Root Tkinter window."""

    def __init__(
        self,
        preferred_engine: str | None = None,
        no_history: bool = False,
        dry_run: bool = False,
    ) -> None:
        super().__init__()
        self.title(f"safe-whale {__version__}")
        self.minsize(1040, 680)
        self._no_history = no_history
        self._dry_run = dry_run
        self._running = False
        self._run_thread: threading.Thread | None = None
        self._run_proc: subprocess.Popen[str] | None = None
        self._built_tag: str | None = None
        self._settings: AppSettings = load_settings()
        self._selected_catalog_name = ""
        self._selected_profile_name = ""
        self._current_usage_pattern = "single_run_cli"

        self._engines = detect_engines()
        if preferred_engine and preferred_engine not in self._engines:
            self._engines.insert(0, preferred_engine)
        if not self._engines:
            self._engines = ["docker"]

        self._build_ui()
        self._refresh_catalog_panel()
        self._refresh_profiles_tab()
        self._refresh_activity_tab()
        self._restore_selected_tab()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # UI construction

    def _build_ui(self) -> None:
        self._help_visible_var = tk.BooleanVar(value=self._settings.help_panel_visible)
        self._build_menu()

        topbar = ttk.Frame(self)
        topbar.pack(fill="x", padx=8, pady=(6, 0))
        help_toggle = ttk.Checkbutton(
            topbar,
            text="Help",
            variable=self._help_visible_var,
            command=self._toggle_help_panel,
        )
        help_toggle.pack(side="right")
        add_tooltip(help_toggle, "Show or hide contextual help for the current tab or control.")

        root_pane = ttk.PanedWindow(self, orient="horizontal")
        root_pane.pack(fill="both", expand=True, padx=8, pady=6)

        self._notebook = ttk.Notebook(root_pane)
        root_pane.add(self._notebook, weight=1)
        self._notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        self._catalog_tab = ttk.Frame(self._notebook)
        self._profiles_tab = ttk.Frame(self._notebook)
        self._launchers_tab = ttk.Frame(self._notebook)
        self._cleanup_tab = ttk.Frame(self._notebook)
        self._pyodide_tab = ttk.Frame(self._notebook)
        self._activity_tab = ttk.Frame(self._notebook)
        for label, tab in [
            ("Catalog", self._catalog_tab),
            ("Profiles", self._profiles_tab),
            ("Launchers", self._launchers_tab),
            ("Cleanup", self._cleanup_tab),
            ("Browser Python", self._pyodide_tab),
            ("Activity", self._activity_tab),
        ]:
            self._notebook.add(tab, text=label)

        self._help_frame = ttk.Frame(root_pane, width=260)
        self._build_help_panel(self._help_frame)
        if self._settings.help_panel_visible:
            root_pane.add(self._help_frame, weight=0)
        self._root_pane = root_pane

        self._build_catalog_tab(self._catalog_tab)
        self._build_profiles_tab(self._profiles_tab)
        self._build_launchers_tab(self._launchers_tab)
        self._build_cleanup_tab(self._cleanup_tab)
        self._build_pyodide_tab(self._pyodide_tab)
        self._build_activity_tab(self._activity_tab)

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        tools_menu = tk.Menu(menubar, tearoff=False)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Open Dockerfiles Folder", command=self._open_dockerfiles_dir)
        tools_menu.add_command(label="Diagnostics", command=self._show_diagnostics)

        help_menu = tk.Menu(menubar, tearoff=False)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_checkbutton(
            label="Show Help Sidebar",
            variable=self._help_visible_var,
            command=self._toggle_help_panel,
        )
        help_menu.add_separator()
        help_menu.add_command(label="Documentation (ReadTheDocs)", command=self._open_readthedocs)

    def _build_help_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Help", font=("", 11, "bold")).pack(anchor="w", padx=8, pady=(8, 2))
        self._help_text = tk.Text(parent, width=34, wrap="word", height=10, state="disabled")
        self._help_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._set_help("Catalog")

    def _build_catalog_tab(self, parent: ttk.Frame) -> None:
        pane = ttk.PanedWindow(parent, orient="horizontal")
        pane.pack(fill="both", expand=True)

        left = ttk.Frame(pane, width=280)
        pane.add(left, weight=0)

        right = ttk.PanedWindow(pane, orient="vertical")
        pane.add(right, weight=1)
        config_frame = ttk.Frame(right)
        output_frame = ttk.Frame(right)
        right.add(config_frame, weight=1)
        right.add(output_frame, weight=1)

        self._build_catalog_panel(left)
        self._build_config_panel(config_frame)
        self._build_output_panel(output_frame)

    def _build_catalog_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Catalog", font=("", 11, "bold")).pack(anchor="w", padx=6, pady=(6, 2))

        self._filter_var = tk.StringVar()
        self._filter_var.trace_add("write", lambda *_: self._refresh_catalog_panel())
        search_entry = ttk.Entry(parent, textvariable=self._filter_var)
        search_entry.pack(fill="x", padx=6, pady=(0, 4))
        search_entry.bind("<FocusIn>", lambda _event: self._set_help("Search"))
        add_tooltip(search_entry, "Search by name, description, tag, alias, classifier, or keyword.")

        filter_row = ttk.Frame(parent)
        filter_row.pack(fill="x", padx=6, pady=(0, 4))
        self._usage_filter_var = tk.StringVar(value="all")
        usage_filter = ttk.Combobox(
            filter_row,
            textvariable=self._usage_filter_var,
            values=["all", "single_run_cli", "wrapper_cli", "pipe_filter", "tui_terminal"],
            state="readonly",
            width=18,
        )
        usage_filter.pack(side="left", fill="x", expand=True)
        usage_filter.bind("<<ComboboxSelected>>", lambda _event: self._refresh_catalog_panel())
        usage_filter.bind("<FocusIn>", lambda _event: self._set_help("Usage Pattern"))
        add_tooltip(usage_filter, "Filter catalog entries by their v2 usage pattern.")
        self._exact_search_var = tk.BooleanVar(value=self._settings.preferred_search_mode == "exact")
        exact_check = ttk.Checkbutton(
            filter_row,
            text="Exact",
            variable=self._exact_search_var,
            command=self._refresh_catalog_panel,
        )
        exact_check.pack(side="left", padx=(6, 0))
        add_tooltip(exact_check, "Exact mode matches only package names and aliases.")

        profiles_row = ttk.Frame(parent)
        profiles_row.pack(fill="x", padx=6, pady=(0, 4))
        self._profiles_only_var = tk.BooleanVar(value=False)
        profiles_check = ttk.Checkbutton(
            profiles_row,
            text="My Profiles only",
            variable=self._profiles_only_var,
            command=self._refresh_catalog_panel,
        )
        profiles_check.pack(side="left")
        add_tooltip(profiles_check, "Show only your saved profiles, hiding catalog entries.")

        list_frame = ttk.Frame(parent)
        list_frame.pack(fill="both", expand=True, padx=6)
        sb = ttk.Scrollbar(list_frame, orient="vertical")
        self._left_list = tk.Listbox(list_frame, yscrollcommand=sb.set, selectmode="browse", activestyle="none")
        sb.config(command=self._left_list.yview)
        self._left_list.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self._left_list.bind("<<ListboxSelect>>", self._on_left_select)
        self._left_list.bind("<Double-Button-1>", lambda _event: self._on_run())
        self._left_items: list[CatalogEntry | Profile | None] = []
        add_tooltip(self._left_list, "Select a catalog entry or saved profile to load its run recipe.")

        ttk.Label(parent, text="Details", font=("", 10, "bold")).pack(anchor="w", padx=6, pady=(6, 0))
        self._metadata = tk.Text(parent, height=10, wrap="word", state="disabled")
        self._metadata.pack(fill="x", padx=6, pady=(2, 4))
        metadata_btn = ttk.Button(parent, text="Refresh PyPI Metadata", command=self._refresh_selected_metadata)
        metadata_btn.pack(fill="x", padx=6, pady=(0, 4))
        add_tooltip(metadata_btn, "Fetch fresh PyPI JSON metadata for the selected catalog entry.")

        btn_row = ttk.Frame(parent)
        btn_row.pack(fill="x", padx=6, pady=(2, 6))
        custom_btn = ttk.Button(btn_row, text="+ Custom", command=self._use_custom)
        custom_btn.pack(side="left", expand=True, fill="x", padx=(0, 2))
        add_tooltip(custom_btn, "Clear the catalog selection and enter a custom package spec.")
        delete_btn = ttk.Button(btn_row, text="Delete Profile", command=self._delete_selected_profile)
        delete_btn.pack(side="left", expand=True, fill="x", padx=(2, 0))
        add_tooltip(delete_btn, "Delete the selected saved profile.")

    def _build_config_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Configuration", font=("", 11, "bold")).pack(anchor="w", padx=8, pady=(6, 2))

        grid = ttk.Frame(parent)
        grid.pack(fill="x", padx=8, pady=4)
        grid.columnconfigure(1, weight=1)
        grid.columnconfigure(3, weight=1)

        self._engine_var = tk.StringVar(value=self._engines[0])
        ttk.Label(grid, text="Engine:").grid(row=0, column=0, sticky="w", padx=(0, 4), pady=2)
        engine_combo = ttk.Combobox(
            grid, textvariable=self._engine_var, values=self._engines, width=10, state="readonly"
        )
        engine_combo.grid(row=0, column=1, sticky="w", pady=2)
        add_tooltip(engine_combo, "Container engine used for Docker/Podman builds and runs.")

        self._pkg_spec_var = tk.StringVar()
        ttk.Label(grid, text="Package spec:").grid(row=1, column=0, sticky="w", padx=(0, 4), pady=2)
        pkg_entry = ttk.Entry(grid, textvariable=self._pkg_spec_var)
        pkg_entry.grid(row=1, column=1, sticky="ew", pady=2)
        add_tooltip(pkg_entry, "Pip package spec to install in the generated image.")

        self._entrypoint_var = tk.StringVar()
        ttk.Label(grid, text="Entrypoint:").grid(row=1, column=2, sticky="w", padx=(8, 4), pady=2)
        entry_entry = ttk.Entry(grid, textvariable=self._entrypoint_var)
        entry_entry.grid(row=1, column=3, sticky="ew", pady=2)
        add_tooltip(entry_entry, "Command baked into the container image ENTRYPOINT.")

        self._cli_args_var = tk.StringVar()
        ttk.Label(grid, text="CLI args:").grid(row=2, column=0, sticky="w", padx=(0, 4), pady=2)
        args_entry = ttk.Entry(grid, textvariable=self._cli_args_var)
        args_entry.grid(row=2, column=1, sticky="ew", pady=2)
        add_tooltip(args_entry, "Arguments forwarded to the tool when it runs.")

        self._apt_var = tk.StringVar()
        ttk.Label(grid, text="Apt packages:").grid(row=2, column=2, sticky="w", padx=(8, 4), pady=2)
        apt_entry = ttk.Entry(grid, textvariable=self._apt_var)
        apt_entry.grid(row=2, column=3, sticky="ew", pady=2)
        add_tooltip(apt_entry, "Debian packages installed during docker build, such as ffmpeg.")

        self._mount_var = tk.StringVar()
        ttk.Label(grid, text="Mount:").grid(row=3, column=0, sticky="w", padx=(0, 4), pady=2)
        mount_entry = ttk.Entry(grid, textvariable=self._mount_var)
        mount_entry.grid(row=3, column=1, sticky="ew", pady=2)
        add_tooltip(mount_entry, "Optional Docker volume mount, for example C:\\work:/work.")

        mem_cpu = ttk.Frame(grid)
        mem_cpu.grid(row=3, column=2, columnspan=2, sticky="ew", padx=(8, 0), pady=2)
        ttk.Label(mem_cpu, text="Mem (MB):").pack(side="left")
        self._mem_var = tk.StringVar(value="1024")
        mem_entry = ttk.Entry(mem_cpu, textvariable=self._mem_var, width=7)
        mem_entry.pack(side="left", padx=(2, 8))
        ttk.Label(mem_cpu, text="CPU:").pack(side="left")
        self._cpu_var = tk.StringVar(value="1.0")
        cpu_entry = ttk.Entry(mem_cpu, textvariable=self._cpu_var, width=5)
        cpu_entry.pack(side="left", padx=2)
        add_tooltip(mem_entry, "Container memory limit in megabytes.")
        add_tooltip(cpu_entry, "Container CPU limit passed to docker run.")

        self._stdin_file_var = tk.StringVar()
        ttk.Label(grid, text="Input file:").grid(row=4, column=0, sticky="w", padx=(0, 4), pady=2)
        stdin_frame = ttk.Frame(grid)
        stdin_frame.grid(row=4, column=1, columnspan=3, sticky="ew", pady=2)
        stdin_frame.columnconfigure(0, weight=1)
        stdin_entry = ttk.Entry(stdin_frame, textvariable=self._stdin_file_var)
        stdin_entry.grid(row=0, column=0, sticky="ew")
        browse_btn = ttk.Button(stdin_frame, text="Browse...", command=self._choose_stdin_file)
        browse_btn.grid(row=0, column=1, padx=(6, 0))
        add_tooltip(stdin_entry, "File to pipe to stdin when using pipe mode.")
        add_tooltip(browse_btn, "Choose an input file for pipe mode.")

        interaction_frame = ttk.Frame(parent)
        interaction_frame.pack(fill="x", padx=8, pady=(2, 0))
        ttk.Label(interaction_frame, text="Interaction:").pack(side="left")
        self._interaction_var = tk.StringVar(value="immediate")
        self._immediate_radio = ttk.Radiobutton(
            interaction_frame, text="Immediate", variable=self._interaction_var, value="immediate"
        )
        self._immediate_radio.pack(side="left", padx=4)
        self._interactive_radio = ttk.Radiobutton(
            interaction_frame, text="Interactive app (TTY)", variable=self._interaction_var, value="interactive"
        )
        self._interactive_radio.pack(side="left", padx=4)
        self._pipe_radio = ttk.Radiobutton(
            interaction_frame, text="Pipe file to stdin", variable=self._interaction_var, value="pipe"
        )
        self._pipe_radio.pack(side="left", padx=4)
        for widget in (self._immediate_radio, self._interactive_radio, self._pipe_radio):
            widget.bind("<FocusIn>", lambda _event: self._set_help("Usage Pattern"))
            add_tooltip(widget, "Controls how safe-whale launches the tool.")
        self._stdin_file_var.trace_add("write", lambda *_: self._sync_interaction_controls())
        self._interaction_var.trace_add("write", lambda *_: self._sync_interaction_controls())
        self._sync_interaction_controls()

        sec_frame = ttk.LabelFrame(parent, text="Security")
        sec_frame.pack(fill="x", padx=8, pady=6)
        sec_frame.bind("<FocusIn>", lambda _event: self._set_help("Security"))

        self._read_only_var = tk.BooleanVar(value=True)
        self._no_new_privs_var = tk.BooleanVar(value=True)
        self._cap_drop_var = tk.BooleanVar(value=True)
        self._tmpfs_var = tk.BooleanVar(value=True)
        self._block_net_var = tk.BooleanVar(value=False)
        self._non_root_var = tk.BooleanVar(value=True)
        self._limit_pids_var = tk.BooleanVar(value=True)

        checks = [
            (self._read_only_var, "Read-only FS", "Run the finished image with a read-only root filesystem."),
            (self._no_new_privs_var, "No-new-privileges", "Prevent privilege escalation inside the container."),
            (self._cap_drop_var, "Cap-drop ALL", "Drop Linux capabilities at runtime."),
            (self._tmpfs_var, "tmpfs /tmp", "Mount writable temporary directories even with read-only FS."),
            (self._block_net_var, "Block network", "Run with Docker network access disabled."),
            (self._non_root_var, "Non-root UID", "Run as UID 10001 after package installation is complete."),
            (self._limit_pids_var, "Limit PIDs (256)", "Limit process count inside the container."),
        ]
        for i, (var, label, tip) in enumerate(checks):
            check = ttk.Checkbutton(sec_frame, text=label, variable=var)
            check.grid(row=i // 4, column=i % 4, sticky="w", padx=8, pady=2)
            check.bind("<FocusIn>", lambda _event: self._set_help("Security"))
            add_tooltip(check, tip)

        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill="x", padx=8, pady=(4, 8))
        save_btn = ttk.Button(btn_frame, text="Save as Profile", command=self._save_profile)
        save_btn.pack(side="left", padx=4)
        self._run_btn = ttk.Button(btn_frame, text="Run", command=self._on_run)
        self._run_btn.pack(side="left", padx=4)
        self._term_btn = ttk.Button(btn_frame, text="Run in Terminal", command=self._on_run_terminal)
        self._term_btn.pack(side="left", padx=4)
        self._install_wrapper_btn = ttk.Button(btn_frame, text="Install Wrapper", command=self._install_current_wrapper)
        self._install_wrapper_btn.pack(side="left", padx=4)
        self._cancel_btn = ttk.Button(btn_frame, text="Cancel", command=self._on_cancel, state="disabled")
        self._cancel_btn.pack(side="left", padx=4)
        dockerfile_btn = ttk.Button(btn_frame, text="Show Dockerfile", command=self._show_dockerfile)
        dockerfile_btn.pack(side="left", padx=4)
        add_tooltip(save_btn, "Save the current configuration as a reusable profile.")
        add_tooltip(self._run_btn, "Build and run one-shot or pipe commands in the output panel.")
        add_tooltip(self._term_btn, "Build if needed, then open the tool in a system terminal.")
        add_tooltip(self._install_wrapper_btn, "Build the image and install or update a shell wrapper.")
        add_tooltip(self._cancel_btn, "Kill the current build or run process.")
        add_tooltip(dockerfile_btn, "Preview the generated Dockerfile and docker run command.")

    def _build_output_panel(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent)
        header.pack(fill="x", padx=8, pady=(4, 0))
        self._output_label = ttk.Label(header, text="Output", font=("", 11, "bold"))
        self._output_label.pack(side="left")
        clear_btn = ttk.Button(header, text="Clear", command=self._clear_output)
        clear_btn.pack(side="right")
        add_tooltip(clear_btn, "Clear the output panel.")
        self._back_btn = ttk.Button(header, text="Back to Output", command=self._restore_output)
        self._saved_output = ""

        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True, padx=8, pady=(2, 8))
        xscroll = ttk.Scrollbar(frame, orient="horizontal")
        yscroll = ttk.Scrollbar(frame, orient="vertical")
        self._output = tk.Text(
            frame,
            state="disabled",
            wrap="none",
            font=("Courier", 10),
            xscrollcommand=xscroll.set,
            yscrollcommand=yscroll.set,
        )
        self._output.bind("<FocusIn>", lambda _event: self._set_help("Output"))
        xscroll.config(command=self._output.xview)
        yscroll.config(command=self._output.yview)
        self._output.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

    def _build_profiles_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        ttk.Label(parent, text="Profiles", font=("", 11, "bold")).grid(row=0, column=0, sticky="w", padx=8, pady=8)
        columns = ("name", "usage", "action", "package")
        self._profiles_tree = ttk.Treeview(parent, columns=columns, show="headings", selectmode="browse")
        for col, heading, width in [
            ("name", "Name", 180),
            ("usage", "Usage pattern", 140),
            ("action", "Preferred action", 130),
            ("package", "Package", 220),
        ]:
            self._profiles_tree.heading(col, text=heading)
            self._profiles_tree.column(col, width=width, anchor="w")
        self._profiles_tree.grid(row=1, column=0, sticky="nsew", padx=8)
        self._profiles_tree.bind("<<TreeviewSelect>>", self._on_profile_tree_select)
        self._profiles_tree.bind("<Double-Button-1>", lambda _event: self._load_selected_profile_in_catalog())
        add_tooltip(
            self._profiles_tree, "Select a profile to inspect it. Double-click or use Edit in Catalog to load it."
        )

        btns = ttk.Frame(parent)
        btns.grid(row=2, column=0, sticky="ew", padx=8, pady=8)
        ttk.Button(btns, text="Refresh", command=self._refresh_profiles_tab).pack(side="left")
        ttk.Button(btns, text="Edit in Catalog", command=self._load_selected_profile_in_catalog).pack(
            side="left", padx=6
        )
        ttk.Button(btns, text="Run Selected", command=self._run_selected_profile).pack(side="left")
        ttk.Button(btns, text="Delete Selected", command=self._delete_profile_from_tab).pack(side="left", padx=6)

    def _build_launchers_tab(self, parent: ttk.Frame) -> None:
        parent.rowconfigure(4, weight=1)
        parent.columnconfigure(1, weight=1)
        ttk.Label(parent, text="Wrapper directory", font=("", 11, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=8, pady=(8, 4)
        )
        self._wrapper_dir_var = tk.StringVar(value=self._settings.wrapper_dir)
        wrapper_entry = ttk.Entry(parent, textvariable=self._wrapper_dir_var)
        wrapper_entry.grid(row=1, column=0, columnspan=2, sticky="ew", padx=(8, 4), pady=2)
        browse = ttk.Button(parent, text="Browse...", command=self._choose_wrapper_dir)
        browse.grid(row=1, column=2, sticky="ew", padx=(4, 8), pady=2)
        self._wrapper_status_var = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self._wrapper_status_var).grid(
            row=2, column=0, columnspan=3, sticky="w", padx=8, pady=(2, 10)
        )
        action_row = ttk.Frame(parent)
        action_row.grid(row=3, column=0, columnspan=3, sticky="ew", padx=8, pady=(0, 6))
        ttk.Button(action_row, text="Install/Update Selected Profile", command=self._install_selected_launcher).pack(
            side="left"
        )
        ttk.Button(action_row, text="Refresh", command=self._refresh_launchers_tab).pack(side="left", padx=6)
        columns = ("name", "profile", "usage", "path", "status")
        self._launchers_tree = ttk.Treeview(parent, columns=columns, show="headings", selectmode="browse")
        for col, heading, width in [
            ("name", "Wrapper", 120),
            ("profile", "Profile", 160),
            ("usage", "Usage pattern", 140),
            ("path", "Path", 320),
            ("status", "Status", 150),
        ]:
            self._launchers_tree.heading(col, text=heading)
            self._launchers_tree.column(col, width=width, anchor="w")
        self._launchers_tree.grid(row=4, column=0, columnspan=3, sticky="nsew", padx=8, pady=(0, 8))
        add_tooltip(wrapper_entry, "Folder where future .cmd or shell wrappers will be generated.")
        add_tooltip(browse, "Choose and validate a launcher wrapper directory.")
        self._update_wrapper_status()
        self._refresh_launchers_tab()

    def _build_cleanup_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        ttk.Label(parent, text="Cleanup", font=("", 11, "bold")).grid(row=0, column=0, sticky="w", padx=8, pady=8)
        columns = ("type", "name", "source", "location", "state")
        self._cleanup_tree = ttk.Treeview(parent, columns=columns, show="headings", selectmode="extended")
        for col, heading, width in [
            ("type", "Type", 100),
            ("name", "Name", 180),
            ("source", "Source", 160),
            ("location", "Location", 360),
            ("state", "State", 100),
        ]:
            self._cleanup_tree.heading(col, text=heading)
            self._cleanup_tree.column(col, width=width, anchor="w")
        self._cleanup_tree.grid(row=1, column=0, sticky="nsew", padx=8)
        actions = ttk.Frame(parent)
        actions.grid(row=2, column=0, sticky="ew", padx=8, pady=8)
        ttk.Button(actions, text="Refresh", command=self._refresh_cleanup_tab).pack(side="left")
        ttk.Button(actions, text="Delete Selected", command=self._delete_selected_cleanup_assets).pack(
            side="left", padx=6
        )
        ttk.Button(actions, text="Clean All Tracked", command=self._delete_all_cleanup_assets).pack(side="left")
        self._cleanup_status_var = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self._cleanup_status_var).grid(row=3, column=0, sticky="w", padx=8, pady=(0, 8))

    def _build_pyodide_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(3, weight=1)
        parent.rowconfigure(5, weight=1)
        ttk.Label(parent, text="Browser Python", font=("", 11, "bold")).grid(
            row=0, column=0, sticky="w", padx=8, pady=8
        )
        status = self._pyodide_status_text()
        ttk.Label(parent, text=status, wraplength=820).grid(row=1, column=0, sticky="w", padx=8, pady=(0, 8))

        form = ttk.Frame(parent)
        form.grid(row=2, column=0, sticky="ew", padx=8)
        form.columnconfigure(1, weight=1)
        self._browser_runtime_var = tk.StringVar(value="pyscript")
        self._pyodide_package_var = tk.StringVar(value=DEMO_PACKAGE)
        self._pyodide_args_var = tk.StringVar(value=DEMO_ARGS)
        ttk.Label(form, text="Runtime:").grid(row=0, column=0, sticky="w", padx=(0, 4), pady=2)
        runtime_combo = ttk.Combobox(
            form,
            textvariable=self._browser_runtime_var,
            values=["pyscript", "pyodide"],
            state="readonly",
            width=14,
        )
        runtime_combo.grid(row=0, column=1, sticky="w", pady=2)
        ttk.Label(form, text="Package:").grid(row=1, column=0, sticky="w", padx=(0, 4), pady=2)
        ttk.Entry(form, textvariable=self._pyodide_package_var).grid(row=1, column=1, sticky="ew", pady=2)
        ttk.Label(form, text="Args:").grid(row=2, column=0, sticky="w", padx=(0, 4), pady=2)
        ttk.Entry(form, textvariable=self._pyodide_args_var).grid(row=2, column=1, sticky="ew", pady=2)
        add_tooltip(runtime_combo, "Choose direct Pyodide or PyScript browser scaffolding.")

        self._pyodide_code = tk.Text(parent, wrap="none", height=10, font=("Courier", 10))
        self._pyodide_code.grid(row=3, column=0, sticky="nsew", padx=8, pady=(6, 4))
        self._pyodide_code.insert("1.0", DEMO_CODE)

        actions = ttk.Frame(parent)
        actions.grid(row=4, column=0, sticky="ew", padx=8, pady=4)
        run_btn = ttk.Button(actions, text="Open Browser Terminal", command=self._on_run_pyodide)
        run_btn.pack(side="left")
        self._pyodide_output = tk.Text(parent, wrap="none", height=8, state="disabled", font=("Courier", 10))
        self._pyodide_output.grid(row=5, column=0, sticky="nsew", padx=8, pady=(4, 8))
        add_tooltip(run_btn, "Generate a browser-hosted PyScript or Pyodide app and open it.")

    def _build_activity_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        ttk.Label(parent, text="Activity", font=("", 11, "bold")).grid(row=0, column=0, sticky="w", padx=8, pady=8)
        columns = ("time", "exit", "engine", "package", "command")
        self._activity_tree = ttk.Treeview(parent, columns=columns, show="headings")
        for col, heading, width in [
            ("time", "Time", 170),
            ("exit", "Exit", 60),
            ("engine", "Engine", 80),
            ("package", "Package", 140),
            ("command", "Command", 420),
        ]:
            self._activity_tree.heading(col, text=heading)
            self._activity_tree.column(col, width=width, anchor="w")
        self._activity_tree.grid(row=1, column=0, sticky="nsew", padx=8)
        ttk.Button(parent, text="Refresh", command=self._refresh_activity_tab).grid(
            row=2, column=0, sticky="w", padx=8, pady=8
        )

    # Notebook and help

    def _on_tab_changed(self, _event: object) -> None:
        label = self._current_tab_label()
        self._settings.last_selected_tab = label
        save_settings(self._settings)
        self._set_help(label)
        if label == "Profiles":
            self._refresh_profiles_tab()
        elif label == "Launchers":
            self._refresh_launchers_tab()
        elif label == "Cleanup":
            self._refresh_cleanup_tab()
        elif label == "Browser Python":
            self._set_help("Browser Python")
        elif label == "Activity":
            self._refresh_activity_tab()

    def _current_tab_label(self) -> str:
        notebook = cast(Any, self._notebook)
        tab_id = notebook.select()
        return str(notebook.tab(tab_id, "text")) if tab_id else "Catalog"

    def _restore_selected_tab(self) -> None:
        notebook = cast(Any, self._notebook)
        for tab_id in notebook.tabs():
            if notebook.tab(tab_id, "text") == self._settings.last_selected_tab:
                notebook.select(tab_id)
                self._set_help(self._settings.last_selected_tab)
                return

    def _toggle_help_panel(self) -> None:
        visible = self._help_visible_var.get()
        self._settings.help_panel_visible = visible
        save_settings(self._settings)
        root_pane = cast(Any, self._root_pane)
        panes = root_pane.panes()
        if visible and str(self._help_frame) not in panes:
            self._root_pane.add(self._help_frame, weight=0)
        elif not visible and str(self._help_frame) in panes:
            self._root_pane.forget(self._help_frame)

    def _set_help(self, topic: str) -> None:
        self._help_text.config(state="normal")
        self._help_text.delete("1.0", "end")
        self._help_text.insert("1.0", topic_text(topic))
        self._help_text.config(state="disabled")

    # Catalog and profile selection

    def _refresh_catalog_panel(self) -> None:
        q = self._filter_var.get()
        self._settings.preferred_search_mode = "exact" if self._exact_search_var.get() else "fuzzy"
        save_settings(self._settings)
        profiles_only = self._profiles_only_var.get()
        catalog = [] if profiles_only else search(q, self._usage_filter_var.get(), self._exact_search_var.get())
        profiles = load_profiles()

        self._left_list.delete(0, "end")
        self._left_items = []

        for entry in catalog:
            label = f"{entry.name}  [{entry.usage_pattern}]"
            self._left_list.insert("end", label)
            self._left_items.append(entry)

        if profiles:
            if not profiles_only:
                self._left_list.insert("end", "-- My Profiles --")
                self._left_items.append(None)
                self._left_list.itemconfig(len(self._left_items) - 1, foreground="gray", selectbackground="gray")
            query = q.lower()
            for profile in profiles:
                if not query or query in profile.name.lower() or query in profile.config.package_spec.lower():
                    self._left_list.insert("end", f"  * {profile.name}")
                    self._left_items.append(profile)

        if catalog:
            self._left_list.selection_set(0)
            self._apply_entry(catalog[0])
        elif not profiles_only:
            self._set_metadata("No catalog matches. Try a broader query or switch out of exact mode.")

    def _on_left_select(self, _event: object) -> None:
        selected_index = self._selected_index()
        if selected_index is None:
            return
        item = self._left_items[selected_index]
        if item is None:
            return
        if isinstance(item, Profile):
            self._apply_config(item.config)
            self._selected_profile_name = item.name
            self._current_usage_pattern = item.usage_pattern
            self._update_action_affordances(item.usage_pattern)
            self._set_metadata(self._profile_metadata(item))
        else:
            self._apply_entry(item)

    def _apply_entry(self, entry: CatalogEntry) -> None:
        self._selected_catalog_name = entry.name
        self._selected_profile_name = ""
        self._current_usage_pattern = entry.usage_pattern
        self._pkg_spec_var.set(entry.name)
        self._entrypoint_var.set(entry.entrypoint)
        self._cli_args_var.set(entry.example_args)
        self._apt_var.set(" ".join(entry.apt_packages))
        self._interaction_var.set(entry.interaction)
        self._sync_interaction_controls()
        self._update_action_affordances(entry.usage_pattern)
        self._set_metadata(self._entry_metadata(entry))
        self._start_metadata_enrichment(entry, force=False)

    def _use_custom(self) -> None:
        self._left_list.selection_clear(0, "end")
        self._pkg_spec_var.set("")
        self._entrypoint_var.set("")
        self._cli_args_var.set("")
        self._apt_var.set("")
        self._stdin_file_var.set("")
        self._selected_catalog_name = ""
        self._selected_profile_name = ""
        self._current_usage_pattern = "single_run_cli"
        self._update_action_affordances(self._current_usage_pattern)
        self._set_metadata("Custom package\n\nEnter a package spec and entrypoint manually.")
        self._sync_interaction_controls()

    def _delete_selected_profile(self) -> None:
        selected_index = self._selected_index()
        if selected_index is None:
            return
        item = self._left_items[selected_index]
        if not isinstance(item, Profile):
            messagebox.showinfo("safe-whale", "Select a profile (*) to delete.")
            return
        if messagebox.askyesno("Delete Profile", f"Delete profile '{item.name}'?"):
            delete_profile(item.name)
            self._refresh_catalog_panel()
            self._refresh_profiles_tab()
            self._refresh_launchers_tab()

    def _selected_index(self) -> int | None:
        selected = cast(tuple[int, ...], cast(Any, self._left_list).curselection())
        if not selected:
            return None
        return selected[0]

    def _set_metadata(self, text: str) -> None:
        self._metadata.config(state="normal")
        self._metadata.delete("1.0", "end")
        self._metadata.insert("1.0", text)
        self._metadata.config(state="disabled")

    def _refresh_selected_metadata(self) -> None:
        selected_index = self._selected_index()
        if selected_index is None:
            return
        item = self._left_items[selected_index]
        if isinstance(item, CatalogEntry):
            self._start_metadata_enrichment(item, force=True)

    def _start_metadata_enrichment(self, entry: CatalogEntry, *, force: bool) -> None:
        if entry.metadata_status in {"cached", "fetched"} and not force:
            return
        selected_name = entry.name
        self._set_metadata(f"{self._entry_metadata(entry)}\n\nFetching PyPI metadata...")

        def worker() -> None:
            try:
                ttl = 0 if force else self._settings.catalog_cache_ttl
                enriched = enrich_catalog_entry(entry, ttl)
            except MetadataError as exc:
                self.after(0, self._metadata_fetch_failed, selected_name, str(exc))
                return
            self.after(0, self._metadata_fetch_done, selected_name, enriched)

        threading.Thread(target=worker, daemon=True).start()

    def _metadata_fetch_done(self, selected_name: str, entry: CatalogEntry) -> None:
        if self._selected_catalog_name != selected_name:
            return
        self._set_metadata(self._entry_metadata(entry))
        for idx, item in enumerate(self._left_items):
            if isinstance(item, CatalogEntry) and item.name == entry.name:
                self._left_items[idx] = entry
                break

    def _metadata_fetch_failed(self, selected_name: str, message: str) -> None:
        if self._selected_catalog_name != selected_name:
            return
        current = self._metadata.get("1.0", "end-1c")
        self._set_metadata(f"{current}\n\nPyPI metadata unavailable: {message}")

    def _entry_metadata(self, entry: CatalogEntry) -> str:
        lines = [
            entry.name,
            "",
            entry.description,
            "",
            f"Entrypoint: {entry.entrypoint}",
            f"Usage pattern: {entry.usage_pattern}",
            f"Interaction: {entry.interaction}",
            f"Recommended action: {entry.preferred_action().replace('_', ' ')}",
            f"Metadata: {entry.metadata_status}",
        ]
        if entry.latest_version:
            lines.append(f"Latest version: {entry.latest_version}")
        if entry.requires_python:
            lines.append(f"Requires Python: {entry.requires_python}")
        if entry.license:
            lines.append(f"License: {entry.license}")
        if entry.tags:
            lines.append(f"Tags: {', '.join(entry.tags)}")
        if entry.aliases:
            lines.append(f"Aliases: {', '.join(entry.aliases)}")
        if entry.apt_packages:
            lines.append(f"Apt hints: {' '.join(entry.apt_packages)}")
        if entry.classifiers:
            lines.append("Classifiers: " + "; ".join(entry.classifiers[:5]))
        if entry.distribution_files:
            lines.append("Files: " + "; ".join(entry.distribution_files[:4]))
        if entry.project_urls:
            lines.append("Project URLs: " + ", ".join(f"{key}: {value}" for key, value in entry.project_urls.items()))
        return "\n".join(lines)

    def _profile_metadata(self, profile: Profile) -> str:
        return "\n".join(
            [
                profile.name,
                "",
                profile.notes or "Saved profile",
                "",
                f"Package: {profile.config.package_spec}",
                f"Entrypoint: {profile.config.entrypoint}",
                f"Usage pattern: {profile.usage_pattern}",
                f"Preferred action: {profile.preferred_action.replace('_', ' ')}",
            ]
        )

    def _update_action_affordances(self, usage_pattern: str) -> None:
        preferred = preferred_action_for_usage_pattern(usage_pattern)
        if preferred == "install_wrapper":
            self._run_btn.config(text="Sample Run")
        elif preferred == "open_terminal":
            self._run_btn.config(text="Open Terminal")
        else:
            self._run_btn.config(text="Run")
        self._term_btn.config(text="Run in Terminal")
        self._install_wrapper_btn.config(state="normal")

    # Config

    def _build_config(self) -> RunConfig:
        apt_raw = self._apt_var.get().strip()
        apt = apt_raw.split() if apt_raw else []
        return RunConfig(
            package_spec=self._pkg_spec_var.get().strip(),
            entrypoint=self._entrypoint_var.get().strip(),
            cli_args=self._cli_args_var.get().strip(),
            apt_packages=apt,
            engine=self._engine_var.get(),
            interaction=self._interaction_var.get(),
            read_only=self._read_only_var.get(),
            no_new_privs=self._no_new_privs_var.get(),
            cap_drop_all=self._cap_drop_var.get(),
            tmpfs_tmp=self._tmpfs_var.get(),
            block_network=self._block_net_var.get(),
            non_root=self._non_root_var.get(),
            limit_pids=self._limit_pids_var.get(),
            memory_mb=int(self._mem_var.get() or "1024"),
            cpus=float(self._cpu_var.get() or "1.0"),
            mount_dir=self._mount_var.get().strip(),
            stdin_file=self._stdin_file_var.get().strip(),
        )

    def _choose_stdin_file(self) -> None:
        chosen = filedialog.askopenfilename(parent=self, title="Select input file")
        if chosen:
            self._stdin_file_var.set(chosen)

    def _sync_interaction_controls(self) -> None:
        has_input_file = bool(self._stdin_file_var.get().strip())
        self._pipe_radio.config(state="normal" if has_input_file else "disabled")
        if not has_input_file and self._interaction_var.get() == "pipe":
            self._interaction_var.set("immediate")

    # Actions

    def _on_run(self) -> None:
        if self._running:
            return
        cfg = self._build_config()
        if not cfg.package_spec:
            messagebox.showwarning("safe-whale", "Please enter a package spec.")
            return
        if cfg.interaction == "pipe" and not cfg.stdin_file:
            messagebox.showwarning("safe-whale", "Choose an input file before using pipe mode.")
            return
        if cfg.interaction == "interactive":
            self._append_output("[safe-whale] Interactive/TUI app detected; launching in terminal.\n")
            self._on_run_terminal()
            return
        if self._dry_run:
            tag = image_tag(cfg)
            self._append_output(generate_dockerfile(cfg))
            self._append_output(f"\n# Run command:\n{build_display_command(cfg, tag)}\n")
            return
        self._built_tag = None
        self._running = True
        self._run_btn.config(state="disabled")
        self._term_btn.config(state="disabled")
        self._install_wrapper_btn.config(state="disabled")
        self._cancel_btn.config(state="normal")
        self._run_thread = threading.Thread(target=self._run_worker, args=(cfg,), daemon=True)
        self._run_thread.start()

    def _run_worker(self, cfg: RunConfig) -> None:
        def on_output(line: str) -> None:
            self.after(0, self._append_output, line)

        def on_proc(p: subprocess.Popen[str]) -> None:
            self._run_proc = p

        result = run_container(cfg, on_output=on_output, on_proc=on_proc)

        if not self._no_history:
            append_history(result)

        tag = image_tag(cfg)
        self.after(0, self._on_run_complete, result.exit_code, tag, result.image_ready)

    def _on_run_complete(self, exit_code: int | None, tag: str, image_ready: bool) -> None:
        self._running = False
        self._built_tag = tag if image_ready else None
        self._run_btn.config(state="normal")
        self._term_btn.config(state="normal")
        self._install_wrapper_btn.config(state="normal")
        self._cancel_btn.config(state="disabled")
        self._append_output(f"\n[Process exited with code {exit_code}]\n")
        self._refresh_activity_tab()

    def _on_run_terminal(self) -> None:
        cfg = self._build_config()
        if not cfg.package_spec:
            messagebox.showwarning("safe-whale", "Please enter a package spec.")
            return
        if cfg.interaction == "pipe":
            messagebox.showinfo("safe-whale", "Pipe-file mode is only supported from the main Run button.")
            return
        tag = image_tag(cfg)
        if self._built_tag == tag:
            run_in_terminal(cfg, tag)
        else:
            self._running = True
            self._run_btn.config(state="disabled")
            self._term_btn.config(state="disabled")
            self._install_wrapper_btn.config(state="disabled")
            self._cancel_btn.config(state="normal")
            self._run_thread = threading.Thread(target=self._build_then_terminal_worker, args=(cfg,), daemon=True)
            self._run_thread.start()

    def _build_then_terminal_worker(self, cfg: RunConfig) -> None:
        def on_output(line: str) -> None:
            self.after(0, self._append_output, line)

        def on_proc(p: subprocess.Popen[str]) -> None:
            self._run_proc = p

        result = run_container(cfg, on_output=on_output, build_only=True, on_proc=on_proc)
        tag = image_tag(cfg)

        def done() -> None:
            self._running = False
            self._built_tag = tag if result.image_ready else None
            self._run_btn.config(state="normal")
            self._term_btn.config(state="normal")
            self._install_wrapper_btn.config(state="normal")
            self._cancel_btn.config(state="disabled")
            if result.image_ready:
                run_in_terminal(cfg, tag)
            else:
                self._append_output(f"\n[Build failed with code {result.exit_code}]\n")

        self.after(0, done)

    def _on_cancel(self) -> None:
        proc = self._run_proc
        if proc is not None:
            with suppress(OSError):
                proc.kill()
            self._run_proc = None
        self._append_output("\n[Cancelled by user]\n")
        self._running = False
        self._run_btn.config(state="normal")
        self._term_btn.config(state="normal")
        self._install_wrapper_btn.config(state="normal")
        self._cancel_btn.config(state="disabled")

    def _show_dockerfile(self) -> None:
        cfg = self._build_config()
        self._saved_output = self._output.get("1.0", "end-1c")
        self._clear_output()
        self._output_label.config(text="Dockerfile")
        self._back_btn.pack(side="right", padx=(0, 4))
        self._append_output(generate_dockerfile(cfg))
        tag = image_tag(cfg)
        self._append_output(f"\n# Run command:\n{build_display_command(cfg, tag)}\n")

    def _restore_output(self) -> None:
        self._back_btn.pack_forget()
        self._output_label.config(text="Output")
        self._clear_output()
        if self._saved_output:
            self._append_output(self._saved_output)

    def _clear_output(self) -> None:
        self._output.config(state="normal")
        self._output.delete("1.0", "end")
        self._output.config(state="disabled")

    def _append_output(self, text: str) -> None:
        self._output.config(state="normal")
        self._output.insert("end", text)
        self._output.see("end")
        self._output.config(state="disabled")

    # Profiles

    def _save_profile(self) -> None:
        default_name = self._selected_profile_name or self._pkg_spec_var.get().strip()
        name = simpledialog.askstring("Save Profile", "Profile name:", initialvalue=default_name, parent=self)
        if not name:
            return
        cfg = self._build_config()
        save_profile(Profile(name=name, config=cfg, usage_pattern=self._current_usage_pattern))
        self._selected_profile_name = name
        self._refresh_catalog_panel()
        self._refresh_profiles_tab()
        self._refresh_launchers_tab()

    def _apply_config(self, cfg: RunConfig) -> None:
        self._pkg_spec_var.set(cfg.package_spec)
        self._entrypoint_var.set(cfg.entrypoint)
        self._cli_args_var.set(cfg.cli_args)
        self._apt_var.set(" ".join(cfg.apt_packages))
        self._engine_var.set(cfg.engine)
        self._interaction_var.set(cfg.interaction)
        self._read_only_var.set(cfg.read_only)
        self._no_new_privs_var.set(cfg.no_new_privs)
        self._cap_drop_var.set(cfg.cap_drop_all)
        self._tmpfs_var.set(cfg.tmpfs_tmp)
        self._block_net_var.set(cfg.block_network)
        self._non_root_var.set(cfg.non_root)
        self._limit_pids_var.set(cfg.limit_pids)
        self._mem_var.set(str(cfg.memory_mb))
        self._cpu_var.set(str(cfg.cpus))
        self._mount_var.set(cfg.mount_dir)
        self._stdin_file_var.set(cfg.stdin_file)
        self._sync_interaction_controls()

    def _refresh_profiles_tab(self) -> None:
        for item in self._profiles_tree.get_children():
            self._profiles_tree.delete(item)
        for profile in load_profiles():
            self._profiles_tree.insert(
                "",
                "end",
                iid=profile.name,
                values=(
                    profile.name,
                    profile.usage_pattern,
                    profile.preferred_action.replace("_", " "),
                    profile.config.package_spec,
                ),
            )

    def _on_profile_tree_select(self, _event: object) -> None:
        profile = self._selected_profile_from_profiles_tab()
        if profile is None:
            return
        self._set_help("Profiles")
        self._selected_profile_name = profile.name
        self._current_usage_pattern = profile.usage_pattern

    def _selected_profile_from_profiles_tab(self) -> Profile | None:
        selected = self._profiles_tree.selection()
        if not selected:
            return None
        selected_name = selected[0]
        for profile in load_profiles():
            if profile.name == selected_name:
                return profile
        return None

    def _load_selected_profile_in_catalog(self) -> None:
        profile = self._selected_profile_from_profiles_tab()
        if profile is None:
            messagebox.showinfo("safe-whale", "Select a profile first.")
            return
        self._apply_profile_to_catalog(profile)
        cast(Any, self._notebook).select(self._catalog_tab)

    def _apply_profile_to_catalog(self, profile: Profile) -> None:
        self._apply_config(profile.config)
        self._selected_profile_name = profile.name
        self._current_usage_pattern = profile.usage_pattern
        self._update_action_affordances(profile.usage_pattern)
        self._set_metadata(self._profile_metadata(profile))

    def _run_selected_profile(self) -> None:
        profile = self._selected_profile_from_profiles_tab()
        if profile is None:
            messagebox.showinfo("safe-whale", "Select a profile first.")
            return
        self._apply_profile_to_catalog(profile)
        cast(Any, self._notebook).select(self._catalog_tab)
        self._on_run()

    def _delete_profile_from_tab(self) -> None:
        selected = self._profiles_tree.selection()
        if not selected:
            messagebox.showinfo("safe-whale", "Select a profile to delete.")
            return
        name = selected[0]
        if messagebox.askyesno("Delete Profile", f"Delete profile '{name}'?"):
            delete_profile(name)
            self._refresh_catalog_panel()
            self._refresh_profiles_tab()
            self._refresh_launchers_tab()

    # Launchers and activity

    def _choose_wrapper_dir(self) -> None:
        chosen = filedialog.askdirectory(parent=self, title="Select wrapper directory")
        if chosen:
            self._wrapper_dir_var.set(chosen)
            self._settings.wrapper_dir = chosen
            save_settings(self._settings)
            self._update_wrapper_status()
            self._refresh_launchers_tab()

    def _update_wrapper_status(self) -> None:
        value = self._wrapper_dir_var.get().strip()
        if not value:
            self._wrapper_status_var.set("No wrapper directory selected.")
            return
        from pathlib import Path

        path = Path(value)
        if not path.exists():
            self._wrapper_status_var.set("Directory does not exist yet.")
        elif not path.is_dir():
            self._wrapper_status_var.set("Selected path is not a directory.")
        else:
            if directory_on_path(path):
                self._wrapper_status_var.set("Directory exists and is on PATH.")
            else:
                self._wrapper_status_var.set(
                    "Directory exists but is not on PATH. Add it to PATH to launch wrappers by name."
                )

    def _refresh_launchers_tab(self) -> None:
        self._update_wrapper_status()
        for item in self._launchers_tree.get_children():
            self._launchers_tree.delete(item)
        wrapper_dir = self._wrapper_dir_var.get().strip()
        for profile in load_profiles():
            info = launcher_info(profile, wrapper_dir)
            self._launchers_tree.insert(
                "",
                "end",
                iid=profile.name,
                values=(
                    info.name,
                    profile.name,
                    profile.usage_pattern,
                    str(info.path) if wrapper_dir else "",
                    info.status,
                ),
            )

    def _install_selected_launcher(self) -> None:
        selected = self._launchers_tree.selection()
        if not selected:
            messagebox.showinfo("safe-whale", "Select a profile in the Launchers tab first.")
            return
        wrapper_dir = self._wrapper_dir_var.get().strip()
        if not wrapper_dir:
            messagebox.showwarning("safe-whale", "Choose a wrapper directory first.")
            return
        profile_name = selected[0]
        for profile in load_profiles():
            if profile.name == profile_name:
                self._build_and_install_launcher(profile, wrapper_dir)
                return

    def _install_current_wrapper(self) -> None:
        wrapper_dir = self._wrapper_dir_var.get().strip()
        if not wrapper_dir:
            messagebox.showwarning("safe-whale", "Choose a wrapper directory on the Launchers tab first.")
            cast(Any, self._notebook).select(self._launchers_tab)
            return
        profile = self._current_or_saved_profile_for_launcher()
        if profile is None:
            return
        self._build_and_install_launcher(profile, wrapper_dir)

    def _current_or_saved_profile_for_launcher(self) -> Profile | None:
        cfg = self._build_config()
        if self._selected_profile_name:
            for profile in load_profiles():
                if profile.name == self._selected_profile_name:
                    return Profile(
                        name=profile.name,
                        config=cfg,
                        usage_pattern=profile.usage_pattern,
                        notes=profile.notes,
                        tags=profile.tags,
                        launcher_name=profile.launcher_name,
                        launcher_installed=profile.launcher_installed,
                        launcher_updated_at=profile.launcher_updated_at,
                        launcher_config_digest=profile.launcher_config_digest,
                        preferred_action=profile.preferred_action,
                    )

        default_name = cfg.package_spec
        name = simpledialog.askstring("Install Wrapper", "Save profile as:", initialvalue=default_name, parent=self)
        if not name:
            return None
        return Profile(name=name, config=cfg, usage_pattern=self._current_usage_pattern)

    def _build_and_install_launcher(self, profile: Profile, wrapper_dir: str) -> None:
        if self._running:
            return
        self._append_output(f"[safe-whale] Building image for launcher profile '{profile.name}'.\n")
        self._running = True
        self._run_btn.config(state="disabled")
        self._term_btn.config(state="disabled")
        self._install_wrapper_btn.config(state="disabled")
        self._cancel_btn.config(state="normal")

        def worker() -> None:
            def on_output(line: str) -> None:
                self.after(0, self._append_output, line)

            def on_proc(p: subprocess.Popen[str]) -> None:
                self._run_proc = p

            result = run_container(profile.config, on_output=on_output, build_only=True, on_proc=on_proc)

            def done() -> None:
                self._running = False
                self._run_btn.config(state="normal")
                self._term_btn.config(state="normal")
                self._install_wrapper_btn.config(state="normal")
                self._cancel_btn.config(state="disabled")
                if not result.image_ready:
                    self._append_output(f"\n[Launcher build failed with code {result.exit_code}]\n")
                    return
                updated = install_launcher(profile, wrapper_dir)
                save_profile(updated)
                self._append_output(f"[safe-whale] Installed wrapper '{updated.launcher_name}'.\n")
                self._refresh_profiles_tab()
                self._refresh_catalog_panel()
                self._refresh_launchers_tab()

            self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def _refresh_activity_tab(self) -> None:
        for item in self._activity_tree.get_children():
            self._activity_tree.delete(item)
        for idx, record in enumerate(load_history()):
            self._activity_tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(
                    str(record.get("timestamp", "")),
                    str(record.get("exit_code", "")),
                    str(record.get("engine", "")),
                    str(record.get("package_spec", "")),
                    str(record.get("command", "")),
                ),
            )

    def _refresh_cleanup_tab(self) -> None:
        for item in self._cleanup_tree.get_children():
            self._cleanup_tree.delete(item)
        assets = list_cleanup_assets()
        for asset in assets:
            self._cleanup_tree.insert(
                "",
                "end",
                iid=asset.asset_id,
                values=(asset.asset_type, asset.name, asset.source, asset.location, asset.state),
            )
        self._cleanup_status_var.set(f"{len(assets)} tracked safe-whale asset(s).")

    def _delete_selected_cleanup_assets(self) -> None:
        selected = self._cleanup_tree.selection()
        if not selected:
            messagebox.showinfo("safe-whale", "Select one or more tracked assets to delete.")
            return
        if not messagebox.askyesno("Delete Assets", f"Delete {len(selected)} tracked safe-whale asset(s)?"):
            return
        results = [delete_managed_asset(asset_id) for asset_id in selected]
        self._cleanup_status_var.set(", ".join(results))
        self._refresh_cleanup_tab()
        self._refresh_launchers_tab()

    def _delete_all_cleanup_assets(self) -> None:
        if not messagebox.askyesno("Clean All Tracked", "Delete all tracked safe-whale assets?"):
            return
        results = delete_unused_assets()
        self._cleanup_status_var.set(f"Cleaned {sum(result == 'deleted' for result in results.values())} asset(s).")
        self._refresh_cleanup_tab()
        self._refresh_launchers_tab()

    def _pyodide_status_text(self) -> str:
        return (
            "Pyodide and PyScript belong in a browser here. This tab generates browser apps with an auto-loaded "
            "pure-Python package demo. It is not a Docker-like backend for arbitrary PyPI CLI tools."
        )

    def _on_run_pyodide(self) -> None:
        cfg = BrowserPyodideConfig(
            code=self._pyodide_code.get("1.0", "end-1c"),
            package_spec=self._pyodide_package_var.get().strip(),
            cli_args=self._pyodide_args_var.get().strip(),
            name=self._pyodide_package_var.get().strip() or "pyodide-terminal",
            runtime="pyscript" if self._browser_runtime_var.get() == "pyscript" else "pyodide",
        )
        self._clear_pyodide_output()
        app = create_browser_pyodide_app(cfg)
        opened = open_browser_pyodide_app(app)
        self._append_pyodide_output(f"[safe-whale] Generated browser {app.runtime} app:\n{app.index_path}\n")
        self._append_pyodide_output(f"[safe-whale] URL: {app.url}\n")
        if not opened:
            self._append_pyodide_output("[safe-whale] Browser launch was not confirmed by the OS.\n")

    def _clear_pyodide_output(self) -> None:
        self._pyodide_output.config(state="normal")
        self._pyodide_output.delete("1.0", "end")
        self._pyodide_output.config(state="disabled")

    def _append_pyodide_output(self, text: str) -> None:
        self._pyodide_output.config(state="normal")
        self._pyodide_output.insert("end", text)
        self._pyodide_output.see("end")
        self._pyodide_output.config(state="disabled")

    # Diagnostics

    def _open_dockerfiles_dir(self) -> None:
        import subprocess as _sp
        import sys as _sys

        directory = str(dockerfiles_dir())
        if _sys.platform == "win32":
            _sp.Popen(["explorer", directory])  # pylint: disable=consider-using-with
        elif _sys.platform == "darwin":
            _sp.Popen(["open", directory])  # pylint: disable=consider-using-with
        else:
            _sp.Popen(["xdg-open", directory])  # pylint: disable=consider-using-with

    def _open_readthedocs(self) -> None:
        import webbrowser

        webbrowser.open("https://safe-whale.readthedocs.io/")

    def _show_diagnostics(self) -> None:
        from safe_whale.storage import _data_dir

        engines = detect_engines()
        msg = (
            f"Detected engines: {', '.join(engines) if engines else '(none)'}\n"
            "Browser Python:   PyScript and Pyodide scaffolds\n"
            f"Data directory:   {_data_dir()}\n"
            f"Dockerfiles:      {dockerfiles_dir()}\n\n"
            "The Engine dropdown is in the Catalog tab because it only affects container builds and runs. "
            "Browser Python launches browser-hosted PyScript/Pyodide apps instead."
        )
        messagebox.showinfo("Diagnostics", msg)

    def _on_close(self) -> None:
        self._settings.wrapper_dir = self._wrapper_dir_var.get().strip()
        self._settings.last_selected_tab = self._current_tab_label()
        self._settings.help_panel_visible = self._help_visible_var.get()
        save_settings(self._settings)
        self.destroy()
