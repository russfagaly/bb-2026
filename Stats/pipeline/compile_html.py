"""
compile_html.py
===============
Generates index.html for GitHub Pages — a fully interactive, mobile-friendly
stats page for 2026 Alameda Little League Majors.

Usage:
    python3 pipeline/compile_html.py

Output:
    ../index.html  (repo root, one level above Stats/)
"""

import os, sys, json, importlib.util
from collections import defaultdict
from datetime import datetime

THIS_DIR  = os.path.dirname(os.path.abspath(__file__))
STATS_DIR = os.path.dirname(THIS_DIR)
REPO_DIR  = os.path.dirname(STATS_DIR)
GAMES_DIR = os.path.join(STATS_DIR, "games")
OUT_PATH  = os.path.join(REPO_DIR, "index.html")

# =============================================================================
# 1. LOAD GAME FILES
# =============================================================================
all_hitting  = []
all_pitching = []

game_files = sorted(f for f in os.listdir(GAMES_DIR) if f.endswith('.py'))
if not game_files:
    sys.exit(f"No game files found in {GAMES_DIR}")

for fname in game_files:
    fpath = os.path.join(GAMES_DIR, fname)
    spec  = importlib.util.spec_from_file_location("gf", fpath)
    mod   = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        print(f"  Warning: skipping {fname}: {e}")
        continue
    team = getattr(mod, 'TEAM', None)
    date = getattr(mod, 'DATE', None)
    if not team or not date:
        continue
    for row in getattr(mod, 'hitting',  []):
        all_hitting.append({**row, 'team': team, 'date': date})
    for row in getattr(mod, 'pitching', []):
        all_pitching.append({**row, 'team': team, 'date': date})

print(f"Loaded {len(game_files)} game files: {len(all_hitting)} hitting rows, {len(all_pitching)} pitching rows")

# =============================================================================
# 2. HELPERS
# =============================================================================
def display_name(raw): return raw.split(' #')[0].strip()
def jersey(raw):
    parts = raw.split(' #')
    return parts[1].strip() if len(parts) > 1 else ''

def ip_to_dec(ip_str):
    w, f = str(ip_str).split('.')
    return int(w) + int(f) / 3

def dec_to_ip(dec):
    w = int(dec); thirds = round((dec - w) * 3)
    return f"{w}.{thirds}"

def pct(n, d): return n / d if d else 0

# =============================================================================
# 3. AGGREGATE PLAYER STATS
# =============================================================================
h_totals = defaultdict(lambda: {'team':'','games':0,'ab':0,'r':0,'h':0,'rbi':0,
    'bb':0,'so':0,'sb':0,'cs':0,'e':0,'doubles':0,'triples':0,'hr':0,'hbp':0})
for row in all_hitting:
    key = (display_name(row['name']), row['team'])
    p = h_totals[key]; p['team'] = row['team']; p['games'] += 1
    for s in ('ab','r','h','rbi','bb','so','sb','cs','e','doubles','triples','hr'):
        p[s] += row.get(s, 0)

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

TEAMS = ['Astros','Brewers','Giants','Guardians','Marlins','Padres','White Sox','Yankees']
team_hit = {t: defaultdict(int) for t in TEAMS}
team_hit_dates = {t: set() for t in TEAMS}
for row in all_hitting:
    t = row['team']
    if t not in team_hit: continue
    team_hit_dates[t].add(row['date'])
    for s in ('ab','r','h','rbi','bb','so','sb','cs','e','doubles','triples','hr'):
        team_hit[t][s] += row.get(s, 0)

team_pit = {t: {'ip_dec':0.0,'h':0,'r':0,'er':0,'bb':0,'so':0,
                'pitches':0,'strikes':0,'bf':0,'hbp':0} for t in TEAMS}
team_pit_dates = {t: set() for t in TEAMS}
for row in all_pitching:
    t = row['team']
    if t not in team_pit: continue
    team_pit_dates[t].add(row['date'])
    team_pit[t]['ip_dec'] += ip_to_dec(row['ip'])
    for s in ('h','r','er','bb','so','hbp'): team_pit[t][s] += row.get(s, 0)
    team_pit[t]['pitches'] += row.get('pitches', 0)
    team_pit[t]['strikes'] += row.get('strikes', 0)
    bf = row.get('bf', 0)
    if bf > 0: team_pit[t]['bf'] += bf

hitting_players  = sorted([(d,p) for (d,_t),p in h_totals.items()], key=lambda x:(x[1]['team'],x[0]))
pitching_players = sorted([(d,p) for (d,_t),p in p_totals.items()], key=lambda x:(x[1]['team'],x[0]))

qual_hitters  = [(n,p) for n,p in hitting_players  if p['ab'] >= 10]
all_hitters   = hitting_players
sb_hitters    = [(n,p) for n,p in hitting_players  if p['sb']+p['cs'] >= 1]
qual_pitchers = [(n,p) for n,p in pitching_players if p['ip_dec'] >= 6.0]
all_pitchers  = pitching_players
kbb_pitchers  = [(n,p) for n,p in pitching_players if p['bb'] > 0 and p['ip_dec'] >= 3.0]

# =============================================================================
# 4. STAT FUNCTIONS
# =============================================================================
def h_avg(p):      return pct(p['h'], p['ab'])
def h_obp(p):      return pct(p['h']+p['bb'], p['ab']+p['bb'])
def h_slg(p):
    return pct(p['h']+p['doubles']+2*p['triples']+3*p['hr'], p['ab'])
def h_ops(p):      return h_obp(p) + h_slg(p)
def h_tb(p):       return p['h']+p['doubles']+2*p['triples']+3*p['hr']
def h_xbh(p):      return p['doubles']+p['triples']+p['hr']
def h_sb_pct(p):   return pct(p['sb'], p['sb']+p['cs'])
def h_walk_pct(p): return pct(p['bb'], p['ab']+p['bb'])
def h_so_pct(p):   return pct(p['so'], p['ab']+p['bb'])

def p_era(p):         return p['er']*9/p['ip_dec']          if p['ip_dec']>0.01 else 99.0
def p_whip(p):        return (p['h']+p['bb'])/p['ip_dec']   if p['ip_dec']>0.01 else 99.0
def p_strike_pct(p):  return pct(p['strikes'], p['pitches'])
def p_hits_per_6(p):  return 6*p['h']/p['ip_dec']           if p['ip_dec']>0 else 0
def p_bb_per_6(p):    return 6*p['bb']/p['ip_dec']          if p['ip_dec']>0 else 0
def p_so_per_6(p):    return 6*p['so']/p['ip_dec']          if p['ip_dec']>0 else 0
def p_walk_pct(p):    return pct(p['bb'], p['bf'])
def p_so_pct(p):      return pct(p['so'], p['bf'])
def p_k_to_bb(p):     return pct(p['so'], p['bb'])
def dec_to_ip_val(p): return p['ip_dec']

