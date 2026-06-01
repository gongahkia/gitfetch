from __future__ import annotations

import os
import platform
import site
import subprocess
import sys
from pathlib import Path


def _rc_file() -> Path:
    shell = Path(os.environ.get("SHELL", "")).name
    if shell == "zsh":
        return Path.home() / ".zshrc"
    if shell == "fish":
        return Path.home() / ".config" / "fish" / "config.fish"
    return Path.home() / ".bashrc"


def _ensure_user_bin_on_path() -> None:
    user_bin = Path(site.getuserbase()) / "bin"
    if str(user_bin) in os.environ.get("PATH", ""):
        return
    rc_file = _rc_file()
    rc_file.parent.mkdir(parents=True, exist_ok=True)
    current = rc_file.read_text(encoding="utf-8") if rc_file.exists() else ""
    if str(user_bin) in current:
        return
    if rc_file.name == "config.fish":
        line = f"set -gx PATH {user_bin} $PATH\n"
    else:
        line = f'export PATH="{user_bin}:$PATH"\n'
    with rc_file.open("a", encoding="utf-8") as fh:
        fh.write(line)
    print(f"Added {user_bin} to {rc_file}")


def main() -> int:
    system = platform.system()
    if system not in {"Darwin", "Linux"}:
        print(f"Unsupported platform: {system}", file=sys.stderr)
        return 1
    pip_args = [sys.executable, "-m", "pip", "install"]
    if not os.environ.get("VIRTUAL_ENV"):
        pip_args.append("--user")
    pip_args.append("git+https://github.com/gongahkia/gitfetch.git")
    subprocess.run(pip_args, check=True)
    _ensure_user_bin_on_path()
    print("gitfetch installed. Restart your shell, then run: gitfetch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
