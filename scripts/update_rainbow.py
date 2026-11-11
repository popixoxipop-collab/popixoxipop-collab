#!/usr/bin/env python3
"""Generate a static rainbow heatmap from GitHub's public contribution calendar.

No credentials or third-party graph service are required. GitHub controls which
contribution counts are visible on the user's public profile.
"""
from __future__ import annotations

import datetime as dt
import html
from html.parser import HTMLParser
from pathlib import Path
import re
import urllib.request

USERNAME = "popixoxipop-collab"
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "rainbow-contributions.svg"
SOURCE = f"https://github.com/users/{USERNAME}/contributions"

class ContributionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.days: list[dict] = []
        self.tooltips: dict[str, str] = {}
        self.active_tooltip: str | None = None
        self.tooltip_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "td" and a.get("data-date") and "ContributionCalendar-day" in a.get("class", ""):
            self.days.append({"date": a["data-date"], "level": int(a["data-level"]), "id": a["id"]})
        if tag == "tool-tip" and a.get("for", "").startswith("contribution-day-component-"):
            self.active_tooltip = a["for"]
            self.tooltip_text = []

    def handle_data(self, data):
        if self.active_tooltip is not None:
            self.tooltip_text.append(data)

    def handle_endtag(self, tag):
        if tag == "tool-tip" and self.active_tooltip is not None:
            self.tooltips[self.active_tooltip] = "".join(self.tooltip_text).strip()
            self.active_tooltip = None
            self.tooltip_text = []

def contribution_count(tooltip: str) -> int:
    if tooltip.startswith("No contributions"):
        return 0
    found = re.match(r"([\d,]+) contributions? on ", tooltip)
    if found is None:
        raise ValueError(f"Unrecognized GitHub tooltip: {tooltip!r}")
    return int(found.group(1).replace(",", ""))

