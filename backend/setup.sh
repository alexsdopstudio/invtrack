#!/usr/bin/env bash
# Bootstrap the backend venv, isolated from any corporate/global pip config
# (e.g. an AWS CodeArtifact extra index on a work machine).
set -euo pipefail
cd "$(dirname "$0")"

PY=${PYTHON:-python3}
[ -d .venv ] || "$PY" -m venv .venv

# Venv-scoped pip config: the highest-precedence pip config *file*. Keeps every
# future `pip install` in this venv on public PyPI even when a user/global
# pip.conf adds a corporate index. Lives inside .venv/, never committed.
cat > .venv/pip.conf <<'EOF'
[global]
index-url = https://pypi.org/simple
extra-index-url =
EOF

# Env vars override config files, and the command line overrides everything —
# clear the former and pin the latter so this install can't touch other indexes.
unset PIP_INDEX_URL PIP_EXTRA_INDEX_URL PIP_CONFIG_FILE 2>/dev/null || true
.venv/bin/pip install --index-url https://pypi.org/simple -r requirements.txt

echo
echo "Backend venv ready (backend/.venv), pinned to public PyPI."
echo "Next: .venv/bin/alembic upgrade head && .venv/bin/uvicorn app.main:app --reload --port 8000"
