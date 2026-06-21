import copy
import json
import os
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib  # type: ignore[no-redef]


DEFAULT_MODULE_ORDER = [
    "identity",
    "stats",
    "languages",
    "contributions",
]

SUPPORTED_PROVIDERS = ["github", "gitlab", "bitbucket", "gitea", "forgejo", "codeberg"]

PROVIDER_TOKEN_ENVS = {
    "github": "GITHUB_TOKEN",
    "gitlab": "GITLAB_TOKEN",
    "bitbucket": "BITBUCKET_TOKEN",
    "gitea": "GITEA_TOKEN",
    "forgejo": "FORGEJO_TOKEN",
    "codeberg": "CODEBERG_TOKEN",
}

OPTIONAL_MODULES = [
    "sparkline",
    "streaks",
    "pull_requests",
    "issues",
    "pinned",
    "rate_limit",
    "social_accounts",
    "organizations",
    "starred",
    "watched",
    "gists",
    "recent_activity",
    "showcase",
    "sponsors",
    "profile_readme",
    "top_repos",
    "releases",
    "discussions",
    "actions_status",
    "repo_health",
    "topics",
    "dependencies",
    "security_advisories",
    "packages",
    "contribution_breakdown",
    "commit_cadence",
    "maintainer_activity",
]

DEFAULT_CONFIG: dict[str, Any] = {
    "profile": {
        "provider": "github",
        "username": "",
        "mode": "public",
        "token_env": "GITHUB_TOKEN",
        "token_command": "",
    },
    "providers": {
        "github": {
            "base_url": "https://api.github.com",
            "token_env": "GITHUB_TOKEN",
        },
        "gitlab": {
            "base_url": "https://gitlab.com/api/v4",
            "token_env": "GITLAB_TOKEN",
        },
        "bitbucket": {
            "base_url": "https://api.bitbucket.org/2.0",
            "token_env": "BITBUCKET_TOKEN",
        },
        "gitea": {
            "base_url": "https://gitea.com/api/v1",
            "token_env": "GITEA_TOKEN",
        },
        "forgejo": {
            "base_url": "",
            "token_env": "FORGEJO_TOKEN",
        },
        "codeberg": {
            "base_url": "https://codeberg.org/api/v1",
            "token_env": "CODEBERG_TOKEN",
        },
    },
    "profiles": {},
    "plugins": {
        "paths": [],
        "modules": [],
    },
    "cache": {
        "enabled": True,
        "ttl_seconds": 1800,
    },
    "display": {
        "avatar": True,
        "avatar_width": 100,
        "ascii_ramp": "BS#&@$%*!:.",
        "heatmap_weeks": 12,
        "theme": "default",
        "color": True,
        "layout": "split",
        "show_empty": False,
        "margin": 0,
        "format": "ansi",
        "avatar_style": "ascii",
        "avatar_color": "auto",
    },
    "repo_filters": {
        "exclude_forks": True,
        "exclude_archived": True,
        "exclude_templates": True,
    },
    "modules": {
        "order": DEFAULT_MODULE_ORDER + OPTIONAL_MODULES,
        "identity": {
            "enabled": True,
            "hide_if_empty": True,
        },
        "stats": {
            "enabled": True,
            "hide_if_empty": True,
        },
        "languages": {
            "enabled": True,
            "hide_if_empty": True,
            "limit": 5,
            "workers": 8,
        },
        "contributions": {
            "enabled": True,
            "hide_if_empty": True,
        },
        "sparkline": {
            "enabled": False,
            "hide_if_empty": True,
            "days": 30,
        },
        "streaks": {
            "enabled": False,
            "hide_if_empty": True,
        },
        "pull_requests": {
            "enabled": False,
            "hide_if_empty": True,
        },
        "issues": {
            "enabled": False,
            "hide_if_empty": True,
        },
        "pinned": {
            "enabled": False,
            "hide_if_empty": True,
            "limit": 6,
        },
        "rate_limit": {
            "enabled": False,
            "hide_if_empty": True,
        },
        "social_accounts": {
            "enabled": False,
            "hide_if_empty": True,
            "limit": 5,
        },
        "organizations": {
            "enabled": False,
            "hide_if_empty": True,
            "limit": 8,
        },
        "starred": {
            "enabled": False,
            "hide_if_empty": True,
            "limit": 5,
        },
        "watched": {
            "enabled": False,
            "hide_if_empty": True,
            "limit": 5,
        },
        "gists": {
            "enabled": False,
            "hide_if_empty": True,
            "limit": 5,
        },
        "recent_activity": {
            "enabled": False,
            "hide_if_empty": True,
            "limit": 5,
        },
        "showcase": {
            "enabled": False,
            "hide_if_empty": True,
            "limit": 5,
        },
        "sponsors": {
            "enabled": False,
            "hide_if_empty": True,
        },
        "profile_readme": {
            "enabled": False,
            "hide_if_empty": True,
            "max_lines": 4,
        },
        "top_repos": {
            "enabled": False,
            "hide_if_empty": True,
            "limit": 5,
        },
        "releases": {
            "enabled": False,
            "hide_if_empty": True,
            "limit": 5,
            "repos_limit": 8,
        },
        "discussions": {
            "enabled": False,
            "hide_if_empty": True,
            "limit": 5,
            "repos_limit": 8,
        },
        "actions_status": {
            "enabled": False,
            "hide_if_empty": True,
            "limit": 5,
            "repos_limit": 8,
        },
        "repo_health": {
            "enabled": False,
            "hide_if_empty": True,
        },
        "topics": {
            "enabled": False,
            "hide_if_empty": True,
            "limit": 8,
        },
        "dependencies": {
            "enabled": False,
            "hide_if_empty": True,
            "limit": 6,
            "repos_limit": 5,
        },
        "security_advisories": {
            "enabled": False,
            "hide_if_empty": True,
            "limit": 5,
            "repos_limit": 8,
        },
        "packages": {
            "enabled": False,
            "hide_if_empty": True,
            "limit": 5,
            "types": ["container", "npm", "maven", "rubygems", "nuget"],
        },
        "contribution_breakdown": {
            "enabled": False,
            "hide_if_empty": True,
        },
        "commit_cadence": {
            "enabled": False,
            "hide_if_empty": True,
            "days": 30,
        },
        "maintainer_activity": {
            "enabled": False,
            "hide_if_empty": True,
        },
    },
}

