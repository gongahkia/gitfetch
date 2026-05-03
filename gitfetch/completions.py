from __future__ import annotations


COMMANDS = ["config", "modules", "repo", "org", "compare", "completions"]
TOP_FLAGS = [
    "--user", "--token", "--mode", "--config", "--set", "--format",
    "--no-avatar", "--margin", "--color", "--no-color", "--theme",
    "--avatar-style", "--avatar-color", "--watch", "--refresh",
    "--offline", "--version", "--help",
]
FORMAT_VALUES = ["ansi", "plain", "json", "svg", "card"]


def _theme_names() -> list[str]:
    from gitfetch.render import THEMES
    return sorted(THEMES.keys())


THEME_VALUES = _theme_names()
STYLE_VALUES = ["ascii", "halfblock", "braille"]
COLOR_VALUES = ["auto", "none", "256", "truecolor"]
MODE_VALUES = ["public", "viewer"]


BASH = """\
_gitfetch_completions() {{
    local cur prev cmds opts
    cur="${{COMP_WORDS[COMP_CWORD]}}"
    prev="${{COMP_WORDS[COMP_CWORD-1]}}"
    cmds="{commands}"
    opts="{flags}"
    case "$prev" in
        --format)        COMPREPLY=( $(compgen -W "{formats}" -- "$cur") ); return ;;
        --theme)         COMPREPLY=( $(compgen -W "{themes}" -- "$cur") ); return ;;
        --avatar-style)  COMPREPLY=( $(compgen -W "{styles}" -- "$cur") ); return ;;
        --avatar-color)  COMPREPLY=( $(compgen -W "{colors}" -- "$cur") ); return ;;
        --mode)          COMPREPLY=( $(compgen -W "{modes}" -- "$cur") ); return ;;
        completions)     COMPREPLY=( $(compgen -W "bash zsh fish" -- "$cur") ); return ;;
    esac
    if [[ "$cur" == --* ]]; then
        COMPREPLY=( $(compgen -W "$opts" -- "$cur") )
    elif [[ ${{COMP_CWORD}} -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "$cmds $opts" -- "$cur") )
    fi
}}
complete -F _gitfetch_completions gitfetch
"""


ZSH = """\
#compdef gitfetch
_gitfetch() {{
    local -a cmds
    cmds=({commands_zsh})
    _arguments -C \\
        '--user[GitHub username]:user:' \\
        '--token[GitHub token]:token:' \\
        '--mode[Profile mode]:mode:({modes})' \\
        '--config[Path to config.toml]:file:_files' \\
        '--set[Override config value]:override:' \\
        '--format[Output format]:format:({formats})' \\
        '--no-avatar[Disable avatar]' \\
        '--margin[Character margin]:n:' \\
        '--color[Force colors on]' \\
        '--no-color[Force colors off]' \\
        '--theme[Color theme]:theme:({themes})' \\
        '--avatar-style[Avatar style]:style:({styles})' \\
        '--avatar-color[Avatar color]:color:({colors})' \\
        '--watch[Re-render every N seconds]:secs:' \\
        '--refresh[Bypass cache reads]' \\
        '--offline[Cache-only mode]' \\
        '--version[Print version]' \\
        '*:: :->args'
    if [[ $state == args && $CURRENT == 1 ]]; then
        _describe -t commands 'gitfetch command' cmds
    fi
}}
compdef _gitfetch gitfetch
"""


FISH = """\
complete -c gitfetch -n "__fish_use_subcommand" -a "{commands}"
complete -c gitfetch -l user -x -d "GitHub username"
complete -c gitfetch -l token -x -d "GitHub token"
complete -c gitfetch -l mode -x -a "{modes}" -d "Profile mode"
complete -c gitfetch -l config -F -d "Path to config.toml"
complete -c gitfetch -l set -x -d "Override KEY=VALUE"
complete -c gitfetch -l format -x -a "{formats}" -d "Output format"
complete -c gitfetch -l no-avatar -d "Disable avatar"
complete -c gitfetch -l margin -x -d "Character margin"
complete -c gitfetch -l color -d "Force colors on"
complete -c gitfetch -l no-color -d "Force colors off"
complete -c gitfetch -l theme -x -a "{themes}" -d "Color theme"
complete -c gitfetch -l avatar-style -x -a "{styles}" -d "Avatar style"
complete -c gitfetch -l avatar-color -x -a "{colors}" -d "Avatar color"
complete -c gitfetch -l watch -x -d "Re-render every N seconds"
complete -c gitfetch -l refresh -d "Bypass cache reads"
complete -c gitfetch -l offline -d "Cache-only mode"
complete -c gitfetch -l version -d "Print version"
complete -c gitfetch -n "__fish_seen_subcommand_from completions" -a "bash zsh fish"
"""


def script_for(shell: str) -> str:
    payload = {
        "commands": " ".join(COMMANDS),
        "commands_zsh": " ".join(f"'{c}'" for c in COMMANDS),
        "flags": " ".join(TOP_FLAGS),
        "formats": " ".join(FORMAT_VALUES),
        "themes": " ".join(THEME_VALUES),
        "styles": " ".join(STYLE_VALUES),
        "colors": " ".join(COLOR_VALUES),
        "modes": " ".join(MODE_VALUES),
    }
    if shell == "bash":
        return BASH.format(**payload)
    if shell == "zsh":
        return ZSH.format(**payload)
    if shell == "fish":
        return FISH.format(**payload)
    raise ValueError(f"unsupported shell: {shell}")
