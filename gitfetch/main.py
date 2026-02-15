import requests
import urllib.request
import json
import os
import os.path
import tempfile
import argparse
from PIL import Image
from datetime import datetime, date

chars = ["B","S","#","&","@","$","%","*","!",":","."]

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

def main():
    currentDate = datetime.now()
    leastNumberDays = -1

    parser = argparse.ArgumentParser(description="GitHub user info as ASCII art")
    parser.add_argument("--user", help="GitHub username")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""), help="GitHub API token (fallback: GITHUB_TOKEN env var)")
    args = parser.parse_args()
    headers = {"Authorization": f"token {args.token}"} if args.token else {}

    configDir = os.path.join(os.path.expanduser("~"), ".config", "gitfetch")
    os.makedirs(configDir, exist_ok=True)
    destinationFilePath = os.path.join(configDir, ".gitfetchConfig")

    if args.user:
        githubUsername = args.user
    elif os.path.isfile(destinationFilePath):
        with open(destinationFilePath, "r") as fhand:
            configFiles = json.load(fhand)
        githubUsername = configFiles["username"]
    else:
        githubUsername = input("Enter Github Username: ")
        with open(destinationFilePath, "w") as fhand:
            json.dump({"username": githubUsername}, fhand)

    githubInfoRetrieval = requests.get(f"https://api.github.com/users/{githubUsername}", headers=headers)
    if githubInfoRetrieval.status_code == 200:
        print("retrieving...")
        userData = json.loads(githubInfoRetrieval.text)
    elif githubInfoRetrieval.status_code == 403:
        print(githubInfoRetrieval.status_code)
        print(json.loads(githubInfoRetrieval.text)["message"])
        return
    else:
        print("error retrieving name, please input a valid username")
        return

    userName = userData["login"]
    userBio = userData["bio"]

    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    try:
        urllib.request.urlretrieve(userData["avatar_url"], tmp.name)
        avatarImg = Image.open(tmp.name)
        width, height = avatarImg.size
        aspect_ratio = height/width
        new_width = 100
        new_height = aspect_ratio * new_width * 0.55
        avatarImg = avatarImg.resize((new_width, int(new_height)))
        avatarImg = avatarImg.convert("L")
        pixels = avatarImg.getdata()
        new_pixels = [chars[pixel//25] for pixel in pixels]
        new_pixels = "".join(new_pixels)
        new_pixels_count = len(new_pixels)
        ImgASCII = [new_pixels[index:index + new_width] for index in range(0, new_pixels_count, new_width)]
    finally:
        tmp.close()
        os.remove(tmp.name)

    createdAt = datetime.fromisoformat(userData["created_at"].replace("Z", "+00:00"))
    hoursSinceCreation = int((datetime.now(createdAt.tzinfo) - createdAt).total_seconds() / 3600)

    repoData = []
    page = 1
    while True:
        resp = requests.get(f"https://api.github.com/users/{githubUsername}/repos", params={"per_page": 100, "page": page}, headers=headers)
        batch = json.loads(resp.text)
        if not batch:
            break
        repoData.extend(batch)
        page += 1
    numberOfRepos = len(repoData)

    followersData = []
    page = 1
    while True:
        resp = requests.get(f"https://api.github.com/users/{githubUsername}/followers", params={"per_page": 100, "page": page}, headers=headers)
        batch = json.loads(resp.text)
        if not batch:
            break
        followersData.extend(batch)
        page += 1
    numberOfFollowers = len(followersData)

    for repo in repoData:
        pushedAt = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
        delta = (datetime.now(pushedAt.tzinfo) - pushedAt).days
        if leastNumberDays == -1 or leastNumberDays > delta:
            leastNumberDays = delta

    # --- top language breakdown ✔️
    langTotals = {}
    for repo in repoData:
        if repo.get("languages_url"):
            langResp = requests.get(repo["languages_url"], headers=headers)
            if langResp.status_code == 200:
                for lang, bytes_count in langResp.json().items():
                    langTotals[lang] = langTotals.get(lang, 0) + bytes_count
    totalBytes = sum(langTotals.values()) or 1
    topLangs = sorted(langTotals.items(), key=lambda x: x[1], reverse=True)[:5]
    langDisplay = ", ".join(f"{l} {b*100//totalBytes}%" for l, b in topLangs)

    infoLines = [
        f"\t\t\t@{prLightPurple(userName)}",
        "\t\t\t------------",
        f"\t\t\t{userBio}",
        f"\t\t\t{hoursSinceCreation} {prRed('hours')} since joining Github",
        f"\t\t\t{numberOfRepos} {prYellow('public Repos')}",
        f"\t\t\t{numberOfFollowers} {prGreen('followers')}",
        f"\t\t\t{leastNumberDays} {prCyan('days')} since last commit",
        f"\t\t\t{prPurple('langs')} {langDisplay}",
    ]
    artHeight = len(ImgASCII)
    startRow = max(0, (artHeight - len(infoLines)) // 2)
    for i, line in enumerate(infoLines):
        idx = startRow + i
        if idx < artHeight:
            ImgASCII[idx] += line
    ImgASCII = "\n".join(ImgASCII)
    print(ImgASCII)

if __name__ == "__main__":
    main()