# League averages
_lg_h   = sum(p['h']  for _,p in hitting_players)
_lg_bb  = sum(p['bb'] for _,p in hitting_players)
_lg_ab  = sum(p['ab'] for _,p in hitting_players)
_lg_tb  = sum(p['h']+p['doubles']+2*p['triples']+3*p['hr'] for _,p in hitting_players)
_lg_obp = (_lg_h+_lg_bb)/(_lg_ab+_lg_bb) if (_lg_ab+_lg_bb)>0 else 1
_lg_slg = _lg_tb/_lg_ab                   if _lg_ab>0          else 1
_lg_er  = sum(p['er']     for _,p in pitching_players)
_lg_ip  = sum(p['ip_dec'] for _,p in pitching_players)
_lg_era = _lg_er*9/_lg_ip                 if _lg_ip>0          else 0
_lg_bb_pit = sum(p['bb'] for _,p in pitching_players)
_lg_so_pit = sum(p['so'] for _,p in pitching_players)
_fip_const = _lg_era - (3*_lg_bb_pit - 2*_lg_so_pit)/_lg_ip if _lg_ip>0 else 0

def h_ops_plus(p):
    obp = pct(p['h']+p['bb'], p['ab']+p['bb'])
    slg = pct(p['h']+p['doubles']+2*p['triples']+3*p['hr'], p['ab'])
    return round(100*(obp/_lg_obp + slg/_lg_slg - 1)) if _lg_obp>0 and _lg_slg>0 else 100

def p_era_plus(p):
    if p['ip_dec']<=0.01: return 0
    era = p['er']*9/p['ip_dec']
    if era==0: return 999
    return round(100*_lg_era/era) if _lg_era>0 else 0

def p_fip_minus(p):
    if p['ip_dec']<=0.01: return 0.0
    return round((3*p['bb']-2*p['so'])/p['ip_dec']+_fip_const, 2)

def p_kbb_ratio(p):
    if p['bb']==0: return 99.0 if p['so']>0 else 0.0
    return round(p['so']/p['bb'], 2)

# =============================================================================
# 5. BUILD LEADERBOARD DATA
# =============================================================================
TOP_N = 10

def build_leaderboard(title, pool, sort_fn, fmt, higher_better, display_fn=None):
    sorted_pool = sorted(pool, key=lambda x: sort_fn(x[1]), reverse=higher_better)[:TOP_N]
    entries = []
    for rank, (name, p) in enumerate(sorted_pool, 1):
        raw = sort_fn(p)
        if display_fn:
            val = display_fn(p)
        elif fmt == '0.000':
            val = f"{raw:.3f}"
        elif fmt == '0.00':
            val = f"{raw:.2f}"
        elif fmt == '0.0%':
            val = f"{raw:.1%}"
        elif fmt is None:
            val = str(int(raw)) if isinstance(raw, float) else str(raw)
        else:
            val = str(raw)
        entries.append({'rank': rank, 'name': name, 'team': p['team'], 'value': val})
    return {'title': title, 'entries': entries}

HIT_CATS_DEF = [
    ("Batting Avg (AVG)",  qual_hitters, h_avg,                  '0.000', True),
    ("On-Base % (OBP)",    qual_hitters, h_obp,                  '0.000', True),
    ("Slugging % (SLG)",   qual_hitters, h_slg,                  '0.000', True),
    ("OPS",                qual_hitters, h_ops,                  '0.000', True),
    ("Hits (H)",           all_hitters,  lambda p: p['h'],        None,    True),
    ("RBI",                all_hitters,  lambda p: p['rbi'],      None,    True),
    ("Runs Scored (R)",    all_hitters,  lambda p: p['r'],        None,    True),
    ("Total Bases (TB)",   all_hitters,  h_tb,                    None,    True),
    ("Walks (BB)",         all_hitters,  lambda p: p['bb'],       None,    True),
    ("Doubles (2B)",       all_hitters,  lambda p: p['doubles'],  None,    True),
    ("Triples (3B)",       all_hitters,  lambda p: p['triples'],  None,    True),
    ("Home Runs (HR)",     all_hitters,  lambda p: p['hr'],       None,    True),
    ("Stolen Bases (SB)",  all_hitters,  lambda p: p['sb'],       None,    True),
    ("SB% (min 1 att)",    sb_hitters,   h_sb_pct,                '0.0%',  True),
    ("Walk % (min 10 AB)", qual_hitters, h_walk_pct,              '0.0%',  True),
    ("K% Fewest (min 10)", qual_hitters, h_so_pct,                '0.0%',  False),
    ("Extra Base Hits",    all_hitters,  h_xbh,                   None,    True),
    ("Errors (Most)",      all_hitters,  lambda p: p['e'],        None,    True),
]

PIT_CATS_DEF = [
    ("Innings Pitched",            all_pitchers,  dec_to_ip_val,    None,   True),
    ("ERA (min 6 IP)",             qual_pitchers, p_era,            '0.00', False),
    ("Hits Allowed (min 6 IP)",    qual_pitchers, lambda p: p['h'], None,   False),
    ("Runs Allowed (Most)",        all_pitchers,  lambda p: p['r'], None,   True),
    ("Earned Runs (Most)",         all_pitchers,  lambda p: p['er'],None,   True),
    ("Walks",                      all_pitchers,  lambda p: p['bb'],None,   True),
    ("Strikeouts (SO)",            all_pitchers,  lambda p: p['so'],None,   True),
    ("Pitches Thrown",             all_pitchers,  lambda p: p['pitches'], None, True),
    ("Strike % (min 6 IP)",        qual_pitchers, p_strike_pct,     '0.0%', True),
    ("HBP Most",                   all_pitchers,  lambda p: p['hbp'],None,  True),
    ("WHIP (min 6 IP)",            qual_pitchers, p_whip,           '0.00', False),
    ("H per 6 IP (min 6 IP)",      qual_pitchers, p_hits_per_6,     '0.00', False),
    ("BB per 6 IP (min 6 IP)",     qual_pitchers, p_bb_per_6,       '0.00', False),
    ("K per 6 IP (min 6 IP)",      qual_pitchers, p_so_per_6,       '0.00', True),
    ("Walk % (min 6 IP)",          qual_pitchers, p_walk_pct,       '0.0%', False),
    ("K% (min 6 IP)",              qual_pitchers, p_so_pct,         '0.0%', True),
    ("Batters Faced (BF)",         all_pitchers,  lambda p: p['bf'],None,   True),
    ("K/BB Ratio (min 6 IP)",      kbb_pitchers,  p_k_to_bb,        '0.00', True),
]

