# CLI Usage

The CLI is `pipx`-shaped but container-backed. With no subcommand, `safe-whale` launches the Tkinter GUI.

```bash
safe-whale --help
safe-whale --version
safe-whale --diagnostics
safe-whale environment
```

## Global Options

Global options can appear before or after subcommands:

- `--dry-run` prints the Dockerfile, build command, run command, profile changes, or cleanup actions without performing them.
- `--engine docker|podman|nerdctl|finch` selects a container engine. If omitted, safe-whale auto-detects an installed engine.
- `--log-level CRITICAL|ERROR|WARNING|INFO|DEBUG|NOTSET` sets logging explicitly.
- `-v` / `--verbose` increases logging detail.
- `-q` / `--quiet` lowers logging detail for pipx CLI compatibility.
- `--no-history` skips appending run history.

## Run Once

Run a PyPI app once:

```bash
safe-whale run ruff -- --version
```

Use a different package spec but a specific entry point:

```bash
safe-whale run --spec rich-cli rich -- --help
```

Useful run/build options:

- `--entrypoint` chooses the executable inside the image.
- `--apt` / `--apt-package` adds Debian packages to the image build.
- `--interaction immediate|interactive|pipe` controls stdio behavior.
- `--stdin-file` displays redirected stdin for pipe-mode dry runs.
- `--mount host_path:container_path[:ro|rw]` bind mounts a host path.
- `--memory` / `--memory-mb` and `--cpus` set resource limits.
- `--network` allows runtime network access.
- `--block-network` runs with `--network none`.
- `--read-only` / `--writable` controls the container root filesystem.
- `--non-root` / `--root` controls the runtime user.
- `--no-new-privs` / `--allow-new-privs` controls `no-new-privileges`.
- `--cap-drop-all` / `--keep-caps` controls Linux capabilities.
- `--tmpfs-tmp` / `--no-tmpfs-tmp` controls `/tmp` tmpfs mounts.
- `--limit-pids` / `--no-limit-pids` controls the PID limit.

## Install Wrappers

Install a saved profile and wrapper:

```bash
safe-whale install ruff
```

`install` builds the image, then discovers the package's `console_scripts` / `gui_scripts` entry points and writes one
wrapper per command (so a package that ships several commands gets several wrappers). On Windows each command produces a
`.cmd` plus a `.ps1` companion. When run in a terminal, `install` first asks for the tool's usage pattern and whether to
use a read-only root filesystem; pass `--yes` (or `--no-input`) to skip the prompts and accept defaults plus any flags
given. `--skip-build` skips discovery and installs only the declared entry point.

Install without building the image first:

```bash
safe-whale install ruff --skip-build
```

Install into a specific wrapper directory:

```bash
safe-whale install ruff --wrapper-dir ~/.local/bin
```

Install multiple package specs:

```bash
safe-whale install ruff black
```

Single-package wrapper naming options:

- `--name` sets the saved profile name.
- `--launcher-name` sets the wrapper command name.
- `--suffix` appends a suffix to generated profile names.
- `--no-wrapper` saves/builds a profile without writing a wrapper.
- `--force` allows overwriting profile or wrapper metadata.
- `--yes` / `-y` (alias `--no-input`) skips interactive prompts and accepts defaults.

## Build Without Installing

```bash
safe-whale build ruff
```

`build` generates and builds the image without saving an installed wrapper profile.

## List, Rebuild, and Remove

```bash
safe-whale list
safe-whale list --json
safe-whale list --short
safe-whale list --catalog --query ruff
safe-whale profiles --json
safe-whale reinstall ruff
safe-whale reinstall-all
safe-whale upgrade ruff
safe-whale upgrade-all
safe-whale uninstall ruff
safe-whale uninstall-all
```

`upgrade` and `upgrade-all` currently rebuild installed profile images from the stored specs. They do not mutate a virtual environment because safe-whale does not create one for installed tools.

## Cleanup and Diagnostics

List managed assets:

```bash
safe-whale cleanup
```

Delete all safe-whale-managed assets:

```bash
safe-whale cleanup --all
```

Delete a specific asset by its id (run `safe-whale cleanup` first to see the ids; wrapper ids look like
`wrapper:<profile>:<command>`):

```bash
safe-whale cleanup wrapper:ruff:ruff
```

Other utility commands:

```bash
safe-whale ensurepath
safe-whale completions
safe-whale help install
```

Completion scripts are not bundled yet; `completions` currently prints guidance.
