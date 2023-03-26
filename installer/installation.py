import os
import platform
import os.path
import shutil
import time

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

# --- copies the desired executable to the ~/.config file path ✔️
destinationFilePath = f"/home/{os.getcwd().split('/')[2]}/.config/gitfetch-build"
shutil.copytree("../gitfetch-build", destinationFilePath)

# --- pseudo loading screen ✔️
counter = 0
filledProgressBar = ""
unfilledProgressBar = "---------------------------------------------------"
os.system("clear")
while counter < 102:
    filledProgressBar += "X"
    unfilledProgressBar = unfilledProgressBar.replace('-', '', 1)
    print(f"{prPurple('Gitfetch installer')}\nCloning files... [{prGreen(filledProgressBar)}{unfilledProgressBar}] {counter}%")
    time.sleep(0.25)
    os.system("clear")
    counter += 2
os.system("clear")
print(f"Files have been {prGreen('succesfully cloned')}!\nPlease follow the following steps to complete installation:\n(1) Close this terminal session and open a new one.\n(2) Run the command 'gitfetch' to get started.\n*These instructions are up on the github README.md as well!")
