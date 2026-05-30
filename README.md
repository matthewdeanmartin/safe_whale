# safe-whale

Run Python command-line tools in hardened container images, with a small Tkinter UI for discovery, profiles, launch
wrappers, history, and cleanup.

`safe-whale` is meant to feel like `pipx` where that vocabulary fits, but the isolation boundary is a container image
rather than a virtual environment. Pick a PyPI CLI tool, inspect what kind of tool it is, build it once, then run it
safely or install a wrapper command.

## Status

- Catalog search with usage patterns for one-shot CLIs, wrapper-first tools, pipe filters, and TUI apps.
- A `pipx`-shaped CLI for run, install, list, rebuild, uninstall, cleanup, diagnostics, and wrapper PATH guidance.
- PyPI metadata enrichment and local metadata caching.
- Saved profiles with stale-wrapper detection.
- pipx-style entry-point discovery: every `console_scripts` / `gui_scripts` command a package exposes gets its own
  wrapper (probed from inside the built image with `importlib.metadata`).
- `.cmd` + `.ps1` (Windows) or executable shell wrapper generation, one per discovered command.
- Interactive `install` setup (when run in a terminal): prompts for the tool's usage pattern and makes the read-only
  vs. writable filesystem trade-off explicit. Use `--yes` / `--no-input` to accept defaults non-interactively.
- Managed cleanup for safe-whale-tracked images, Dockerfiles, and wrappers.
- Docker-first execution. Podman/nerdctl/finch are detected, but Docker is the most exercised path.
- Browser-hosted PyScript and direct Pyodide experiments. The Browser Python tab auto-loads a pure-Python package demo
  so package installation is visible on first run.

## Quick Start

Install dependencies and launch the app:

```powershell
uv sync
uv run safe-whale
```

The CLI can also be used directly. It intentionally mirrors the `pipx` command vocabulary where that maps to
container-backed tools:

```powershell
uv run safe-whale run --dry-run ruff -- --version
uv run safe-whale install ruff --wrapper-dir .\.tmp\bin --skip-build
uv run safe-whale list
uv run safe-whale uninstall ruff --dry-run
```

When installed from PyPI, use the console script directly:

```powershell
safe-whale --help
safe-whale run ruff -- --version
safe-whale install ruff
```

`install` builds the image, then discovers every command the package ships and installs a wrapper for each — e.g.
`safe-whale install httpie` produces both `http` and `https`. In a terminal it first asks for the tool's usage pattern
and whether to run with a read-only root filesystem; pass `--yes` (or `--no-input`) to skip the prompts and accept
defaults plus any flags you supplied.

Global options work before or after subcommands:

- `--dry-run` shows Dockerfiles, build commands, run commands, profile changes, and cleanup actions without performing
  them.
- `--log-level DEBUG|INFO|WARNING|ERROR|CRITICAL` controls logging.
- `-v` / `--verbose` is a shorthand for more detailed logging.
- `--engine docker|podman|nerdctl|finch` selects the container engine.
- `--no-history` skips run history.

safe-whale-specific runtime options include `--entrypoint`, `--apt`, `--interaction`, `--stdin-file`, `--mount`,
`--memory`, `--cpus`, `--network` / `--block-network`, `--read-only` / `--writable`, `--non-root` / `--root`,
`--cap-drop-all` / `--keep-caps`, `--tmpfs-tmp` / `--no-tmpfs-tmp`, and `--limit-pids` / `--no-limit-pids`.

Other useful commands:

```powershell
uv run safe-whale environment
uv run safe-whale ensurepath
uv run safe-whale cleanup
uv run safe-whale list --catalog --query ruff
uv run safe-whale install-all pipx-list.json
```

Useful development checks:

```powershell
uv run pytest -q
uv run ruff check safe_whale tests
uv run mypy --hide-error-context safe_whale tests
```

In the Codex desktop sandbox on Windows, use the workspace-local cache/temp recipe in [spec/codex.md](spec/codex.md).

## Host Runtime Preliminaries

