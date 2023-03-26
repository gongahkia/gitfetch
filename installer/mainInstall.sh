#!/bin/bash

# --- appends the two neccesary lines to user's .bashrc file
echo "export PATH=~/.config/gitfetch-build/bin:$PATH" >> ~/.bashrc
echo "alias gitfetch='gitfetch.py'" >> ~/.bashrc

python3 installation.py
