#!/bin/bash

# colors within Bash prompts ✔️ 
RED="\e[31m"
GREEN="\e[32m"
BLUE="\e[34m"
GRAY="\e[90m"
ENDCOLOR="\e[0m"

# check the linux distro of local machine ✔️ 
function linuxDistro() {
    if [[ -f /etc/os-release ]]
    then
        source /etc/os-release
        echo $ID
    fi
}

# check OS of local machine, install pip3 accordingly ✔️
if [[ $OSTYPE == darwin ]]; then
    printf "OS: ${BLUE}MacOS${ENDCOLOR}\n"
    curl -O https://bootstrap.pypa.io/ez_setup.py
    python3 ez_setup.py
    curl -O https://bootstrap.pypa.io/get-pip.py
    python3 get-pip.py
    cd /usr/local/bin
    ln -s ../../../Library/Frameworks/Python.framework/Versions/3.3/bin/pip pip

elif [[ $OSTYPE == linux-gnu ]]; then
    case $(linuxDistro) in
        raspbian)
            printf "OS: ${BLUE}Linux${ENDCOLOR}\nDistro: ${BLUE}Raspbian${ENDCOLOR}\n"
            printf "${RED}No support${ENDCOLOR} for Rapsberry Pi OS"
            ;;
        fedora)
            printf "OS: ${BLUE}Linux${ENDCOLOR}\nDistro: ${BLUE}Fedora${ENDCOLOR}\n"
            sudo dnf install python3-pip
            ;;
        ubuntu)
            printf "OS: ${BLUE}Linux${ENDCOLOR}\nDistro: ${BLUE}Ubuntu/Debian${ENDCOLOR}\n"
            sudo apt install python3-pip
            ;;
        * )
            printf "OS: ${RED}Not found${ENDCOLOR}\nDistro: ${RED}Not found${ENDCOLOR}\n"
            ;;
    esac
fi

# install python3 dependencies via pip3 package manager ✔️
pip3 install requests
pip3 install Pillow

# --- appends the two neccesary lines to user's .bashrc file ✔️
echo "export PATH=~/.config/gitfetch-build/bin:$PATH" >> ~/.bashrc
echo "alias gitfetch='gitfetch.py'" >> ~/.bashrc

# --- runs main python installation file to clone gitfetch executable build ✔️
python3 installation.py
