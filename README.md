# gitfetch 🛻

[Neofetch](https://github.com/dylanaraps/neofetch) for your Github profile.

> ***Gitfetch*** is optimized for terminals with font size 10.

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

### WSL (Debian, Ubuntu, Fedora)

```console
> git clone https://github.com/gongahkia/gitfetch
> cd installer
> ./mainInstall.sh
```

### Linux, MacOS

```console
$ git clone https://github.com/gongahkia/gitfetch
$ cd installer
$ ./mainInstall.sh
```
# Troubleshooting

Encountered an issue that isn't covered here? Open an issue or shoot me a message on Telegram, and I'll get it sorted asap!

---

### I want to uninstall Gitfetch 😔

```console
```

---

### `ls`, `sudo` and other terminal commands suddenly don't work 😭

> *This might seem daunting, but I believe in you. You got this.*

**Step 1:**  
```console
$ cd ~ && ls -a
```

**Step 2:**  
Check to ensure that the file titled `.bashrc` shows up.

**Step 3:**  
Use your favourite text editor to insert the string `export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games"` at the **top** of your `.bashrc` file.

**Step 4:**
```console
$ nvim .bashrc
$ cat .bashrc
```

**Step 5:**
Check to ensure that the string has been added. End your terminal session and start a new one to reload `.bashrc` file.

---

### I typed the wrong Github username and want to change it 🤡

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
$ nvim .gitfetchConfig
$ cat .gitfetchConfig
```

**Step 5:**
Check to ensure that your username has been updated. End your terminal session and start a new one to reload `.gitfetchConfig` file.
