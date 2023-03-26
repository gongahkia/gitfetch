# TODO
    # --- * need to account for users who have multiple newline characters in their user bio
    # --- * convert github username to be taken as a bash argument the first time

# --- required imports ✔️
import requests
import urllib.request
import json
import os
import os.path
from PIL import Image
from datetime import date

# --- prepwork ✔️
chars = ["B","S","#","&","@","$","%","*","!",":","."]
leastNumberDays = -1

# --- colored text in terminal, argument taken in with single quote strings '' ✔️
def prRed(word):
    return "\033[91m{}\033[00m" .format(word)
def prGreen(word):
    return "\033[92m{}\033[00m" .format(word)
def prYellow(word):
    return "\033[93m{}\033[00m" .format(word)
def prLightPurple(word):
    return "\033[94m{}\033[00m" .format(word)
def prPurple(word):
    return "\033[95m{}\033[00m" .format(word)
def prCyan(word):
    return "\033[96m{}\033[00m" .format(word)
def prLightGray(word):
    return "\033[97m{}\033[00m" .format(word)
def prBlack(word):
    return "\033[98m{}\033[00m" .format(word)

currentDate = str(date.today())
yearCurrent:int = int(currentDate.split("-")[0])
monthCurrent:int = int(currentDate.split("-")[1])
dayCurrent:int = int(currentDate.split("-")[2])

# --- actual program loop ✔️
while True:
    if os.path.isfile(".gitfetchConfig"): # --- set default github username once, then run it automatically after ✔️
        fhand = open(".gitfetchConfig", "r")
        configFiles = json.load(fhand)
        githubUsername:str = configFiles["username"]
    else:
        githubUsername:str = input("Enter Github Username: ")
        fhand = open(".gitfetchConfig", "w")
        fhand.write('{"username" : "'+ githubUsername + '"}')
        fhand.close()

    githubInfoRetrieval = requests.get(f"https://api.github.com/users/{githubUsername}") 

    if githubInfoRetrieval.status_code == 200:
        print("retrieving...")
        userData:dict = json.loads(githubInfoRetrieval.text)
        
    elif githubInfoRetrieval.status_code == 403: # --- possible to get rate-limited by Github API so be careful
        print(githubInfoRetrieval.status_code)
        print(json.loads(githubInfoRetrieval.text)["message"])
        break

    else:
        print("error retrieving name, please input a valid username")
        break
    
    # --- general user info ✔️
    userName = userData["login"]
    userBio = userData["bio"]

    # --- include ASCII art here ✔️   
    urllib.request.urlretrieve(userData["avatar_url"], "avatar.jpg")
    avatarImg = Image.open("avatar.jpg")
    
    width, height = avatarImg.size
    aspect_ratio = height/width
    new_width = 100 # --- default is 120, can be adjusted for greater resolution 
    new_height = aspect_ratio * new_width * 0.55
    avatarImg = avatarImg.resize((new_width, int(new_height)))

    avatarImg = avatarImg.convert("L")
    pixels = avatarImg.getdata()

    new_pixels = [chars[pixel//25] for pixel in pixels]
    new_pixels = "".join(new_pixels)
    new_pixels_count = len(new_pixels)
    ImgASCII = [new_pixels[index:index + new_width] for index in range(0, new_pixels_count, new_width)]
    os.system("rm avatar.jpg")

    # --- number of hours since creation of account ✔️
    dateOfCreation:str = userData["created_at"].split("T")[0]
    yearOfCreation:int = int(dateOfCreation.split("-")[0])
    monthOfCreation:int = int(dateOfCreation.split("-")[1])
    dayOfCreation:int = int(dateOfCreation.split("-")[2])
    yearDiff:int = yearCurrent - yearOfCreation
    monthDiff:int = monthCurrent - monthOfCreation
    dayDiff:int = dayCurrent - dayOfCreation
    hoursSinceCreation:int = abs(((yearDiff - 1) * 365) + (monthDiff * 30) + (dayDiff)) * 24

    # --- number of github repos ✔️
    githubRepoInfo = requests.get(f"https://api.github.com/users/{githubUsername}/repos")
    repoData:dict = json.loads(githubRepoInfo.text)
    numberOfRepos:int = len(repoData)

    # --- number of followers and their names (up to 10 displayed) ✔️
    githubFollowersInfo = requests.get(f"https://api.github.com/users/{githubUsername}/followers")
    followersData:dict = json.loads(githubFollowersInfo.text)
    numberOfFollowers = len(followersData)

    # --- days since last commit/action ✔️
    currentDateFormatted:date = date(yearCurrent, monthCurrent, dayCurrent)
    for repo in repoData:
        tempDateList:list = (repo["pushed_at"].split("T")[0]).split("-")
        givenDateFormatted:date = date(int(tempDateList[0]), int(tempDateList[1]), int(tempDateList[2]))
        delta = currentDateFormatted - givenDateFormatted
        if leastNumberDays == -1 or leastNumberDays > delta.days:
            leastNumberDays = delta.days
    
    # --- combining ASCII art and all the collated info ✔️
    ImgASCII[24] += f"\t\t\t@{prLightPurple(userName)}"
    ImgASCII[25] += "\t\t\t------------"
    ImgASCII[26] += f"\t\t\t{userBio}"
    ImgASCII[27] += f"\t\t\t{hoursSinceCreation} {prRed('hours')} since joining Github"
    ImgASCII[28] += f"\t\t\t{numberOfRepos} {prYellow('public Repos')}"
    ImgASCII[29] += f"\t\t\t{numberOfFollowers} {prGreen('followers')}"
    ImgASCII[30] += f"\t\t\t{leastNumberDays} {prCyan('days')} since last commit"
    ImgASCII = "\n".join(ImgASCII)

    print(ImgASCII)

    # --- if user wants the ASCII file to be saved to machine, uncomment the below portion ✔️
    """with open("avatarImgASCII.txt", "w") as f:
        f.write(ImgASCII)"""

    break # --- break statement to ensure I don't get rate-limited by Github API immediately
