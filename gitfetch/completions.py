from __future__ import annotations

from gitfetch.config import SUPPORTED_PROVIDERS


COMMANDS = ["config", "modules", "repo", "org", "compare", "completions", "token"]
TOP_FLAGS = [
    "--user", "--provider", "--base-url", "--profile", "--token", "--mode", "--config", "--set", "--format",
    "--save", "--no-avatar", "--margin", "--color", "--no-color", "--theme",
    "--avatar-style", "--avatar-color", "--watch", "--refresh",
    "--offline", "--version", "--help",
]
FORMAT_VALUES = ["ansi", "plain", "json", "svg", "card", "png"]


def _theme_names() -> list[str]:
    from gitfetch.render import THEMES
    return sorted(THEMES.keys())


THEME_VALUES = _theme_names()
STYLE_VALUES = ["ascii", "halfblock", "braille"]
COLOR_VALUES = ["auto", "none", "256", "truecolor"]
MODE_VALUES = ["public", "viewer"]
PROVIDER_VALUES = SUPPORTED_PROVIDERS


BASH = """\
_gitfetch_profile_names() {{
    gitfetch config profiles list 2>/dev/null | awk 'NF >= 2 {{ print $1 }}'
}}

_gitfetch_completions() {{
    local cur prev cmds opts
    cur="${{COMP_WORDS[COMP_CWORD]}}"
    prev="${{COMP_WORDS[COMP_CWORD-1]}}"
    cmds="{commands}"
    opts="{flags}"
    case "$prev" in
        --format)        COMPREPLY=( $(compgen -W "{formats}" -- "$cur") ); return ;;
        --provider)      COMPREPLY=( $(compgen -W "{providers}" -- "$cur") ); return ;;
        --theme)         COMPREPLY=( $(compgen -W "{themes}" -- "$cur") ); return ;;
        --avatar-style)  COMPREPLY=( $(compgen -W "{styles}" -- "$cur") ); return ;;
        --avatar-color)  COMPREPLY=( $(compgen -W "{colors}" -- "$cur") ); return ;;
        --mode)          COMPREPLY=( $(compgen -W "{modes}" -- "$cur") ); return ;;
        --profile)       COMPREPLY=( $(compgen -W "$(_gitfetch_profile_names)" -- "$cur") ); return ;;
        completions)     COMPREPLY=( $(compgen -W "bash zsh fish" -- "$cur") ); return ;;
    esac
    if [[ "$cur" == --* ]]; then
        COMPREPLY=( $(compgen -W "$opts" -- "$cur") )
        case "${{COMP_WORDS[1]}}" in
            repo) COMPREPLY=( $(compgen -W "$opts --contributors-limit --commits-limit" -- "$cur") ) ;;
            org) COMPREPLY=( $(compgen -W "$opts --members-limit --repos-limit" -- "$cur") ) ;;
            compare) COMPREPLY=( $(compgen -W "$opts --column-width" -- "$cur") ) ;;
        esac
        return
    fi
    if [[ ${{COMP_CWORD}} -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "$cmds $opts" -- "$cur") )
        return
    fi
    case "${{COMP_WORDS[1]}}" in
        config)
            case "${{COMP_WORDS[2]}}" in
                init) COMPREPLY=( $(compgen -W "--preset --force" -- "$cur") ) ;;
                wizard) COMPREPLY=( $(compgen -W "--force" -- "$cur") ) ;;
                profiles)
                    case "${{COMP_WORDS[3]}}" in
                        set) COMPREPLY=( $(compgen -W "--user --provider --mode --token-env --token-command" -- "$cur") ) ;;
                        remove) COMPREPLY=( $(compgen -W "$(_gitfetch_profile_names)" -- "$cur") ) ;;
                        *) COMPREPLY=( $(compgen -W "list set remove" -- "$cur") ) ;;
                    esac ;;
                *) COMPREPLY=( $(compgen -W "init wizard path validate profiles" -- "$cur") ) ;;
            esac ;;
        modules) COMPREPLY=( $(compgen -W "list" -- "$cur") ) ;;
        completions) COMPREPLY=( $(compgen -W "bash zsh fish" -- "$cur") ) ;;
        token)
            case "${{COMP_WORDS[2]}}" in
                store) COMPREPLY=( $(compgen -W "--service --account --token" -- "$cur") ) ;;
                get|status|delete) COMPREPLY=( $(compgen -W "--service --account" -- "$cur") ) ;;
                *) COMPREPLY=( $(compgen -W "store get status delete" -- "$cur") ) ;;
            esac ;;
    esac
}}
complete -F _gitfetch_completions gitfetch
"""


