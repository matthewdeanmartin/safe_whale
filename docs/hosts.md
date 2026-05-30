# Host Runtimes

`safe-whale` has two runtime families:

- Container engines for the main goal: run PyPI command-line tools in hardened Docker/Podman-style containers.
- Browser Python for PyScript/Pyodide experiments that run inside the browser sandbox.

Browser Python is useful for browser-compatible Python snippets and pure-Python packages. It is not a replacement for Docker/Podman and is not expected to run arbitrary PyPI CLI tools.

Official references:

- Docker Desktop overview and installers: <https://docs.docker.com/desktop/>
- Docker Engine on Linux: <https://docs.docker.com/engine/install/>
- Podman installation: <https://podman.io/docs/installation>
- PyScript configuration: <https://docs.pyscript.net/2026.3.1/user-guide/configuration/>
- Pyodide packages: <https://pyodide.org/en/stable/usage/packages-in-pyodide.html>

## Which Runtime Should I Pick?

Use Docker if you want the path of least resistance. It is the primary runtime exercised by `safe-whale`.

Use Podman if you already prefer rootless containers or want a daemonless Linux-native workflow. On Windows and macOS, Podman still uses a small Linux VM called a Podman machine.

Use Browser Python if you want PyScript or direct Pyodide in a browser sandbox. The default demo installs `snowballstemmer` and runs it on page load so package installation is visible.

## Runtime Matrix

| Runtime | Windows | macOS | Linux | Recommended for safe-whale now |
| --- | --- | --- | --- | --- |
| Docker | Docker Desktop with WSL 2 backend | Docker Desktop | Docker Engine or Docker Desktop | Yes |
| Podman | Podman machine over WSL 2 | Podman machine VM | Native distro package | Yes, secondary |
| PyScript / Pyodide | Browser with network access to runtime/package assets | Browser with network access to runtime/package assets | Browser with network access to runtime/package assets | Experimental |

## Windows

### Docker on Windows

Install Docker Desktop for Windows from Docker’s official installer. Docker Desktop includes Docker Engine, CLI, Build, Compose, and the Windows integration pieces.

Recommended checks:

```powershell
docker version
docker info
docker run --rm hello-world
```

Notes:

- Use the Linux containers / WSL 2 backend for `safe-whale`.
- Docker Desktop and Podman can both be installed, but do not let both fight over Docker-compatible sockets unless you deliberately want that compatibility layer.
- The Catalog tab has the Engine selector because it controls container builds and runs.

```powershell
uv run safe-whale --engine docker
```

### Podman on Windows

Install Podman Desktop or the Podman CLI from the official Podman instructions. On Windows, Podman uses a WSL 2-backed Podman machine.

Typical setup:

```powershell
podman machine init
podman machine start
podman info
```

Then launch safe-whale explicitly:

```powershell
uv run safe-whale --engine podman
```

## macOS

### Docker on macOS

Install Docker Desktop for Mac. Docker provides separate downloads for Apple silicon and Intel Macs.

Verify:

```bash
docker version
docker info
docker run --rm hello-world
```

Then:

```bash
uv run safe-whale --engine docker
```

### Podman on macOS

Install Podman from the official installer. Homebrew can work, but Podman’s own docs recommend the official installer path for stability.

Initialize and start a Podman machine:

```bash
podman machine init
podman machine start
podman info
```

Then:

```bash
uv run safe-whale --engine podman
```

## Linux

### Docker on Linux

Install Docker Engine using Docker’s distro-specific docs. Distribution packages may also exist, but Docker’s packages are the reference path.

Verify:

```bash
docker version
docker info
docker run --rm hello-world
```

If your user cannot access Docker:

```bash
sudo usermod -aG docker "$USER"
```

Then log out and back in. Consider your local security policy before adding users to the Docker group; Docker access is effectively powerful host access.

### Podman on Linux

Install Podman from your distribution packages. Common examples:

```bash
# Debian / Ubuntu
sudo apt-get update
sudo apt-get install -y podman

# Fedora
sudo dnf install -y podman

# Arch / Manjaro
sudo pacman -S podman
```

Verify:

```bash
podman info
podman run --rm docker.io/library/hello-world
```

Then:

```bash
uv run safe-whale --engine podman
```

## Browser Python Notes

Pyodide is CPython compiled to WebAssembly/Emscripten. PyScript is a browser framework for building Python-backed web pages and can use Pyodide as one of its runtimes.

For `safe-whale`, Browser Python generates either:

- a direct Pyodide terminal-style page, or
- a PyScript page with a `packages` configuration.

What works:

- Python snippets and scripts.
- Packages included in Pyodide via `pyodide.loadPackage`.
- Pure-Python wheels from PyPI through `micropip.install`.
- Some binary packages already built for Pyodide.
- Browser UI code designed for Pyodide/PyScript.

What does not behave like Docker:

- Arbitrary PyPI command-line tools.
- TUI/curses apps.
- Subprocess-heavy tools.
- Native wheels unless they have a Pyodide/Emscripten build.
- Tkinter apps.
- Browser-hosted local web servers.

## How This Maps to safe-whale

Current:

- `docker`, `podman`, `nerdctl`, and `finch` can be detected as container engines.
- Docker is the most tested path.
- The Catalog tab owns the Engine selector because it controls container builds/runs.
- Browser Python generates and opens browser-hosted PyScript/Pyodide scaffolds.
- Cleanup tracks and deletes only safe-whale-created images, Dockerfiles, and wrappers.