def make_svg():
    req = urllib.request.Request(
        SOURCE,
        headers={"User-Agent": "ProfileRainbow/1.0 (+https://github.com/popixoxipop-collab)"},
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        if response.status != 200:
            raise RuntimeError(f"GitHub returned {response.status}")
        source = response.read().decode("utf-8")

    parser = ContributionParser()
    parser.feed(source)
    if len(parser.days) < 350:
        raise ValueError(f"Expected at least 350 GitHub contribution cells, found {len(parser.days)}")

    unique_dates = {x["date"] for x in parser.days}
    if len(unique_dates) != len(parser.days):
        raise ValueError("Duplicate GitHub contribution date detected")

    for cell in parser.days:
        if cell["id"] not in parser.tooltips:
            raise ValueError(f"Missing tooltip for {cell['date']}")
        cell["count"] = contribution_count(parser.tooltips[cell["id"]])

    headline = re.search(
        r'id="js-contribution-activity-description"[^>]*>\s*([\d,]+)\s+contributions',
        source, flags=re.I,
    )
    if headline is None:
        raise ValueError("Could not read yearly contribution headline from GitHub")
    total = int(headline.group(1).replace(",", ""))

    days = sorted(parser.days, key=lambda x: x["date"])
    first = dt.date.fromisoformat(days[0]["date"])
    last = dt.date.fromisoformat(days[-1]["date"])
    first_sunday = first - dt.timedelta(days=(first.weekday() + 1) % 7)
    last_col = (last - first_sunday).days // 7
    if last_col < 50 or last_col > 54:
        raise ValueError(f"Unexpected calendar width: {last_col + 1} weeks")

    week_step = 20
    left = 71
    grid_top = 151
    grid_width = (last_col + 1) * week_step
    width = max(1190, left + grid_width + 37)
    height = 368
    weekday_colors = [
        "#ff697a", "#ffad59", "#f6d86c", "#66d49c",
        "#55c5d9", "#68a6ff", "#bc8fff",
    ]
    opacity = [1.0, .44, .64, .82, 1.0]
    cells = []
    month_labels = []
    prior_month = None

    for cell in days:
        date = dt.date.fromisoformat(cell["date"])
        col = (date - first_sunday).days // 7
        row = (date.weekday() + 1) % 7
        x = left + col * week_step
        y = grid_top + row * week_step
        level = cell["level"]
        if not 0 <= level <= 4:
            raise ValueError(f"Invalid GitHub contribution level: {level}")
        color = "#1d2c40" if level == 0 else weekday_colors[row]
        alpha = 1 if level == 0 else opacity[level]
        msg = f"{date.isoformat()}: {cell['count']:,} contribution(s)"
        cells.append(
            f'<rect x="{x}" y="{y}" width="15" height="15" rx="3" '
            f'fill="{color}" opacity="{alpha:.2f}"><title>{html.escape(msg)}</title></rect>'
        )
        if date.day <= 7 and date.month != prior_month:
            label = date.strftime("%b")
            if date.month == 1:
                label = f"Jan {date.year}"
            month_labels.append(
                f'<text x="{x}" y="140" font-size="13" '
                f'fill="#a6bbd6" font-family="Arial, sans-serif">{label}</text>'
            )
            prior_month = date.month

    display_period = f"{first.strftime('%b %d, %Y')} — {last.strftime('%b %d, %Y')}"
    updated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    count_cells = sum(x["count"] for x in days)
    legends = []
    for n, op in enumerate([1, .44, .64, .82, 1]):
        c = "#1d2c40" if n == 0 else "#66d49c"
        legends.append(f'<rect x="{830+n*24}" y="318" width="15" height="15" rx="3" fill="{c}" opacity="{op:.2f}"/>')

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}"
  width="{width}" height="{height}" role="img" aria-labelledby="svg-title svg-desc">
  <title id="svg-title">Rainbow GitHub contributions, last year</title>
  <desc id="svg-desc">GitHub public contribution activity for {USERNAME}, {display_period}; GitHub reports {total:,} contributions. Colored cells reflect GitHub activity levels, colored by weekday.</desc>
  <defs>
    <linearGradient id="spectrum" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#ff697a"/>
      <stop offset=".17" stop-color="#ffad59"/>
      <stop offset=".34" stop-color="#f6d86c"/>
      <stop offset=".51" stop-color="#66d49c"/>
      <stop offset=".68" stop-color="#55c5d9"/>
      <stop offset=".84" stop-color="#68a6ff"/>
      <stop offset="1" stop-color="#bc8fff"/>
    </linearGradient>
  </defs>
  <rect width="{width}" height="{height}" rx="19" fill="#101a2d"/>
  <rect width="{width}" height="6" rx="3" fill="url(#spectrum)"/>
  <text x="34" y="47" font-family="Arial, sans-serif" font-weight="750" font-size="24" fill="#f0f6ff">🌈 RAINBOW CONTRIBUTIONS</text>
  <text x="35" y="75" font-family="Arial, sans-serif" font-size="15" fill="#b8c9e2">{display_period}</text>
  <text x="{width-34}" y="46" font-family="Arial, sans-serif" font-weight="750" font-size="31" fill="#f5f8ff" text-anchor="end">{total:,}</text>
  <text x="{width-34}" y="72" font-family="Arial, sans-serif" font-size="13" fill="#a9bad4" text-anchor="end">GitHub reported contributions</text>
  <path d="M34 99H{width-34}" stroke="#32435f" stroke-width="1"/>
  <text x="27" y="{grid_top+33}" fill="#9cb2d1" font-size="13" font-family="Arial, sans-serif">Mon</text>
  <text x="27" y="{grid_top+73}" fill="#9cb2d1" font-size="13" font-family="Arial, sans-serif">Wed</text>
  <text x="27" y="{grid_top+113}" fill="#9cb2d1" font-size="13" font-family="Arial, sans-serif">Fri</text>
  {''.join(month_labels)}
  {''.join(cells)}
  <text x="35" y="331" fill="#afc2df" font-family="Arial, sans-serif" font-size="14">Less</text>
  {''.join(legends)}
  <text x="961" y="331" fill="#afc2df" font-family="Arial, sans-serif" font-size="14">More</text>
  <text x="35" y="354" fill="#7f99b8" font-family="Arial, sans-serif" font-size="11">Source: GitHub public profile · Refreshed {updated} · Privacy settings may affect visible totals</text>
</svg>
'''
    OUTPUT.parent.mkdir(exist_ok=True, parents=True)
    OUTPUT.write_text(svg, encoding="utf-8")
    print(f"PASS days={len(days)} grid_sum={count_cells} github_headline={total} "
          f"range={first}..{last} output={OUTPUT}")

if __name__ == "__main__":
    make_svg()
