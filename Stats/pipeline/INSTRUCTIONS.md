# 2026 Alameda Little League Majors — Stats Pipeline Instructions

This document tells any future Claude session exactly how to add new game data and rebuild the stats workbook. Read this fully before touching any files.

---

## Folder Structure

```
mnt/Stats/
  images/               ← All source PNG screenshots (GameChanger box scores)
  games/                ← One .py file per team per game date (source of truth)
  pipeline/
    compile.py          ← Builds the Excel backup (.xlsx)
    compile_sheets.py   ← Pushes live data to Google Sheets (run on local Mac)
    validate.py         ← Data integrity checker — run BEFORE compiling
    name_registry.py    ← Canonical player name map (team, jersey) → name
    recompile.sh        ← Full pipeline: validate → Excel → Google Sheets
    install_autorun.sh  ← One-command macOS daily scheduler installer
    credentials.json    ← Google service account key (do not share/commit)
    INSTRUCTIONS.md     ← This file
  2026 ALL MAJORS STATS.xlsx   ← Excel backup (overwritten each compile)
```

**Live Google Sheet:** https://docs.google.com/spreadsheets/d/1wvF3cMIxd_XeI71QNM6gkyrK192QEc_uMm4hSUG67Ms

**The `games/` folder is the single source of truth.** The .xlsx is generated from it. Never manually edit the workbook — always edit game files and recompile.

---

## How to Add New Games

### Step 1 — Add the new images to `images/`

