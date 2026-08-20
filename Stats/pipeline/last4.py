"""
last4.py — per-appearance pitching log and the "Last 4 Appearances" view.
=========================================================================

Why this module exists
----------------------
compile_html.py has a SEASON OVERRIDE that replaces per-game aggregates with
workbook season totals from data/season_2026.json. That is fine for season
leaderboards but fatal here: this report is *about* individual appearances, and
the override destroys per-game detail. So we read Stats/games/*.py directly and
never touch the override's output.

Date handling
-------------
Game files carry DATE = "MM/DD" with no year. We take the date from the FILENAME
(YYYY_MM_DD_Team_Name.py) instead, so ordering is unambiguous.

Opponent / home-away / result
-----------------------------
OPPONENT and RESULT exist only on the 84 files recovered from the Drive backup;
the 82 original files (<= 04/19) lack them. Rather than leave half the season
blank we resolve every game against the schedule in season_2026.json, which
covers all 83 games. Where a file *does* carry OPPONENT/RESULT we cross-check it
against the schedule and report any disagreement instead of silently preferring
one source.

Helpers are injected by the caller (compile_html.py) rather than re-implemented,
so innings math stays in exactly one place.
"""

import os, re, json, importlib.util
from collections import defaultdict
from datetime import date

# compile_html.p_era uses er*9/ip. Its rate stats (p_so_per_6 etc.) use 6.
# We match the module we sit beside so that "Season ERA" and "Last-4 ERA" are
# computed identically and can be read side by side. Change here, not inline.
ERA_INNINGS = 9
RATE_INNINGS = 6

FILENAME_RE = re.compile(r'^(\d{4})_(\d{2})_(\d{2})_(.+)\.py$')

# GameChanger sometimes appends the pitcher's decision to the name field, e.g.
# "Conor F #24 (L)". That is a scoring artifact, not part of the name, and it
# silently splits a pitcher into two people. The three known cases were fixed at
# source on 2026-08-17. We do NOT normalize silently — if one reappears we want
# it surfaced, because a silent merge would hide a real data-entry problem.
DECISION_SUFFIX = re.compile(r'\s*\((?:W|L|S|SV|BS|H|HLD)\)\s*$', re.I)


def _schedule_index(season_path):
    """(date, team) -> schedule row. Returns {} when the workbook is absent."""
    if not os.path.exists(season_path):
        return {}
    season = json.load(open(season_path, encoding='utf-8'))
    idx = {}
    for row in season.get('games', []):
        d, away, home, ascore, hscore, winner = row[0], row[1], row[2], row[3], row[4], row[5]
        idx[(d, away)] = {'opp': home,  'home': False, 'us': ascore, 'them': hscore, 'winner': winner}
        idx[(d, home)] = {'opp': away,  'home': True,  'us': hscore, 'them': ascore, 'winner': winner}
    return idx


def load_appearances(games_dir, season_path, ip_to_dec):
    """Return (appearances, warnings).

    appearances: one dict per pitcher per game, chronologically sortable.
    warnings:    data problems to surface, never silently corrected.
    """
    sched = _schedule_index(season_path)
    appearances, warnings = [], []

    for fname in sorted(os.listdir(games_dir)):
        if not fname.endswith('.py'):
            continue
        m = FILENAME_RE.match(fname)
        if not m:
            warnings.append(f"{fname}: filename does not match YYYY_MM_DD_Team.py — skipped")
            continue
        y, mo, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
        gdate = date(y, mo, dd)
        iso = gdate.isoformat()

        spec = importlib.util.spec_from_file_location('last4_gf', os.path.join(games_dir, fname))
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            warnings.append(f"{fname}: failed to import ({e}) — skipped")
            continue

        team = getattr(mod, 'TEAM', None)
        if not team:
            warnings.append(f"{fname}: no TEAM — skipped")
            continue

        ctx = sched.get((iso, team))
        file_opp = getattr(mod, 'OPPONENT', None)
        file_res = getattr(mod, 'RESULT', None)

        if ctx is None:
            warnings.append(f"{fname}: no schedule row for ({iso}, {team}); opponent/result unavailable")
            opp, is_home, us, them, result = file_opp, None, None, None, file_res
        else:
            opp, is_home = ctx['opp'], ctx['home']
            us, them = ctx['us'], ctx['them']
            result = 'W' if ctx['winner'] == team else ('L' if ctx['winner'] else None)
            # cross-check the file's own fields where they exist
            if file_opp and file_opp != opp:
                warnings.append(f"{fname}: OPPONENT='{file_opp}' but schedule says '{opp}'")
            if file_res and result and file_res.upper()[:1] != result:
                warnings.append(f"{fname}: RESULT='{file_res}' but schedule says '{result}'")

        for row in getattr(mod, 'pitching', []):
            raw = row.get('name', '')
            if DECISION_SUFFIX.search(raw):
                warnings.append(
                    f"{fname}: pitcher name '{raw}' carries a W/L decision suffix. "
                    f"This splits one pitcher into two. Strip it at source.")
            try:
                ip_dec = ip_to_dec(row['ip'])
            except Exception:
                warnings.append(f"{fname}: unparseable ip '{row.get('ip')}' for {raw} — skipped")
                continue
            frac = str(row['ip']).split('.')[-1]
            if frac not in ('0', '1', '2'):
                warnings.append(f"{fname}: ip '{row['ip']}' for {raw} — thirds must end .0/.1/.2")

            appearances.append({
                'name': raw, 'team': team, 'date': iso, 'gdate': gdate,
                'opp': opp, 'home': is_home, 'result': result, 'us': us, 'them': them,
                'ip': str(row['ip']), 'ip_dec': ip_dec,
                'h': row.get('h', 0), 'r': row.get('r', 0), 'er': row.get('er', 0),
                'bb': row.get('bb', 0), 'so': row.get('so', 0), 'hbp': row.get('hbp', 0),
                'pitches': row.get('pitches', 0), 'strikes': row.get('strikes', 0),
                'bf': row.get('bf', 0),
            })

    return appearances, warnings


