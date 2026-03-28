"""
validate.py
===========
Validation suite for 2026 Alameda Little League Majors game files.

Run this script whenever new game files are added:

    python3 pipeline/validate.py

It loads every .py file from games/, runs a set of integrity checks, and
prints a clear pass/fail report. Any ERROR must be fixed before recompiling.
WARNINGs are worth reviewing but won't block compilation.

Checks performed
----------------
1. Schema check       – every row has required fields and no negative values
2. Jersey registry    – every player's (team, jersey) is in the registry;
                        unknown jerseys are flagged for review
3. Name aliases       – bare names matching ALIASES are flagged (old format)
4. Jersey conflicts   – same jersey, different bare name within one team
                        (excludes the known Astros swap)
5. XBH ≤ H           – 2B+3B+HR can't exceed total hits in a single game
6. IP sanity          – IP must be X.0, X.1, or X.2 (no .3 or higher)
7. Duplicate rows     – same player appearing twice in hitting or pitching
8. Missing jerseys    – players whose name has no # (jersey always required)
"""

import os, sys, re, importlib.util
from collections import defaultdict

# Allow running from repo root or from within pipeline/
THIS_DIR  = os.path.dirname(os.path.abspath(__file__))
STATS_DIR = os.path.dirname(THIS_DIR)           # mnt/Stats/
GAMES_DIR = os.path.join(STATS_DIR, "games")

# Insert pipeline/ dir so name_registry can be imported directly
sys.path.insert(0, THIS_DIR)
sys.path.insert(0, STATS_DIR)

try:
    from pipeline.name_registry import REGISTRY, ALIASES
except ImportError:
    from name_registry import REGISTRY, ALIASES

# ---------------------------------------------------------------------------
# Known exceptions — do not flag these as errors
# ---------------------------------------------------------------------------
KNOWN_JERSEY_SWAPS = {
    # (team, jersey, bare_name): swap happened; both names valid for that jersey
    ("Astros", "11", "Lukas I"): True,
    ("Astros", "11", "Kolin I"): True,
    ("Astros", "13", "Lukas I"): True,
    ("Astros", "13", "Kolin I"): True,
    # Two different Henry S on Yankees
    ("Yankees", "7",  "Henry S"): True,
    ("Yankees", "47", "Henry S"): True,
}

