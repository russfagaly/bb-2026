"""Cross-check Stats/data/season_2026.json for internal consistency.

The workbook publishes player rows, team rows, standings and a game log that
are all derived from the same underlying box scores, so they must reconcile:

  1. player hitting rows summed by team == team hitting row
  2. player pitching rows summed by team == team pitching row
  3. game log re-tallied == standings W/L, runs scored, runs allowed
  4. game count == sum of team W+L / 2

Exit code is nonzero if anything fails.
"""
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data", "season_2026.json")

d = json.load(open(DATA))


def rows(prefix):
    cols = d[f"{prefix}_cols"]
    return [dict(zip(cols, r)) for r in d[prefix]]


hitting = rows("hitting")
pitching = rows("pitching")
team_hit = {r["team"]: r for r in rows("team_hitting")}
team_pit = {r["team"]: r for r in rows("team_pitching")}
standings = {r["team"]: r for r in rows("standings")}
games = rows("games")

errors = []
notes = []


def ip_to_outs(ip):
    w, f = str(ip).split(".")
    return int(w) * 3 + int(f)


def outs_to_ip(outs):
    return f"{outs // 3}.{outs % 3}"


# --- 1. player hitting sums vs team hitting -------------------------------
FIELDS_H = ["ab", "r", "h", "2b", "3b", "hr", "rbi", "bb", "so", "sb", "cs", "e"]
agg = defaultdict(lambda: defaultdict(int))
for r in hitting:
    for f in FIELDS_H:
        agg[r["team"]][f] += r[f]

for team, tot in sorted(team_hit.items()):
    for f in FIELDS_H:
        got, want = agg[team][f], tot[f]
        if got != want:
            errors.append(f"HIT  {team:<10} {f:>4}: players sum {got}, team row {want}")

# --- 2. player pitching sums vs team pitching -----------------------------
FIELDS_P = ["h", "r", "er", "bb", "so", "hbp", "bf", "pitches", "strikes"]
aggp = defaultdict(lambda: defaultdict(int))
outs = defaultdict(int)
for r in pitching:
    for f in FIELDS_P:
        aggp[r["team"]][f] += r[f]
    outs[r["team"]] += ip_to_outs(r["ip"])

for team, tot in sorted(team_pit.items()):
    for f in FIELDS_P:
        got, want = aggp[team][f], tot[f]
        if got != want:
            errors.append(f"PIT  {team:<10} {f:>7}: players sum {got}, team row {want}")
    got_ip, want_ip = outs_to_ip(outs[team]), tot["ip"]
    if got_ip != want_ip:
        errors.append(f"PIT  {team:<10}      ip: players sum {got_ip}, team row {want_ip}")

# --- 3. game log re-tallied vs standings ----------------------------------
rec = defaultdict(lambda: {"w": 0, "l": 0, "rs": 0, "ra": 0})
for g in games:
    a, h = g["away"], g["home"]
    asc, hsc = g["away_score"], g["home_score"]
    rec[a]["rs"] += asc; rec[a]["ra"] += hsc
    rec[h]["rs"] += hsc; rec[h]["ra"] += asc
    if asc > hsc:
        rec[a]["w"] += 1; rec[h]["l"] += 1
    elif hsc > asc:
        rec[h]["w"] += 1; rec[a]["l"] += 1

for team, s in sorted(standings.items()):
    r = rec[team]
    for f in ("w", "l", "rs", "ra"):
        if r[f] != s[f]:
            errors.append(f"LOG  {team:<10} {f:>3}: game log {r[f]}, standings {s[f]}")

# --- 4. game count --------------------------------------------------------
expected = sum(s["w"] + s["l"] for s in standings.values()) / 2
if len(games) != expected:
    errors.append(f"LOG  game count {len(games)}, standings imply {expected:g}")

# --- report ---------------------------------------------------------------
print(f"players: {len(hitting)} hitting, {len(pitching)} pitching")
print(f"games:   {len(games)} logged, {min(g['date'] for g in games)} .. {max(g['date'] for g in games)}")
for n in notes:
    print(f"  note: {n}")
if errors:
    print(f"\n{len(errors)} MISMATCHES:")
    for e in errors:
        print("  " + e)
    sys.exit(1)
print("\nAll cross-checks passed.")