def _agg(rows, dec_to_ip):
    """Sum a set of appearances into one line."""
    t = {k: sum(a[k] for a in rows) for k in
         ('h', 'r', 'er', 'bb', 'so', 'hbp', 'pitches', 'strikes', 'bf')}
    # sum outs, not decimals, so thirds never drift
    outs = sum(round(a['ip_dec'] * 3) for a in rows)
    t['ip_dec'] = outs / 3
    t['ip'] = dec_to_ip(t['ip_dec'])
    ip = t['ip_dec']
    t['era'] = t['er'] * ERA_INNINGS / ip if ip > 0.01 else None
    t['whip'] = (t['h'] + t['bb']) / ip if ip > 0.01 else None
    t['k6'] = t['so'] * RATE_INNINGS / ip if ip > 0.01 else None
    t['bb6'] = t['bb'] * RATE_INNINGS / ip if ip > 0.01 else None
    t['kbb'] = (t['so'] / t['bb']) if t['bb'] else None
    t['spct'] = (t['strikes'] / t['pitches']) if t['pitches'] else None
    t['g'] = len(rows)
    return t


def build(appearances, dec_to_ip, n=4):
    """Group by pitcher, attach last-n window, season line, and rest days."""
    by = defaultdict(list)
    for a in appearances:
        by[(a['team'], a['name'])].append(a)

    out = []
    for (team, name), rows in by.items():
        rows.sort(key=lambda a: a['gdate'])
        for i, a in enumerate(rows):
            a['rest'] = (a['gdate'] - rows[i - 1]['gdate']).days if i else None
        last = rows[-n:]
        for i, a in enumerate(last):
            a['era_g'] = a['er'] * ERA_INNINGS / a['ip_dec'] if a['ip_dec'] > 0.01 else None
            a['whip_g'] = (a['h'] + a['bb']) / a['ip_dec'] if a['ip_dec'] > 0.01 else None
            a['spct_g'] = (a['strikes'] / a['pitches']) if a['pitches'] else None
        out.append({
            'name': name, 'team': team,
            'display': name.split(' #')[0].strip(),
            'appearances': last,
            'last_n': _agg(last, dec_to_ip),
            'season': _agg(rows, dec_to_ip),
            'total_apps': len(rows),
            'last_date': rows[-1]['date'],
        })
    out.sort(key=lambda p: (p['team'], p['last_date']), reverse=False)
    return out


def season_diff(appearances, season_path, dec_to_ip):
    """Diff per-game season totals against the workbook. Reports, never adjusts."""
    if not os.path.exists(season_path):
        return [], "season_2026.json absent — no diff performed"
    season = json.load(open(season_path, encoding='utf-8'))
    cols = season['pitching_cols']
    wb = {r[0]: dict(zip(cols, r)) for r in season['pitching']}

    by = defaultdict(list)
    for a in appearances:
        by[a['name'].split(' #')[0].strip()].append(a)

    rows = []
    for disp, apps in sorted(by.items()):
        mine = _agg(apps, dec_to_ip)
        w = wb.get(disp)
        if not w:
            rows.append({'player': disp, 'note': 'not in workbook', 'deltas': {}})
            continue
        deltas = {}
        for k_mine, k_wb in (('g', 'g'), ('h', 'h'), ('r', 'r'), ('er', 'er'),
                             ('bb', 'bb'), ('so', 'so'), ('hbp', 'hbp'),
                             ('pitches', 'pitches'), ('strikes', 'strikes'), ('bf', 'bf')):
            if k_wb in w and w[k_wb] is not None:
                d = mine[k_mine] - w[k_wb]
                if d:
                    deltas[k_wb] = (mine[k_mine], w[k_wb], d)
        if 'ip' in w:
            try:
                if abs(mine['ip_dec'] - float(str(w['ip']).replace('.1', '.333').replace('.2', '.667'))) > 0.02:
                    deltas['ip'] = (mine['ip'], w['ip'], None)
            except Exception:
                pass
        if deltas:
            rows.append({'player': disp, 'team': apps[0]['team'], 'deltas': deltas})
    unmatched = [d for d in wb if d not in by]
    return rows, (f"{len(unmatched)} workbook pitchers absent from per-game files: {unmatched}"
                  if unmatched else "every workbook pitcher present in per-game files")