PRESETS: dict[str, dict[str, Any]] = {
    "minimal": {
        "display": {"avatar": False},
        "modules": {
            "order": ["identity", "stats", "languages"],
            "identity": {"enabled": True},
            "stats": {"enabled": True},
            "languages": {"enabled": True},
            "contributions": {"enabled": False},
        },
    },
    "compact": {
        "display": {"avatar": True, "layout": "stack"},
        "modules": {
            "order": ["identity", "stats", "languages", "contributions"],
        },
    },
    "full": {
        "modules": {
            "identity": {"enabled": True},
            "stats": {"enabled": True},
            "languages": {"enabled": True},
            "contributions": {"enabled": True},
            "social_accounts": {"enabled": True},
            "organizations": {"enabled": True},
            "starred": {"enabled": True},
            "watched": {"enabled": True},
            "gists": {"enabled": True},
            "recent_activity": {"enabled": True},
            "showcase": {"enabled": True},
            "sponsors": {"enabled": True},
            "profile_readme": {"enabled": True},
            "top_repos": {"enabled": True},
        },
    },
    "showcase": {
        "modules": {
            "order": [
                "identity",
                "stats",
                "showcase",
                "top_repos",
                "profile_readme",
                "recent_activity",
                "social_accounts",
            ],
            "showcase": {"enabled": True},
            "top_repos": {"enabled": True},
            "profile_readme": {"enabled": True},
            "recent_activity": {"enabled": True},
            "social_accounts": {"enabled": True},
        },
    },
}

