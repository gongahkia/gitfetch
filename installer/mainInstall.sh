#!/bin/bash
# gitfetch installer — installs via pip
set -e
RED="\e[31m"
GREEN="\e[32m"
BLUE="\e[34m"
ENDCOLOR="\e[0m"

printf "${BLUE}gitfetch installer${ENDCOLOR}\n"

if ! command -v python3 &> /dev/null; then
    printf "${RED}python3 not found${ENDCOLOR}. Please install Python 3.10+ and pip first.\n"
    exit 1
fi

PYTHON_BIN=$(command -v python3)
if ! "$PYTHON_BIN" -m pip --version &> /dev/null; then
    printf "${RED}pip not found for python3${ENDCOLOR}. Please install pip for Python 3.10+.\n"
    exit 1
fi
if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
    printf "${RED}Python 3.10+ is required${ENDCOLOR}.\n"
    exit 1
fi

if [[ -n "$VIRTUAL_ENV" ]]; then
    "$PYTHON_BIN" -m pip install git+https://github.com/gongahkia/gitfetch.git
else
    "$PYTHON_BIN" -m pip install --user git+https://github.com/gongahkia/gitfetch.git
fi

# detect shell and add to PATH if needed
SHELL_NAME=$(basename "$SHELL")
case "$SHELL_NAME" in
    zsh)  RC_FILE="$HOME/.zshrc" ;;
    fish) RC_FILE="$HOME/.config/fish/config.fish" ;;
    *)    RC_FILE="$HOME/.bashrc" ;;
esac

mkdir -p "$(dirname "$RC_FILE")"
PIP_BIN=$("$PYTHON_BIN" -m site --user-base)/bin
if ! grep -Fq "$PIP_BIN" "$RC_FILE" 2>/dev/null; then
    if [[ "$SHELL_NAME" == "fish" ]]; then
        echo "set -gx PATH $PIP_BIN \$PATH" >> "$RC_FILE"
    else
        echo "export PATH=\"$PIP_BIN:\$PATH\"" >> "$RC_FILE"
    fi
    printf "Added ${GREEN}$PIP_BIN${ENDCOLOR} to ${BLUE}$RC_FILE${ENDCOLOR}\n"
fi

printf "${GREEN}gitfetch installed!${ENDCOLOR} Restart your shell, then run: gitfetch\n"
