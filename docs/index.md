# safe-whale

`safe-whale` runs Python command-line tools in hardened container images and can install wrapper commands for repeated use. It is intentionally close to `pipx` in vocabulary, but the isolation boundary is a container image instead of a Python virtual environment.

Use `safe-whale` when you want to try or keep a PyPI CLI while avoiding direct installation into your user Python environment.

## Current Feature Set

- Tkinter UI for catalog discovery, saved profiles, launch wrappers, history, cleanup, and browser Python experiments.
- CLI commands for one-shot runs, installs, rebuilds, listing, uninstalling, cleanup, environment diagnostics, and wrapper PATH guidance.
- Dockerfile generation with deterministic image tags.
- Runtime hardening for read-only roots, non-root execution, no-new-privileges, dropped capabilities, process, CPU, and memory limits, optional network blocking, and optional bind mounts.
- Entry-point discovery that installs one wrapper per `console_scripts` / `gui_scripts` command, pipx-style.
- `.cmd` plus `.ps1` wrappers on Windows and POSIX shell wrappers elsewhere.
- Local profile, history, generated Dockerfile, and managed-asset storage under the safe-whale data directory.
- Browser-hosted PyScript and Pyodide scaffolds for browser-compatible Python experiments.

## Status

This is early v2 work. Docker is the most exercised container path. Podman, nerdctl, and Finch are detected and can be selected, but they have a smaller test surface today.

Browser Python is experimental and separate from the container workflow. It can run browser-compatible Python and pure-Python packages, but it is not a general replacement for container-backed PyPI CLI tools.

## Start Here

- [Installation](installation.md)
- [CLI usage](usage/cli.md)
- [pipx compatibility](usage/pipx-compatibility.md)
- [Host runtime setup](hosts.md)
- [Prior art](PRIOR_ART.md)
