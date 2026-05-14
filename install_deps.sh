#!/usr/bin/env bash
# Install SethTests Python dependencies into a local venv (avoids PEP 668 / ensurepip issues).
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

# Override with: export PYTHON=/root/tools/python3.10/bin/python3
if [[ -n "${PYTHON:-}" ]]; then
  PY="$PYTHON"
elif [[ -x /root/tools/python3.10/bin/python3 ]]; then
  PY=/root/tools/python3.10/bin/python3
else
  PY="$(command -v python3 || true)"
fi

if [[ -z "$PY" || ! -x "$PY" ]]; then
  echo "No usable Python interpreter. Set PYTHON to a python3 binary." >&2
  exit 1
fi

echo "Using interpreter: $PY"
"$PY" -m venv .venv
./.venv/bin/pip install -U pip setuptools wheel
./.venv/bin/pip install -r "$REPO_ROOT/requirements.txt"
echo
echo "Dependencies installed under $REPO_ROOT/.venv"
echo "Run tests with:"
echo "  $REPO_ROOT/.venv/bin/python $REPO_ROOT/seth_test_runner.py --host <host>"
