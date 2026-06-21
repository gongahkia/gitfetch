t[![](https://img.shields.io/badge/gitfetch_1.0-passing-light_green)](https://github.com/gongahkia/gitfetch/releases/tag/1.0)
[![](https://img.shields.io/badge/gitfetch_2.0-passing-green)](https://github.com/gongahkia/gitfetch/releases/tag/2.0)
![](https://github.com/gongahkia/gitfetch/actions/workflows/tests.yml/badge.svg)

# `Gitfetch` 🛻

Serving you snapshots of your [Git Provider](https://git-scm.com/) profile in the [CLI](https://en.wikipedia.org/wiki/Command-line_interface).

## Stack

* *Scripting*: [Python](https://www.python.org/), [Pip](https://pypi.org/project/pip/), [Pillow](https://pypi.org/project/Pillow/), [Requests](https://pypi.org/project/requests/)
* *API*: [GitHub Rest API](https://docs.github.com/en/rest?apiVersion=2022-11-28), [GitLab REST API](https://docs.gitlab.com/api/rest/), [Bitbucket Cloud REST API](https://developer.atlassian.com/cloud/bitbucket/rest/), [Gitea REST API](https://docs.gitea.com/api/), [Forgejo API](https://forgejo.org/docs/latest/user/api-usage/)

## Screenshots

<div align="center">
    <img src="assets/gitfetch.png" width="90%">
</div>

## Features

- ASCII art avatar rendered from your Git Provider profile picture
- Provider support for GitHub, GitLab, Bitbucket Cloud, Gitea, Forgejo, and Codeberg
- Profile stats: hours since joining, public repos, followers, days since last commit
- Top-5 language breakdown by repository bytes
- Contribution heatmap (last 12 weeks, requires `--token`)
- Config presets: `minimal`, `compact`, `full`, and `showcase`
- Named profiles for switching between saved provider users or token sources
- Public and authenticated viewer modes
- Terminal themes, margins, color controls, and split or stacked layouts
- Avatar styles: `ascii`, `halfblock`, and `braille`
- Output formats: `ansi`, `plain`, `json`, `svg`, `card`, and `png`
- Repository mode with repository stats, language breakdown, contributors, and recent commits
- Organization mode with organization stats, top repositories, and public members
- Compare mode with side-by-side profiles, rankings, language overlap, and metric summaries
- Cache, refresh, watch, and offline modes
- Bash, Zsh, and Fish shell completions
- Local plugin modules loaded from Python files

## Usage

> [!NOTE]  
> Note that `Gitfetch` minimally requires Python3.10+ to be installed, which can be downloaded [here](https://www.python.org/downloads/).  
> **Also** note that `Gitfetch` is optimized for terminals with font size 10.

The below instructions are for locally installing and running `Gitfetch`.

1. First run the below commands to install `Gitfetch` to your own machine.

```console
$ pip install git+https://github.com/gongahkia/gitfetch.git # use pip for a one-line install

$ git clone https://github.com/gongahkia/gitfetch # alternatively use the shell installer
$ cd gitfetch/installer
$ ./mainInstall.sh
```

2. Then execute any of the below commands once to intialise and store your `Gitfetch` config globally on your machine.

```console
$ gitfetch # uses saved username
$ gitfetch --user octocat # specify username
$ gitfetch --provider gitlab --user gitlab-org # render a GitLab user or namespace
$ gitfetch --provider bitbucket --user atlassian # render a Bitbucket workspace
$ gitfetch --provider codeberg --user forgejo # render a Codeberg profile or org
$ gitfetch --provider gitea --user gitea # render a Gitea.com profile or org
$ gitfetch --no-avatar # stats only, no ASCII art
$ gitfetch --token ghp_xxxx # authenticated; also accepts provider env variables such as GITHUB_TOKEN, GITLAB_TOKEN, BITBUCKET_TOKEN, GITEA_TOKEN, FORGEJO_TOKEN, or CODEBERG_TOKEN
```

3. You can also render repositories, organizations, comparisons, and files directly from the CLI.

```console
$ gitfetch repo octocat/Hello-World # render a repository profile
$ gitfetch org github # render an organization profile
$ gitfetch compare octocat torvalds # compare two or more users side-by-side
$ gitfetch --provider gitlab repo gitlab-org/gitlab # render a GitLab project
$ gitfetch --provider bitbucket repo atlassian/python-bitbucket # render a Bitbucket repository
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

Public optional modules include `social_accounts`, `organizations`, `starred`, `watched`, `gists`, `recent_activity`, `profile_readme`, `top_repos`, `releases`, `actions_status`, `repo_health`, `topics`, `dependencies`, `packages`, `commit_cadence`, and `maintainer_activity`.

Token-backed optional modules include `contributions`, `sparkline`, `streaks`, `pull_requests`, `issues`, `pinned`, `showcase`, `sponsors`, `discussions`, `security_advisories`, and `contribution_breakdown`.

## Config

`Gitfetch` reads `~/.config/gitfetch/config.toml` by default. You can use another file with `--config`.

```console
$ gitfetch config init --preset compact
$ gitfetch config init --preset full --force
$ gitfetch --config ./gitfetch.toml --user octocat
$ gitfetch --provider gitlab --base-url https://gitlab.example.com/api/v4 --user alice
$ gitfetch --provider gitea --base-url https://git.example.com/api/v1 --user alice
$ gitfetch --provider forgejo --base-url https://forgejo.example.com/api/v1 --user alice
```

You can override any dotted config value for one run.

```console
$ gitfetch --set display.avatar=false
$ gitfetch --set profile.provider=gitlab
$ gitfetch --set providers.gitlab.base_url=https://gitlab.example.com/api/v4
$ gitfetch --set providers.forgejo.base_url=https://forgejo.example.com/api/v1
$ gitfetch --set modules.languages.limit=3
$ gitfetch --set repo_filters.exclude_forks=false
```

## Plugins

Plugin modules are local Python files that expose `register()` or `MODULES`. Add plugin paths and enabled plugin module names to `config.toml`.

```console
$ gitfetch --set 'plugins.paths=["./my_gitfetch_plugin.py"]' --set 'plugins.modules=["my_metric"]'
```

A minimal plugin looks like this.

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

### A module says it requires a token 🔐

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

### I want to uninstall `Gitfetch` 😔

```console
$ pip uninstall gitfetch
```

If you installed via the installer script, also remove the `export PATH` line the installer added to your shell rc file (`~/.bashrc`, `~/.zshrc`, or `~/.config/fish/config.fish`).

### `ls`, `sudo` and other terminal commands suddenly don't work 😭

> *This might seem daunting, but I believe in you. You got this.*

**Step 1:**  
```console
$ cd ~ && ls -a
```

**Step 2:**  
Check to ensure that the file titled `.bashrc` shows up.

**Step 3:**  
Use your favourite text editor to insert the line `export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games"` at the **top** of your `.bashrc` file.

**Step 4:**
```console
$ nvim .bashrc
$ cat .bashrc
```

**Step 5:**
Check to ensure that the line has been added. End your terminal session and start a new one to reload `.bashrc` file.

### I typed the wrong username and want to change it 🤡

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