ZSH = """\
#compdef gitfetch
_gitfetch_profiles() {{
    local -a profiles
    profiles=(${{(f)"$(gitfetch config profiles list 2>/dev/null | awk 'NF >= 2 {{ print $1 }}')"}})
    _describe -t profiles 'saved profile' profiles
}}

_gitfetch() {{
    local -a cmds
    cmds=({commands_zsh})
    _arguments -C \\
        '--user[Provider username or workspace]:user:' \\
        '--provider[Git provider]:provider:({providers})' \\
        '--base-url[Provider API base URL]:url:' \\
        '--profile[Saved profile name]:profile:_gitfetch_profiles' \\
        '--token[Provider token]:token:' \\
        '--mode[Profile mode]:mode:({modes})' \\
        '--config[Path to config.toml]:file:_files' \\
        '--set[Override config value]:override:' \\
        '--format[Output format]:format:({formats})' \\
        '--save[Write output to file]:file:_files' \\
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
    if [[ $state == args ]]; then
        case $words[2] in
            config)
                case $words[3] in
                    init) _arguments '--preset[preset]:preset:(minimal compact full showcase)' '--force[overwrite config]' ;;
                    wizard) _arguments '--force[overwrite config]' ;;
                    profiles)
                        case $words[4] in
                            set) _arguments '--user[profile user]:user:' '--provider[provider]:provider:({providers})' '--mode[mode]:mode:({modes})' '--token-env[token env]:env:' '--token-command[token command]:command:' ;;
                            remove) _gitfetch_profiles ;;
                            *) _values 'profile command' list set remove ;;
                        esac ;;
                    *) _values 'config command' init wizard path validate profiles ;;
                esac ;;
            modules) _values 'modules command' list ;;
            repo) _arguments '--contributors-limit[contributors]:count:' '--commits-limit[commits]:count:' ;;
            org) _arguments '--members-limit[members]:count:' '--repos-limit[repositories]:count:' ;;
            compare) _arguments '--column-width[column width]:width:' ;;
            completions) _values 'shell' bash zsh fish ;;
            token)
                case $words[3] in
                    store) _arguments '--service[keychain service]:service:' '--account[keychain account]:account:' '--token[token]:token:' ;;
                    get|status|delete) _arguments '--service[keychain service]:service:' '--account[keychain account]:account:' ;;
                    *) _values 'token command' store get status delete ;;
                esac ;;
        esac
    fi
}}
compdef _gitfetch gitfetch
"""


FISH = """\
function __gitfetch_profiles
    gitfetch config profiles list 2>/dev/null | string match -r '^[^ ]+'
end

complete -c gitfetch -n "__fish_use_subcommand" -a "{commands}"
complete -c gitfetch -l user -x -d "Provider username or workspace"
complete -c gitfetch -l provider -x -a "{providers}" -d "Git provider"
complete -c gitfetch -l base-url -x -d "Provider API base URL"
complete -c gitfetch -l profile -x -a "(__gitfetch_profiles)" -d "Saved profile name"
complete -c gitfetch -l token -x -d "Provider token"
complete -c gitfetch -l mode -x -a "{modes}" -d "Profile mode"
complete -c gitfetch -l config -F -d "Path to config.toml"
complete -c gitfetch -l set -x -d "Override KEY=VALUE"
complete -c gitfetch -l format -x -a "{formats}" -d "Output format"
complete -c gitfetch -l save -F -d "Write output to file"
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
complete -c gitfetch -n "__fish_seen_subcommand_from config" -a "init wizard path validate profiles"
complete -c gitfetch -n "__fish_seen_subcommand_from config; and __fish_seen_subcommand_from init" -l preset -x -a "minimal compact full showcase"
complete -c gitfetch -n "__fish_seen_subcommand_from config; and __fish_seen_subcommand_from init" -l force
complete -c gitfetch -n "__fish_seen_subcommand_from config; and __fish_seen_subcommand_from wizard" -l force
complete -c gitfetch -n "__fish_seen_subcommand_from config; and __fish_seen_subcommand_from profiles" -a "list set remove"
complete -c gitfetch -n "__fish_seen_subcommand_from config; and __fish_seen_subcommand_from remove" -a "(__gitfetch_profiles)"
complete -c gitfetch -n "__fish_seen_subcommand_from config; and __fish_seen_subcommand_from set" -l user -x
complete -c gitfetch -n "__fish_seen_subcommand_from config; and __fish_seen_subcommand_from set" -l provider -x -a "{providers}"
complete -c gitfetch -n "__fish_seen_subcommand_from config; and __fish_seen_subcommand_from set" -l mode -x -a "{modes}"
complete -c gitfetch -n "__fish_seen_subcommand_from config; and __fish_seen_subcommand_from set" -l token-env -x
complete -c gitfetch -n "__fish_seen_subcommand_from config; and __fish_seen_subcommand_from set" -l token-command -x
complete -c gitfetch -n "__fish_seen_subcommand_from modules" -a "list"
complete -c gitfetch -n "__fish_seen_subcommand_from repo" -l contributors-limit -x
complete -c gitfetch -n "__fish_seen_subcommand_from repo" -l commits-limit -x
complete -c gitfetch -n "__fish_seen_subcommand_from org" -l members-limit -x
complete -c gitfetch -n "__fish_seen_subcommand_from org" -l repos-limit -x
complete -c gitfetch -n "__fish_seen_subcommand_from compare" -l column-width -x
complete -c gitfetch -n "__fish_seen_subcommand_from token" -a "store get status delete"
complete -c gitfetch -n "__fish_seen_subcommand_from token; and __fish_seen_subcommand_from store" -l service -x
complete -c gitfetch -n "__fish_seen_subcommand_from token; and __fish_seen_subcommand_from store" -l account -x
complete -c gitfetch -n "__fish_seen_subcommand_from token; and __fish_seen_subcommand_from store" -l token -x
complete -c gitfetch -n "__fish_seen_subcommand_from token; and not __fish_seen_subcommand_from store" -l service -x
complete -c gitfetch -n "__fish_seen_subcommand_from token; and not __fish_seen_subcommand_from store" -l account -x
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
        "providers": " ".join(PROVIDER_VALUES),
    }
    if shell == "bash":
        return BASH.format(**payload)
    if shell == "zsh":
        return ZSH.format(**payload)
    if shell == "fish":
        return FISH.format(**payload)
    raise ValueError(f"unsupported shell: {shell}")