MODULE_METADATA: dict[str, dict[str, Any]] = {
    "identity": {"token_required": False, "description": "Name, bio, company, blog, and location."},
    "stats": {"token_required": False, "description": "Age, repo counts, followers, and recent activity."},
    "languages": {"token_required": False, "description": "Top languages rolled up across repositories."},
    "contributions": {"token_required": True, "description": "GraphQL contribution heatmap."},
    "sparkline": {"token_required": True, "description": "Single-line cadence sparkline of recent days."},
    "streaks": {"token_required": True, "description": "Current and longest contribution streaks."},
    "pull_requests": {"token_required": True, "description": "Open / merged / closed pull request totals."},
    "issues": {"token_required": True, "description": "Open / closed issue totals."},
    "pinned": {"token_required": True, "description": "Pinned repositories and gists from the profile."},
    "rate_limit": {"token_required": False, "description": "Live API rate-limit usage and reset window."},
    "social_accounts": {"token_required": False, "description": "Public social links from the social accounts API."},
    "organizations": {"token_required": False, "description": "Public organizations the user belongs to."},
    "starred": {"token_required": False, "description": "Recently starred repositories."},
    "watched": {"token_required": False, "description": "Recently watched repositories."},
    "gists": {"token_required": False, "description": "Recent public gists."},
    "recent_activity": {"token_required": False, "description": "Recent public GitHub events."},
    "showcase": {"token_required": True, "description": "Pinned profile items via GraphQL."},
    "sponsors": {"token_required": True, "description": "Sponsor listing availability via GraphQL."},
    "profile_readme": {"token_required": False, "description": "Summary from the profile README repository."},
    "top_repos": {"token_required": False, "description": "Top repositories by stars."},
    "releases": {"token_required": False, "description": "Recent releases from owned repositories."},
    "discussions": {"token_required": True, "description": "Discussion counts across recent repositories."},
    "actions_status": {"token_required": False, "description": "Latest GitHub Actions run status by repository."},
    "repo_health": {"token_required": False, "description": "Repository hygiene and maintenance signals."},
    "topics": {"token_required": False, "description": "Top repository topics across the profile."},
    "dependencies": {"token_required": False, "description": "Dependency SBOM package summary for recent repositories."},
    "security_advisories": {"token_required": True, "description": "Repository security advisory summary."},
    "packages": {"token_required": False, "description": "Public GitHub Packages summary."},
    "contribution_breakdown": {"token_required": True, "description": "Commit, issue, PR, and review contribution totals."},
    "commit_cadence": {"token_required": False, "description": "Recent commit cadence from contribution data or public events."},
    "maintainer_activity": {"token_required": False, "description": "Recent repository maintenance activity."},
}


class ConfigError(RuntimeError):
    pass


def config_dir() -> Path:
    return Path.home() / ".config" / "gitfetch"


def config_path() -> Path:
    return config_dir() / "config.toml"


def legacy_config_path() -> Path:
    return config_dir() / ".gitfetchConfig"


def cache_dir() -> Path:
    return Path.home() / ".cache" / "gitfetch"


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
    return base


def preset_config(name: str) -> dict[str, Any]:
    if name not in PRESETS:
        raise ConfigError(f"unknown preset: {name}")
    data = copy.deepcopy(DEFAULT_CONFIG)
    return _merge(data, copy.deepcopy(PRESETS[name]))


