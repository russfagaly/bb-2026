# 2026 Alameda Little League Majors — Stats Site Brief

## What this is

A season-stats tracker for an 8-team Little League division. Box scores come
from GameChanger screenshots, data is hand-extracted into per-game Python files,
and a Python pipeline compiles it all into an Excel workbook, a live Google
Sheet, and a single-page HTML site hosted on GitHub Pages.

I'm now rebuilding the web presentation in Claude Design. This package contains
everything I have — raw data, compiled data, narrative reports, and the current
site as a visual reference.

## Season snapshot

- **League:** 2026 Alameda Little League Majors (8 teams)
- **Teams:** Astros, Brewers, Giants, Guardians, Marlins, Padres, White Sox, Yankees
- **Date range in this snapshot:** 2026-03-07 through 2026-04-19 (27 game days)
- **82 game files** → 916 hitting lines, 256 pitching lines
- **96 distinct hitters, 54 distinct pitchers**

## What the new site should do

In rough priority order:

1. **Leaderboards** — ranked Top 10 for the hitting and pitching categories
   already computed in `compiled_data/leaderboards.json`. Mobile-first; parents
   should be able to pull it up on their phone at the field.
2. **Team pages** — one per team, showing team totals, the roster with season
   stats, and a game log.
3. **Player pages** — season line plus game-by-game for the player.
4. **Schedule / results** — list of game days with the teams that played.
5. **Narrative reports** — surface the kind of written analysis in
   `narrative_reports/Pitching_Report_2026.md` alongside the numbers.
6. **Live refresh** — today the Google Sheet is rebuilt nightly on a Mac
   LaunchAgent. Ideally the new site reads from the same source so it stays in
   sync without me touching anything.

The existing `reference/current_site_index.html` is the mobile-first SPA I built
that works today — use it as a visual + structural baseline. Treat it as a
starting point, not a constraint; the Design rebuild is the chance to make it
cleaner.

## What's in this package

```
PROJECT_BRIEF.md              ← this file
compiled_data/                ← JSON + xlsx — feed these to the site
  meta.json                      league meta, teams, counts, data notes
  player_stats.json              season totals per player (hitting + pitching)
  team_stats.json                season totals per team
  leaderboards.json              ranked Top-10 for every category
  schedule.json                  game days with teams that played
  games.json                     every raw per-player-per-game line
  2026 ALL MAJORS STATS.xlsx     the same data as a workbook
narrative_reports/            ← written content to surface in the UI
  Pitching_Report_2026.md        season pitching analysis
  padres_vs_yankees_report.html  sample single-game write-up
reference/
  current_site_index.html        my current GitHub Pages site (visual baseline)
source/                       ← everything needed to rebuild data from scratch
  games/*.py                     one file per (team, date) — source of truth
  pipeline/*.py, *.sh, *.md      compile, validate, name registry, instructions
  images/*.png                   GameChanger box score screenshots (242 files)
```

## Data model (for the Design import)

`player_stats.json` is the easiest starting point. Each hitter row:

```
{
  "name": "Colton D",
  "team": "Astros",
  "jersey": "19",
  "games": 8,
  "ab": 23, "r": 7, "h": 9,
  "doubles": 3, "triples": 0, "hr": 1,
  "rbi": 8, "bb": 4, "so": 3,
  "sb": 4, "cs": 1, "e": 2, "hbp": 0,
  "avg": 0.391, "obp": 0.481, "slg": 0.652, "ops": 1.133,
  "tb": 15, "xbh": 4
}
```

Each pitcher row:

```
{
  "name": "Ace Beaver",
  "team": "White Sox",
  "jersey": "12",
  "games": 5,
  "ip": "21.2", "ip_dec": 21.667,
  "h": 18, "r": 7, "er": 4, "bb": 9, "so": 28,
  "hbp": 0, "bf": 95, "pitches": 312, "strikes": 195,
  "era": 1.66, "whip": 1.25, "strike_pct": 0.625,
  "k_per_6": 7.75, "bb_per_6": 2.49, "h_per_6": 4.98,
  "k_bb": 3.11
}
```

`games.json` has the same fields but with `team`, `date`, `iso_date`, and `file`
on every row — use it for game logs and player detail pages.

## Data quirks worth knowing

- **Name format.** Canonical player strings in `games/*.py` are
  `First LastInitial #Jersey` (e.g. `"Colton D #19"`). The JSON splits that into
  `name` and `jersey`.
- **Jersey swap.** Astros #11/#13 (Lukas I and Kolin I) swapped jerseys after
  03/10. Both rows are correct data, not a dedup bug.
- **Two Henrys.** Yankees has two different players named "Henry S" — #7 and
  #47. Treat as distinct.
- **Truncated names.** GameChanger truncates some long names; the `...` form
  (e.g. `"Benjami..."`) is the canonical key in the data.
- **bf = 0** in the raw game file means the batters-faced number was illegible
  on the screenshot. The compile logic already excludes those from totals so
  the JSON is clean.

## How the data is refreshed today

1. I drop GameChanger box-score screenshots into `source/images/`.
2. In a Claude session I ask it to extract data and write a new
   `source/games/YYYY_MM_DD_Team.py` file.
3. `pipeline/validate.py` checks data integrity.
4. `pipeline/compile.py` rebuilds the Excel workbook.
5. A macOS LaunchAgent runs `pipeline/compile_sheets.py` nightly to push to
   Google Sheets, and a GitHub Action rebuilds `index.html` on push.

Full instructions are in `source/pipeline/INSTRUCTIONS.md`.

## What I'd like from Claude Design

A clean, fast, mobile-first site that reads from `compiled_data/*.json` (or the
equivalent after you pull it in), organized around leaderboards / teams /
players / schedule / reports. Feel free to reshape the JSON schema if that
makes the front-end cleaner — I can rewrite `gen_stats_json.py` to produce
whatever format works best.
