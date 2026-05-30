# Installation

## Requirements

- Python 3.10 or newer
- A working Tkinter desktop environment if you want the GUI
- At least one supported container engine for container-backed runs
- Network access when building images or loading browser Python assets

Docker is the recommended runtime today. See [Host Runtimes](hosts.md) for Docker, Podman, and Browser Python setup notes.

## Install From PyPI

When published, install the CLI and GUI entry points with `pipx`:

```bash
pipx install safe-whale
```

You can also use `pip`:

```bash
pip install safe-whale
```

`pipx` installs `safe-whale` itself into an isolated virtual environment. Tools installed by `safe-whale install` are still built into container images and exposed through generated wrapper commands.

## Install From Source

```bash
git clone https://github.com/matthewdeanmartin/safe_whale.git
cd safe_whale
uv sync
```

Launch the GUI:

```bash
uv run safe-whale
```

Show CLI help:

```bash
uv run safe-whale --help
```

You can also launch the module directly:

```bash
uv run python -m safe_whale --help
```

## Wrapper PATH Setup

`safe-whale install` can create wrapper commands. The wrapper directory is chosen in this order:

1. `--wrapper-dir`
1. `SAFE_WHALE_BIN_DIR`
1. The saved GUI setting
1. The platform default

The default is `%LOCALAPPDATA%\safe-whale\bin` on Windows and `~/.local/bin` on macOS/Linux.

Check whether the resolved wrapper directory is on `PATH`:

```bash
safe-whale ensurepath
```

Show the resolved storage and wrapper locations:

```bash
safe-whale environment
```
