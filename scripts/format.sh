#!/bin/sh -e
set -x

# choose runner: uv if available, else plain
if command -v uv >/dev/null 2>&1; then
    RUNNER="uv run"
else
    RUNNER=""
fi

$RUNNER ruff check src tests --fix
$RUNNER ruff format src tests