# ---------------------------------------------------------------------------
# Required fields
# ---------------------------------------------------------------------------
HIT_REQUIRED  = {"name","ab","r","h","rbi","bb","so","doubles","triples","hr","sb","cs","e"}
PIT_REQUIRED  = {"name","ip","h","r","er","bb","so","pitches","strikes","bf","hbp"}
HIT_NONNEG    = {"ab","r","h","rbi","bb","so","doubles","triples","hr","sb","cs","e"}
PIT_NONNEG    = {"h","r","er","bb","so","pitches","strikes","bf","hbp"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def bare(raw):
    return raw.split(' #')[0].strip()

def jersey(raw):
    m = re.search(r'#(\d+)', raw)
    return m.group(1) if m else None

def load_game(path):
    spec = importlib.util.spec_from_file_location("gf", path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def ip_ok(ip_str):
    """Return True if ip_str is a valid X.0/X.1/X.2 notation."""
    try:
        whole, frac = str(ip_str).split('.')
        return int(frac) in (0, 1, 2)
    except Exception:
        return False

# ---------------------------------------------------------------------------
# Main validation
# ---------------------------------------------------------------------------
def validate_all(games_dir=GAMES_DIR):
    errors   = []
    warnings = []

    def err(msg): errors.append(msg)
    def warn(msg): warnings.append(msg)

    # Per-team jersey → {names seen}  (for cross-game conflict detection)
    team_jersey_names = defaultdict(lambda: defaultdict(set))  # team -> jersey -> {names}

    game_files = sorted(f for f in os.listdir(games_dir) if f.endswith('.py'))
    if not game_files:
        err(f"No game files found in {games_dir}")

    for fname in game_files:
        path = os.path.join(games_dir, fname)
        try:
            mod = load_game(path)
        except Exception as e:
            err(f"[{fname}] PARSE ERROR: {e}")
            continue

        tag = f"[{fname}]"

        # Metadata
        if not hasattr(mod, 'TEAM') or not hasattr(mod, 'DATE'):
            err(f"{tag} Missing TEAM or DATE")
            continue
        team = mod.TEAM
        date = mod.DATE

        # ── Check 1: Schema ────────────────────────────────────────────────
        seen_hit_names = set()
        seen_pit_names = set()

        for i, row in enumerate(getattr(mod, 'hitting', [])):
            loc = f"{tag} hitting[{i}] ({row.get('name','?')})"
            missing = HIT_REQUIRED - set(row.keys())
            if missing:
                err(f"{loc}: missing fields {missing}")
            for f2 in HIT_NONNEG:
                if row.get(f2, 0) < 0:
                    err(f"{loc}: negative value {f2}={row[f2]}")
            # Duplicate check
            n = row.get('name','')
            if n in seen_hit_names:
                err(f"{loc}: DUPLICATE hitting row for '{n}'")
            seen_hit_names.add(n)

        for i, row in enumerate(getattr(mod, 'pitching', [])):
            loc = f"{tag} pitching[{i}] ({row.get('name','?')})"
            missing = PIT_REQUIRED - set(row.keys())
            if missing:
                err(f"{loc}: missing fields {missing}")
            for f2 in PIT_NONNEG:
                if row.get(f2, 0) < 0:
                    err(f"{loc}: negative value {f2}={row[f2]}")
            n = row.get('name','')
            if n in seen_pit_names:
                err(f"{loc}: DUPLICATE pitching row for '{n}'")
            seen_pit_names.add(n)

        # ── Check 2 & 3 & 4 & 8: Name/jersey checks ────────────────────────
        for kind, rows in [("hitting", getattr(mod,'hitting',[])),
                           ("pitching", getattr(mod,'pitching',[]))]:
            for row in rows:
                raw  = row.get('name', '')
                b    = bare(raw)
                j    = jersey(raw)

                # Check 8: Missing jersey
                if j is None:
                    err(f"{tag} {kind}: '{raw}' has no jersey number")
                    continue

                # Check 3: Alias (old format name)
                if b in ALIASES:
                    canon = ALIASES[b]
                    err(f"{tag} {kind}: '{raw}' → should be '{canon} #{j}' (old name format)")

                # Check 2: Not in registry
                reg_name = REGISTRY.get((team, j))
                if reg_name is None:
                    warn(f"{tag} {kind}: ({team}, #{j}) '{b}' not in registry — new player?")
                elif reg_name != b:
                    # Check if this is a known swap
                    if not KNOWN_JERSEY_SWAPS.get((team, j, b)):
                        err(f"{tag} {kind}: ({team}, #{j}) expected '{reg_name}', got '{b}'")

                # Check 4: Cross-game jersey conflict tracking
                team_jersey_names[team][j].add(b)

        # ── Check 5: XBH ≤ H ──────────────────────────────────────────────
        for i, row in enumerate(getattr(mod, 'hitting', [])):
            xbh = row.get('doubles',0) + row.get('triples',0) + row.get('hr',0)
            h   = row.get('h', 0)
            if xbh > h:
                err(f"{tag} hitting[{i}] ({row.get('name','?')}): "
                    f"XBH({xbh}) > H({h})  "
                    f"(2B={row.get('doubles',0)}, 3B={row.get('triples',0)}, HR={row.get('hr',0)})")

        # ── Check 6: IP sanity ─────────────────────────────────────────────
        for i, row in enumerate(getattr(mod, 'pitching', [])):
            if not ip_ok(row.get('ip', '')):
                err(f"{tag} pitching[{i}] ({row.get('name','?')}): "
                    f"invalid IP '{row.get('ip')}' (must be X.0, X.1, or X.2)")

    # ── Check 4 (global): jersey conflicts across all games ────────────────
    for team, jmap in team_jersey_names.items():
        for j, names in jmap.items():
            if len(names) > 1:
                skip = all(KNOWN_JERSEY_SWAPS.get((team, j, n)) for n in names)
                if not skip:
                    warn(f"Jersey conflict: ({team}, #{j}) has multiple names: {names}")

    # ── Report ─────────────────────────────────────────────────────────────
    print("=" * 70)
    print("VALIDATION REPORT")
    print("=" * 70)
    print(f"Game files checked: {len(game_files)}")
    print()

    if errors:
        print(f"❌  ERRORS ({len(errors)}) — must fix before compiling:")
        for e in errors:
            print(f"   {e}")
        print()
    else:
        print("✅  No errors found.")
        print()

    if warnings:
        print(f"⚠️   WARNINGS ({len(warnings)}) — review recommended:")
        for w in warnings:
            print(f"   {w}")
        print()
    else:
        print("✅  No warnings.")
        print()

    if not errors:
        print("Ready to compile ✅")
    else:
        print("Fix errors above, then rerun validate.py before compiling.")

    return len(errors) == 0


if __name__ == "__main__":
    ok = validate_all()
    sys.exit(0 if ok else 1)
