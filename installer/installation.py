from __future__ import annotations

import os
import platform
import shlex
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
    if str(user_bin) in os.environ.get("PATH", "").split(os.pathsep):
        return
    rc_file = _rc_file()
    rc_file.parent.mkdir(parents=True, exist_ok=True)
    current = rc_file.read_text(encoding="utf-8") if rc_file.exists() else ""
    if str(user_bin) in current:
        return
    if rc_file.name == "config.fish":
        line = f"set -gx PATH {shlex.quote(str(user_bin))} $PATH\n"
    else:
        line = f'export PATH={shlex.quote(str(user_bin))}:"$PATH"\n'
    with rc_file.open("a", encoding="utf-8") as fh:
        if current and not current.endswith("\n"):
            fh.write("\n")
        fh.write(line)
    print(f"Added {user_bin} to {rc_file}")


def main() -> int:
    if sys.version_info < (3, 10):  # noqa: UP036 - installer also runs before package version validation
        print("Python 3.10+ is required", file=sys.stderr)
        return 1
    system = platform.system()
    if system not in {"Darwin", "Linux"}:
        print(f"Unsupported platform: {system}", file=sys.stderr)
        return 1
    pip_args = [sys.executable, "-m", "pip", "install"]
    virtualenv = sys.prefix != sys.base_prefix
    if not virtualenv:
        pip_args.append("--user")
    source = Path(__file__).resolve().parents[1]
    pip_args.append(str(source) if (source / "pyproject.toml").is_file() else "git+https://github.com/gongahkia/gitfetch.git")
    try:
        subprocess.run(pip_args, check=True)
    except (OSError, subprocess.CalledProcessError):
        print("Installation failed; inspect pip's diagnostic above.", file=sys.stderr)
        return 1
    if not virtualenv:
        _ensure_user_bin_on_path()
    print("gitfetch installed. Run: gitfetch" if virtualenv else "gitfetch installed. Restart your shell, then run: gitfetch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
