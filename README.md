# `Gitfetch` 🛻

Neofetch for Git hosting profiles: a fast, non-interactive CLI with responsive terminal output and shareable SVG/PNG cards.

This checkout contains v3 development work. Published 2.0 artifacts and the current Homebrew formula do not yet contain every feature described below; the release version has not been changed.

## Stack

* *Scripting*: [Python](https://www.python.org/), [Pip](https://pypi.org/project/pip/), [Pillow](https://pypi.org/project/Pillow/), [Requests](https://pypi.org/project/requests/)
* *API*: [GitHub Rest API](https://docs.github.com/en/rest?apiVersion=2022-11-28), [GitLab REST API](https://docs.gitlab.com/api/rest/), [Bitbucket Cloud REST API](https://developer.atlassian.com/cloud/bitbucket/rest/), [Gitea REST API](https://docs.gitea.com/api/), [Forgejo API](https://forgejo.org/docs/latest/user/api-usage/)

## Screenshots

Historical classic terminal example; modern presets and exported cards have different layouts.

<div align="center">
    <img src="assets/gitfetch.png" width="90%">
</div>

## Features

* Provider support for 6 Git Providers
    * [GitHub](https://github.com/)
    * [GitLab](https://gitlab.com/)
    * [Bitbucket Cloud](https://bitbucket.org/product)
    * [Gitea](https://about.gitea.com/)
    * [Codeberg](https://codeberg.org/)
    * [Forgejo](https://forgejo.org/)
* Profile stats
    * ASCII art avatar of Git Provider Profile
        * `ascii`
        * `halfblock`
        * `braille`
    * Hours since joining
    * Public repos
    * Followers
    * Days since last commit
    * Languages with provider-specific units: bytes, repository prevalence, or primary-language repository counts
    * Contribution
    * Repository mode with provider-available repository stats, language data, contributors, and recent commits
    * Organization mode with organization stats, repositories, and public members heatmap (last 12 weeks, requires `--token`)
* 4 `Gitfetch` Config presets
    * `minimal`
    * `compact`
    * `full`
    * `showcase`
* 6 Default Output formats
    * `ansi`
    * `plain`
    * `json`
    * `svg`
    * `card`
    * `png`
* Bash, Zsh, and Fish shell completions

## Usage

> [!WARNING]  
> `Gitfetch` minimally requires Python 3.10+ to be installed, which can be downloaded [here](https://www.python.org/downloads/).  

The below instructions are for locally installing and running `Gitfetch`.

1. First run the below commands to install `Gitfetch` to your own machine.

```console
$ git clone https://github.com/gongahkia/gitfetch
$ cd gitfetch
$ python3 -m venv .venv
$ source .venv/bin/activate # Windows: .venv\Scripts\activate
$ python -m pip install .
$ gitfetch config wizard # save your username once
# Alternatively, inside the activated environment: ./installer/mainInstall.sh
```

2. Then use any of the below commands to render a profile.

```console
$ gitfetch # uses saved username
$ gitfetch --user octocat # specify username
$ gitfetch --provider gitlab --user gitlab-org # render a GitLab user or namespace
$ gitfetch --provider bitbucket --user atlassian # render a Bitbucket workspace
$ gitfetch --provider codeberg --user forgejo # render a Codeberg profile or org
$ gitfetch --provider gitea --user gitea # render a Gitea.com profile or org
$ gitfetch --no-avatar # stats only, no ASCII art
$ gitfetch --presentation modern # responsive terminal profile, also available in captured/plain output
$ gitfetch --presentation classic # preserve the previous terminal style
$ gitfetch --details # expand enabled modern sections; may scroll, collects no additional data
$ gitfetch --offline # cached provider data and avatars only; missing avatars are omitted
$ gitfetch --refresh # bypass response and avatar cache reads
$ gitfetch --token ghp_xxxx # authenticated; also accepts provider env variables such as GITHUB_TOKEN, GITLAB_TOKEN, BITBUCKET_TOKEN, GITEA_TOKEN, FORGEJO_TOKEN, or CODEBERG_TOKEN
```

3. You can also render repositories, organizations, comparisons, and files directly from the CLI.

```console
$ gitfetch repo octocat/Hello-World # render a repository profile
$ gitfetch org github # render an organization profile
$ gitfetch compare octocat torvalds # compare two or more users side-by-side
$ gitfetch --provider gitlab repo gitlab-org/gitlab # render a GitLab project
$ gitfetch --provider bitbucket repo atlassian/atlassian-event # render a Bitbucket repository
$ gitfetch --provider codeberg repo forgejo/forgejo # render a Codeberg repository
$ gitfetch --provider gitea repo gitea/tea # render a Gitea.com repository
$ gitfetch --format json --user octocat # machine-readable output
$ gitfetch --format svg --save profile.svg --user octocat # terminal render as SVG
$ gitfetch --format card --save profile-card.svg --user octocat # shareable profile card
$ gitfetch --format png --save profile-card.png --user octocat # shareable PNG card
```

4. For a guided setup, run the interactive config wizard.

```console
$ gitfetch config wizard
$ gitfetch config validate
$ gitfetch config path
```

5. For multiple accounts or saved targets, store named profiles in your config.

```console
$ gitfetch config profiles set work --provider github --user octocat --mode public
$ gitfetch config profiles set lab --provider gitlab --user gitlab-org --token-env GITLAB_TOKEN
$ gitfetch config profiles set forge --provider codeberg --user forgejo --token-env CODEBERG_TOKEN
$ gitfetch config profiles list
$ gitfetch --profile work
```

6. On macOS, you can store your token in Keychain and point `Gitfetch` at it through `profile.token_command`.

```console
$ gitfetch token store --service gitfetch --account work
$ gitfetch token status --service gitfetch --account work
$ gitfetch --set profile.token_command="security find-generic-password -a work -s gitfetch -w" --profile work
```

## Appearance and exports

Configuration presets (`config init --preset minimal|compact|full|showcase`) select
modules and settings. Visual presets only change how selected data appears:

```sh
gitfetch --presentation modern --visual-preset balanced
gitfetch --user octocat --presentation modern --visual-preset compact --theme nord
gitfetch --presentation modern --visual-preset showcase --details
gitfetch --avatar-renderer text --avatar-style halfblock
gitfetch --set display.avatar_fit=original
```

Modern presentation automatically fits visible avatar alpha; classic preserves
the source canvas. Kitty graphics are selected conservatively on supported direct
Ghostty/Kitty terminals. Unknown terminals, pipes, SSH, tmux and unverified Zellij
paths use safe text fallbacks. No full-screen UI or active terminal probe is used.
Windows uses text fallback. Physical support depends on the effective terminal.

```toml
[display]
visual_preset = "showcase"
layout = "split" # or stack
theme = "catppuccin-mocha"
[display.colors]
identity = "#cba6f7"
accent = "#89b4fa"
```

```sh
gitfetch --presentation modern --visual-preset showcase --format svg --save terminal.svg
gitfetch --format card --save profile.svg
gitfetch --visual-preset compact --theme nord --format png --save profile.png
gitfetch --set display.export_style=legacy --format card --save legacy.svg
```

`svg` is terminal-style output; `card` and `png` share a graphical layout.
Exports preserve the original avatar canvas by default; opt in with
`--set display.export_avatar_fit=visible`. Card dimensions use
`display.card_width`/`display.card_height`, bounded to eight million pixels.
`--details` expands already-selected data; fixed-size cards may still omit content
with a notice. Custom colors require six-digit hexadecimal values. Use
`--no-color` for terminal text or `--theme mono` for a monochrome card palette
(avatars retain their source colors).
Bundled fonts avoid optional system-font dependencies; some CJK/emoji glyphs may
appear as boxes. See [migration notes](docs/MIGRATION-V3.md) and
[export behavior](docs/export-design.md) for compatibility details.

## Modules

Run the below command to inspect all supported modules and whether they require a token.

```console
$ gitfetch modules list
```

The default module set includes identity, stats, languages, and contributions. Extra modules can be enabled in `config.toml` or with `--set`.

```console
$ gitfetch --set modules.repo_health.enabled=true --set modules.top_repos.enabled=true
$ gitfetch --set modules.releases.enabled=true --set modules.actions_status.enabled=true
$ gitfetch --set modules.contribution_breakdown.enabled=true --token ghp_xxxx
```

### Public optional modules

* `social_accounts`
* `organizations`
* `starred`
* `watched`
* `gists`
* `recent_activity`
* `profile_readme`
* `top_repos`
* `releases`
* `actions_status`
* `repo_health`
* `topics`
* `dependencies`
* `packages`
* `commit_cadence`
* `maintainer_activity`

### Token-backed optional modules

* `contributions`
* `sparkline`
* `streaks`
* `pull_requests`
* `issues`
* `pinned`
* `showcase`
* `sponsors`
* `discussions`
* `security_advisories`
* `contribution_breakdown`

## Config

`Gitfetch` by default reads `~/.config/gitfetch/config.toml` at the global path. 

You can optionally specify another file with `--config`.

```console
$ gitfetch config init --preset compact
$ gitfetch config init --preset full --force
$ gitfetch --config ./gitfetch.toml --user octocat
$ gitfetch --provider gitlab --base-url https://gitlab.example.com/api/v4 --user alice
$ gitfetch --provider gitea --base-url https://git.example.com/api/v1 --user alice
$ gitfetch --provider forgejo --base-url https://forgejo.example.com/api/v1 --user alice
```

You can also override any dotted config value for one run.

```console
$ gitfetch --set display.avatar=false
$ gitfetch --set profile.provider=gitlab
$ gitfetch --set providers.gitlab.base_url=https://gitlab.example.com/api/v4
$ gitfetch --set providers.forgejo.base_url=https://forgejo.example.com/api/v1
$ gitfetch --set modules.languages.limit=3
$ gitfetch --set modules.languages.max_repos=0 # scan every repo; default samples 40 to limit API cost
$ gitfetch --set repo_filters.exclude_forks=false
```

## Plugins

Plugin modules are local Python files that expose `register()` or `MODULES`. Add plugin paths and enabled plugin module names to `config.toml`.

```console
$ gitfetch --set 'plugins.paths=["./my_gitfetch_plugin.py"]' --set 'plugins.modules=["my_metric"]' --set plugins.allow_unsafe=true
```

### Example plugin

```python
from gitfetch.modules.builtin import ModuleResult

def my_metric(config, context, client):
    return ModuleResult("my_metric", "My Metric", [f"repos: {len(context.repos)}"], {"repos": len(context.repos)})

def register():
    return {
        "my_metric": {
            "handler": my_metric,
            "description": "Example local metric.",
            "token_required": False,
        }
    }
```

## Completions

Print a completion script for your shell, then source it from your shell config.

```console
$ gitfetch completions bash
$ gitfetch completions zsh
$ gitfetch completions fish
```

## Troubleshooting

Encountered an issue that isn't covered here? Open an issue or shoot me a message on Telegram, and I'll get it sorted asap!

### Situation 1: A module says it requires a token 🔐

Some Git Provider data is only available through authenticated API calls. Pass `--token`, set `GITHUB_TOKEN`, `GITLAB_TOKEN`, `BITBUCKET_TOKEN`, `GITEA_TOKEN`, `FORGEJO_TOKEN`, or `CODEBERG_TOKEN`, configure `profile.token_env`, or use `profile.token_command`.

```console
$ export GITHUB_TOKEN=ghp_xxxx
$ export GITLAB_TOKEN=glpat_xxxx
$ export BITBUCKET_TOKEN=xxxx
$ export GITEA_TOKEN=xxxx
$ export FORGEJO_TOKEN=xxxx
$ export CODEBERG_TOKEN=xxxx
$ gitfetch --token ghp_xxxx
$ gitfetch --set profile.token_command="security find-generic-password -a work -s gitfetch -w"
```

### Situation 2: I want to uninstall `Gitfetch` 😔

```console
$ pip uninstall gitfetch
```

If you installed via the installer script, also remove the `export PATH` line the installer added to your shell rc file (`~/.bashrc`, `~/.zshrc`, or `~/.config/fish/config.fish`).

### Situation 3: Shell PATH problems

Reactivate your virtual environment and inspect your shell startup file for old
installer PATH lines. Remove duplicate or incorrect entries; do not replace your
entire PATH. The current installer leaves shell files untouched in a virtualenv.

### Situation 4: I typed the wrong username and want to change it 🤡

**Step 1:**  
```console
$ cd ~/.config/gitfetch
$ ls -a
```

**Step 2:**  
Check to ensure that the file titled `config.toml` shows up.

**Step 3:**  
Use your favourite text editor to edit `profile.username`.

**Step 4:**  
```console
$ nvim config.toml
$ cat config.toml
```

**Step 5:**
Check to ensure that your username has been updated. The next `gitfetch` run reads `config.toml`.
