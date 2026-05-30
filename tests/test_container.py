"""Tests for container command builder — no Docker required."""

from safe_whale.container import (
    _base_project,
    build_display_command,
    build_run_argv,
    generate_dockerfile,
    image_tag,
)
from safe_whale.models import RunConfig


def _cfg(**kwargs: object) -> RunConfig:
    defaults: dict[str, object] = dict(
        package_spec="httpie==3.2.2",
        entrypoint="http",
        engine="docker",
    )
    defaults.update(kwargs)
    return RunConfig(**defaults)  # type: ignore[arg-type]


class TestBaseProject:
    def test_simple(self):
        assert _base_project("httpie") == "httpie"

    def test_version_pin(self):
        assert _base_project("httpie==3.2.2") == "httpie"

    def test_extras(self):
        assert _base_project("yt-dlp[websockets]") == "yt-dlp"

    def test_complex(self):
        assert _base_project("mypy>=1.0,<2.0") == "mypy"


class TestBuildRunArgv:
    def test_engine_and_run(self):
        argv = build_run_argv(_cfg(), "some-tag")
        assert argv[0] == "docker"
        assert argv[1] == "run"

    def test_tag_present(self):
        argv = build_run_argv(_cfg(), "my-tag")
        assert "my-tag" in argv

    def test_non_root_user_flag(self):
        argv = build_run_argv(_cfg(non_root=True), "tag")
        assert "--user" in argv
        assert "10001:10001" in argv

    def test_no_non_root(self):
        argv = build_run_argv(_cfg(non_root=False), "tag")
        assert "--user" not in argv

    def test_read_only(self):
        argv = build_run_argv(_cfg(read_only=True), "tag")
        assert "--read-only" in argv

    def test_read_only_off(self):
        argv = build_run_argv(_cfg(read_only=False), "tag")
        assert "--read-only" not in argv

    def test_block_network(self):
        argv = build_run_argv(_cfg(block_network=True), "tag")
        assert "--network" in argv
        assert "none" in argv

    def test_memory_limit(self):
        argv = build_run_argv(_cfg(memory_mb=512), "tag")
        assert "512m" in argv

    def test_cli_args_appended_not_entrypoint(self):
        # Entrypoint is baked into the image; only cli_args appear after the tag.
        argv = build_run_argv(_cfg(cli_args="--version"), "tag")
        assert "--version" in argv
        # The entrypoint itself should NOT be re-appended
        tag_idx = argv.index("tag")
        assert argv[tag_idx + 1] == "--version"

    def test_interactive_cli_args_still_reach_entrypoint(self):
        argv = build_run_argv(
            _cfg(
                package_spec="babi",
                entrypoint="babi",
                interaction="interactive",
                cli_args="notes.txt",
            ),
            "tag",
        )
        assert "-it" in argv
        tag_idx = argv.index("tag")
        assert argv[tag_idx + 1] == "notes.txt"

    def test_pipe_mode_attaches_stdin(self):
        argv = build_run_argv(
            _cfg(
                interaction="pipe",
                stdin_file=r"C:\input\data.json",
                cli_args="--from-stdin",
            ),
            "tag",
        )
        assert "-i" in argv
        tag_idx = argv.index("tag")
        assert argv[tag_idx + 1] == "--from-stdin"


class TestGenerateDockerfile:
    def test_contains_from(self):
        df = generate_dockerfile(_cfg())
        assert "FROM python:3.13-slim" in df

    def test_contains_package(self):
        df = generate_dockerfile(_cfg())
        assert "httpie==3.2.2" in df

    def test_root_user_action_flag(self):
        df = generate_dockerfile(_cfg())
        assert "--root-user-action=ignore" in df

    def test_non_root_user(self):
        df = generate_dockerfile(_cfg(non_root=True))
        assert "appuser" in df

    def test_root_no_user(self):
        df = generate_dockerfile(_cfg(non_root=False))
        assert "appuser" not in df

    def test_entrypoint(self):
        df = generate_dockerfile(_cfg())
        assert '"http"' in df

    def test_interactive_uses_selected_entrypoint(self):
        df = generate_dockerfile(_cfg(package_spec="babi", entrypoint="babi", interaction="interactive"))
        assert 'ENTRYPOINT ["babi"]' in df
        assert 'ENTRYPOINT ["bash"]' not in df
        assert 'CMD ["-l"]' not in df

    def test_apt_step(self):
        df = generate_dockerfile(_cfg(apt_packages=["ffmpeg"]))
        assert "apt-get install" in df
        assert "ffmpeg" in df


class TestImageTag:
    def test_deterministic(self):
        cfg = _cfg()
        assert image_tag(cfg) == image_tag(cfg)

    def test_different_for_different_pkg(self):
        assert image_tag(_cfg(package_spec="black")) != image_tag(_cfg(package_spec="ruff"))

    def test_contains_package_name(self):
        assert "httpie" in image_tag(_cfg(package_spec="httpie"))

    def test_prefix(self):
        assert image_tag(_cfg()).startswith("safe-whale-")


class TestDisplayCommand:
    def test_multiline(self):
        cmd = build_display_command(_cfg(), "my-tag")
        assert "\n" in cmd

    def test_contains_tag(self):
        cmd = build_display_command(_cfg(), "my-tag")
        assert "my-tag" in cmd

    def test_pipe_mode_shows_input_redirection(self):
        cmd = build_display_command(
            _cfg(interaction="pipe", stdin_file=r"C:\input\data.json"),
            "my-tag",
        )
        assert "<" in cmd
        assert "data.json" in cmd