GameChanger produces box score screenshots. The user will say something like "I added images from March 22." Images follow these naming patterns (though the exact filenames don't matter):

- **Hitting box score (basic):** Shows AB, R, H, RBI, BB, SO per player
- **Hitting extended (XBH):** Shows 2B, 3B, HR, SB, CS, E per player
- **Pitching box score:** Shows IP, H, R, ER, BB, SO per pitcher
- **Pitching extended:** Shows Pitches-Strikes per pitcher and Batters Faced

Each game generates **4 images** (2 hitting + 2 pitching), one team per game.

### Step 2 — Read the images and identify what's new

Tell Claude: "New images have been added to `images/`. Please identify which game files are missing and extract the data."

Claude should:
1. List all files in `images/` and compare against existing `games/` files to find gaps
2. Use the Read tool on each new PNG to view it

### Step 3 — Extract data from images

For each new game, read all 4 images for that team+date:

**From hitting basic image:**
- Player name with jersey number (e.g., "Colton D #19")
- AB, R, H, RBI, BB, SO

**From hitting XBH image (second hitting screenshot):**
- Doubles (2B), Triples (3B), Home Runs (HR)
- Stolen Bases (SB), Caught Stealing (CS), Errors (E)

**From pitching basic image:**
- Player name with jersey number
- IP (must be X.0, X.1, or X.2 format)
- H, R, ER, BB, SO, HBP

**From pitching extended image:**
- Look for lines like: `Pitches-Strikes: Name1 P-S, Name2 P-S, ...`
- Look for lines like: `Batters Faced: Name1 BF, Name2 BF, ...`
- Extract pitches, strikes, bf for each pitcher

**Important data notes:**
- If pitch count or BF text is illegible, use 0 (not null). bf=0 is specifically handled to mean "unknown" in compile.py.
- HBP is rarely shown on GameChanger; default to 0 if not shown.

### Step 4 — Check names against the registry

Before writing any game file, validate every player name:

```python
from pipeline.name_registry import REGISTRY, ALIASES, canonical_name

# For a raw name like "M Moyer #7" on Brewers:
bare = "M Moyer"
if bare in ALIASES:
    print(f"Use '{ALIASES[bare]}' instead")  # → "Miles M"

# For a jersey lookup:
expected = canonical_name("Brewers", "7")  # → "Miles M"
```

**Name format rules:**
- Always use `First-Name Last-Initial #Jersey` format, e.g., `"Miles M #7"`
- GameChanger sometimes outputs `First-Initial Last-Name` (e.g., `"M Moyer"`). Check `ALIASES` and correct it.
- GameChanger sometimes truncates long names (e.g., `"Camero... #34"`). If a canonical entry exists in `REGISTRY`, use it; otherwise keep the truncated form consistently.
- If a player's jersey number is not yet in `REGISTRY`, add them to `name_registry.py` and document them.

**Conflict handling:**
- Same (team, jersey) as existing registry entry → use the registry name (it's canonical)
- New jersey not in registry → add to registry, noting any ambiguity
- Two different names for same jersey → check other images for that game to resolve; if still ambiguous, ask the user before writing the file

### Step 5 — Write the game file

Create a new file in `games/` named `YYYY_MM_DD_TeamName.py` (underscores, no spaces):

```
games/2026_03_22_Astros.py
games/2026_03_22_Brewers.py
```

Template:

```python
"""
2026 Alameda Little League Majors
Team:  Astros
Date:  03/22
"""
TEAM = "Astros"
DATE = "03/22"

# Hitting: all stats including 2B/3B/HR/SB/CS/E already merged
hitting = [
    {"name": "Colton D #19", "ab": 3, "r": 1, "h": 2, "rbi": 1, "bb": 0, "so": 0,
     "doubles": 1, "triples": 0, "hr": 0, "sb": 0, "cs": 0, "e": 0},
    # ... one dict per player
]

# Pitching: includes pitches/strikes/BF
pitching = [
    {"name": "Colton D #19", "ip": "2.0", "h": 0, "r": 1, "er": 0, "bb": 2,
     "so": 3, "pitches": 34, "strikes": 20, "bf": 9, "hbp": 0},
    # ... one dict per pitcher
]
```

**Required fields:**
- Hitting: `name, ab, r, h, rbi, bb, so, doubles, triples, hr, sb, cs, e`
- Pitching: `name, ip, h, r, er, bb, so, pitches, strikes, bf, hbp`

All numeric fields must be integers ≥ 0. IP must be a string like `"2.0"`, `"1.1"`, `"3.2"`.

### Step 6 — Validate

```bash
cd mnt/Stats
python3 pipeline/validate.py
```

Fix any **ERROR** before proceeding. **WARNINGs** may need investigation.

Common errors and fixes:
| Error | Fix |
|---|---|
| `old name format` | Update name to canonical format per ALIASES |
| `XBH > H` | Recheck XBH image; correct doubles/triples/hr |
| `not in registry` | New player — add to REGISTRY in name_registry.py |
| `expected X, got Y` | Name mismatch — correct to registry value |
| `invalid IP` | IP must end in .0, .1, or .2 only |
| `no jersey number` | Add `#NN` to the player's name |

### Step 7 — Compile

```bash
python3 pipeline/compile.py
```

This overwrites `2026 ALL MAJORS STATS.xlsx` with the freshly built workbook.

### Step 8 — Verify

After compiling, spot-check a few numbers:
- Open the xlsx and confirm the new players/games appear
- Check a player's season totals against their game-by-game lines
- Confirm Pitches and Strike% are non-zero for new pitchers

---

## Quick Reference: Teams and Their Known Abbreviations

| Team | Notes |
|---|---|
| Astros | Lukas I (#11 early, #13 later) and Kolin I (#13 early, #11 later) swapped jerseys — both are correct. |
| Brewers | — |
| Giants | — |
| Guardians | — |
| Marlins | — |
| Padres | — |
| White Sox | — |
| Yankees | Two different players named "Henry S" — #7 and #47. Both are real. |

---

## Known Persistent Truncations (GameChanger limitation)

GameChanger truncates some long names consistently. These are the correct canonical forms:

| Player | Team | Jersey | Note |
|---|---|---|---|
| `Benjami... #26` | Astros | 26 | Full name unknown from images |
| `Sebasti... #33` | Brewers | 33 | Full name unknown |
| `Cassius... #24` | Marlins | 24 | Full name unknown |
| `Andreas... #27` | Marlins | 27 | Full name unknown |
| `Severin... #15` | Yankees | 15 | Full name unknown |
| `Camero... → Cameron L #34` | Giants | 34 | Fixed in game files |
| `Thomas... → Thomas B #10` | Giants | 10 | Fixed in game files |

If you see the `...` form in a new image, use the canonical form shown here (e.g. `"Benjami... #26"`) to ensure it aggregates with prior games.

---

## When to Update `name_registry.py`

Update the registry whenever:
1. A new player appears for the first time (add their `(team, jersey) → name` entry)
2. A player's name was previously stored in a truncated/wrong form and is now fully known (update the REGISTRY entry AND use `sed` to fix old game files)
3. A jersey swap is confirmed (document it in KNOWN_JERSEY_SWAPS in validate.py)

---

## Recompile Checklist

```
[ ] New image files added to images/
[ ] Data extracted from all 4 images per game
[ ] Names validated against name_registry.py (no aliases, no missing jerseys)
[ ] New game files written to games/ (one per team per date)
[ ] name_registry.py updated if new players appeared
[ ] python3 pipeline/validate.py → no errors
[ ] python3 pipeline/compile.py → ✅ saved (Excel backup)
[ ] Spot-check xlsx totals
[ ] Google Sheet updates automatically overnight (or run bash pipeline/recompile.sh manually)
```

---

## Google Sheets Automation

The live Google Sheet is pushed to from your Mac (not from Claude's VM, which
can't reach Google's servers directly). Two automation options:

### Option A — Fully automatic: daily at 6 AM (recommended)

Run this ONCE from your Mac terminal:

```bash
bash /path/to/Stats/pipeline/install_autorun.sh
```

This installs a macOS LaunchAgent that wakes up at 11:45 AM PT every day and runs
the full pipeline (validate → Excel backup → Google Sheets push) automatically.
Your Mac just needs to be on and awake. A log is written to `pipeline/recompile.log`.

To uninstall:
```bash
bash /path/to/Stats/pipeline/install_autorun.sh --uninstall
```

### Option B — Manual push any time

```bash
bash /path/to/Stats/pipeline/recompile.sh
```

Or just the Sheets push:
```bash
cd /path/to/Stats && python3 pipeline/compile_sheets.py
```

### Note for Claude sessions
Claude (running in its VM) handles steps 1–6 of the checklist above — extracting
data, writing game files, validating, and building the Excel backup. The Google
Sheets push must be triggered from the user's Mac (automatically via LaunchAgent
or manually via recompile.sh), since Claude's VM cannot reach Google's API servers.

---

## Architecture Notes for Claude

- `compile.py` is completely self-contained. It has no dependencies on the old `stats_data.py`, `pitching_extra.py`, `xbh_v2.py`, or `fresh_hitting_main.py` files. Those were used to migrate data to the `games/` format and are now obsolete.
- All hitting data (including XBH: 2B/3B/HR/SB/CS/E) lives in the `hitting` list in each game file.
- All pitching data (including pitches/strikes/BF) lives in the `pitching` list in each game file.
- Rate stats (AVG, OBP, SLG, OPS, ERA, WHIP, Strike%) are all computed in Python in `compile.py` — never stored in the game files.
- `bf=0` in a pitching row means the value was illegible in the source image. `compile.py` skips `bf=0` rows when summing batters faced, so the player's total BF will be understated but won't incorrectly count zero.
