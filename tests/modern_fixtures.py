"""Synthetic, fixed-date profiles and a local image for modern UI previews."""
import copy
import os
from datetime import date, datetime, timedelta, timezone
from unittest import mock

from PIL import Image, ImageDraw

from gitfetch.config import preset_config
from gitfetch.modules.builtin import ModuleResult
from gitfetch.presentation import build_profile_document
from gitfetch.render import render_output
from gitfetch.semantics import Measurement

REFERENCE = date(2026, 1, 28)
DIMENSIONS = ((40, 12), (60, 20), (80, 24), (100, 30), (120, 40), (140, 40), (200, 15), (200, 60))
CASES = {
    "standard-80x24": (80, 24, {}),
    "comfortable-100x30": (100, 30, {}),
    "large-140x40": (140, 40, {}),
    "compact-60x20": (60, 20, {}),
    "wide-short-200x15": (200, 15, {}),
    "no-avatar": (80, 24, {"avatar": False}),
    "details": (80, 24, {"details": True}),
    "monochrome": (100, 30, {"theme": "mono"}),
    "partial-contributions": (100, 30, {"partial": True}),
    "unicode-biography": (80, 24, {"unicode": True}),
}


def fixture(provider="github", *, partial=False, unicode=False, secondary=True):
    user = {"login": "alex-dev", "name": "Alex Rivera", "bio": "Building thoughtful developer tools and small, useful things for the open web.",
            "location": "Singapore", "company": "Open Source Collective", "blog": "alex.example",
            "avatar_url": "https://synthetic.invalid/avatar.png", "created_at": "2018-04-14T00:00:00Z",
            "public_repos": 42, "followers": 1280, "following": 87, "public_gists": 0}
    if unicode:
        user["name"] = "林明 · Alex Rivera"
        user["bio"] = "创造有用的软件 · cafe\u0301 · 👩🏽‍💻 · مرحبا بالعالم · " * 12
    if provider != "github":
        user["public_gists"] = None
    if provider == "bitbucket":
        user["followers"] = user["following"] = None
    totals = (("Python", 7300), ("TypeScript", 1600), ("Go", 600), ("Rust", 300), ("Shell", 100), ("Other", 100))
    unit = "bytes"
    scope = "languages in selected repositories"
    denominator = 10000
    if provider in {"gitlab", "bitbucket"}:
        totals = (("Python", 18), ("TypeScript", 12), ("Go", 8), ("Rust", 2), ("Shell", 1))
        unit = "repositories"
        denominator = 20
        scope = "language prevalence in selected repositories" if provider == "gitlab" else "primary language of selected repositories"
        if provider == "bitbucket":
            totals = (("Python", 12), ("TypeScript", 4), ("Go", 2), ("Rust", 1), ("Shell", 1))
    language = Measurement(provider=provider, unit=unit, scope=scope, coverage="partial", sample_size=20,
                           denominator=denominator, eligible_repositories=42, attempted=20,
                           sampling_policy="first 20 selected repositories", language_totals=totals)
    weeks = []
    counts = []
    for index in range(84):
        day = REFERENCE - timedelta(days=83 - index)
        if partial and index % 9 == 0:
            continue
        value = ((index * 7) % 13) if index % 6 else 0
        counts.append(value)
        if not weeks or day.weekday() == 6:
            weeks.append({"contributionDays": []})
        weeks[-1]["contributionDays"].append({"date": day.isoformat(), "contributionCount": value})
    contribution = Measurement(sum(counts), provider, "activity actions" if provider in {"gitea", "forgejo", "codeberg"} else "contributions",
                               "observed activity window", coverage="unknown" if partial or provider in {"gitea", "forgejo", "codeberg"} else "complete",
                               start=(REFERENCE - timedelta(days=83)).isoformat(), end=REFERENCE.isoformat())
    modules = [
        ModuleResult("identity", "Identity", ["@alex-dev", "Alex Rivera"], {"user": user}),
        ModuleResult("stats", "Stats", ["42 public repos", "1280 followers"], {"user": user}),
        ModuleResult("languages", "Languages", ["legacy languages"], [{"language": name, unit: value} for name, value in totals[:5]], measurements={"languages": language}),
        ModuleResult("contributions", "Contributions", ["legacy calendar"], weeks, measurements={"contributions": contribution}),
    ]
    if secondary:
        modules.extend([
            ModuleResult("streaks", "Streaks", ["observed streaks"], {"current": 3, "longest": 18, "total": sum(counts)}, measurements={
                "contributions": contribution,
                "current": Measurement(3, provider, "days", "observed current streak", coverage=contribution.coverage, start=contribution.start, end=contribution.end),
                "longest": Measurement(18, provider, "days", "longest observed streak in window", coverage=contribution.coverage, start=contribution.start, end=contribution.end)}),
            ModuleResult("pinned", "Pinned", ["alex-dev/gitfetch"], [
                {"__typename": "Repository", "nameWithOwner": "alex-dev/gitfetch", "stargazerCount": 284,
                 "primaryLanguage": {"name": "Python"}, "description": "A beautiful Git profile in your terminal.", "url": "https://example.test/gitfetch"},
                {"__typename": "Repository", "nameWithOwner": "alex-dev/tiny-tools", "stargazerCount": 0,
                 "primaryLanguage": {"name": "Go"}, "description": "Small tools, carefully made."}]),
            ModuleResult("recent_activity", "Recent activity", ["recent events"], [
                {"type": "PushEvent", "repo": "alex-dev/gitfetch", "created_at": "2026-01-28T09:00:00Z"},
                {"type": "ReleaseEvent", "repo": "alex-dev/tiny-tools", "created_at": "2026-01-27T12:00:00Z"}]),
        ])
    unsupported = {"pinned"} if provider != "github" else set()
    if provider in {"gitlab", "bitbucket"}:
        unsupported |= {"contributions", "streaks"}
    modules = [ModuleResult(module.name, module.title, [f"unsupported on {provider}"],
                            {"unsupported": True, "provider": provider, "reason": "no matching profile endpoint"},
                            measurements={module.name: Measurement(provider=provider, availability="unsupported")})
               if module.name in unsupported else module for module in modules]
    document = build_profile_document(user, modules, provider=provider, instance=f"https://{provider}.example/api")
    return user, modules, document


