# gitfetch 🛻

[Neofetch](https://github.com/dylanaraps/neofetch) for your Github profile.

> ***Gitfetch*** is optimized for terminals with a font size 10

![](assets/gitfetch.png)

# Quick start

## Prerequisites

***Gitfetch*** minimally requires Python3+ to be installed. Download from [here](https://www.python.org/downloads/). 

## Dependencies

All dependencies are handled by the installer.

- [Python Pip3+](https://pypi.org/project/pip/)
- [Pillow](https://pypi.org/project/Pillow/)
- [Requests](https://pypi.org/project/requests/)

## Installation

### Linux, MacOS

```console
$ git clone https://github.com/gongahkia/gitfetch
$ cd installer
$ ./mainInstall.sh
```
# Troubleshooting

Encountered an issue that isn't covered here? Open an issue or shoot me a message on Telegram, and I'll get it sorted asap!

## I want to uninstall Gitfetch 😔

```console
```

## `ls`, `sudo` and other terminal commands suddenly don't work 😭

```console
```

## I typed the wrong Github username and want to change it 🤡

**Step 1:**  
```console
$ cd ~/.config/gitfetch-build/bin
$ ls -a
```

**Step 2:**  
Check to ensure that the file titled `.gitfetchConfig` shows up.

**Step 3:**  
Use your favourite text editor to edit the value associated with the *'username'* key in the file.

**Step 4:**  
```console
$ cat .gitfetchConfig
$ nvim .gitfetchConfig
```
