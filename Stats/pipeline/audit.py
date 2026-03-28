"""
audit.py
========
Season-level data quality audit for 2026 Alameda Little League Majors.

Runs AFTER compile.py succeeds. Checks that aggregated stats are plausible
and flags anything that looks wrong, missing, or unprocessed.

Unlike validate.py (which checks game file structure), audit.py checks the
COMPILED season totals — catching things like impossible batting averages,
suspiciously missing pitch data, or new image files that were never processed.

Usage
-----
    cd mnt/Stats
    python3 pipeline/audit.py

Exit codes
----------
    0 = clean (or only warnings)
    1 = one or more ERRORs found
"""

import os, sys, re, importlib.util
from collections import defaultdict

THIS_DIR  = os.path.dirname(os.path.abspath(__file__))
STATS_DIR = os.path.dirname(THIS_DIR)
GAMES_DIR = os.path.join(STATS_DIR, "games")
IMG_DIR   = os.path.join(STATS_DIR, "images")

# =============================================================================
# Load all game data (same as compile.py)
# =============================================================================
all_hitting  = []
all_pitching = []

game_files = sorted(f for f in os.listdir(GAMES_DIR) if f.endswith('.py'))
for fname in game_files:
    path = os.path.join(GAMES_DIR, fname)
    spec = importlib.util.spec_from_file_location("gf", path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    team = mod.TEAM; date = mod.DATE
    for row in getattr(mod, 'hitting',  []): all_hitting.append({**row,  'team': team, 'date': date, '_file': fname})
    for row in getattr(mod, 'pitching', []): all_pitching.append({**row, 'team': team, 'date': date, '_file': fname})

def display_name(raw): return raw.split(' #')[0].strip()
def ip_to_dec(s):
    s = str(s)
    if '.' not in s: return float(s)
    w, f = s.split('.'); return int(w) + int(f) / 3.0
def pct(n, d): return n/d if d else 0

# Aggregate season hitting
h_totals = defaultdict(lambda: {'team':'','games':0,'ab':0,'r':0,'h':0,'rbi':0,
    'bb':0,'so':0,'sb':0,'cs':0,'e':0,'doubles':0,'triples':0,'hr':0})
for row in all_hitting:
    key = (display_name(row['name']), row['team'])
    p = h_totals[key]; p['team'] = row['team']; p['games'] += 1
    for s in ('ab','r','h','rbi','bb','so','sb','cs','e','doubles','triples','hr'):
        p[s] += row.get(s, 0)

# Aggregate season pitching
p_totals = defaultdict(lambda: {'team':'','games':0,'ip_dec':0.0,'h':0,'r':0,'er':0,
    'bb':0,'so':0,'pitches':0,'strikes':0,'bf':0,'hbp':0})
for row in all_pitching:
    key = (display_name(row['name']), row['team'])
    p = p_totals[key]; p['team'] = row['team']; p['games'] += 1
    p['ip_dec'] += ip_to_dec(row['ip'])
    for s in ('h','r','er','bb','so','hbp'): p[s] += row.get(s, 0)
    p['pitches'] += row.get('pitches', 0); p['strikes'] += row.get('strikes', 0)
    bf = row.get('bf', 0)
    if bf > 0: p['bf'] += bf

# Games per team
team_dates_h = defaultdict(set)
team_dates_p = defaultdict(set)
for row in all_hitting:  team_dates_h[row['team']].add(row['date'])
for row in all_pitching: team_dates_p[row['team']].add(row['date'])

TEAMS = ['Astros','Brewers','Giants','Guardians','Marlins','Padres','White Sox','Yankees']

# =============================================================================
# Audit checks
# =============================================================================
errors   = []
warnings = []

def err(msg):  errors.append(msg)
def warn(msg): warnings.append(msg)

# ── 1. Impossible season hitting stats ───────────────────────────────────────
for (name, team), p in h_totals.items():
    ab = p['ab']; h_ = p['h']; bb = p['bb']
    d  = p['doubles']; t = p['triples']; hr = p['hr']
    xbh = d + t + hr

    if xbh > h_:
        err(f"HITTING: {name} ({team}) XBH({xbh}) > H({h_}) — impossible season total")

    if ab > 0:
        avg = h_ / ab
        if avg > 1.0:
            err(f"HITTING: {name} ({team}) AVG={avg:.3f} > 1.000 — impossible")
        elif avg > 0.750:
            warn(f"HITTING: {name} ({team}) AVG={avg:.3f} — unusually high, worth verifying")

        obp = pct(h_+bb, ab+bb)
        if obp > 1.0:
            err(f"HITTING: {name} ({team}) OBP={obp:.3f} > 1.000 — impossible")

        slg = pct(h_+d+2*t+3*hr, ab)
        if slg > 4.0:
            err(f"HITTING: {name} ({team}) SLG={slg:.3f} > 4.000 — impossible")

    # More games than their team played
    team_g = len(team_dates_h[team])
    if p['games'] > team_g:
        err(f"HITTING: {name} ({team}) appears in {p['games']} games but team only has {team_g}")

# ── 2. Impossible season pitching stats ──────────────────────────────────────
for (name, team), p in p_totals.items():
    ip_d = p['ip_dec']

    if p['strikes'] > p['pitches'] and p['pitches'] > 0:
        err(f"PITCHING: {name} ({team}) strikes({p['strikes']}) > pitches({p['pitches']}) — impossible")

    if p['pitches'] > 0:
        spct = p['strikes'] / p['pitches']
        if spct > 0.95:
            warn(f"PITCHING: {name} ({team}) Strike%={spct:.1%} — suspiciously high, check pitch counts")
        if spct < 0.30 and ip_d >= 2.0:
            warn(f"PITCHING: {name} ({team}) Strike%={spct:.1%} — suspiciously low, check pitch counts")

    if ip_d >= 3.0:
        era = p['er'] * 9 / ip_d
        if era == 0.0 and p['h'] == 0 and p['bb'] == 0 and ip_d >= 6.0:
            warn(f"PITCHING: {name} ({team}) ERA=0.00, 0 H, 0 BB in {ip_d:.1f} IP — verify data")

    team_g = len(team_dates_p[team])
    if p['games'] > team_g:
        err(f"PITCHING: {name} ({team}) appears in {p['games']} games but team only has {team_g}")

# ── 3. Teams with zero pitch data ────────────────────────────────────────────
for team in TEAMS:
    team_pitches = sum(
        row.get('pitches', 0)
        for row in all_pitching
        if row['team'] == team
    )
    if team_pitches == 0 and team_dates_p[team]:
        err(f"PITCHING: {team} has {len(team_dates_p[team])} games but zero total pitches — pitch images may not have been extracted")
    elif team_pitches < 100 and len(team_dates_p[team]) >= 3:
        warn(f"PITCHING: {team} has only {team_pitches} total pitches across {len(team_dates_p[team])} games — seems low")

# ── 4. New images without corresponding game files ───────────────────────────
# Parse game file coverage: {(team_keyword, date_keyword)} from filenames
processed = set()
for fname in game_files:
    # e.g. 2026_03_07_Astros.py → ('astros', '03_07')
    m = re.match(r'(\d{4})_(\d{2}_\d{2})_(.+)\.py', fname)
    if m:
        date_key = m.group(2)          # '03_07'
        team_key = m.group(3).lower().replace('_', '')  # 'white_sox' -> 'whitesox'
        processed.add((team_key, date_key))

unprocessed_images = []
if os.path.isdir(IMG_DIR):
    for img in sorted(os.listdir(IMG_DIR)):
        if not img.lower().endswith('.png'): continue
        # Image filenames like: "Hitting - 2026 03 07 Brewers - 1.png"
        # Extract month and day from YYYY MM DD pattern
        date_m = re.search(r'\d{4}[ _\-](\d{2})[ _\-](\d{2})', img)
        if not date_m: continue
        date_key = f"{date_m.group(1)}_{date_m.group(2)}"
        # Try to find a team name in the filename
        img_lower = img.lower().replace(' ', '').replace('_', '').replace('-', '')
        matched_team = None
        for team in TEAMS:
            if team.lower().replace(' ', '') in img_lower:
                matched_team = team.lower().replace(' ', '')  # 'whitesox'
                break
        if matched_team and (matched_team, date_key) not in processed:
            unprocessed_images.append(img)

if unprocessed_images:
    warn(f"UNPROCESSED IMAGES: {len(unprocessed_images)} image(s) in images/ have no matching game file:")
    for img in unprocessed_images[:10]:  # show up to 10
        warn(f"  → {img}")
    if len(unprocessed_images) > 10:
        warn(f"  ... and {len(unprocessed_images)-10} more")

# ── 5. Games with missing or incomplete data ─────────────────────────────────
# Check each game file: any game where pitching has all-zero pitches
for fname in game_files:
    path = os.path.join(GAMES_DIR, fname)
    spec = importlib.util.spec_from_file_location("gf2", path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    pit_rows = getattr(mod, 'pitching', [])
    if pit_rows:
        total_pitches = sum(r.get('pitches', 0) for r in pit_rows)
        if total_pitches == 0:
            warn(f"GAME FILE: {fname} — all pitchers have 0 pitches (pitch image may not have been extracted)")

# =============================================================================
# Report
# =============================================================================
print("=" * 70)
print("DATA QUALITY AUDIT")
print("=" * 70)
print(f"Season hitting records:  {len(h_totals)} players")
print(f"Season pitching records: {len(p_totals)} pitchers")
print(f"Game files:              {len(game_files)}")
print(f"Images folder:           {len([f for f in os.listdir(IMG_DIR) if f.endswith('.png')]) if os.path.isdir(IMG_DIR) else 'N/A'} PNGs")
print()

if errors:
    print(f"❌  ERRORS ({len(errors)}) — stats may be inaccurate:")
    for e in errors:
        print(f"   {e}")
    print()
else:
    print("✅  No data errors found.")
    print()

if warnings:
    print(f"⚠️   WARNINGS ({len(warnings)}) — worth reviewing:")
    for w in warnings:
        print(f"   {w}")
    print()
else:
    print("✅  No warnings.")
    print()

if not errors and not warnings:
    print("All stats look clean ✅")
elif not errors:
    print("Stats look correct. Review warnings above when you get a chance.")
else:
    print("Errors found — consider fixing game files and recompiling.")

sys.exit(1 if errors else 0)


if __name__ == "__main__":
    pass  # already ran above