You need at least one runtime. Docker is the recommended default today.

| Host    | Docker                                                                                                  | Podman                                                                                                                                                                                                      | Browser Python                                               |
|---------|---------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------|
| Windows | Install Docker Desktop, enable WSL 2, verify with `docker info`.                                        | Install Podman Desktop/Podman CLI, then `podman machine init` and `podman machine start`. Avoid making Podman mimic Docker while Docker Desktop is also active unless you know which socket your tools use. | PyScript/Pyodide run in the browser and do not need Node.js. |
| macOS   | Install Docker Desktop and verify `docker info`.                                                        | Install Podman, then `podman machine init` and `podman machine start`.                                                                                                                                      | PyScript/Pyodide run in the browser.                         |
| Linux   | Install Docker Engine from Docker’s distro docs, or Docker Desktop if you prefer. Verify `docker info`. | Install `podman` from your distro packages and verify `podman info`.                                                                                                                                        | PyScript/Pyodide run in the browser.                         |

Long version: [docs/hosts.md](docs/hosts.md).

## Usage Patterns

Catalog entries carry a usage pattern so the UI can suggest the right action:

- `single_run_cli`: works well in the in-app output panel.
- `wrapper_cli`: best installed as a shell/editor wrapper.
- `pipe_filter`: best as a wrapper, with optional file-based sample runs.
- `tui_terminal`: needs a real terminal; curses/full-screen apps cannot render correctly in the output panel.
- Browser Pyodide/PyScript experiments: run in a generated browser app, not in the Tkinter output panel and not in
  Docker. They are useful for browser-compatible Python, not arbitrary PyPI CLI tools.

## pipx Compatibility

`safe-whale` borrows `pipx` command names for familiar workflows, but it does not create per-tool virtual environments.
The main difference is:

| pipx                                             | safe-whale                                        |
|--------------------------------------------------|---------------------------------------------------|
| Installs apps into managed virtual environments. | Builds apps into managed container images.        |
| Wrappers call venv entry points.                 | Wrappers run hardened containers.                 |
| Uses pip inside managed venvs.                   | Uses pip during image build, then runs the image. |

Implemented container-backed commands include `run`, `install`, `install-all`, `list`, `profiles`, `uninstall`,
`uninstall-all`, `reinstall`, `reinstall-all`, `upgrade`, `upgrade-all`, `cleanup`, `environment`, `ensurepath`,
`completions`, and `help`.

The commands `inject`, `uninject`, `pin`, `unpin`, `runpip`, `interpreter`, and `upgrade-shared` are recognized for
compatibility, but currently return an explicit unsupported-operation message because they do not map cleanly to the
container model yet.

Long version: [docs/usage/pipx-compatibility.md](docs/usage/pipx-compatibility.md).

## Safety Model

`safe-whale` builds a Dockerfile first, then applies runtime hardening when running the already-built image:

- read-only root filesystem
- non-root UID
- no-new-privileges
- capability drop
- PID, CPU, and memory limits
- optional network blocking
- optional bind mount and stdin file for tools that need local input

Cleanup only targets assets safe-whale created or explicitly tracked.

## Project Docs

- [docs/index.md](docs/index.md): MkDocs / Read the Docs home page.
- [docs/installation.md](docs/installation.md): install, source checkout, and wrapper PATH setup.
- [docs/usage/cli.md](docs/usage/cli.md): current CLI command reference.
- [docs/usage/pipx-compatibility.md](docs/usage/pipx-compatibility.md): what matches pipx and what differs.
- [docs/hosts.md](docs/hosts.md): Docker, Podman, and Browser Python setup notes by host OS.
- [spec/spec_v2.md](spec/spec_v2.md): v2 product specification.
- [spec/learnings.md](spec/learnings.md): container/runtime lessons learned during development.
- [spec/codex.md](spec/codex.md): local Codex sandbox notes.

Published documentation is configured through [mkdocs.yml](mkdocs.yml) and [.readthedocs.yaml](.readthedocs.yaml).
