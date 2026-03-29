# GitFetch Companion Guide

This document is the active manual for the modern GitFetch workflow.
The original `README.md` remains intentionally unchanged.

## Positioning

GitFetch is a profile-first GitHub CLI fetch tool.
It is not trying to replace:

- `fastfetch`, which is the benchmark for fetch-tool configurability and presets
- `neofetch`, which popularized approachable visual customization
- `onefetch`, which focuses on local repository summaries

GitFetch instead focuses on remote GitHub profile data, terminal-friendly presentation, and configuration-driven personalization.

## Quick Start

Initialize a config file:

```console
$ gitfetch config init
```

Use a different preset:

```console
$ gitfetch config init --preset showcase --force
```

Render a profile without touching your saved config:

```console
$ gitfetch --user octocat
$ gitfetch --user octocat --format plain
$ gitfetch --user octocat --format json
```

Inspect the config path and available modules:

```console
$ gitfetch config path
$ gitfetch config validate
$ gitfetch modules list
```

## Config Format

GitFetch stores configuration in:

```text
~/.config/gitfetch/config.toml
```

If a legacy `~/.config/gitfetch/.gitfetchConfig` file exists, GitFetch will reuse the stored username until you write a new TOML config.

### Example `config.toml`

```toml
[profile]
username = "octocat"
mode = "public"
token_env = "GITHUB_TOKEN"

[cache]
enabled = true
ttl_seconds = 1800

[display]
avatar = true
avatar_width = 100
ascii_ramp = "BS#&@$%*!:."
heatmap_weeks = 12
theme = "default"
color = true
layout = "split"
show_empty = false

[repo_filters]
exclude_forks = true
exclude_archived = true
exclude_templates = true

[modules]
order = ["identity", "stats", "languages", "contributions", "top_repos"]

[modules.identity]
enabled = true
hide_if_empty = true

[modules.stats]
enabled = true
hide_if_empty = true

[modules.languages]
enabled = true
hide_if_empty = true
limit = 5

[modules.contributions]
enabled = true
hide_if_empty = true

[modules.top_repos]
enabled = true
hide_if_empty = true
limit = 5
```

## Presets

GitFetch ships with these config presets:

- `minimal`: text-first output, no avatar, only the essential modules
- `compact`: the default balance of avatar plus core profile modules
- `full`: enables every built-in module, including token-aware ones
- `showcase`: emphasizes pinned items, top repositories, activity, and profile README

## CLI Flags

Runtime overrides:

- `--user <username>`: render a different user without editing config
- `--token <token>`: override the token for the current run
- `--mode public|viewer`: choose public-only or self-view mode
- `--config <path>`: use a different TOML file
- `--set key=value`: override any config key for one run
- `--format ansi|plain|json`: switch output format
- `--no-avatar`: disable avatar rendering for one run

## Module Catalog

| Module | Description | Token Required |
| --- | --- | --- |
| `identity` | Name, login, bio, company, blog, location | No |
| `stats` | Account age, repos, gists, followers, following, recent activity | No |
| `languages` | Language rollup across filtered repositories | No |
| `contributions` | GraphQL contribution heatmap | Yes |
| `social_accounts` | Public social links | No |
| `organizations` | Public org memberships | No |
| `starred` | Recently starred repositories | No |
| `watched` | Recently watched repositories | No |
| `gists` | Recent public gists | No |
| `recent_activity` | Public GitHub events | No |
| `showcase` | Pinned profile items from GitHub GraphQL | Yes |
| `sponsors` | Sponsor listing availability | Yes |
| `profile_readme` | Summary of the public profile README | No |
| `top_repos` | Top repositories by stars | No |

## Public Mode vs Viewer Mode

`public` mode only uses public profile data and public repository endpoints.

`viewer` mode activates only when:

1. a token is present
2. the token resolves to the same GitHub login as the requested user

When that happens, GitFetch can include self-only information such as private repository counts from authenticated endpoints.

## Output Formats

### ANSI

Best for interactive terminals. Uses colors and, when enabled, ASCII avatar rendering.

### Plain

Best for logs, pipes, and environments where terminal color or layout is limited.

### JSON

Best for scripts and machine consumption. GitFetch emits the resolved module payloads as JSON.

## Caching And Rate Limits

GitFetch caches expensive REST and GraphQL responses under:

```text
~/.cache/gitfetch/
```

This reduces repeated language-rollup and profile module calls. The default TTL is 30 minutes and can be tuned in `config.toml`.

Notes:

- GraphQL-backed modules such as `contributions`, `showcase`, and `sponsors` require a token
- public GitHub requests can still hit lower anonymous rate limits
- language rollups are the most expensive public-path operation because they require per-repository language queries

## Packaging Notes

The Homebrew formula currently targets the existing `2.0` source archive.
The package metadata now points at this companion guide for richer documentation while keeping the original `README.md` untouched.

## Troubleshooting

- If `gitfetch` says no username is configured, either write `config.toml` with `gitfetch config init` or pass `--user`
- If `contributions`, `showcase`, or `sponsors` do not appear, provide a token via `--token` or your configured token environment variable
- If output is too wide, set `display.layout = "stack"` or lower `display.avatar_width`
- If data feels stale, lower `cache.ttl_seconds` or clear `~/.cache/gitfetch/`