def build_ip_leaderboard(title, pool, higher_better):
    sorted_pool = sorted(pool, key=lambda x: x[1]['ip_dec'], reverse=higher_better)[:TOP_N]
    entries = []
    for rank, (name, p) in enumerate(sorted_pool, 1):
        entries.append({'rank': rank, 'name': name, 'team': p['team'], 'value': dec_to_ip(p['ip_dec'])})
    return {'title': title, 'entries': entries}

hit_leaderboards = [build_leaderboard(*c) for c in HIT_CATS_DEF]
pit_leaderboards = []
for c in PIT_CATS_DEF:
    if c[0] == "Innings Pitched":
        pit_leaderboards.append(build_ip_leaderboard(c[0], c[1], c[4]))
    else:
        pit_leaderboards.append(build_leaderboard(*c))

# =============================================================================
# 6. BUILD TEAM DATA
# =============================================================================
teams_data = {}
for team in TEAMS:
    th = team_hit[team]
    tp = team_pit[team]
    g_hit = len(team_hit_dates[team])
    g_pit = len(team_pit_dates[team])
    g     = max(g_hit, g_pit)
    ab = th['ab']; h_ = th['h']; bb = th['bb']
    d  = th['doubles']; t_ = th['triples']; hr_ = th['hr']
    ip_d = tp['ip_dec']
    teams_data[team] = {
        'games': g,
        'hitting': {
            'g': g_hit, 'ab': ab, 'r': int(th['r']), 'h': int(h_),
            'doubles': int(d), 'triples': int(t_), 'hr': int(hr_),
            'rbi': int(th['rbi']), 'bb': int(bb), 'so': int(th['so']),
            'sb': int(th['sb']), 'cs': int(th['cs']), 'e': int(th['e']),
            'avg': f"{h_/ab:.3f}" if ab>0 else ".000",
            'obp': f"{(h_+bb)/(ab+bb):.3f}" if (ab+bb)>0 else ".000",
            'slg': f"{(h_+d+2*t_+3*hr_)/ab:.3f}" if ab>0 else ".000",
            'ops': f"{((h_+bb)/(ab+bb) + (h_+d+2*t_+3*hr_)/ab):.3f}" if ab>0 and (ab+bb)>0 else ".000",
        },
        'pitching': {
            'g': g_pit, 'ip': dec_to_ip(ip_d),
            'h': int(tp['h']), 'r': int(tp['r']), 'er': int(tp['er']),
            'bb': int(tp['bb']), 'so': int(tp['so']), 'hbp': int(tp['hbp']),
            'bf': int(tp['bf']), 'pitches': int(tp['pitches']), 'strikes': int(tp['strikes']),
            'era':  f"{tp['er']*9/ip_d:.2f}"             if ip_d>0 else "0.00",
            'whip': f"{(tp['h']+tp['bb'])/ip_d:.2f}"     if ip_d>0 else "0.00",
            'kip':  f"{tp['so']/ip_d:.2f}"               if ip_d>0 else "0.00",
            'spct': f"{tp['strikes']/tp['pitches']:.1%}" if tp['pitches']>0 else "0.0%",
        }
    }

# =============================================================================
# 7. BUILD PLAYER DATA (combined hitting + pitching)
# =============================================================================
# Build jersey registry: name+team -> jersey number
jersey_map = {}
for row in all_hitting + all_pitching:
    name = display_name(row['name'])
    team = row['team']
    j    = jersey(row['name'])
    if j:
        jersey_map[(name, team)] = j

all_player_keys = set(k for k,_ in h_totals.items()) | set(k for k,_ in p_totals.items())

players_data = []
for (name, team) in sorted(all_player_keys, key=lambda x: (x[1], x[0])):
    hp = h_totals.get((name, team))
    pp = p_totals.get((name, team))
    jnum = jersey_map.get((name, team), '')

    hitting_stats = None
    if hp and hp['games'] > 0:
        ab = hp['ab']; h_ = hp['h']; bb = hp['bb']
        d  = hp['doubles']; t_ = hp['triples']; hr = hp['hr']
        ops_plus = h_ops_plus(hp)
        hitting_stats = {
            'gp': hp['games'], 'ab': ab, 'r': int(hp['r']), 'h': int(h_),
            'doubles': int(d), 'triples': int(t_), 'hr': int(hr),
            'rbi': int(hp['rbi']), 'bb': int(bb), 'so': int(hp['so']),
            'sb': int(hp['sb']), 'cs': int(hp['cs']), 'e': int(hp['e']),
            'avg': f"{h_/ab:.3f}" if ab>0 else ".000",
            'obp': f"{(h_+bb)/(ab+bb):.3f}" if (ab+bb)>0 else ".000",
            'slg': f"{(h_+d+2*t_+3*hr)/ab:.3f}" if ab>0 else ".000",
            'ops': f"{h_obp(hp)+h_slg(hp):.3f}",
            'ops_plus': ops_plus,
        }

    pitching_stats = None
    if pp and pp['games'] > 0:
        ip_d = pp['ip_dec']
        era_plus  = p_era_plus(pp)
        fip_minus = p_fip_minus(pp)
        kbb       = p_kbb_ratio(pp)
        pitching_stats = {
            'g': pp['games'], 'ip': dec_to_ip(ip_d), 'ip_dec': round(ip_d, 2),
            'h': int(pp['h']), 'r': int(pp['r']), 'er': int(pp['er']),
            'bb': int(pp['bb']), 'so': int(pp['so']), 'hbp': int(pp['hbp']),
            'pitches': int(pp['pitches']), 'strikes': int(pp['strikes']),
            'bf': int(pp['bf']),
            'era':      f"{pp['er']*9/ip_d:.2f}"            if ip_d>0 else "0.00",
            'whip':     f"{(pp['h']+pp['bb'])/ip_d:.2f}"    if ip_d>0 else "0.00",
            'kip':      f"{pp['so']/ip_d:.2f}"              if ip_d>0 else "0.00",
            'spct':     f"{pp['strikes']/pp['pitches']:.1%}" if pp['pitches']>0 else "0.0%",
            'era_plus': era_plus,
            'fip_minus': fip_minus,
            'kbb':      kbb,
        }

    players_data.append({
        'name': name, 'team': team, 'jersey': jnum,
        'hitting': hitting_stats,
        'pitching': pitching_stats,
    })

