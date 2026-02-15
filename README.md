[![](https://img.shields.io/badge/gitfetch_1.0-passing-light_green)](https://github.com/gongahkia/gitfetch/releases/tag/1.0)
[![](https://img.shields.io/badge/gitfetch_2.0-passing-green)](https://github.com/gongahkia/gitfetch/releases/tag/2.0)

# `Gitfetch` 🛻

Serving you snapshots of your [GitHub](https://github.com/) profile in the [CLI](https://en.wikipedia.org/wiki/Command-line_interface). 

## Stack

* *Scripting*: [Python](https://www.python.org/), [Pip](https://pypi.org/project/pip/), [Pillow](https://pypi.org/project/Pillow/), [Requests](https://pypi.org/project/requests/)
* *API*: [GitHub Rest API](https://docs.github.com/en/rest?apiVersion=2022-11-28)

## Screenshots

<img src="assets/gitfetch.png" width="60%">

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
$ gitfetch --no-avatar # stats only, no ASCII art
$ gitfetch --token ghp_xxxx # authenticated (5000 req/hr), also accepts a GITHUB_TOKEN env variable as fallback
```

## Features

- ASCII art avatar rendered from your GitHub profile picture
- Profile stats: hours since joining, public repos, followers, days since last commit
- Top-5 language breakdown by repository bytes
- Contribution heatmap (last 12 weeks, requires `--token`)

## Troubleshooting

Encountered an issue that isn't covered here? Open an issue or shoot me a message on Telegram, and I'll get it sorted asap!

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

### I typed the wrong GitHub username and want to change it 🤡

**Step 1:**  
```console
$ cd ~/.config/gitfetch
$ ls -a
```

**Step 2:**  
Check to ensure that the file titled `.gitfetchConfig` shows up.

**Step 3:**  
Use your favourite text editor to edit the value associated with the *'username'* key in the file.

**Step 4:**  
```console
$ nvim .gitfetchConfig
$ cat .gitfetchConfig
```

**Step 5:**
Check to ensure that your username has been updated. End your terminal session and start a new one to reload `.gitfetchConfig` file.
