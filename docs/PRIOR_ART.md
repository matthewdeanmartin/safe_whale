# Prior Art

`safe-whale` is not the first attempt to make command-line tools feel native while running them through containers. The closest existing projects already cover Docker-backed wrappers, tool-per-image catalogs, host-integrated development containers, and non-Docker Python tool runners.

The narrower gap for `safe-whale` is pipx-shaped installation of Python CLI packages from PyPI, backed by generated container images and host wrapper commands.

## Closest Matches

### Whalebrew

[Whalebrew](https://github.com/whalebrew/whalebrew) is the strongest prior art. It describes itself as Homebrew, but with Docker images, and creates native-feeling aliases for tools packaged as container images. A user can install something like `whalebrew/ffmpeg` and then run `ffmpeg` as a normal command.

The key difference is package source and build ownership. Whalebrew expects a container image package to exist. `safe-whale` starts from a Python package specification, generates a Dockerfile, builds the image, stores a profile, and can create a wrapper.

### Dockerized

[Dockerized](https://github.com/datastack-net/dockerized) provides an `npx`-like workflow for running popular command-line tools through Docker with `dockerized <command>`. It is close to ephemeral "run this tool in Docker" use and can fall back to Jessie Frazelle's Dockerfiles collection.

That is less focused on persistent pipx-style management: install, list, rebuild, upgrade, uninstall, and wrapper lifecycle around a PyPI package.

### Jessie Frazelle's Dockerfiles

[jessfraz/dockerfiles](https://github.com/jessfraz/dockerfiles) is a large collection of Dockerfiles for desktop and server tools. It is important prior art for the tool-per-image model and for the ecosystem that Dockerized builds on.

It is a library of images and recipes rather than a package-manager-like installer UX for Python command-line apps.

### Distrobox and Toolbx

[Distrobox](https://distrobox.it/) and [Toolbx](https://github.com/containers/toolbox) focus on host-integrated container environments for development, troubleshooting, and interactive shell work. They address the same broad desire to keep the host clean while still making tools convenient.

They are closer to containerized development environments than one CLI app per generated image. `safe-whale` is intentionally narrower: each saved profile represents a tool command, runtime policy, generated image, and optional wrapper.

### Nixery

[Nixery](https://github.com/tazjin/nixery) is a Docker-compatible registry that builds and serves container images from Nix packages on demand. Package names are encoded in the image path, which makes it conceptually relevant to ad-hoc tool images.

The package universe and UX are different. Nixery is Nix-first and registry-first; `safe-whale` is PyPI-first and pipx-shaped.

### uv, uvx, and pipx

[uv](https://github.com/astral-sh/uv) provides `uvx` / `uv tool run` for ephemeral Python CLI execution and `uv tool install` for persistent tool installation, similar to [pipx](https://github.com/pypa/pipx). These are the strongest non-container competitors for Python CLI workflows.

They are excellent when Python virtual environment isolation is enough. `safe-whale` is aimed at cases where the user wants a stronger boundary from host Python state, native dependencies, shell state, or host package manager churn.

## Open Niche

The specific niche that still appears useful is:

```bash
safe-whale install ruff
safe-whale install git+https://example.com/project.git
safe-whale run black -- .
ruff check .
safe-whale upgrade-all
safe-whale uninstall ruff
```

with a tool that:

- resolves Python packages from PyPI or direct package specifications;
- builds or reuses a per-tool container image;
- creates host wrappers in a user-controlled wrapper directory;
- mounts the current working directory deliberately;
- handles UID/GID, Windows shell behavior, cache directories, environment variables, stdin/stdout, and secrets carefully;
- supports one-shot `pipx run`-style execution;
- can later move to faster image builds, for example by using uv inside generated images.

## Positioning

The safest positioning is not "inventing containerized CLI tools." Whalebrew, Dockerized, Distrobox, Toolbx, Nixery, pipx, and uv already cover large parts of the landscape.

The sharper claim is:

> pipx-style Python CLI app installation with container-backed isolation.

Or, more directly:

> Whalebrew requires container images. pipx and uv require host Python environments. `safe-whale` takes Python package specs and gives you pipx-like commands backed by generated container images.

Avoid claiming that this is automatically "more secure than pipx." Docker sockets, bind mounts, home-directory access, environment variables, and secrets all complicate that claim. Better claims are:

- keeps Python, native dependencies, Node, Java, Rust, and system packages off the host;
- creates normal commands that run inside per-tool containers;
- supports hardened runtime defaults such as read-only roots, non-root execution, dropped capabilities, resource limits, and optional network blocking;
- is designed around Windows, Linux, and CI wrapper behavior rather than assuming a single Unix shell path.

## Design Lessons

The hard part is usually not producing a minimal Dockerfile for a Python CLI. A basic generated image can be simple:

```dockerfile
FROM python:3.13-slim
RUN pip install --no-cache-dir cowsay
ENTRYPOINT ["cowsay"]
```

A future uv-backed image could use Astral's [uv Docker integration](https://docs.astral.sh/uv/guides/integration/docker/) and install tools into `/usr/local/bin`:

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim
RUN uv tool install cowsay
ENTRYPOINT ["cowsay"]
```

The harder work is wrapper behavior. The wrapper needs to translate a normal host command into a container run while preserving expected CLI behavior:

```bash
docker run --rm \
  -v "$PWD:/workdir" \
  -w /workdir \
  -v "$HOME/.cache/safe-whale/ruff:/cache" \
  -e XDG_CACHE_HOME=/cache \
  --user "$(id -u):$(id -g)" \
  safe-whale/ruff:latest "$@"
```

Windows path translation, Git Bash, TTY handling, stdin/stdout, current directory mounts, writable cache directories, and secret handling are the real product surface.
