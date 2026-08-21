#!/usr/bin/env python3
"""Generate terminal-style GitHub stats SVG cards (dark + light).

Fetches public stats for USER via the GitHub GraphQL API and renders
generated/stats-dark.svg + generated/stats-light.svg. No external
dependencies — stdlib only.

Env:
  GITHUB_TOKEN   token for the GraphQL API (provided by Actions)
  STATS_OFFLINE  if set, JSON with the stats fields (skips the API)
"""
import json
import os
import sys
import urllib.request

USER = "adirangel"
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "generated")

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    contributionsCollection {
      contributionCalendar { totalContributions }
    }
    repositories(ownerAffiliations: OWNER, first: 100, isFork: false) {
      totalCount
      nodes {
        stargazerCount
        primaryLanguage { name color }
      }
    }
  }
}
"""


def fetch_stats():
    offline = os.environ.get("STATS_OFFLINE")
    if offline:
        return json.loads(offline)

    token = os.environ["GITHUB_TOKEN"]
    body = json.dumps({"query": QUERY, "variables": {"login": USER}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if "errors" in data:
        raise SystemExit(f"GraphQL errors: {data['errors']}")

    user = data["data"]["user"]
    repos = user["repositories"]
    langs = {}
    for node in repos["nodes"]:
        lang = node.get("primaryLanguage")
        if lang:
            entry = langs.setdefault(lang["name"], {"count": 0, "color": lang["color"] or "#8b949e"})
            entry["count"] += 1
    top_langs = sorted(langs.items(), key=lambda kv: -kv[1]["count"])[:5]

    return {
        "followers": user["followers"]["totalCount"],
        "prs": user["pullRequests"]["totalCount"],
        "issues": user["issues"]["totalCount"],
        "contributions": user["contributionsCollection"]["contributionCalendar"]["totalContributions"],
        "repos": repos["totalCount"],
        "stars": sum(n["stargazerCount"] for n in repos["nodes"]),
        "langs": [
            {"name": name, "count": info["count"], "color": info["color"]}
            for name, info in top_langs
        ],
    }


THEMES = {
    "dark": {
        "border": "#3d59a1",
        "title": "#38bdae",
        "prompt": "#bf91f3",
        "label": "#a9b1d6",
        "value": "#70a5fd",
        "dim": "#565f89",
    },
    "light": {
        "border": "#d0d7de",
        "title": "#1a7f37",
        "prompt": "#8250df",
        "label": "#57606a",
        "value": "#0969da",
        "dim": "#6e7781",
    },
}

W, H = 495, 195
FONT = "'JetBrains Mono','Cascadia Code',Consolas,'Liberation Mono',monospace"


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(stats, theme):
    c = THEMES[theme]
    fmt = lambda n: f"{n:,}"
    rows = [
        ("stars", fmt(stats["stars"]), "repos", fmt(stats["repos"])),
        ("commits (1y)", fmt(stats["contributions"]), "pull requests", fmt(stats["prs"])),
        ("issues", fmt(stats["issues"]), "followers", fmt(stats["followers"])),
    ]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="GitHub stats for {USER}">',
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="10" fill="none" stroke="{c["border"]}" stroke-opacity="0.6"/>',
        # terminal window dots
        '<circle cx="22" cy="22" r="5.5" fill="#ff5f56"/>',
        '<circle cx="40" cy="22" r="5.5" fill="#ffbd2e"/>',
        '<circle cx="58" cy="22" r="5.5" fill="#27c93f"/>',
        f'<text x="76" y="27" font-family={json.dumps(FONT)} font-size="13" fill="{c["prompt"]}">{USER}@devops:~$'
        f' <tspan fill="{c["title"]}">./stats.sh --live</tspan></text>',
        f'<line x1="16" y1="38" x2="{W - 16}" y2="38" stroke="{c["border"]}" stroke-opacity="0.35"/>',
    ]

    y = 64
    for l1, v1, l2, v2 in rows:
        parts.append(
            f'<text x="28" y="{y}" font-family={json.dumps(FONT)} font-size="13">'
            f'<tspan fill="{c["title"]}">▸</tspan> <tspan fill="{c["label"]}">{esc(l1)}</tspan>'
            f'<tspan x="196" fill="{c["value"]}" font-weight="bold">{v1}</tspan>'
            f'<tspan x="262" fill="{c["title"]}">▸</tspan> <tspan fill="{c["label"]}">{esc(l2)}</tspan>'
            f'<tspan x="440" fill="{c["value"]}" font-weight="bold">{v2}</tspan></text>'
        )
        y += 26

    # language bar
    langs = stats["langs"]
    total = sum(l["count"] for l in langs) or 1
    bar_x, bar_w, bar_y = 28, W - 56, 150
    x = bar_x
    parts.append(f'<clipPath id="bar"><rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="8" rx="4"/></clipPath>')
    for lang in langs:
        seg = bar_w * lang["count"] / total
        parts.append(
            f'<rect x="{x:.1f}" y="{bar_y}" width="{seg:.1f}" height="8" fill="{lang["color"]}" clip-path="url(#bar)"/>'
        )
        x += seg

    lx = bar_x
    for lang in langs:
        name = esc(lang["name"])
        parts.append(
            f'<circle cx="{lx + 4}" cy="{bar_y + 25}" r="4" fill="{lang["color"]}"/>'
            f'<text x="{lx + 13}" y="{bar_y + 29}" font-family={json.dumps(FONT)} font-size="11" fill="{c["dim"]}">{name}</text>'
        )
        lx += 13 + 7 * len(lang["name"]) + 22

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main():
    stats = fetch_stats()
    os.makedirs(OUT_DIR, exist_ok=True)
    for theme in THEMES:
        path = os.path.join(OUT_DIR, f"stats-{theme}.svg")
        with open(path, "w") as f:
            f.write(render(stats, theme))
        print(f"wrote {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
