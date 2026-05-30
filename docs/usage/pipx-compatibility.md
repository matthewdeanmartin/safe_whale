# pipx Compatibility

`safe-whale` borrows command names from `pipx` where they make sense for container-backed Python tools. The goal is familiar muscle memory, not identical internals.

## Mental Model

| pipx | safe-whale |
| --- | --- |
| Installs each app into a managed virtual environment. | Builds each app into a managed container image. |
| Creates app wrappers that run venv entry points. | Creates wrappers that run hardened containers. |
| Uses a selected Python interpreter for venvs. | Uses `python:3.13-slim` in generated Dockerfiles today. |
| Uses pip inside managed venvs. | Uses pip during image build, then runs the resulting image. |
| App isolation is Python environment isolation. | App isolation is container runtime isolation plus hardening flags. |

## Commands With Container-Backed Behavior

- `run`: build if needed and run an app.
- `install`: save a profile, optionally build the image, discover the package's entry-point commands, and write a
  wrapper per command.
- `install-all`: install packages found in a `pipx list --json` metadata file.
- `list`: list saved profiles, or catalog entries with `--catalog`.
- `profiles`: list saved profiles.
- `uninstall` / `uninstall-all`: remove profiles, wrappers, generated Dockerfiles, and optionally images.
- `reinstall` / `reinstall-all`: rebuild installed profile images.
- `upgrade` / `upgrade-all`: rebuild profile images from the stored package specs.
- `ensurepath`: report whether the wrapper directory is on `PATH`.
- `environment`: print safe-whale storage and wrapper locations.
- `cleanup`: list or delete safe-whale-managed assets.
- `help`: show top-level or command-specific help.

## Recognized Compatibility Commands

These command names are recognized so scripts and users get a deliberate safe-whale response instead of an unknown-command error:

- `inject`
- `uninject`
- `pin`
- `unpin`
- `runpip`
- `interpreter`
- `upgrade-shared`

With `--dry-run`, they explain that they are recognized but have no safe-whale action yet. Without `--dry-run`, they return a usage-style error.

## pip Options Accepted But Ignored

Some pipx/pip-style options are accepted on relevant commands but hidden from help because they do not yet change container behavior:

- `--include-deps`
- `--include-apps`
- `--system-site-packages`
- `--python`
- `--fetch-python`
- `--fetch-missing-python`
- `--preinstall`
- `--index-url` / `-i`
- `--editable` / `-e`
- `--pip-args`
- `--backend`
- `--global`

## Practical Differences

- Builds require a container engine and usually network access.
- Installed wrappers start containers, so first-run and cold-start costs differ from pipx venv entry points.
- Runtime writes are blocked by default except for tmpfs mounts and explicit bind mounts.
- Runtime network access is allowed by default today; pass `--block-network` when a tool does not need network access.
- Native host integration is intentionally narrower than pipx. Tools that need direct access to host interpreters, host package managers, shells, daemons, sockets, or full-screen terminal behavior may need explicit mounts, interactive mode, or a different workflow.
- Browser Pyodide/PyScript experiments are not a pipx compatibility layer.
