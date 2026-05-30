"""Built-in catalog of popular Python CLI tools."""

from __future__ import annotations

from safe_whale.models import CatalogEntry


def _tags(*values: str) -> list[str]:
    return list(values)


CATALOG: list[CatalogEntry] = [
    # ── Text & data tools ──────────────────────────────────────────────────────
    CatalogEntry(
        name="httpie",
        entrypoint="http",
        description="Human-friendly HTTP client for APIs & debugging.",
        example_args="--help",
        tags=_tags("http", "api", "network"),
        aliases=_tags("http client", "api client", "curl"),
        keywords=_tags("http", "rest", "json"),
        project_urls={"Homepage": "https://httpie.io/", "Source": "https://github.com/httpie/cli"},
    ),
    CatalogEntry(
        name="rich-cli",
        entrypoint="rich",
        description="Rich text & markdown rendering in the terminal.",
        example_args="--help",
        usage_pattern="pipe_filter",
        tags=_tags("text", "markdown", "formatting"),
        aliases=_tags("render markdown", "pretty terminal output"),
        keywords=_tags("rich", "markdown", "ansi"),
    ),
    CatalogEntry(
        name="howdoi",
        entrypoint="howdoi",
        description="Instant answers from StackOverflow from your terminal.",
        example_args="format a date in python",
        tags=_tags("search", "developer"),
        aliases=_tags("stackoverflow", "answer questions"),
    ),
    # ── TUI apps (need a real TTY — always run in terminal) ───────────────────
    CatalogEntry(
        name="babi",
        entrypoint="babi",
        description="A lightweight terminal text editor (TUI — opens in terminal).",
        interaction="interactive",
        tags=_tags("editor", "terminal"),
        aliases=_tags("terminal editor", "text editor"),
    ),
    CatalogEntry(
        name="glances",
        entrypoint="glances",
        description="Curses-based system monitor (TUI — opens in terminal).",
        interaction="interactive",
        tags=_tags("monitoring", "system", "terminal"),
        aliases=_tags("system monitor", "process monitor"),
    ),
    CatalogEntry(
        name="visidata",
        entrypoint="vd",
        description="Interactive terminal spreadsheet for data exploration (TUI).",
        interaction="interactive",
        tags=_tags("data", "spreadsheet", "terminal"),
        aliases=_tags("csv viewer", "data explorer"),
    ),
    CatalogEntry(
        name="litecli",
        entrypoint="litecli",
        description="CLI for SQLite with auto-completion and syntax highlighting (TUI).",
        interaction="interactive",
        tags=_tags("database", "sqlite", "terminal"),
        aliases=_tags("sqlite client", "sql shell"),
    ),
    CatalogEntry(
        name="pgcli",
        entrypoint="pgcli",
        description="Postgres CLI with auto-completion and syntax highlighting (TUI).",
        interaction="interactive",
        tags=_tags("database", "postgres", "terminal"),
        aliases=_tags("postgres client", "sql shell"),
    ),
    CatalogEntry(
        name="bpytop",
        entrypoint="bpytop",
        description="Python-based resource monitor with a full-screen terminal UI.",
        interaction="interactive",
        tags=_tags("monitoring", "system", "terminal"),
    ),
    CatalogEntry(
        name="s-tui",
        entrypoint="s-tui",
        description="Terminal UI for CPU monitoring, stress testing, and temperature graphs.",
        interaction="interactive",
        tags=_tags("monitoring", "system", "terminal"),
    ),
    CatalogEntry(
        name="mitmproxy",
        entrypoint="mitmproxy",
        description="Interactive terminal UI for inspecting and modifying HTTP traffic.",
        interaction="interactive",
        tags=_tags("http", "proxy", "security", "terminal"),
    ),
    CatalogEntry(
        name="pudb",
        entrypoint="pudb3",
        description="Full-screen console debugger for Python programs.",
        interaction="interactive",
        tags=_tags("debugging", "developer", "terminal"),
    ),
    CatalogEntry(
        name="rtv",
        entrypoint="rtv",
        description="Terminal Reddit client with a keyboard-driven full-screen UI.",
        interaction="interactive",
        tags=_tags("terminal", "client"),
    ),
    CatalogEntry(
        name="mps-youtube",
        entrypoint="mpsyt",
        description="Interactive terminal client for searching and playing YouTube audio.",
        interaction="interactive",
        tags=_tags("media", "terminal"),
    ),
    CatalogEntry(
        name="harlequin",
        entrypoint="harlequin",
        description="Terminal SQL IDE with an interactive query workflow.",
        interaction="interactive",
        tags=_tags("database", "sql", "terminal"),
    ),
    CatalogEntry(
        name="bpython",
        entrypoint="bpython",
        description="Curses-style Python REPL with autocomplete and inline help.",
        interaction="interactive",
        tags=_tags("repl", "developer", "terminal"),
    ),
    CatalogEntry(
        name="ptpython",
        entrypoint="ptpython",
        description="Prompt-toolkit Python REPL with multi-line editing and completions.",
        interaction="interactive",
        tags=_tags("repl", "developer", "terminal"),
    ),
    CatalogEntry(
        name="http-prompt",
        entrypoint="http-prompt",
        description="Interactive HTTP REPL built on HTTPie for exploring APIs.",
        interaction="interactive",
        tags=_tags("http", "api", "terminal"),
    ),
    CatalogEntry(
        name="toot",
        entrypoint="toot",
        description="Mastodon CLI and TUI client. Run 'toot tui' for the full-screen interface.",
        interaction="interactive",
        tags=_tags("social", "mastodon", "terminal"),
        aliases=_tags("mastodon client", "social media"),
        project_urls={"Homepage": "https://github.com/ihabunek/toot"},
    ),
    CatalogEntry(
        name="tuir",
        entrypoint="tuir",
        description="Text-based interface (TUI) for browsing Reddit from your terminal.",
        interaction="interactive",
        tags=_tags("social", "reddit", "terminal"),
        aliases=_tags("reddit client", "reddit browser"),
        project_urls={"Homepage": "https://github.com/proycon/tuir"},
    ),
    CatalogEntry(
        name="kanban-tui",
        entrypoint="kanban-tui",
        description="Customizable terminal-based Kanban task manager built with Textual.",
        interaction="interactive",
        tags=_tags("productivity", "kanban", "tasks", "terminal"),
        aliases=_tags("kanban board", "task manager", "todo"),
        project_urls={"Homepage": "https://github.com/Zaloog/kanban-tui"},
    ),
    CatalogEntry(
        name="kanban-python",
        entrypoint="kanban",
        description="Kanban board terminal app in Python.",
        interaction="interactive",
        tags=_tags("productivity", "kanban", "tasks", "terminal"),
        aliases=_tags("kanban board", "task manager"),
        project_urls={"Homepage": "https://github.com/Zaloog/kanban-python"},
    ),
    CatalogEntry(
        name="rsstui",
        entrypoint="rsstui",
        description="RSS feed reader TUI built with Textual.",
        interaction="interactive",
        tags=_tags("rss", "news", "terminal"),
        aliases=_tags("rss reader", "feed reader"),
        project_urls={"Homepage": "https://pypi.org/project/rsstui/"},
    ),
    CatalogEntry(
        name="hatch",
        entrypoint="hatch",
        description="Python project manager with an interactive shell environment.",
        interaction="interactive",
        tags=_tags("developer", "packaging", "terminal"),
        aliases=_tags("python project manager", "build tool"),
        project_urls={"Homepage": "https://hatch.pypa.io/"},
    ),
    CatalogEntry(
        name="posting",
        entrypoint="posting",
        description="Modern API client TUI — a terminal alternative to Postman.",
        interaction="interactive",
        tags=_tags("http", "api", "terminal"),
        aliases=_tags("api client", "rest client", "postman"),
        project_urls={"Homepage": "https://github.com/darrenburns/posting"},
    ),
    CatalogEntry(
        name="dunk",
        entrypoint="dunk",
        description="Prettier git diffs rendered in your pager (pipe-mode tool).",
        usage_pattern="pipe_filter",
        tags=_tags("git", "developer", "terminal"),
        aliases=_tags("git diff viewer", "diff formatter"),
        project_urls={"Homepage": "https://github.com/darrenburns/dunk"},
    ),
    CatalogEntry(
        name="tig",
        entrypoint="tig",
        description="Text-mode interface for Git — browse commits, branches, and diffs in a TUI.",
        interaction="interactive",
        tags=_tags("git", "developer", "terminal"),
        aliases=_tags("git browser", "git tui", "git log viewer"),
    ),
    # ── Download / media ──────────────────────────────────────────────────────
    CatalogEntry(
        name="yt-dlp",
        entrypoint="yt-dlp",
        description="Feature-rich video downloader. Add ffmpeg for full support.",
        apt_packages=["ffmpeg"],
        example_args="--version",
        usage_pattern="wrapper_cli",
        tags=_tags("download", "media", "video"),
        aliases=_tags("youtube downloader", "video downloader"),
    ),
    CatalogEntry(
        name="gallery-dl",
        entrypoint="gallery-dl",
        description="Download image galleries from many websites.",
        example_args="--version",
        usage_pattern="wrapper_cli",
        tags=_tags("download", "media", "images"),
        aliases=_tags("gallery downloader", "image downloader"),
    ),
    # ── Project / templating ──────────────────────────────────────────────────
    CatalogEntry(
        name="cookiecutter",
        entrypoint="cookiecutter",
        description="Project templating toolkit.",
        example_args="--help",
        usage_pattern="wrapper_cli",
        tags=_tags("project", "template"),
        aliases=_tags("project generator", "scaffold"),
    ),
    CatalogEntry(
        name="mkdocs",
        entrypoint="mkdocs",
        description="Static site generator for project docs.",
        example_args="--help",
        usage_pattern="wrapper_cli",
        tags=_tags("docs", "site", "project"),
    ),
    CatalogEntry(
        name="speedtest-cli",
        entrypoint="speedtest",
        description="Internet bandwidth test CLI.",
        example_args="--simple",
        tags=_tags("network", "diagnostics"),
        aliases=_tags("bandwidth test", "internet speed"),
    ),
    # ── Code quality ──────────────────────────────────────────────────────────
    CatalogEntry(
        name="black",
        entrypoint="black",
        description="The uncompromising Python code formatter.",
        example_args="--help",
        usage_pattern="wrapper_cli",
        tags=_tags("formatting", "developer", "code quality"),
        aliases=_tags("python formatter", "format python"),
    ),
    CatalogEntry(
        name="ruff",
        entrypoint="ruff",
        description="An extremely fast Python linter and formatter.",
        example_args="--help",
        usage_pattern="wrapper_cli",
        tags=_tags("lint", "formatting", "developer", "code quality"),
        aliases=_tags("python linter", "format python"),
    ),
    CatalogEntry(
        name="mypy",
        entrypoint="mypy",
        description="Optional static typing for Python.",
        example_args="--help",
        usage_pattern="wrapper_cli",
        tags=_tags("typing", "developer", "code quality"),
        aliases=_tags("type checker", "python types"),
    ),
    CatalogEntry(
        name="bandit",
        entrypoint="bandit",
        description="Security-oriented static analyser for Python code.",
        example_args="--help",
        usage_pattern="wrapper_cli",
        tags=_tags("security", "developer", "code quality"),
        aliases=_tags("security scanner", "python security"),
    ),
    CatalogEntry(
        name="twine",
        entrypoint="twine",
        description="Utilities for publishing packages to PyPI.",
        example_args="--help",
        usage_pattern="wrapper_cli",
        tags=_tags("packaging", "developer", "publish"),
    ),
]


