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

def color(text, code):
    return f"\033[{code}m{text}\033[00m"
def prRed(w): return color(w, 91)
def prGreen(w): return color(w, 92)
def prYellow(w): return color(w, 93)
def prLightPurple(w): return color(w, 94)
def prPurple(w): return color(w, 95)
def prCyan(w): return color(w, 96)
def prLightGray(w): return color(w, 97)
def prBlack(w): return color(w, 98)

HEATMAP_BLOCKS = [" ", "░", "▒", "▓", "█"]

def api_get(url, **kwargs):
    """wrapper for requests.get with network error handling"""
    try:
        resp = requests.get(url, timeout=15, **kwargs)
        resp.raise_for_status()
        return resp
    except requests.exceptions.ConnectionError:
        print(f"error: could not connect to {url}")
        raise SystemExit(1)
    except requests.exceptions.Timeout:
        print(f"error: request timed out for {url}")
        raise SystemExit(1)
    except requests.exceptions.HTTPError as e:
        if resp.status_code == 403:
            print(f"error: rate limited — {resp.json().get('message', '')}")
        elif resp.status_code == 404:
            print("error: user not found")
        else:
            print(f"error: HTTP {resp.status_code}")
        raise SystemExit(1)

def fetch_contributions(username, token):
    """fetch contribution data via GitHub GraphQL API, requires token"""
    query = """query($login: String!) {
        user(login: $login) {
            contributionsCollection {
                contributionCalendar {
                    weeks { contributionDays { contributionCount date } }
                }
            }
        }
    }"""
    resp = requests.post("https://api.github.com/graphql",
        json={"query": query, "variables": {"login": username}},
        headers={"Authorization": f"bearer {token}"})
    if resp.status_code != 200:
        return None
    data = resp.json()
    try:
        weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    except (KeyError, TypeError):
        return None
    return weeks

def render_heatmap(weeks, num_weeks=12):
    """render mini heatmap grid from recent weeks using unicode blocks"""
    recent = weeks[-num_weeks:] if len(weeks) > num_weeks else weeks
    maxCount = max((d["contributionCount"] for w in recent for d in w["contributionDays"]), default=1) or 1
    rows = [] # 7 rows (Sun-Sat)
    for day_idx in range(7):
        row = ""
        for week in recent:
            days = week["contributionDays"]
            if day_idx < len(days):
                level = min(4, days[day_idx]["contributionCount"] * 4 // maxCount)
                row += HEATMAP_BLOCKS[level]
            else:
                row += " "
        rows.append(row)
    return rows

def main():
    currentDate = datetime.now()
    leastNumberDays = -1

    parser = argparse.ArgumentParser(description="GitHub user info as ASCII art")
    parser.add_argument("--user", help="GitHub username")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""), help="GitHub API token (fallback: GITHUB_TOKEN env var)")
    parser.add_argument("--no-avatar", action="store_true", help="print stats only, skip avatar download")
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

    print("retrieving...")
    githubInfoRetrieval = api_get(f"https://api.github.com/users/{githubUsername}", headers=headers)
    userData = githubInfoRetrieval.json()

    userName = userData["login"]
    userBio = userData["bio"]

    if not args.no_avatar:
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
        resp = api_get(f"https://api.github.com/users/{githubUsername}/repos", params={"per_page": 100, "page": page}, headers=headers)
        batch = resp.json()
        if not batch:
            break
        repoData.extend(batch)
        page += 1
    numberOfRepos = userData["public_repos"] # from /users/ endpoint directly
    numberOfFollowers = userData["followers"] # from /users/ endpoint directly

    for repo in repoData:
        pushedAt = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
        delta = (datetime.now(pushedAt.tzinfo) - pushedAt).days
        if leastNumberDays == -1 or leastNumberDays > delta:
            leastNumberDays = delta

    # --- top language breakdown ✔️
    langTotals = {}
    for repo in repoData:
        if repo.get("languages_url"):
            langResp = api_get(repo["languages_url"], headers=headers)
            if langResp.status_code == 200:
                for lang, bytes_count in langResp.json().items():
                    langTotals[lang] = langTotals.get(lang, 0) + bytes_count
    totalBytes = sum(langTotals.values()) or 1
    topLangs = sorted(langTotals.items(), key=lambda x: x[1], reverse=True)[:5]
    langDisplay = ", ".join(f"{l} {b*100//totalBytes}%" for l, b in topLangs)

    infoLines = [
        f"@{prLightPurple(userName)}",
        "------------",
        f"{userBio}",
        f"{hoursSinceCreation} {prRed('hours')} since joining Github",
        f"{numberOfRepos} {prYellow('public Repos')}",
        f"{numberOfFollowers} {prGreen('followers')}",
        f"{leastNumberDays} {prCyan('days')} since last commit",
        f"{prPurple('langs')} {langDisplay}",
    ]

    if args.no_avatar:
        for line in infoLines:
            print(line)
    else:
        artHeight = len(ImgASCII)
        startRow = max(0, (artHeight - len(infoLines)) // 2)
        for i, line in enumerate(infoLines):
            idx = startRow + i
            if idx < artHeight:
                ImgASCII[idx] += "\t\t\t" + line
        print("\n".join(ImgASCII))

    # --- contribution heatmap (requires token) ✔️
    if args.token:
        weeks = fetch_contributions(githubUsername, args.token)
        if weeks:
            heatmap = render_heatmap(weeks)
            print(f"\n{prGreen('contributions')} (last 12 weeks)")
            for row in heatmap:
                print(f"  {row}")

if __name__ == "__main__":
    main()
