"""Subprocess management: build images and run containers."""

from __future__ import annotations

from contextlib import ExitStack
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import IO

from safe_whale.container import build_run_argv, generate_dockerfile, image_tag
from safe_whale.models import ManagedAsset, RunConfig, RunResult

OutputCallback = Callable[[str], None]
ProcCallback = Callable[["subprocess.Popen[str]"], None]


def _stream_output(proc: subprocess.Popen[str], callback: OutputCallback) -> tuple[str, str]:
    """Read stdout and stderr from proc, calling callback for each line."""
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    def read_stream(stream: IO[str] | None, lines: list[str]) -> None:
        if stream is None:
            return
        for line in stream:
            lines.append(line)
            callback(line)

    t_out = threading.Thread(target=read_stream, args=(proc.stdout, stdout_lines), daemon=True)
    t_err = threading.Thread(target=read_stream, args=(proc.stderr, stderr_lines), daemon=True)
    t_out.start()
    t_err.start()
    t_out.join()
    t_err.join()
    proc.wait()

    return "".join(stdout_lines), "".join(stderr_lines)


def _write_dockerfile(cfg: RunConfig, directory: Path) -> None:
    """Write a Dockerfile into directory."""
    (directory / "Dockerfile").write_text(generate_dockerfile(cfg), encoding="utf-8")


def run_container(
    cfg: RunConfig,
    on_output: OutputCallback | None = None,
    dockerfile_dir: Path | None = None,
    build_only: bool = False,
    on_proc: ProcCallback | None = None,
) -> RunResult:
    """Build a Docker image from cfg, then (unless build_only) run it.

    dockerfile_dir: use this directory for the build context instead of a
    fresh temp dir.
    build_only: stop after the build phase; do not docker-run. Used when the
    caller will open a terminal window for the actual run.
    on_proc: called with each Popen object as soon as it is created, so the
    caller can kill it (e.g. from a Cancel button).
    """
    if on_output is None:

        def on_output(_line: str) -> None:
            pass

    started = datetime.now()
    tag = image_tag(cfg)
    build_cmd_str = ""
    temp_build_dir: Path | None = None
    result: RunResult

    try:
        # ── Build phase ───────────────────────────────────────────────────────
        if dockerfile_dir is None:
            temp_build_dir = Path(tempfile.mkdtemp(prefix="SAFE_WHALE_"))
            _write_dockerfile(cfg, temp_build_dir)
            dockerfile_dir = temp_build_dir

        build_argv = [cfg.engine, "build", "-t", tag, str(dockerfile_dir)]
        build_cmd_str = " ".join(shlex.quote(a) for a in build_argv)
        on_output(f"$ {build_cmd_str}\n")

        with subprocess.Popen(
            build_argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        ) as build_proc:
            if on_proc:
                on_proc(build_proc)
            build_stdout, _ = _stream_output(build_proc, on_output)

        if build_proc.returncode != 0:
            result = RunResult(
                config=cfg,
                timestamp=started,
                exit_code=build_proc.returncode,
                stdout=build_stdout,
                stderr="",
                command=build_cmd_str,
                image_ready=False,
            )
        else:
            _record_image_asset(cfg, tag, started)

        if build_proc.returncode == 0 and build_only:
            result = RunResult(
                config=cfg,
                timestamp=started,
                exit_code=0,
                stdout=build_stdout,
                stderr="",
                command=build_cmd_str,
                image_ready=True,
            )
        elif build_proc.returncode == 0:
            # ── Run phase ─────────────────────────────────────────────────────
            run_argv = build_run_argv(cfg, tag)
            run_cmd_str = " ".join(shlex.quote(a) for a in run_argv)
            if cfg.interaction == "pipe" and cfg.stdin_file:
                run_cmd_str = f"{run_cmd_str} < {shlex.quote(cfg.stdin_file)}"
            on_output(f"$ {run_cmd_str}\n")

            with ExitStack() as stack:
                stdin_handle: IO[str] | None = None
                if cfg.interaction == "pipe" and cfg.stdin_file:
                    stdin_handle = stack.enter_context(
                        Path(cfg.stdin_file).open("r", encoding="utf-8", errors="replace")
                    )
                proc = stack.enter_context(
                    subprocess.Popen(
                        run_argv,
                        stdin=stdin_handle,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                    )
                )
                if on_proc:
                    on_proc(proc)
                stdout, stderr = _stream_output(proc, on_output)
            result = RunResult(
                config=cfg,
                timestamp=started,
                exit_code=proc.returncode,
                stdout=stdout,
                stderr=stderr,
                command=run_cmd_str,
                image_ready=True,
            )
    except FileNotFoundError as exc:
        missing_target = cfg.stdin_file if cfg.interaction == "pipe" and cfg.stdin_file else cfg.engine
        target_kind = "input file" if cfg.interaction == "pipe" and cfg.stdin_file else "container engine"
        msg = f"Error: {target_kind} '{missing_target}' not found.\n{exc}\n"
        on_output(msg)
        result = RunResult(
            config=cfg,
            timestamp=started,
            exit_code=127,
            stdout="",
            stderr=msg,
            command=build_cmd_str,
            image_ready=False,
        )
    finally:
        if temp_build_dir is not None:
            shutil.rmtree(temp_build_dir, ignore_errors=True)

    return result


