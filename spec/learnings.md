# safe-whale: Engineering Learnings

Lessons learned through actually running containers during development.
Each entry has a root cause and the fix applied.

______________________________________________________________________

## 1. `--read-only` breaks pip in run-mode

**Symptom:** `pip install` fails with `[Errno 30] Read-only file system: '/root/.local'`.

**Root cause:** `--read-only` makes the entire container filesystem read-only at the Docker
level, including `/usr/local/lib/python3.13/site-packages`. pip needs to write there to
install packages. There is no way to install-on-the-fly into a read-only container.

**Fix:** Switch to a Dockerfile-always model. pip installs as root during `docker build`
(writable layer), and `--read-only` is only applied at `docker run` time, after everything
is already installed. This is the correct Docker idiom.

______________________________________________________________________

## 2. `--user 65532:65532` + `apt-get`/`pip` = permission denied

**Symptom:** `E: Could not open lock file /var/lib/apt/lists/lock - open (13: Permission denied)`.

**Root cause:** `--user` applies to the entire container process from PID 1. If you pass
it on `docker run`, even the shell that runs `apt-get update && pip install ...` runs as
that UID. Neither `apt` nor `pip` can write to system paths as a non-root user.

**Fix:** Same as above — use Dockerfile mode. Install as root during build, switch user
with `USER appuser` in the Dockerfile before the `ENTRYPOINT`. `--user` on `docker run`
then overrides correctly at runtime, after install is complete.

______________________________________________________________________

## 3. `su` fails with `--cap-drop=ALL`

**Symptom:** `su: cannot set groups: Operation not permitted` when trying to drop privs
inside the container shell script.

**Root cause:** `su` needs `CAP_SETUID` and `CAP_SETGID` to change user identity.
`--cap-drop=ALL` strips both. There is no way to use `su` or `sudo` in a cap-dropped
container without re-granting those specific capabilities, which defeats the purpose.

**Fix:** Don't use `su` inside the container. Set the user at the Dockerfile level with
`USER appuser`. `--cap-drop=ALL` at `docker run` time is then safe and correct.

______________________________________________________________________

## 4. TUI apps need `-t` (TTY) and `TERM`

**Symptom:** `_curses.error: setupterm: could not find terminal` when running babi or
other curses-based apps.

**Root cause:** Two separate issues:

- Without `-t`, Docker does not allocate a pseudo-TTY. The container's stdout is a pipe,
  not a terminal. `curses.initscr()` calls `setupterm()` which requires a real TTY fd.
- Even with `-t`, the `TERM` environment variable is not inherited from the host. The
  container starts with `TERM` unset or `"unknown"`, and `setupterm` cannot find a
  terminfo entry for that.

**Fix:** For `interaction="interactive"`, add both `-it` (stdin + TTY) and
`-e TERM=xterm-256color` to the `docker run` command. `xterm-256color` is available in
the `python:3.13-slim` base image's terminfo database.

**Corollary:** TUI apps cannot stream output into the safe-whale output panel. The panel
receives bytes from a pipe; a curses app writes escape sequences to a TTY. These are
fundamentally incompatible. TUI apps must always run in a separate terminal window.

______________________________________________________________________

## 5. Catalog entries should carry their interaction mode

**Lesson:** Whether an app is a one-shot CLI (`httpie --help`) or a full-screen TUI
(`babi`, `glances`, `visidata`) is a property of the *tool*, not the user's choice.
Storing `interaction` on `CatalogEntry` means the right mode is set automatically when
a user picks an app from the catalog, and the ▶ Run button auto-routes TUI apps to
"Run in Terminal" with an explanation rather than silently producing a broken output.

______________________________________________________________________

## 6. ENTRYPOINT is already set — don't repeat it in `docker run` args

**Symptom:** `python: can't open file '/home/appuser/python'` — Docker was running
`python python -c '...'`.

**Root cause:** `build_run_argv` was appending `[entrypoint] + shlex.split(cli_args)`
after the image tag. But the image already has `ENTRYPOINT ["python"]` baked in. Docker
concatenates them: `ENTRYPOINT + CMD`, so the entrypoint appeared twice.

**Fix:** Only append `shlex.split(cli_args)` after the tag, never the entrypoint itself.
The entrypoint is the image's concern; `docker run <tag> <args>` passes args *to* the
entrypoint, not repeats it.

______________________________________________________________________

## 7. `shutil.which("wt")` returns `None` on Windows even when `wt` is installed

**Symptom:** "Run in Terminal" does not open a new terminal window. Falls through to
`cmd /k`, which may also not appear depending on how the Python process was launched
(e.g. from uv or Git Bash without a console).

**Root cause:** Windows Terminal (`wt.exe`) is installed as an **AppX package** with an
**App Execution Alias** at:

```
%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe
```

This directory is on the `PATH` for interactive user shells (Explorer, cmd.exe launched
normally) but **not** inherited by subprocess environments spawned from Git Bash, uv, or
other non-standard launchers. `shutil.which("wt")` therefore returns `None`, so the code
falls back to `cmd /k`. `cmd` launched with `CREATE_NEW_CONSOLE` from a Tkinter process
may open a console window that immediately closes, or may not appear at all.

**Fix needed:** Explicitly check the `%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe` path
as a fallback before concluding `wt` is unavailable. Something like:

```python
import os, pathlib

def _find_wt() -> str | None:
    # shutil.which misses the AppX alias location
    if shutil.which("wt"):
        return "wt"
    alias = pathlib.Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WindowsApps" / "wt.exe"
    if alias.exists():
        return str(alias)
    return None
```

Then use `subprocess.Popen([wt_path, "new-tab", "--"] + run_argv)`.

______________________________________________________________________

## 8. Pip install warnings don't indicate failure

Running pip as root inside a container produces:

```
WARNING: Running pip as the 'root' user can result in broken permissions...
```

This is cosmetic. Add `--root-user-action=ignore` to the `pip install` command in the
Dockerfile to suppress it. It is correct to install as root inside a container build
context — the warning is aimed at host-system pip usage.

______________________________________________________________________

## 9. Docker layer caching makes the Dockerfile model fast after first run

The initial `docker build` for a package takes 10–60 seconds (network + install).
Subsequent runs with the same `package_spec` + security config are instant because the
image tag is derived from the Dockerfile content hash — Docker's layer cache handles the
rest. This makes the "always Dockerfile" approach practical even for casual use.

______________________________________________________________________

## 10. `sh -lc '...'` one-liners are fragile and OS-dependent

The original design built a `sh -lc 'apt-get update && pip install ... && exec app'`
command string, then passed it as a single argument. Problems encountered:

- Windows Terminal / `cmd.exe` mangles POSIX single-quote escaping
- Shell quoting of the inner script is error-prone (nested quotes, `$` expansion)
- `--read-only` and `--user` cannot both be set (write needed for install, user change
  needs caps)
- `su` to drop privs requires caps that `--cap-drop=ALL` removes

**All of these go away** with the Dockerfile-always model. The Dockerfile is a static
file with no quoting concerns, `docker build` handles the install as root with full write
access, and `docker run` applies hardening flags to the already-installed image.