def search(query: str, usage_pattern: str = "all", exact: bool = False) -> list[CatalogEntry]:
    """Return catalog entries matching query, ranked by local catalog signals."""
    q = query.strip().lower()
    candidates = [entry for entry in CATALOG if usage_pattern in ("all", entry.usage_pattern)]
    if not q:
        return list(candidates)

    ranked: list[tuple[int, str, CatalogEntry]] = []
    for entry in candidates:
        score = _match_score(entry, q, exact)
        if score > 0:
            ranked.append((score, entry.name, entry))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [entry for _score, _name, entry in ranked]


def get_by_name(name: str) -> CatalogEntry | None:
    """Return a catalog entry by exact package name, or None."""
    for entry in CATALOG:
        if entry.name == name:
            return entry
    return None


def _match_score(entry: CatalogEntry, query: str, exact: bool) -> int:
    name = entry.name.lower()
    aliases = [alias.lower() for alias in entry.aliases]
    if exact:
        return 100 if query == name or query in aliases else 0
    score = 0
    if query == name:
        score += 120
    if name.startswith(query):
        score += 80
    if query in name:
        score += 60
    if any(alias.startswith(query) for alias in aliases):
        score += 55
    if any(query in alias for alias in aliases):
        score += 45
    if query in entry.description.lower():
        score += 25
    for value in entry.tags:
        if query in value.lower():
            score += 35
    for value in entry.keywords:
        if query in value.lower():
            score += 30
    for value in entry.classifiers:
        if query in value.lower():
            score += 15
    return score
