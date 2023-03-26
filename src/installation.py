# TODO
    # --- * inside .sh shell script, run this installation file as "sudo installion.py" by default to write the file to the usr/bin class with shutil()
    # --- * to include in bash script, automatically download pip3, and download pillow, requests via pip3
    # --- * append lines to User's .bashrc to add program to their file, and add an alias so typing gitfetch is equal to calling the shell executable ./main.sh
    # --- * create a folder with the binary that will be downloaded to the ~/../../usr/bin file path
    # --- * need to account for those users without a .config directory, and make it for them
    # --- * style installation in same format as me downloading the items to nvim to my chromebook

import os
import platform
import os.path
import shutil

# --- colored text in terminal, argument taken in with single quote strings '' ✔️
def prRed(word):
    return "\033[91m{}\033[00m" .format(word)
def prGreen(word):
    return "\033[92m{}\033[00m" .format(word)
def prPurple(word):
    return "\033[95m{}\033[00m" .format(word)

# --- determine current platform ✔️
match platform.system(): 
    case "Linux":
        print(f"{prPurple('Hooray')}, installing now on {prGreen('Linux')}!")
    case "Darwin":
        print(f"{prPurple('Hooray')}, installing now on {prGreen('MacOS')}!")
    case "Windows":
        print(f"Sorry. Gitfetch is {prRed('not able to support windows')} currently!")
    case _:
        print(f"My brother in Christ, {prRed('what OS are you even using')}?")

# --- copies the desired binary to the ~/../../usr/bin file path ✔️
    # --- * edit this to copy the folder containing the gitfetch binary to the desired file path
shutil.copy("gitfetch.py", "/home/../../usr/bin")

print(f"Files have been {prGreen('succesfully added')}!")

os.chdir("/usr/bin")
os.system("ls")