def migrate_legacy_username() -> str | None:
    legacy = legacy_config_path()
    if not legacy.exists():
        return None
    try:
        payload = json.loads(legacy.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    username = payload.get("username")
    if isinstance(username, str) and username.strip():
        return username.strip()
    return None


def load_config(path: Path | None = None) -> dict[str, Any]:
    target = path or config_path()
    data = copy.deepcopy(DEFAULT_CONFIG)
    if target.exists():
        try:
            parsed = tomllib.loads(target.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ConfigError(f"invalid config at {target}: {exc}") from exc
        _merge(data, parsed)
    else:
        legacy_username = migrate_legacy_username()
        if legacy_username:
            data["profile"]["username"] = legacy_username
    normalize_config(data)
    return data


def normalize_config(config: dict[str, Any]) -> None:
    modules = config.setdefault("modules", {})
    order = modules.get("order", DEFAULT_MODULE_ORDER + OPTIONAL_MODULES)
    seen: list[str] = []
    normalized_order: list[str] = []
    for name in order:
        if name in MODULE_METADATA and name not in seen:
            seen.append(name)
            normalized_order.append(name)
    for name in MODULE_METADATA:
        if name not in seen:
            normalized_order.append(name)
    modules["order"] = normalized_order
    provider = str(config["profile"].get("provider", "github")).lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise ConfigError(f"profile.provider must be one of: {', '.join(SUPPORTED_PROVIDERS)}")
    config["profile"]["provider"] = provider
    providers = config.setdefault("providers", {})
    for name in SUPPORTED_PROVIDERS:
        provider_config = providers.setdefault(name, {})
        default_provider = DEFAULT_CONFIG["providers"][name]
        provider_config.setdefault("base_url", default_provider["base_url"])
        provider_config.setdefault("token_env", default_provider["token_env"])
        if name == provider and not str(provider_config.get("base_url", "")).strip():
            raise ConfigError(f"providers.{name}.base_url must not be empty")
    if config["profile"].get("mode") not in {"public", "viewer"}:
        raise ConfigError("profile.mode must be 'public' or 'viewer'")
    if config["display"].get("layout") not in {"split", "stack"}:
        raise ConfigError("display.layout must be 'split' or 'stack'")
    if config["display"].get("avatar_width", 0) <= 0:
        raise ConfigError("display.avatar_width must be greater than 0")
    if config["display"].get("heatmap_weeks", 0) <= 0:
        raise ConfigError("display.heatmap_weeks must be greater than 0")
    if config["display"].get("margin", 0) < 0:
        raise ConfigError("display.margin must be non-negative")
    from gitfetch.render import THEMES
    theme = config["display"].get("theme", "default")
    if theme not in THEMES:
        raise ConfigError(f"display.theme '{theme}' is not a known theme (try one of: {', '.join(sorted(THEMES))})")
    style = config["display"].get("avatar_style", "ascii")
    if style not in {"ascii", "halfblock", "braille"}:
        raise ConfigError(f"display.avatar_style '{style}' is not a known style")
    color_mode = config["display"].get("avatar_color", "auto")
    if color_mode not in {"auto", "none", "256", "truecolor"}:
        raise ConfigError(f"display.avatar_color '{color_mode}' must be auto, none, 256, or truecolor")
    if config["cache"].get("ttl_seconds", 0) < 0:
        raise ConfigError("cache.ttl_seconds must be non-negative")


def get_token(cli_token: str | None, config: dict[str, Any]) -> str:
    if cli_token:
        return cli_token
    profile = config.get("profile", {})
    provider = str(profile.get("provider", "github")).lower()
    provider_config = config.get("providers", {}).get(provider, {})
    env_names: list[str] = []
    provider_env = str(provider_config.get("token_env") or PROVIDER_TOKEN_ENVS.get(provider, "GITHUB_TOKEN"))
    profile_env = str(profile.get("token_env") or "")
    if profile_env and (provider == "github" or profile_env != "GITHUB_TOKEN"):
        env_names.append(profile_env)
    if provider_env:
        env_names.append(provider_env)
    default_env = PROVIDER_TOKEN_ENVS.get(provider)
    if default_env:
        env_names.append(default_env)
    if profile_env:
        env_names.append(profile_env)
    for env_name in dict.fromkeys(env_names):
        env_token = os.environ.get(env_name, "")
        if env_token:
            return env_token
    token_command = config.get("profile", {}).get("token_command", "")
    if token_command:
        import shlex
        import subprocess

        try:
            result = subprocess.run(
                shlex.split(token_command),
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, ValueError, subprocess.SubprocessError):
            return ""
        if result.returncode == 0:
            return result.stdout.strip()
    return ""


def apply_named_profile(config: dict[str, Any], name: str | None) -> None:
    if not name:
        return
    profiles = config.get("profiles", {})
    profile = profiles.get(name)
    if not isinstance(profile, dict):
        raise ConfigError(f"unknown profile '{name}'")
    _merge(config["profile"], copy.deepcopy(profile))


def set_override(config: dict[str, Any], dotted_key: str, raw_value: str) -> None:
    parts = dotted_key.split(".")
    current = config
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = _coerce_value(raw_value)


def _coerce_value(value: str) -> Any:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None
    try:
        return int(value)
    except ValueError:
        pass
    if value.startswith("[") and value.endswith("]"):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def write_config(path: Path, config: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_toml(config).rstrip() + "\n", encoding="utf-8")


def to_toml(config: dict[str, Any]) -> str:
    lines: list[str] = []
    _write_table(lines, [], config)
    return "\n".join(lines)


def _write_table(lines: list[str], prefix: list[str], data: dict[str, Any]) -> None:
    scalars = {k: v for k, v in data.items() if not isinstance(v, dict)}
    tables = {k: v for k, v in data.items() if isinstance(v, dict)}

    if prefix:
        if lines and lines[-1] != "":
            lines.append("")
        lines.append(f"[{'.'.join(prefix)}]")
    for key, value in scalars.items():
        lines.append(f"{key} = {_format_toml_value(value)}")
    for key, value in tables.items():
        _write_table(lines, prefix + [key], value)


def _format_toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if value is None:
        return '""'
    if isinstance(value, list):
        return "[" + ", ".join(_format_toml_value(item) for item in value) + "]"
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