def _record_image_asset(cfg: RunConfig, tag: str, timestamp: datetime) -> None:
    """Track a successfully built safe-whale image for managed cleanup."""
    from safe_whale.storage import upsert_managed_asset

    upsert_managed_asset(
        ManagedAsset(
            asset_id=f"image:{cfg.engine}:{tag}",
            asset_type="image",
            engine=cfg.engine,
            name=tag,
            location=tag,
            source=cfg.package_spec,
            created_at=timestamp,
            last_used_at=timestamp,
            state="present",
        )
    )


def run_in_terminal(cfg: RunConfig, tag: str) -> None:
    """Launch `docker run <tag>` in a new system terminal window."""
    if cfg.interaction == "pipe":
        raise ValueError("Pipe mode is not supported in terminal launches.")
    run_argv = build_run_argv(cfg, tag)

    if sys.platform == "win32":
        _run_in_terminal_windows(run_argv)
    elif sys.platform == "darwin":
        _run_in_terminal_macos(run_argv)
    else:
        _run_in_terminal_linux(run_argv)


def _find_wt() -> str | None:
    """Return the path to wt.exe, checking the AppX alias dir that shutil.which misses."""
    import os
    import pathlib
    import shutil as _shutil

    if _shutil.which("wt"):
        return "wt"
    # Windows Terminal installs as an AppX package; its execution alias lives here
    # but this directory is not on PATH in subprocesses launched from Git Bash / uv.
    alias = pathlib.Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WindowsApps" / "wt.exe"
    if alias.exists():
        return str(alias)
    return None


def _run_in_terminal_windows(run_argv: list[str]) -> None:
    wt = _find_wt()
    if wt:
        subprocess.Popen([wt, "new-tab", "--", *run_argv])  # pylint: disable=consider-using-with
    else:
        CREATE_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010)
        subprocess.Popen(  # pylint: disable=consider-using-with
            ["cmd", "/k", *run_argv],
            creationflags=CREATE_NEW_CONSOLE,
        )


def _run_in_terminal_macos(run_argv: list[str]) -> None:
    cmd_str = " ".join(shlex.quote(a) for a in run_argv)
    escaped = cmd_str.replace("\\", "\\\\").replace('"', '\\"')
    apple_script = f'tell application "Terminal" to do script "{escaped}"'
    subprocess.Popen(["osascript", "-e", apple_script])  # pylint: disable=consider-using-with


def _run_in_terminal_linux(run_argv: list[str]) -> None:
    import shutil as _shutil2

    for term in ["gnome-terminal", "xterm", "x-terminal-emulator", "konsole"]:
        if _shutil2.which(term):
            if term == "gnome-terminal":
                subprocess.Popen([term, "--", *run_argv])  # pylint: disable=consider-using-with
            else:
                subprocess.Popen([term, "-e", *run_argv])  # pylint: disable=consider-using-with
            return
