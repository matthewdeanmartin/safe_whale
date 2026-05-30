# Codex Notes

This project is uv-based. Prefer these commands from the repo root:

```powershell
$env:UV_CACHE_DIR='.uv-cache'; uv run pytest -q
$env:UV_CACHE_DIR='.uv-cache'; uv run ruff check safe_whale tests
$env:UV_CACHE_DIR='.uv-cache'; uv run mypy --hide-error-context safe_whale tests
```

In the Codex desktop sandbox on Windows, uv's default cache under
`C:\Users\matth\AppData\Local\uv\cache` can be denied. Use the workspace-local
`.uv-cache` directory instead.

Pytest's default temp root under `AppData\Local\Temp` can also be denied. If
tests using `tmp_path` fail during setup with `PermissionError`, run pytest with
workspace-local temp/cache paths:

```powershell
$env:UV_CACHE_DIR='.uv-cache'
$env:TMP='C:\github\safe_whale\.tmp'
$env:TEMP='C:\github\safe_whale\.tmp'
uv run pytest -q --basetemp C:\github\safe_whale\.tmp\pytest --cache-clear -o cache_dir=C:\github\safe_whale\.tmp\pytest_cache
```

The `.uv-cache` and `.tmp` directories are local scratch space and should stay
out of version control.
