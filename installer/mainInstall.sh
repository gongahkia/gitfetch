#!/bin/bash
# Use the same installer policy for shell and Python entrypoints.
set -e
if ! command -v python3 >/dev/null 2>&1; then
    printf 'python3 not found. Install Python 3.11+ first.\n' >&2
    exit 1
fi
INSTALLER_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$INSTALLER_DIR/installation.py"
