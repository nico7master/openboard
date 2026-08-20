#!/usr/bin/env bash
# Phase 1 gate entry point: full test suite
set -e
cd "$(dirname "$0")/.."
/opt/venv/bin/python -m pytest -q "$@"