# =============================================================================
# 8. ASSEMBLE JSON PAYLOAD
# =============================================================================
stats_json = json.dumps({
    'generated':        datetime.now().strftime('%B %d, %Y'),
    'teams':            TEAMS,
    'leaderboards':     {'hitting': hit_leaderboards, 'pitching': pit_leaderboards},
    'teams_data':       teams_data,
    'players':          players_data,
}, separators=(',', ':'))

# =============================================================================
# 9. HTML TEMPLATE
# =============================================================================
TEAM_COLORS = {
    'Astros':    {'bg': '#002D62', 'accent': '#EB6E1F'},
    'Brewers':   {'bg': '#12284B', 'accent': '#FFC52F'},
    'Giants':    {'bg': '#FD5A1E', 'accent': '#27251F'},
    'Guardians': {'bg': '#00385D', 'accent': '#E31937'},
    'Marlins':   {'bg': '#00A3E0', 'accent': '#FF6600'},
    'Padres':    {'bg': '#2F241D', 'accent': '#FFC425'},
    'White Sox': {'bg': '#27251F', 'accent': '#C4CED4'},
    'Yankees':   {'bg': '#003087', 'accent': '#E4002C'},
}
TEAM_COLORS_JSON = json.dumps(TEAM_COLORS, separators=(',',':'))

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>2026 Alameda Little League Majors Stats</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background:#f1f5f9; }}
  .tab-btn {{ transition: all .15s; }}
  .tab-btn.active {{ background:#1e3a5f; color:#fff; }}
  .tab-btn:not(.active) {{ background:#e2e8f0; color:#475569; }}
  .tab-section {{ display:none; }}
  .tab-section.active {{ display:block; }}
  .sortable th {{ cursor:pointer; user-select:none; white-space:nowrap; }}
  .sortable th:hover {{ background:#1e4d8c !important; }}
  .sortable th .sort-icon {{ margin-left:4px; opacity:.5; font-size:10px; }}
  .sortable th.asc .sort-icon::after {{ content:'▲'; opacity:1; }}
  .sortable th.desc .sort-icon::after {{ content:'▼'; opacity:1; }}
  .sortable th:not(.asc):not(.desc) .sort-icon::after {{ content:'⇅'; }}
  .lb-card {{ background:#fff; border-radius:10px; box-shadow:0 1px 4px rgba(0,0,0,.1); overflow:hidden; }}
  .lb-card-header {{ padding:8px 12px; font-weight:700; font-size:12px; letter-spacing:.3px; }}
  .lb-row {{ display:grid; grid-template-columns:24px 1fr auto auto; gap:4px; align-items:center; padding:5px 10px; font-size:12px; }}
  .lb-row:nth-child(even) {{ background:#f8fafc; }}
  .lb-rank {{ color:#94a3b8; font-size:11px; font-weight:600; }}
  .lb-val {{ font-weight:700; font-size:13px; min-width:40px; text-align:right; }}
  .lb-team-badge {{ font-size:10px; color:#64748b; white-space:nowrap; }}
  .team-card {{ border-radius:12px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,.12); cursor:pointer; transition:transform .15s; }}
  .team-card:hover {{ transform:translateY(-2px); }}
  .team-card-header {{ padding:16px; color:#fff; }}
  .team-card-body {{ background:#fff; padding:12px; display:none; }}
  .team-card-body.open {{ display:block; }}
  .stat-pill {{ background:#f1f5f9; border-radius:6px; padding:4px 8px; text-align:center; }}
  .stat-pill .val {{ font-size:18px; font-weight:700; }}
  .stat-pill .lbl {{ font-size:10px; color:#64748b; }}
  .player-row {{ cursor:pointer; transition:background .1s; }}
  .player-row:hover {{ background:#dbeafe !important; }}
  .modal-overlay {{ position:fixed; inset:0; background:rgba(0,0,0,.5); z-index:100; display:none; align-items:center; justify-content:center; padding:16px; }}
  .modal-overlay.open {{ display:flex; }}
  .modal-box {{ background:#fff; border-radius:16px; width:100%; max-width:680px; max-height:90vh; overflow-y:auto; box-shadow:0 20px 60px rgba(0,0,0,.3); }}
  .modal-header {{ padding:20px; color:#fff; border-radius:16px 16px 0 0; }}
  .section-title {{ font-size:18px; font-weight:700; color:#1e3a5f; margin-bottom:12px; }}
  .overflow-x-auto::-webkit-scrollbar {{ height:4px; }}
  .overflow-x-auto::-webkit-scrollbar-track {{ background:#f1f5f9; }}
  .overflow-x-auto::-webkit-scrollbar-thumb {{ background:#cbd5e1; border-radius:2px; }}
  .top-nav {{ display:flex; gap:4px; flex-wrap:nowrap; overflow-x:auto; scrollbar-width:none; }}
  .top-nav::-webkit-scrollbar {{ display:none; }}
  .top-nav .tab-btn {{ white-space:nowrap; flex-shrink:0; }}
  @media (max-width:640px) {{
    .lb-grid {{ grid-template-columns:1fr 1fr !important; }}
    .top-nav .tab-btn {{ padding:6px 12px; font-size:12px; }}
  }}
</style>
</head>
<body class="min-h-screen">

<!-- HEADER -->
<header style="background:linear-gradient(135deg,#1a3a5c,#1e5799)" class="text-white shadow-lg">
  <div class="max-w-7xl mx-auto px-4 py-4">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-xl font-bold tracking-tight">⚾ 2026 Alameda Little League</h1>
        <p class="text-blue-200 text-sm font-semibold">Majors Division Statistics</p>
      </div>
      <div class="text-right">
        <div class="text-blue-200 text-xs">Updated</div>
        <div class="text-white text-sm font-semibold" id="updated-date"></div>
      </div>
    </div>
    <!-- Nav — always visible, scrollable on mobile -->
    <nav class="top-nav mt-3">
      <button class="tab-btn active px-4 py-2 rounded-lg text-sm font-semibold" onclick="showTab('leaders',this)">🏆 Leaders</button>
      <button class="tab-btn px-4 py-2 rounded-lg text-sm font-semibold" onclick="showTab('teams',this)">🏟️ Teams</button>
      <button class="tab-btn px-4 py-2 rounded-lg text-sm font-semibold" onclick="showTab('hitters',this)">🥎 Hitters</button>
      <button class="tab-btn px-4 py-2 rounded-lg text-sm font-semibold" onclick="showTab('pitchers',this)">⚾ Pitchers</button>
      <button class="tab-btn px-4 py-2 rounded-lg text-sm font-semibold" onclick="showTab('players',this)">👤 Players</button>
    </nav>
  </div>
</header>

<!-- MAIN CONTENT -->
<main class="max-w-7xl mx-auto px-3 py-4 main-content">

  <!-- ── LEADERS TAB ─────────────────────────────────────────── -->
  <section id="tab-leaders" class="tab-section active">
    <div class="mb-6">
      <h2 class="section-title">🏆 Hitting Leaders</h2>
      <div class="lb-grid grid gap-3" style="grid-template-columns:repeat(3,1fr)" id="hit-lb-grid"></div>
    </div>
    <div>
      <h2 class="section-title">⚾ Pitching Leaders</h2>
      <div class="lb-grid grid gap-3" style="grid-template-columns:repeat(3,1fr)" id="pit-lb-grid"></div>
    </div>
  </section>

  <!-- ── TEAMS TAB ───────────────────────────────────────────── -->
  <section id="tab-teams" class="tab-section">
    <h2 class="section-title">🏟️ Team Stats</h2>
    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" id="teams-grid"></div>
  </section>

  <!-- ── HITTERS TAB ─────────────────────────────────────────── -->
  <section id="tab-hitters" class="tab-section">
    <h2 class="section-title">🥎 Player Hitting</h2>
    <div class="flex flex-wrap gap-2 mb-3">
      <input id="hit-search" type="text" placeholder="Search player..." class="border rounded-lg px-3 py-2 text-sm flex-1 min-w-0" oninput="filterHitters()"/>
      <select id="hit-team-filter" class="border rounded-lg px-3 py-2 text-sm" onchange="filterHitters()">
        <option value="">All Teams</option>
      </select>
    </div>
    <div class="overflow-x-auto rounded-xl shadow">
      <table class="sortable w-full text-xs border-collapse" id="hit-table">
        <thead>
          <tr style="background:#1e3a5f;color:#fff">
            <th class="px-3 py-2 text-left sticky left-0 z-10" style="background:#1e3a5f" data-col="name" data-type="str">Player<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="team" data-type="str">Team<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="gp" data-type="num">GP<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="ab" data-type="num">AB<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="r" data-type="num">R<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="h" data-type="num">H<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="doubles" data-type="num">2B<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="triples" data-type="num">3B<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="hr" data-type="num">HR<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="rbi" data-type="num">RBI<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="bb" data-type="num">BB<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="so" data-type="num">SO<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="sb" data-type="num">SB<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="e" data-type="num">E<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="avg" data-type="str">AVG<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="obp" data-type="str">OBP<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="slg" data-type="str">SLG<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="ops" data-type="str">OPS<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="ops_plus" data-type="num">OPS+<span class="sort-icon"></span></th>
          </tr>
        </thead>
        <tbody id="hit-table-body"></tbody>
      </table>
    </div>
  </section>

  <!-- ── PITCHERS TAB ────────────────────────────────────────── -->
  <section id="tab-pitchers" class="tab-section">
    <h2 class="section-title">⚾ Player Pitching</h2>
    <div class="flex flex-wrap gap-2 mb-3">
      <input id="pit-search" type="text" placeholder="Search player..." class="border rounded-lg px-3 py-2 text-sm flex-1 min-w-0" oninput="filterPitchers()"/>
      <select id="pit-team-filter" class="border rounded-lg px-3 py-2 text-sm" onchange="filterPitchers()">
        <option value="">All Teams</option>
      </select>
    </div>
    <div class="overflow-x-auto rounded-xl shadow">
      <table class="sortable w-full text-xs border-collapse" id="pit-table">
        <thead>
          <tr style="background:#1a4731;color:#fff">
            <th class="px-3 py-2 text-left sticky left-0 z-10" style="background:#1a4731" data-col="name" data-type="str">Player<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="team" data-type="str">Team<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="g" data-type="num">G<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="ip_dec" data-type="num">IP<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="h" data-type="num">H<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="r" data-type="num">R<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="er" data-type="num">ER<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="bb" data-type="num">BB<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="so" data-type="num">SO<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="hbp" data-type="num">HBP<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="pitches" data-type="num">Pitches<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="spct" data-type="str">Strike%<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="bf" data-type="num">BF<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="era" data-type="str">ERA<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="whip" data-type="str">WHIP<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="kip" data-type="str">K/IP<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="kbb" data-type="num">K/BB<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="fip_minus" data-type="num">FIP-<span class="sort-icon"></span></th>
            <th class="px-2 py-2" data-col="era_plus" data-type="num">ERA+<span class="sort-icon"></span></th>
          </tr>
        </thead>
        <tbody id="pit-table-body"></tbody>
      </table>
    </div>
  </section>

  <!-- ── PLAYERS TAB ─────────────────────────────────────────── -->
  <section id="tab-players" class="tab-section">
    <h2 class="section-title">👤 Player Cards</h2>
    <div class="flex flex-wrap gap-2 mb-4">
      <input id="player-search" type="text" placeholder="Search player..." class="border rounded-lg px-3 py-2 text-sm flex-1 min-w-0" oninput="filterPlayerCards()"/>
      <select id="player-team-filter" class="border rounded-lg px-3 py-2 text-sm" onchange="filterPlayerCards()">
        <option value="">All Teams</option>
      </select>
    </div>
    <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3" id="player-cards-grid"></div>
  </section>

</main>

<!-- PLAYER MODAL -->
<div class="modal-overlay" id="player-modal" onclick="closeModal(event)">
  <div class="modal-box" id="modal-box"></div>
</div>

<!-- TEAM MODAL -->
<div class="modal-overlay" id="team-modal" onclick="closeTeamModal(event)">
  <div class="modal-box" id="team-modal-box"></div>
</div>

<!-- DATA -->
<script>
const STATS = {stats_json};
const TEAM_COLORS = {TEAM_COLORS_JSON};
</script>

<!-- APP -->
<script>
// ── TAB SWITCHING ─────────────────────────────────────────────────────────
function showTab(name, btn) {{
  document.querySelectorAll('.tab-section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  if (btn) {{
    // Also deactivate the matching button in the other nav bar
    document.querySelectorAll('.tab-btn').forEach(b => {{
      if (b.textContent.trim() === btn.textContent.trim()) b.classList.add('active');
    }});
  }}
}}

// ── INIT ──────────────────────────────────────────────────────────────────
document.getElementById('updated-date').textContent = STATS.generated;

// Populate team filters
['hit-team-filter','pit-team-filter','player-team-filter'].forEach(id => {{
  const sel = document.getElementById(id);
  STATS.teams.forEach(t => {{
    const opt = document.createElement('option');
    opt.value = t; opt.textContent = t;
    sel.appendChild(opt);
  }});
}});

// ── LEADERBOARD RENDERING ─────────────────────────────────────────────────
function renderLeaderboards() {{
  const teamColorMap = {{}};
  STATS.teams.forEach(t => {{
    const c = TEAM_COLORS[t] || {{bg:'#374151',accent:'#9ca3af'}};
    teamColorMap[t] = c;
  }});

  function renderGrid(cats, containerId, headerBg) {{
    const grid = document.getElementById(containerId);
    cats.forEach(cat => {{
      const card = document.createElement('div');
      card.className = 'lb-card';
      let rows = cat.entries.map((e,i) => `
        <div class="lb-row" style="${{i%2===0?'background:#f8fafc':''}}">
          <span class="lb-rank">${{e.rank}}</span>
          <span style="font-weight:500;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${{e.name}}</span>
          <span class="lb-team-badge">${{e.team}}</span>
          <span class="lb-val" style="color:${{headerBg}}">${{e.value}}</span>
        </div>`).join('');
      card.innerHTML = `
        <div class="lb-card-header" style="background:${{headerBg}};color:#fff">${{cat.title}}</div>
        ${{rows}}`;
      grid.appendChild(card);
    }});
  }}

  renderGrid(STATS.leaderboards.hitting,  'hit-lb-grid', '#1e3a5f');
  renderGrid(STATS.leaderboards.pitching, 'pit-lb-grid', '#1a4731');
}}
renderLeaderboards();

// ── TEAM CARDS ────────────────────────────────────────────────────────────
function renderTeams() {{
  const grid = document.getElementById('teams-grid');
  STATS.teams.forEach(team => {{
    const td = STATS.teams_data[team];
    const c  = TEAM_COLORS[team] || {{bg:'#374151',accent:'#9ca3af'}};
    const card = document.createElement('div');
    card.className = 'team-card';
    card.style.background = '#fff';
    card.innerHTML = `
      <div class="team-card-header" style="background:${{c.bg}}">
        <div style="font-size:20px;font-weight:800;letter-spacing:-0.5px">${{team}}</div>
        <div style="font-size:12px;opacity:0.8;margin-top:2px">${{td.games}} games played</div>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:10px">
          <div style="text-align:center">
            <div style="font-size:20px;font-weight:800;color:${{c.accent}}">${{td.hitting.avg}}</div>
            <div style="font-size:10px;opacity:0.7">Team AVG</div>
          </div>
          <div style="text-align:center">
            <div style="font-size:20px;font-weight:800;color:${{c.accent}}">${{td.hitting.r}}</div>
            <div style="font-size:10px;opacity:0.7">Runs</div>
          </div>
          <div style="text-align:center">
            <div style="font-size:20px;font-weight:800;color:${{c.accent}}">${{td.pitching.era}}</div>
            <div style="font-size:10px;opacity:0.7">Team ERA</div>
          </div>
        </div>
      </div>
      <div style="padding:8px 12px;font-size:11px;color:#64748b;border-bottom:1px solid #f1f5f9;text-align:center">
        Tap for full stats
      </div>`;
    card.addEventListener('click', () => openTeamModal(team));
    grid.appendChild(card);
  }});
}}
renderTeams();

// ── TEAM MODAL ────────────────────────────────────────────────────────────
function openTeamModal(team) {{
  const td = STATS.teams_data[team];
  const c  = TEAM_COLORS[team] || {{bg:'#374151',accent:'#9ca3af'}};
  const th = td.hitting; const tp = td.pitching;

  const modalBox = document.getElementById('team-modal-box');
  modalBox.innerHTML = `
    <div class="modal-header" style="background:${{c.bg}}">
      <button onclick="closeTeamModal()" style="float:right;font-size:20px;opacity:.7;background:none;border:none;color:#fff;cursor:pointer">✕</button>
      <div style="font-size:24px;font-weight:800">${{team}}</div>
      <div style="opacity:.75;font-size:13px">${{td.games}} games played</div>
    </div>
    <div style="padding:16px">
      <div style="font-weight:700;font-size:14px;color:${{c.bg}};margin-bottom:10px">🥎 Team Hitting</div>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:16px">
        ${{[['AVG',th.avg],['OBP',th.obp],['SLG',th.slg],['OPS',th.ops],
           ['R',th.r],['H',th.h],['HR',th.hr],['RBI',th.rbi],
           ['BB',th.bb],['SO',th.so],['SB',th.sb],['E',th.e]
          ].map(([l,v])=>`<div class="stat-pill"><div class="val">${{v}}</div><div class="lbl">${{l}}</div></div>`).join('')}}
      </div>
      <div style="font-weight:700;font-size:14px;color:#1a4731;margin-bottom:10px">⚾ Team Pitching</div>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px">
        ${{[['ERA',tp.era],['WHIP',tp.whip],['IP',tp.ip],['SO',tp.so],
           ['BB',tp.bb],['H',tp.h],['ER',tp.er],['HBP',tp.hbp],
           ['Pitches',tp.pitches],['Strike%',tp.spct],['BF',tp.bf],['K/IP',tp.kip]
          ].map(([l,v])=>`<div class="stat-pill"><div class="val" style="font-size:14px">${{v}}</div><div class="lbl">${{l}}</div></div>`).join('')}}
      </div>
      <div style="margin-top:16px;padding-top:12px;border-top:1px solid #f1f5f9">
        <div style="font-weight:700;font-size:14px;color:#374151;margin-bottom:10px">👤 Roster</div>
        <div style="display:flex;flex-wrap:wrap;gap:6px" id="team-roster-${{team}}"></div>
      </div>
    </div>`;

  // Populate roster
  const rosterDiv = document.getElementById('team-roster-' + team);
  STATS.players.filter(p => p.team === team).sort((a,b)=>a.name.localeCompare(b.name)).forEach(p => {{
    const badge = document.createElement('span');
    badge.style.cssText = `background:${{c.bg}};color:#fff;padding:4px 10px;border-radius:20px;font-size:12px;cursor:pointer`;
    badge.textContent = p.name + (p.jersey ? ' #' + p.jersey : '');
    badge.addEventListener('click', () => {{ closeTeamModal(); openPlayerModal(p.name, p.team); }});
    rosterDiv.appendChild(badge);
  }});

  document.getElementById('team-modal').classList.add('open');
}}

function closeTeamModal(event) {{
  if (!event || event.target === document.getElementById('team-modal')) {{
    document.getElementById('team-modal').classList.remove('open');
  }}
}}

// ── HITTING TABLE ─────────────────────────────────────────────────────────
let hitData = [], hitSortCol = null, hitSortDir = 1;

function buildHitterRows() {{
  hitData = STATS.players.filter(p => p.hitting).map(p => ({{
    ...p.hitting, name: p.name, team: p.team, jersey: p.jersey
  }}));
}}

function renderHitTable(data) {{
  const tbody = document.getElementById('hit-table-body');
  tbody.innerHTML = data.map((row, i) => `
    <tr class="player-row" style="${{i%2===0?'background:#f0f7ff':'background:#fff'}}"
        onclick="openPlayerModal('${{row.name.replace(/'/g,"\\\\'")}}','${{row.team}}')">
      <td class="px-3 py-2 font-semibold sticky left-0 z-10" style="${{i%2===0?'background:#f0f7ff':'background:#fff'}}">${{row.name}}</td>
      <td class="px-2 py-2 text-center text-gray-500">${{row.team}}</td>
      <td class="px-2 py-2 text-center">${{row.gp}}</td>
      <td class="px-2 py-2 text-center">${{row.ab}}</td>
      <td class="px-2 py-2 text-center">${{row.r}}</td>
      <td class="px-2 py-2 text-center">${{row.h}}</td>
      <td class="px-2 py-2 text-center">${{row.doubles}}</td>
      <td class="px-2 py-2 text-center">${{row.triples}}</td>
      <td class="px-2 py-2 text-center">${{row.hr}}</td>
      <td class="px-2 py-2 text-center">${{row.rbi}}</td>
      <td class="px-2 py-2 text-center">${{row.bb}}</td>
      <td class="px-2 py-2 text-center">${{row.so}}</td>
      <td class="px-2 py-2 text-center">${{row.sb}}</td>
      <td class="px-2 py-2 text-center">${{row.e}}</td>
      <td class="px-2 py-2 text-center font-semibold">${{row.avg}}</td>
      <td class="px-2 py-2 text-center font-semibold">${{row.obp}}</td>
      <td class="px-2 py-2 text-center font-semibold">${{row.slg}}</td>
      <td class="px-2 py-2 text-center font-semibold">${{row.ops}}</td>
      <td class="px-2 py-2 text-center font-bold" style="color:#1e3a5f">${{row.ops_plus}}</td>
    </tr>`).join('');
}}

function filterHitters() {{
  const q    = document.getElementById('hit-search').value.toLowerCase();
  const team = document.getElementById('hit-team-filter').value;
  let filtered = hitData.filter(r =>
    (!q || r.name.toLowerCase().includes(q)) &&
    (!team || r.team === team));
  if (hitSortCol) sortArray(filtered, hitSortCol, hitSortDir, 'hit');
  renderHitTable(filtered);
}}

buildHitterRows();
renderHitTable(hitData);

// ── PITCHING TABLE ────────────────────────────────────────────────────────
let pitData = [], pitSortCol = null, pitSortDir = 1;

function buildPitcherRows() {{
  pitData = STATS.players.filter(p => p.pitching).map(p => ({{
    ...p.pitching, name: p.name, team: p.team, jersey: p.jersey
  }}));
}}

function renderPitTable(data) {{
  const tbody = document.getElementById('pit-table-body');
  tbody.innerHTML = data.map((row, i) => `
    <tr class="player-row" style="${{i%2===0?'background:#f0fff4':'background:#fff'}}"
        onclick="openPlayerModal('${{row.name.replace(/'/g,"\\\\'")}}','${{row.team}}')">
      <td class="px-3 py-2 font-semibold sticky left-0 z-10" style="${{i%2===0?'background:#f0fff4':'background:#fff'}}">${{row.name}}</td>
      <td class="px-2 py-2 text-center text-gray-500">${{row.team}}</td>
      <td class="px-2 py-2 text-center">${{row.g}}</td>
      <td class="px-2 py-2 text-center">${{row.ip}}</td>
      <td class="px-2 py-2 text-center">${{row.h}}</td>
      <td class="px-2 py-2 text-center">${{row.r}}</td>
      <td class="px-2 py-2 text-center">${{row.er}}</td>
      <td class="px-2 py-2 text-center">${{row.bb}}</td>
      <td class="px-2 py-2 text-center">${{row.so}}</td>
      <td class="px-2 py-2 text-center">${{row.hbp}}</td>
      <td class="px-2 py-2 text-center">${{row.pitches}}</td>
      <td class="px-2 py-2 text-center">${{row.spct}}</td>
      <td class="px-2 py-2 text-center">${{row.bf}}</td>
      <td class="px-2 py-2 text-center font-semibold">${{row.era}}</td>
      <td class="px-2 py-2 text-center font-semibold">${{row.whip}}</td>
      <td class="px-2 py-2 text-center font-semibold">${{row.kip}}</td>
      <td class="px-2 py-2 text-center font-semibold">${{row.kbb}}</td>
      <td class="px-2 py-2 text-center font-semibold">${{row.fip_minus}}</td>
      <td class="px-2 py-2 text-center font-bold" style="color:#1a4731">${{row.era_plus}}</td>
    </tr>`).join('');
}}

function filterPitchers() {{
  const q    = document.getElementById('pit-search').value.toLowerCase();
  const team = document.getElementById('pit-team-filter').value;
  let filtered = pitData.filter(r =>
    (!q || r.name.toLowerCase().includes(q)) &&
    (!team || r.team === team));
  if (pitSortCol) sortArray(filtered, pitSortCol, pitSortDir, 'pit');
  renderPitTable(filtered);
}}

buildPitcherRows();
renderPitTable(pitData);

// ── TABLE SORTING ─────────────────────────────────────────────────────────
function sortArray(arr, col, dir, type) {{
  arr.sort((a, b) => {{
    let av = a[col], bv = b[col];
    if (typeof av === 'string' && typeof bv === 'string') {{
      return dir * av.localeCompare(bv);
    }}
    return dir * ((parseFloat(av)||0) - (parseFloat(bv)||0));
  }});
}}

document.querySelectorAll('.sortable').forEach(table => {{
  const isHit = table.id === 'hit-table';
  table.querySelectorAll('th[data-col]').forEach(th => {{
    th.addEventListener('click', () => {{
      const col = th.dataset.col;
      const allTh = table.querySelectorAll('th');
      let dir = 1;
      if (isHit) {{
        dir = (hitSortCol === col) ? -hitSortDir : 1;
        hitSortCol = col; hitSortDir = dir;
      }} else {{
        dir = (pitSortCol === col) ? -pitSortDir : 1;
        pitSortCol = col; pitSortDir = dir;
      }}
      allTh.forEach(t => t.classList.remove('asc','desc'));
      th.classList.add(dir===1 ? 'desc' : 'asc');
      if (isHit) filterHitters(); else filterPitchers();
    }});
  }});
}});

// ── PLAYER CARDS GRID ─────────────────────────────────────────────────────
function renderPlayerCards(data) {{
  const grid = document.getElementById('player-cards-grid');
  grid.innerHTML = '';
  data.forEach(p => {{
    const c = TEAM_COLORS[p.team] || {{bg:'#374151',accent:'#9ca3af'}};
    const card = document.createElement('div');
    card.style.cssText = `background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.1);cursor:pointer;transition:transform .1s`;
    card.onmouseenter = () => card.style.transform = 'translateY(-2px)';
    card.onmouseleave = () => card.style.transform = '';
    const roles = [];
    if (p.hitting)  roles.push('🥎');
    if (p.pitching) roles.push('⚾');
    card.innerHTML = `
      <div style="background:${{c.bg}};padding:10px;text-align:center">
        <div style="width:36px;height:36px;border-radius:50%;background:${{c.accent}};margin:0 auto 4px;display:flex;align-items:center;justify-content:center;font-weight:800;color:${{c.bg}};font-size:14px">${{p.jersey||'?'}}</div>
        <div style="color:#fff;font-weight:700;font-size:12px;line-height:1.2">${{p.name}}</div>
        <div style="color:rgba(255,255,255,.6);font-size:10px">${{roles.join(' ')}}</div>
      </div>
      <div style="padding:8px;font-size:11px;text-align:center">
        ${{p.hitting ? `<div style="color:#1e3a5f;font-weight:600">AVG ${{p.hitting.avg}}</div>` : ''}}
        ${{p.pitching ? `<div style="color:#1a4731;font-weight:600">ERA ${{p.pitching.era}}</div>` : ''}}
        <div style="color:#94a3b8;font-size:10px;margin-top:2px">${{p.team}}</div>
      </div>`;
    card.addEventListener('click', () => openPlayerModal(p.name, p.team));
    grid.appendChild(card);
  }});
}}

function filterPlayerCards() {{
  const q    = document.getElementById('player-search').value.toLowerCase();
  const team = document.getElementById('player-team-filter').value;
  const filtered = STATS.players.filter(p =>
    (!q || p.name.toLowerCase().includes(q)) &&
    (!team || p.team === team));
  renderPlayerCards(filtered);
}}

renderPlayerCards(STATS.players);

// ── PLAYER MODAL ──────────────────────────────────────────────────────────
function openPlayerModal(name, team) {{
  const player = STATS.players.find(p => p.name === name && p.team === team);
  if (!player) return;
  const c = TEAM_COLORS[team] || {{bg:'#374151',accent:'#9ca3af'}};
  const h = player.hitting; const pi = player.pitching;

  let content = `
    <div class="modal-header" style="background:${{c.bg}}">
      <button onclick="document.getElementById('player-modal').classList.remove('open')"
        style="float:right;font-size:20px;opacity:.7;background:none;border:none;color:#fff;cursor:pointer">✕</button>
      <div style="display:flex;align-items:center;gap:12px">
        <div style="width:52px;height:52px;border-radius:50%;background:${{c.accent}};display:flex;align-items:center;justify-content:center;font-weight:900;color:${{c.bg}};font-size:22px">${{player.jersey||'?'}}</div>
        <div>
          <div style="font-size:22px;font-weight:800">${{player.name}}</div>
          <div style="opacity:.75;font-size:13px">${{team}}</div>
        </div>
      </div>
    </div>
    <div style="padding:16px">`;

  if (h) {{
    content += `
      <div style="font-weight:700;font-size:15px;color:#1e3a5f;margin-bottom:10px">🥎 Hitting Stats</div>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:8px">
        ${{[['AVG',h.avg],['OBP',h.obp],['SLG',h.slg],['OPS',h.ops]].map(([l,v])=>
          `<div class="stat-pill" style="background:#eff6ff"><div class="val" style="color:#1e3a5f;font-size:16px">${{v}}</div><div class="lbl">${{l}}</div></div>`).join('')}}
      </div>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:12px">
        ${{[['GP',h.gp],['AB',h.ab],['R',h.r],['H',h.h],
           ['2B',h.doubles],['3B',h.triples],['HR',h.hr],['RBI',h.rbi],
           ['BB',h.bb],['SO',h.so],['SB',h.sb],['E',h.e],['OPS+',h.ops_plus]
          ].map(([l,v])=>`<div class="stat-pill"><div class="val" style="font-size:14px">${{v}}</div><div class="lbl">${{l}}</div></div>`).join('')}}
      </div>`;
  }}

  if (pi) {{
    content += `
      <div style="font-weight:700;font-size:15px;color:#1a4731;margin-bottom:10px;${{h?'padding-top:12px;border-top:1px solid #f1f5f9':''}}">⚾ Pitching Stats</div>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:8px">
        ${{[['ERA',pi.era],['WHIP',pi.whip],['FIP-',pi.fip_minus],['ERA+',pi.era_plus]].map(([l,v])=>
          `<div class="stat-pill" style="background:#f0fdf4"><div class="val" style="color:#1a4731;font-size:16px">${{v}}</div><div class="lbl">${{l}}</div></div>`).join('')}}
      </div>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px">
        ${{[['G',pi.g],['IP',pi.ip],['H',pi.h],['R',pi.r],
           ['ER',pi.er],['BB',pi.bb],['SO',pi.so],['HBP',pi.hbp],
           ['Pitches',pi.pitches],['Strike%',pi.spct],['BF',pi.bf],['K/BB',pi.kbb]
          ].map(([l,v])=>`<div class="stat-pill"><div class="val" style="font-size:14px">${{v}}</div><div class="lbl">${{l}}</div></div>`).join('')}}
      </div>`;
  }}

  content += '</div>';
  document.getElementById('modal-box').innerHTML = content;
  document.getElementById('player-modal').classList.add('open');
}}

function closeModal(event) {{
  if (event.target === document.getElementById('player-modal')) {{
    document.getElementById('player-modal').classList.remove('open');
  }}
}}

// Close modal on escape key
document.addEventListener('keydown', e => {{
  if (e.key === 'Escape') {{
    document.getElementById('player-modal').classList.remove('open');
    document.getElementById('team-modal').classList.remove('open');
  }}
}});
</script>
</body>
</html>"""

# =============================================================================
# 10. WRITE OUTPUT
# =============================================================================
os.makedirs(REPO_DIR, exist_ok=True)
with open(OUT_PATH, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"\n✅  Saved: {OUT_PATH}")
print(f"    Players:  {len(players_data)}")
print(f"    Teams:    {len(TEAMS)}")
print(f"    Hit LBs:  {len(hit_leaderboards)}")
print(f"    Pit LBs:  {len(pit_leaderboards)}")
