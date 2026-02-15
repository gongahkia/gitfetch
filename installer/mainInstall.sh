#!/bin/bash
# gitfetch installer — installs via pip
set -e
RED="\e[31m"
GREEN="\e[32m"
BLUE="\e[34m"
ENDCOLOR="\e[0m"

printf "${BLUE}gitfetch installer${ENDCOLOR}\n"

if ! command -v pip3 &> /dev/null; then
    printf "${RED}pip3 not found${ENDCOLOR}. Please install Python 3 and pip first.\n"
    exit 1
fi

pip3 install --user git+https://github.com/gongahkia/gitfetch.git

# detect shell and add to PATH if needed
SHELL_NAME=$(basename "$SHELL")
case "$SHELL_NAME" in
    zsh)  RC_FILE="$HOME/.zshrc" ;;
    fish) RC_FILE="$HOME/.config/fish/config.fish" ;;
    *)    RC_FILE="$HOME/.bashrc" ;;
esac

PIP_BIN=$(python3 -m site --user-base)/bin
if ! grep -q "$PIP_BIN" "$RC_FILE" 2>/dev/null; then
    if [[ "$SHELL_NAME" == "fish" ]]; then
        echo "set -gx PATH $PIP_BIN \$PATH" >> "$RC_FILE"
    else
        echo "export PATH=\"$PIP_BIN:\$PATH\"" >> "$RC_FILE"
    fi
    printf "Added ${GREEN}$PIP_BIN${ENDCOLOR} to ${BLUE}$RC_FILE${ENDCOLOR}\n"
fi

printf "${GREEN}gitfetch installed!${ENDCOLOR} Restart your shell, then run: gitfetch\n"
