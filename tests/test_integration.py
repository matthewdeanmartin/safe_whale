"""Integration tests — require a running Docker daemon.

Run with:  pytest -m integration
Skip with: pytest -m "not integration"  (default in CI without Docker)
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from safe_whale.container import generate_dockerfile, image_tag
from safe_whale.models import RunConfig
from safe_whale.runner import run_container


def _docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        subprocess.run(["docker", "info"], check=True, capture_output=True, timeout=10)
        return True
    except (FileNotFoundError, subprocess.SubprocessError):
        return False


requires_docker = pytest.mark.skipif(not _docker_available(), reason="Docker daemon not available")
pytestmark = pytest.mark.integration


def _run(cfg: RunConfig) -> tuple[int | None, str]:
    lines: list[str] = []
    result = run_container(cfg, on_output=lines.append)
    return result.exit_code, "".join(lines)


def _base_cfg(**kwargs: object) -> RunConfig:
    defaults: dict[str, object] = {
        "package_spec": "httpie",
        "entrypoint": "http",
        "cli_args": "--version",
        "non_root": False,
        "read_only": False,
        "cap_drop_all": False,
        "tmpfs_tmp": False,
        "no_new_privs": False,
        "limit_pids": False,
    }
    defaults.update(kwargs)
    return RunConfig(**defaults)  # type: ignore[arg-type]


@requires_docker
class TestBasicRun:
    def test_httpie_version(self):
        cfg = _base_cfg()
        exit_code, output = _run(cfg)
        assert exit_code == 0
        assert any(c.isdigit() for c in output)

    def test_ruff_version(self):
        cfg = _base_cfg(package_spec="ruff", entrypoint="ruff", cli_args="--version")
        exit_code, output = _run(cfg)
        assert exit_code == 0
        assert "ruff" in output.lower()

    def test_black_version(self):
        cfg = _base_cfg(package_spec="black", entrypoint="black", cli_args="--version")
        exit_code, output = _run(cfg)
        assert exit_code == 0
        assert "black" in output.lower()


@requires_docker
class TestSecurityFlags:
    def test_non_root_uid(self):
        """Process inside container should run as uid 10001."""
        # Build an image with httpie, use python as the entrypoint to check uid.
        # The Dockerfile ENTRYPOINT must match what we run.
        cfg = _base_cfg(
            package_spec="httpie",
            entrypoint="python",
            cli_args="-c 'import os; print(os.getuid())'",
            non_root=True,
            read_only=False,
            cap_drop_all=False,
        )
        exit_code, output = _run(cfg)
        assert exit_code == 0, output
        assert "10001" in output

    def test_read_only_blocks_root_writes(self):
        """With --read-only, writing to / should fail (non-zero exit)."""
        cfg = _base_cfg(
            package_spec="httpie",
            entrypoint="python",
            cli_args='-c \'open("/canary", "w")\'',
            non_root=False,
            read_only=True,
            tmpfs_tmp=True,
            cap_drop_all=False,
        )
        exit_code, _ = _run(cfg)
        assert exit_code != 0, "Expected write to / to fail with read-only FS"

    def test_cap_drop_all_doesnt_break_python(self):
        """Dropping all caps should still let basic Python run."""
        cfg = _base_cfg(
            package_spec="httpie",
            entrypoint="python",
            cli_args="-c 'print(1+1)'",
            non_root=False,
            read_only=False,
            cap_drop_all=True,
        )
        exit_code, output = _run(cfg)
        assert exit_code == 0
        assert "2" in output

    def test_memory_limit_respected(self):
        cfg = _base_cfg(memory_mb=256)
        exit_code, _ = _run(cfg)
        assert exit_code == 0

    def test_tmpfs_tmp_writable_under_read_only(self):
        """/tmp must be writable via tmpfs even when the FS is read-only."""
        cfg = _base_cfg(
            package_spec="httpie",
            entrypoint="python",
            cli_args='-c \'open("/tmp/t","w").write("ok"); print(open("/tmp/t").read())\'',
            non_root=False,
            read_only=True,
            tmpfs_tmp=True,
            cap_drop_all=False,
        )
        exit_code, output = _run(cfg)
        assert exit_code == 0, output
        assert "ok" in output

    def test_pids_limit(self):
        cfg = _base_cfg(limit_pids=True)
        exit_code, _ = _run(cfg)
        assert exit_code == 0


@requires_docker
class TestDockerfileGeneration:
    def test_generated_dockerfile_builds(self, tmp_path: object) -> None:
        from pathlib import Path

        cfg = RunConfig(package_spec="httpie", entrypoint="http", non_root=True)
        df_path = Path(str(tmp_path)) / "Dockerfile"
        df_path.write_text(generate_dockerfile(cfg), encoding="utf-8")
        tag = image_tag(cfg) + "-itest"

        result = subprocess.run(
            ["docker", "build", "-t", tag, str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        subprocess.run(["docker", "rmi", tag], capture_output=True, check=False)

    def test_non_root_dockerfile_runs_as_10001(self, tmp_path: object) -> None:
        from pathlib import Path

        cfg = RunConfig(
            package_spec="httpie",
            entrypoint="python",
            cli_args="-c 'import os; print(os.getuid())'",
            non_root=True,
            read_only=False,
            cap_drop_all=False,
        )
        df_path = Path(str(tmp_path)) / "Dockerfile"
        df_path.write_text(generate_dockerfile(cfg), encoding="utf-8")
        tag = image_tag(cfg) + "-itest3"

        build = subprocess.run(
            ["docker", "build", "-t", tag, str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        assert build.returncode == 0, build.stderr

        run = subprocess.run(
            ["docker", "run", "--rm", "--user", "10001:10001", tag, "-c", "import os; print(os.getuid())"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert run.returncode == 0, run.stderr + run.stdout
        assert "10001" in run.stdout
        subprocess.run(["docker", "rmi", tag], capture_output=True, check=False)