def avatar_image():
    image = Image.new("RGB", (96, 96), "#202136")
    draw = ImageDraw.Draw(image)
    for y in range(96):
        draw.line((0, y, 95, y), fill=(45 + y, 60 + y // 2, 130 + y))
    draw.rounded_rectangle((8, 8, 87, 87), radius=18, fill="#282a46")
    draw.ellipse((32, 20, 63, 51), fill="#dec3a5")
    draw.rounded_rectangle((22, 56, 73, 90), radius=17, fill="#83c4cd")
    draw.arc((30, 15, 66, 48), 180, 360, fill="#3b2d38", width=10)
    return image


def preview(case="standard-80x24", *, ansi=False, **overrides):
    columns, rows, settings = CASES[case]
    settings = {**settings, **overrides}
    user, modules, document = fixture(partial=settings.pop("partial", False), unicode=settings.pop("unicode", False))
    config = copy.deepcopy(preset_config("minimal"))
    config["display"].update({"presentation": "modern", "avatar": True, "layout": "split", **settings})
    config["_color_force"] = "on" if ansi else "off"
    with (mock.patch("gitfetch.render.shutil.get_terminal_size", return_value=os.terminal_size((columns, rows))),
          mock.patch("gitfetch.render._load_avatar", return_value=avatar_image()),
          mock.patch("gitfetch.render.datetime") as clock):
        clock.now.return_value = datetime.combine(REFERENCE, datetime.min.time(), timezone.utc)
        output = render_output(config, user, modules, "ansi" if ansi else "plain", document=document)
        # Empty split separators contain invisible legacy avatar padding.
        return "\n".join(line if line.strip() else "" for line in output.split("\n"))
