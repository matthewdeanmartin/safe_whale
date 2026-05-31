#!/usr/bin/env bash
# Smoke test: exercises the safe-whale argparse surface and verifies invocations exit cleanly.
# It intentionally keeps assertions light; Python unit tests cover detailed behavior.

set -ou pipefail

if [ -d /usr/bin ]; then
    export PATH="/usr/bin:/bin:${PATH:-}"
fi

PASS=0
FAIL=0
if [ -n "${PYTHON:-}" ]; then
    read -r -a CLI_PYTHON <<< "$PYTHON"
elif command -v "${UV:-uv}" > /dev/null 2>&1; then
    CLI_PYTHON=("${UV:-uv}" run python)
else
    CLI_PYTHON=(python)
fi
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_ROOT="${SAFE_WHALE_SMOKE_TMP:-${ROOT_DIR}/.tmp/safe-whale-smoke-$$}"

export XDG_DATA_HOME="${TMP_ROOT}/xdg-data"
export LOCALAPPDATA="${TMP_ROOT}/localappdata"
export SAFE_WHALE_DATA_DIR="${TMP_ROOT}/data"
export SAFE_WHALE_BIN_DIR="${TMP_ROOT}/bin"
mkdir -p "$XDG_DATA_HOME" "$LOCALAPPDATA" "$SAFE_WHALE_DATA_DIR" "$$SAFE_WHALE_BIN_DIR"

run_cli() {
    "${CLI_PYTHON[@]}" -m safe_whale "$@"
}

check() {
    local desc="$1"
    shift
    if "$@" > /dev/null 2>&1; then
        echo "  PASS: $desc"
        ((PASS++))
    else
        echo "  FAIL: $desc  (cmd: $*)"
        ((FAIL++))
    fi
}

check_fails() {
    local desc="$1"
    shift
    if "$@" > /dev/null 2>&1; then
        echo "  FAIL: $desc  (expected non-zero exit, got 0)"
        ((FAIL++))
    else
        echo "  PASS: $desc"
        ((PASS++))
    fi
}

write_pipx_metadata() {
    cat > "${TMP_ROOT}/pipx-list.json" <<'JSON'
{
  "venvs": {
    "ruff": {
      "metadata": {
        "main_package": {
          "package_or_url": "ruff"
        }
      }
    }
  }
}
JSON
}

echo "=== safe-whale basic CLI checks ==="
echo ""
echo "using: ${CLI_PYTHON[*]} -m safe_whale"
echo "data:  ${TMP_ROOT}"
echo ""

echo "--- read-only actions ---"
check "safe-whale --help" run_cli --help
check "safe-whale --version" run_cli --version
check "safe-whale --diagnostics" run_cli --diagnostics
check "safe-whale help" run_cli help
check "safe-whale help run" run_cli help run
check "safe-whale list" run_cli list
check "safe-whale list --catalog" run_cli list --catalog
check "safe-whale profiles" run_cli profiles
check "safe-whale cleanup" run_cli cleanup
check "safe-whale environment" run_cli environment
check "safe-whale ensurepath" run_cli ensurepath
check "safe-whale completions" run_cli completions

for cmd in \
    run install install-all build list uninstall uninstall-all reinstall reinstall-all \
    upgrade upgrade-all profiles cleanup environment ensurepath completions inject uninject \
    pin unpin runpip interpreter upgrade-shared help
do
    check "safe-whale ${cmd} --help" run_cli "$cmd" --help
done

echo ""
echo "--- dry-run actions ---"
write_pipx_metadata
check "dry-run run" run_cli run --dry-run --engine docker ruff -- --version
check "global dry-run run" run_cli --dry-run run --engine docker ruff
check "dry-run build" run_cli build --dry-run --engine docker ruff
check "dry-run install" run_cli install --dry-run --engine docker ruff
check "dry-run install-all" run_cli install-all --dry-run --engine docker "${TMP_ROOT}/pipx-list.json"

# Seed an isolated profile so dry-run operations that require installed profiles can exercise their happy paths.
check "seed isolated profile" run_cli install --skip-build --no-wrapper --engine docker ruff
check "dry-run uninstall" run_cli uninstall --dry-run ruff
check "dry-run uninstall-all" run_cli uninstall-all --dry-run
check "dry-run reinstall" run_cli reinstall --dry-run ruff
check "dry-run reinstall-all" run_cli reinstall-all --dry-run
check "dry-run upgrade" run_cli upgrade --dry-run ruff
check "dry-run upgrade-all" run_cli upgrade-all --dry-run
check "dry-run cleanup --all" run_cli cleanup --dry-run --all
check "dry-run cleanup asset" run_cli cleanup --dry-run wrapper:ruff
check "dry-run ensurepath" run_cli ensurepath --dry-run

for cmd in inject uninject pin unpin runpip interpreter upgrade-shared
do
    check "dry-run ${cmd}" run_cli "$cmd" --dry-run ruff requests
done

echo ""
echo "--- expected non-zero compatibility paths ---"
check_fails "unsupported inject without dry-run" run_cli inject ruff requests

echo ""
echo "=== Results: ${PASS} passed, ${FAIL} failed ==="

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
