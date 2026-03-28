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
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  html, body {{ max-width:100vw; overflow-x:hidden; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; background:#f0f4f8; }}

  /* ── HEADER & NAV ── */
  #site-header {{ position:sticky; top:0; z-index:50; background:linear-gradient(160deg,#0f2744,#1a4a8a); box-shadow:0 2px 12px rgba(0,0,0,.35); }}
  .header-inner {{ max-width:900px; margin:0 auto; padding:10px 14px 0; }}
  .header-top {{ display:flex; align-items:center; justify-content:space-between; margin-bottom:10px; }}
  .header-title {{ font-size:15px; font-weight:800; color:#fff; letter-spacing:-.2px; line-height:1.2; }}
  .header-subtitle {{ font-size:11px; color:#93c5fd; font-weight:500; margin-top:1px; }}
  .header-date {{ text-align:right; flex-shrink:0; }}
  .header-date-label {{ font-size:10px; color:#93c5fd; }}
  .header-date-val {{ font-size:12px; font-weight:700; color:#fff; }}

  /* Nav tabs */
  .nav-tabs {{ display:flex; gap:2px; overflow-x:auto; scrollbar-width:none; }}
  .nav-tabs::-webkit-scrollbar {{ display:none; }}
  .nav-tab {{ flex:1; min-width:0; border:none; background:transparent; color:rgba(255,255,255,.55);
              padding:9px 4px; font-size:11px; font-weight:700; cursor:pointer; text-align:center;
              border-bottom:3px solid transparent; transition:all .15s; white-space:nowrap; letter-spacing:.2px; }}
  .nav-tab:hover {{ color:#fff; background:rgba(255,255,255,.08); }}
  .nav-tab.active {{ color:#fff; border-bottom-color:#38bdf8; background:rgba(255,255,255,.1); }}
  .nav-tab .tab-icon {{ display:block; font-size:16px; margin-bottom:1px; }}

  /* ── TAB SECTIONS ── */
  .tab-section {{ display:none; }}
  .tab-section.active {{ display:block; }}
  .page {{ max-width:900px; margin:0 auto; padding:14px; }}

  /* ── SECTION HEADERS ── */
  .sec-hdr {{ display:flex; align-items:center; gap:8px; margin-bottom:12px; margin-top:4px; }}
  .sec-hdr-bar {{ width:4px; height:20px; border-radius:2px; flex-shrink:0; }}
  .sec-hdr-text {{ font-size:15px; font-weight:800; color:#0f2744; }}

  /* ── LEADERBOARD ── */
  .lb-grid {{ display:grid; gap:10px; grid-template-columns:repeat(2,1fr); }}
  .lb-card {{ background:#fff; border-radius:12px; overflow:hidden; box-shadow:0 1px 6px rgba(0,0,0,.09); }}
  .lb-card-hdr {{ padding:9px 12px; font-size:10px; font-weight:800; letter-spacing:.4px;
                  text-transform:uppercase; color:#fff; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
  .lb-entry {{ display:grid; grid-template-columns:20px 1fr auto; gap:4px; align-items:center;
               padding:6px 10px; border-top:1px solid #f1f5f9; }}
  .lb-entry:first-of-type {{ border-top:none; }}
  .lb-entry:nth-child(even) {{ background:#fafbfc; }}
  .lb-rank {{ font-size:11px; font-weight:700; color:#94a3b8; }}
  .lb-rank.top3 {{ color:#f59e0b; }}
  .lb-name {{ font-size:12px; font-weight:600; color:#1e293b; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
  .lb-right {{ text-align:right; }}
  .lb-val {{ font-size:13px; font-weight:800; line-height:1; }}
  .lb-team {{ font-size:9px; color:#94a3b8; margin-top:1px; }}

  /* ── TEAM CARDS ── */
  .team-card {{ border-radius:14px; overflow:hidden; box-shadow:0 2px 10px rgba(0,0,0,.13); cursor:pointer; transition:transform .12s,box-shadow .12s; }}
  .team-card:active {{ transform:scale(.98); }}

  /* ── SEARCH / FILTER BAR ── */
  .filter-bar {{ display:flex; gap:8px; margin-bottom:10px; }}
  .filter-bar input, .filter-bar select {{
    border:1.5px solid #e2e8f0; border-radius:10px; padding:8px 12px;
    font-size:13px; background:#fff; outline:none; transition:border .15s; }}
  .filter-bar input {{ flex:1; min-width:0; }}
  .filter-bar input:focus, .filter-bar select:focus {{ border-color:#38bdf8; }}

  /* ── SORTABLE TABLES ── */
  .tbl-scroll {{ overflow-x:auto; }}
  .tbl-scroll::-webkit-scrollbar {{ height:3px; }}
  .tbl-scroll::-webkit-scrollbar-thumb {{ background:#cbd5e1; border-radius:2px; }}
  .tbl-wrap {{ border-radius:12px; overflow:hidden; box-shadow:0 1px 6px rgba(0,0,0,.09); }}
  .sortable {{ width:100%; border-collapse:collapse; font-size:12px; }}
  .sortable thead tr {{ background:#0f2744; }}
  .sortable.green thead tr {{ background:#0d3320; }}
  .sortable th {{ color:#fff; padding:9px 8px; font-weight:700; font-size:11px; letter-spacing:.3px;
                  cursor:pointer; user-select:none; white-space:nowrap; text-align:center; }}
  .sortable th:first-child {{ text-align:left; padding-left:12px; }}
  .sortable th:hover {{ background:#1a4a8a; }}
  .sortable.green th:hover {{ background:#155e32; }}
  .sortable thead th.sticky-col {{ background:#0f2744; z-index:3; }}
  .sortable.green thead th.sticky-col {{ background:#0d3320; }}
  .sort-icon {{ font-size:9px; margin-left:3px; opacity:.6; }}
  .sortable th.asc .sort-icon::after {{ content:'▲'; opacity:1; }}
  .sortable th.desc .sort-icon::after {{ content:'▼'; opacity:1; }}
  .sortable th:not(.asc):not(.desc) .sort-icon::after {{ content:'⇅'; }}
  .sortable td {{ padding:7px 8px; text-align:center; border-bottom:1px solid #f1f5f9; }}
  .sortable td:first-child {{ text-align:left; padding-left:12px; font-weight:600; }}
  .sortable tbody tr:nth-child(even) {{ background:#f8fafc; }}
  .sortable tbody tr:hover {{ background:#e0f2fe !important; cursor:pointer; }}
  .sortable.green tbody tr:hover {{ background:#dcfce7 !important; }}
  .sticky-col {{ position:sticky; left:0; z-index:2; background:#fff; }}
  .sortable tbody tr:nth-child(even) .sticky-col {{ background:#f8fafc; }}
  .sortable tbody tr:hover .sticky-col {{ background:#e0f2fe !important; }}
  .sortable.green tbody tr:hover .sticky-col {{ background:#dcfce7 !important; }}

  /* ── MODALS ── */
  .modal-overlay {{ position:fixed; inset:0; background:rgba(0,0,0,.55); z-index:200; display:none;
                    align-items:flex-end; justify-content:center; }}
  .modal-overlay.open {{ display:flex; }}
  .modal-box {{ background:#fff; border-radius:20px 20px 0 0; width:100vw; max-width:640px;
                max-height:92vh; overflow-x:hidden; overflow-y:auto;
                box-shadow:0 -4px 30px rgba(0,0,0,.2); animation:slideUp .22s ease; }}
  @keyframes slideUp {{ from {{ transform:translateY(60px); opacity:0; }} to {{ transform:translateY(0); opacity:1; }} }}
  .modal-hdr {{ position:relative; padding:8px 42px 8px 12px; color:#fff; }}
  .modal-body {{ padding:8px 10px 12px; }}
  .modal-close {{ position:absolute; top:8px; right:8px; width:26px; height:26px;
                  border-radius:50%; background:rgba(255,255,255,.2); border:none; color:#fff;
                  font-size:14px; cursor:pointer; display:flex; align-items:center;
                  justify-content:center; }}

  /* ── STAT PILLS ── */
  .pill {{ background:#f8fafc; border-radius:7px; padding:5px 1px; text-align:center;
           min-width:0; overflow:hidden; }}
  .pill-val {{ font-size:11px; font-weight:800; color:#0f2744; line-height:1;
               white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
  .pill-lbl {{ font-size:7px; color:#94a3b8; font-weight:600; text-transform:uppercase;
               margin-top:2px; letter-spacing:.1px; white-space:nowrap; }}
  .pill.blue {{ background:#eff6ff; }}
  .pill.blue .pill-val {{ color:#1d4ed8; font-size:12px; }}
  .pill.green {{ background:#f0fdf4; }}
  .pill.green .pill-val {{ color:#15803d; font-size:12px; }}

  /* ── PILL GRIDS — minmax(0,1fr) forces columns to actually shrink ── */
  .pills-key {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:4px; margin-bottom:5px; }}
  .pills-counts {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:4px; margin-bottom:7px; }}

  /* ── PLAYER CARDS GRID ── */
  .player-grid {{ display:grid; grid-template-columns:repeat(2,1fr); gap:8px; }}
  .p-card {{ background:#fff; border-radius:12px; overflow:hidden; cursor:pointer;
             box-shadow:0 1px 5px rgba(0,0,0,.1); transition:transform .12s; }}
  .p-card:active {{ transform:scale(.97); }}

  /* ── RESPONSIVE ── */
  @media (min-width:480px) {{
    .lb-grid {{ grid-template-columns:repeat(3,1fr); }}
    .player-grid {{ grid-template-columns:repeat(3,1fr); }}
  }}
  @media (min-width:640px) {{
    .nav-tab {{ font-size:13px; padding:10px 8px; }}
    .nav-tab .tab-icon {{ font-size:18px; }}
    .modal-overlay {{ align-items:center; }}
    .modal-box {{ border-radius:20px; max-height:85vh; }}
    .lb-grid {{ grid-template-columns:repeat(6,1fr); }}
    .player-grid {{ grid-template-columns:repeat(4,1fr); }}
  }}

  /* ── MOBILE TABLE: hide non-essential columns so tables fit without h-scroll ── */
  /* Hitting: keep Player, Team, GP, H, HR, RBI, AVG, OBP, OPS (9 cols) */
  @media (max-width:639px) {{
    #hit-table th:nth-child(4),  #hit-table td:nth-child(4),   /* AB */
    #hit-table th:nth-child(5),  #hit-table td:nth-child(5),   /* R */
    #hit-table th:nth-child(7),  #hit-table td:nth-child(7),   /* 2B */
    #hit-table th:nth-child(8),  #hit-table td:nth-child(8),   /* 3B */
    #hit-table th:nth-child(11), #hit-table td:nth-child(11),  /* BB */
    #hit-table th:nth-child(12), #hit-table td:nth-child(12),  /* SO */
    #hit-table th:nth-child(13), #hit-table td:nth-child(13),  /* SB */
    #hit-table th:nth-child(14), #hit-table td:nth-child(14),  /* E */
    #hit-table th:nth-child(17), #hit-table td:nth-child(17),  /* SLG */
    #hit-table th:nth-child(19), #hit-table td:nth-child(19)   /* OPS+ */
    {{ display:none; }}
  }}
  /* Pitching: keep Player, Team, G, IP, BB, SO, ERA, WHIP (8 cols) */
  @media (max-width:639px) {{
    #pit-table th:nth-child(5),  #pit-table td:nth-child(5),   /* H */
    #pit-table th:nth-child(6),  #pit-table td:nth-child(6),   /* R */
    #pit-table th:nth-child(7),  #pit-table td:nth-child(7),   /* ER */
    #pit-table th:nth-child(10), #pit-table td:nth-child(10),  /* HBP */
    #pit-table th:nth-child(11), #pit-table td:nth-child(11),  /* Pitches */
    #pit-table th:nth-child(12), #pit-table td:nth-child(12),  /* Strike% */
    #pit-table th:nth-child(13), #pit-table td:nth-child(13),  /* BF */
    #pit-table th:nth-child(16), #pit-table td:nth-child(16),  /* K/IP */
    #pit-table th:nth-child(17), #pit-table td:nth-child(17),  /* K/BB */
    #pit-table th:nth-child(18), #pit-table td:nth-child(18),  /* FIP- */
    #pit-table th:nth-child(19), #pit-table td:nth-child(19)   /* ERA+ */
    {{ display:none; }}
  }}
  /* On mobile, disable table's own h-scroll since columns now fit */
  @media (max-width:639px) {{
    .tbl-scroll {{ overflow-x:visible; }}
    .sortable {{ table-layout:fixed; width:100%; }}
    .sortable td, .sortable th {{ overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
  }}
</style>
</head>
<body>

<!-- STICKY HEADER + NAV -->
<div id="site-header">
  <div class="header-inner">
    <div class="header-top">
      <div>
        <div class="header-title">⚾ Alameda Little League Majors</div>
        <div class="header-subtitle" id="header-subtitle">2026 Season</div>
      </div>
      <div class="header-date">
        <div class="header-date-label">Last Updated</div>
        <div class="header-date-val" id="updated-date"></div>
      </div>
    </div>
    <nav class="nav-tabs">
      <button class="nav-tab active" onclick="showTab('leaders',this)">
        <span class="tab-icon">🏆</span>Leaders
      </button>
      <button class="nav-tab" onclick="showTab('teams',this)">
        <span class="tab-icon">🏟️</span>Teams
      </button>
      <button class="nav-tab" onclick="showTab('hitters',this)">
        <span class="tab-icon">🥎</span>Hitters
      </button>
      <button class="nav-tab" onclick="showTab('pitchers',this)">
        <span class="tab-icon">⚾</span>Pitchers
      </button>
      <button class="nav-tab" onclick="showTab('players',this)">
        <span class="tab-icon">👤</span>Players
      </button>
    </nav>
  </div>
</div>

<!-- ── LEADERS TAB ──────────────────────────────────────────────────────── -->
<section id="tab-leaders" class="tab-section active">
  <div class="page">
    <div class="sec-hdr"><div class="sec-hdr-bar" style="background:#2563eb"></div><div class="sec-hdr-text">Hitting Leaders</div></div>
    <div class="lb-grid" id="hit-lb-grid"></div>
    <div class="sec-hdr" style="margin-top:20px"><div class="sec-hdr-bar" style="background:#16a34a"></div><div class="sec-hdr-text">Pitching Leaders</div></div>
    <div class="lb-grid" id="pit-lb-grid"></div>
  </div>
</section>

<!-- ── TEAMS TAB ─────────────────────────────────────────────────────────── -->
<section id="tab-teams" class="tab-section">
  <div class="page">
    <div class="sec-hdr"><div class="sec-hdr-bar" style="background:#7c3aed"></div><div class="sec-hdr-text">Team Stats</div></div>
    <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:10px" id="teams-grid"></div>
  </div>
</section>

<!-- ── HITTERS TAB ── -->
<section id="tab-hitters" class="tab-section">
  <div class="page">
    <div class="sec-hdr">
      <div class="sec-hdr-bar" style="background:#2563eb"></div>
      <div class="sec-hdr-text">Player Hitting</div>
    </div>
    <div class="filter-bar">
      <input id="hit-search" type="text" placeholder="🔍  Search player…" oninput="filterHitters()"/>
      <select id="hit-team-filter" onchange="filterHitters()">
        <option value="">All Teams</option>
      </select>
    </div>
    <div class="tbl-scroll tbl-wrap">
      <table class="sortable" id="hit-table">
        <thead>
          <tr>
            <th class="sticky-col" data-col="name" data-type="str">Player<span class="sort-icon"></span></th>
            <th data-col="team" data-type="str">Team<span class="sort-icon"></span></th>
            <th data-col="gp" data-type="num">GP<span class="sort-icon"></span></th>
            <th data-col="ab" data-type="num">AB<span class="sort-icon"></span></th>
            <th data-col="r" data-type="num">R<span class="sort-icon"></span></th>
            <th data-col="h" data-type="num">H<span class="sort-icon"></span></th>
            <th data-col="doubles" data-type="num">2B<span class="sort-icon"></span></th>
            <th data-col="triples" data-type="num">3B<span class="sort-icon"></span></th>
            <th data-col="hr" data-type="num">HR<span class="sort-icon"></span></th>
            <th data-col="rbi" data-type="num">RBI<span class="sort-icon"></span></th>
            <th data-col="bb" data-type="num">BB<span class="sort-icon"></span></th>
            <th data-col="so" data-type="num">SO<span class="sort-icon"></span></th>
            <th data-col="sb" data-type="num">SB<span class="sort-icon"></span></th>
            <th data-col="e" data-type="num">E<span class="sort-icon"></span></th>
            <th data-col="avg" data-type="str">AVG<span class="sort-icon"></span></th>
            <th data-col="obp" data-type="str">OBP<span class="sort-icon"></span></th>
            <th data-col="slg" data-type="str">SLG<span class="sort-icon"></span></th>
            <th data-col="ops" data-type="str">OPS<span class="sort-icon"></span></th>
            <th data-col="ops_plus" data-type="num">OPS+<span class="sort-icon"></span></th>
          </tr>
        </thead>
        <tbody id="hit-table-body"></tbody>
      </table>
    </div>
  </div>
</section>

<!-- ── PITCHERS TAB ── -->
<section id="tab-pitchers" class="tab-section">
  <div class="page">
    <div class="sec-hdr">
      <div class="sec-hdr-bar" style="background:#16a34a"></div>
      <div class="sec-hdr-text">Player Pitching</div>
    </div>
    <div class="filter-bar">
      <input id="pit-search" type="text" placeholder="🔍  Search player…" oninput="filterPitchers()"/>
      <select id="pit-team-filter" onchange="filterPitchers()">
        <option value="">All Teams</option>
      </select>
    </div>
    <div class="tbl-scroll tbl-wrap">
      <table class="sortable green" id="pit-table">
        <thead>
          <tr>
            <th class="sticky-col" data-col="name" data-type="str">Player<span class="sort-icon"></span></th>
            <th data-col="team" data-type="str">Team<span class="sort-icon"></span></th>
            <th data-col="g" data-type="num">G<span class="sort-icon"></span></th>
            <th data-col="ip_dec" data-type="num">IP<span class="sort-icon"></span></th>
            <th data-col="h" data-type="num">H<span class="sort-icon"></span></th>
            <th data-col="r" data-type="num">R<span class="sort-icon"></span></th>
            <th data-col="er" data-type="num">ER<span class="sort-icon"></span></th>
            <th data-col="bb" data-type="num">BB<span class="sort-icon"></span></th>
            <th data-col="so" data-type="num">SO<span class="sort-icon"></span></th>
            <th data-col="hbp" data-type="num">HBP<span class="sort-icon"></span></th>
            <th data-col="pitches" data-type="num">Pitches<span class="sort-icon"></span></th>
            <th data-col="spct" data-type="str">Strike%<span class="sort-icon"></span></th>
            <th data-col="bf" data-type="num">BF<span class="sort-icon"></span></th>
            <th data-col="era" data-type="str">ERA<span class="sort-icon"></span></th>
            <th data-col="whip" data-type="str">WHIP<span class="sort-icon"></span></th>
            <th data-col="kip" data-type="str">K/IP<span class="sort-icon"></span></th>
            <th data-col="kbb" data-type="num">K/BB<span class="sort-icon"></span></th>
            <th data-col="fip_minus" data-type="num">FIP-<span class="sort-icon"></span></th>
            <th data-col="era_plus" data-type="num">ERA+<span class="sort-icon"></span></th>
          </tr>
        </thead>
        <tbody id="pit-table-body"></tbody>
      </table>
    </div>
  </div>
</section>

<!-- ── PLAYERS TAB ── -->
<section id="tab-players" class="tab-section">
  <div class="page">
    <div class="sec-hdr">
      <div class="sec-hdr-bar" style="background:#0369a1"></div>
      <div class="sec-hdr-text">Player Cards</div>
    </div>
    <div class="filter-bar">
      <input id="player-search" type="text" placeholder="🔍  Search player…" oninput="filterPlayerCards()"/>
      <select id="player-team-filter" onchange="filterPlayerCards()">
        <option value="">All Teams</option>
      </select>
    </div>
    <div class="player-grid" id="player-cards-grid"></div>
  </div>
</section>

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
// ── TAB SWITCHING ──
function showTab(name, btn) {{
  document.querySelectorAll('.tab-section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  if (btn) btn.classList.add('active');
}}

// ── INIT ──
document.getElementById('updated-date').textContent = STATS.generated;
document.getElementById('header-subtitle').textContent = '2026 Season · Stats';
['hit-team-filter','pit-team-filter','player-team-filter'].forEach(id => {{
  const sel = document.getElementById(id);
  STATS.teams.forEach(t => {{
    const opt = document.createElement('option');
    opt.value = t; opt.textContent = t;
    sel.appendChild(opt);
  }});
}});

// ── LEADERBOARDS ──
function renderLeaderboards() {{
  function renderGrid(cats, containerId, color) {{
    const grid = document.getElementById(containerId);
    cats.forEach(cat => {{
      const card = document.createElement('div');
      card.className = 'lb-card';
      const entries = cat.entries.map(e => `
        <div class="lb-entry">
          <span class="lb-rank${{e.rank<=3?' top3':''}}">${{e.rank}}</span>
          <span class="lb-name">${{e.name}}</span>
          <div class="lb-right">
            <div class="lb-val" style="color:${{color}}">${{e.value}}</div>
            <div class="lb-team">${{e.team}}</div>
          </div>
        </div>`).join('');
      card.innerHTML = `<div class="lb-card-hdr" style="background:${{color}}">${{cat.title}}</div>${{entries}}`;
      grid.appendChild(card);
    }});
  }}
  renderGrid(STATS.leaderboards.hitting,  'hit-lb-grid', '#1e3a5f');
  renderGrid(STATS.leaderboards.pitching, 'pit-lb-grid', '#1a4731');
}}
renderLeaderboards();

// ── TEAMS ──
function renderTeams() {{
  const grid = document.getElementById('teams-grid');
  STATS.teams.forEach(team => {{
    const td = STATS.teams_data[team];
    const c  = TEAM_COLORS[team] || {{bg:'#374151',accent:'#9ca3af'}};
    const card = document.createElement('div');
    card.className = 'team-card';
    card.innerHTML = `
      <div style="background:${{c.bg}};padding:14px;color:#fff">
        <div style="font-size:17px;font-weight:800;letter-spacing:-.3px">${{team}}</div>
        <div style="font-size:11px;opacity:.7;margin-top:2px">${{td.games}} games</div>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:4px;margin-top:10px">
          ${{[['AVG',td.hitting.avg],['Runs',td.hitting.r],['ERA',td.pitching.era]].map(([l,v])=>`
            <div style="text-align:center">
              <div style="font-size:17px;font-weight:800;color:${{c.accent}}">${{v}}</div>
              <div style="font-size:9px;opacity:.7">${{l}}</div>
            </div>`).join('')}}
        </div>
      </div>
      <div style="padding:8px 12px;font-size:11px;color:#64748b;text-align:center;background:#fff">
        Tap for full stats →
      </div>`;
    card.addEventListener('click', () => openTeamModal(team));
    grid.appendChild(card);
  }});
}}
renderTeams();

// ── TEAM MODAL ──
function openTeamModal(team) {{
  const td = STATS.teams_data[team];
  const c  = TEAM_COLORS[team] || {{bg:'#374151',accent:'#9ca3af'}};
  const th = td.hitting; const tp = td.pitching;
  const pill = (l,v) => `<div class="pill"><div class="pill-val">${{v}}</div><div class="pill-lbl">${{l}}</div></div>`;
  document.getElementById('team-modal-box').innerHTML = `
    <div class="modal-hdr" style="background:${{c.bg}}">
      <button class="modal-close" onclick="document.getElementById('team-modal').classList.remove('open')">✕</button>
      <div style="font-size:18px;font-weight:800">${{team}}</div>
      <div style="opacity:.7;font-size:11px;margin-top:1px">${{td.games}} games played</div>
    </div>
    <div class="modal-body">
      <div style="font-weight:700;font-size:11px;color:#1e3a5f;margin-bottom:5px">🥎 Team Hitting</div>
      <div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:4px;margin-bottom:10px">
        ${{[['AVG',th.avg],['OBP',th.obp],['SLG',th.slg],['OPS',th.ops],
           ['Runs',th.r],['Hits',th.h],['HR',th.hr],['RBI',th.rbi],
           ['BB',th.bb],['SO',th.so],['SB',th.sb],['E',th.e]
          ].map(([l,v])=>pill(l,v)).join('')}}
      </div>
      <div style="font-weight:700;font-size:11px;color:#1a4731;margin-bottom:5px">⚾ Team Pitching</div>
      <div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:4px;margin-bottom:10px">
        ${{[['ERA',tp.era],['WHIP',tp.whip],['IP',tp.ip],['SO',tp.so],
           ['BB',tp.bb],['H',tp.h],['ER',tp.er],['HBP',tp.hbp],
           ['Pitches',tp.pitches],['Strike%',tp.spct],['BF',tp.bf],['K/IP',tp.kip]
          ].map(([l,v])=>pill(l,v)).join('')}}
      </div>
      <div style="font-weight:700;font-size:13px;color:#374151;margin-bottom:8px">👤 Roster</div>
      <div style="display:flex;flex-wrap:wrap;gap:5px" id="team-roster-${{team.replace(/ /g,'-')}}"></div>
    </div>`;
  STATS.players.filter(p => p.team===team).sort((a,b)=>a.name.localeCompare(b.name)).forEach(p => {{
    const badge = document.createElement('span');
    badge.style.cssText = `background:${{c.bg}};color:#fff;padding:5px 10px;border-radius:20px;font-size:12px;cursor:pointer`;
    badge.textContent = p.name + (p.jersey ? ' #' + p.jersey : '');
    badge.addEventListener('click', () => {{ closeTeamModal(); openPlayerModal(p.name, p.team); }});
    document.getElementById('team-roster-' + team.replace(/ /g,'-')).appendChild(badge);
  }});
  document.getElementById('team-modal').classList.add('open');
}}
function closeTeamModal(event) {{
  if (!event || event.target===document.getElementById('team-modal'))
    document.getElementById('team-modal').classList.remove('open');
}}

// ── HITTING TABLE ──
let hitData=[], hitSortCol=null, hitSortDir=1;
function buildHitterRows() {{
  hitData = STATS.players.filter(p=>p.hitting).map(p=>( {{...p.hitting,name:p.name,team:p.team,jersey:p.jersey}} ));
}}
function renderHitTable(data) {{
  document.getElementById('hit-table-body').innerHTML = data.map(row=>`
    <tr onclick="openPlayerModal('${{row.name.replace(/'/g,"\\\\'")}}','${{row.team}}')">
      <td class="sticky-col">${{row.name}}</td>
      <td style="color:#64748b">${{row.team}}</td>
      <td>${{row.gp}}</td><td>${{row.ab}}</td><td>${{row.r}}</td><td>${{row.h}}</td>
      <td>${{row.doubles}}</td><td>${{row.triples}}</td><td>${{row.hr}}</td><td>${{row.rbi}}</td>
      <td>${{row.bb}}</td><td>${{row.so}}</td><td>${{row.sb}}</td><td>${{row.e}}</td>
      <td style="font-weight:700">${{row.avg}}</td><td style="font-weight:700">${{row.obp}}</td>
      <td style="font-weight:700">${{row.slg}}</td><td style="font-weight:700">${{row.ops}}</td>
      <td style="font-weight:800;color:#1e3a5f">${{row.ops_plus}}</td>
    </tr>`).join('');
}}
function filterHitters() {{
  const q=document.getElementById('hit-search').value.toLowerCase();
  const team=document.getElementById('hit-team-filter').value;
  let d=hitData.filter(r=>(!q||r.name.toLowerCase().includes(q))&&(!team||r.team===team));
  if (hitSortCol) sortArray(d,hitSortCol,hitSortDir);
  renderHitTable(d);
}}
buildHitterRows(); renderHitTable(hitData);

// ── PITCHING TABLE ──
let pitData=[], pitSortCol=null, pitSortDir=1;
function buildPitcherRows() {{
  pitData = STATS.players.filter(p=>p.pitching).map(p=>( {{...p.pitching,name:p.name,team:p.team,jersey:p.jersey}} ));
}}
function renderPitTable(data) {{
  document.getElementById('pit-table-body').innerHTML = data.map(row=>`
    <tr onclick="openPlayerModal('${{row.name.replace(/'/g,"\\\\'")}}','${{row.team}}')">
      <td class="sticky-col">${{row.name}}</td>
      <td style="color:#64748b">${{row.team}}</td>
      <td>${{row.g}}</td><td>${{row.ip}}</td><td>${{row.h}}</td><td>${{row.r}}</td>
      <td>${{row.er}}</td><td>${{row.bb}}</td><td>${{row.so}}</td><td>${{row.hbp}}</td>
      <td>${{row.pitches}}</td><td>${{row.spct}}</td><td>${{row.bf}}</td>
      <td style="font-weight:700">${{row.era}}</td><td style="font-weight:700">${{row.whip}}</td>
      <td style="font-weight:700">${{row.kip}}</td><td style="font-weight:700">${{row.kbb}}</td>
      <td style="font-weight:700">${{row.fip_minus}}</td>
      <td style="font-weight:800;color:#1a4731">${{row.era_plus}}</td>
    </tr>`).join('');
}}
function filterPitchers() {{
  const q=document.getElementById('pit-search').value.toLowerCase();
  const team=document.getElementById('pit-team-filter').value;
  let d=pitData.filter(r=>(!q||r.name.toLowerCase().includes(q))&&(!team||r.team===team));
  if (pitSortCol) sortArray(d,pitSortCol,pitSortDir);
  renderPitTable(d);
}}
buildPitcherRows(); renderPitTable(pitData);

// ── TABLE SORTING ──
function sortArray(arr, col, dir) {{
  arr.sort((a,b) => {{
    const av=a[col], bv=b[col];
    if (typeof av==='string'&&typeof bv==='string') return dir*av.localeCompare(bv);
    return dir*((parseFloat(av)||0)-(parseFloat(bv)||0));
  }});
}}
document.querySelectorAll('.sortable').forEach(table => {{
  const isHit = table.id==='hit-table';
  table.querySelectorAll('th[data-col]').forEach(th => {{
    th.addEventListener('click', () => {{
      const col=th.dataset.col;
      let dir=1;
      if (isHit) {{ dir=(hitSortCol===col)?-hitSortDir:1; hitSortCol=col; hitSortDir=dir; }}
      else {{ dir=(pitSortCol===col)?-pitSortDir:1; pitSortCol=col; pitSortDir=dir; }}
      table.querySelectorAll('th').forEach(t=>t.classList.remove('asc','desc'));
      th.classList.add(dir===1?'desc':'asc');
      if (isHit) filterHitters(); else filterPitchers();
    }});
  }});
}});

// ── PLAYER CARDS ──
function fmt(v) {{ return typeof v==='string' ? v.replace(/^0\./,'.') : v; }}
function renderPlayerCards(data) {{
  const grid=document.getElementById('player-cards-grid');
  grid.innerHTML='';
  data.forEach(p => {{
    const c=TEAM_COLORS[p.team]||{{bg:'#374151',accent:'#9ca3af'}};
    const roles=[];
    if (p.hitting) roles.push('🥎');
    if (p.pitching) roles.push('⚾');
    const card=document.createElement('div');
    card.className='p-card';
    card.innerHTML=`
      <div style="background:${{c.bg}};padding:12px 6px 8px;text-align:center">
        <div style="width:42px;height:42px;border-radius:50%;background:${{c.accent}};margin:0 auto 5px;display:flex;align-items:center;justify-content:center;font-weight:900;color:${{c.bg}};font-size:16px">${{p.jersey||'?'}}</div>
        <div style="color:#fff;font-weight:800;font-size:12px;line-height:1.2;letter-spacing:-.1px">${{p.name}}</div>
        <div style="color:rgba(255,255,255,.6);font-size:11px;margin-top:2px">${{roles.join(' ')}}</div>
      </div>
      <div style="padding:6px 8px 5px;text-align:center;background:#fff;border-top:2px solid ${{c.accent}}">
        ${{p.hitting?`<div style="color:#1e3a5f;font-weight:800;font-size:13px">AVG ${{fmt(p.hitting.avg)}}</div>`:''}}
        ${{p.pitching?`<div style="color:#1a4731;font-weight:800;font-size:13px">ERA ${{p.pitching.era}}</div>`:''}}
        <div style="color:#94a3b8;font-size:9px;margin-top:2px;font-weight:600">${{p.team}}</div>
      </div>`;
    card.addEventListener('click',()=>openPlayerModal(p.name,p.team));
    grid.appendChild(card);
  }});
}}
function filterPlayerCards() {{
  const q=document.getElementById('player-search').value.toLowerCase();
  const team=document.getElementById('player-team-filter').value;
  renderPlayerCards(STATS.players.filter(p=>(!q||p.name.toLowerCase().includes(q))&&(!team||p.team===team)));
}}
renderPlayerCards(STATS.players);

// ── PLAYER MODAL ──
function openPlayerModal(name, team) {{
  const player=STATS.players.find(p=>p.name===name&&p.team===team);
  if (!player) return;
  const c=TEAM_COLORS[team]||{{bg:'#374151',accent:'#9ca3af'}};
  const h=player.hitting; const pi=player.pitching;
  const pill=(l,v,cls='')=>`<div class="pill ${{cls}}"><div class="pill-val">${{v}}</div><div class="pill-lbl">${{l}}</div></div>`;
  let body=`
    <div class="modal-hdr" style="background:${{c.bg}}">
      <button class="modal-close" onclick="document.getElementById('player-modal').classList.remove('open')">✕</button>
      <div style="display:flex;align-items:center;gap:10px">
        <div style="width:38px;height:38px;border-radius:50%;background:${{c.accent}};display:flex;align-items:center;justify-content:center;font-weight:900;color:${{c.bg}};font-size:15px;flex-shrink:0">${{player.jersey||'?'}}</div>
        <div>
          <div style="font-size:16px;font-weight:800;line-height:1.1">${{player.name}}</div>
          <div style="opacity:.75;font-size:11px;margin-top:1px">${{team}}</div>
        </div>
      </div>
    </div>
    <div class="modal-body">`;
  if (h) {{
    body+=`
      <div style="font-weight:700;font-size:11px;color:#1e3a5f;margin-bottom:5px">🥎 Hitting</div>
      <div class="pills-key">
        ${{[['AVG',h.avg],['OBP',h.obp],['SLG',h.slg],['OPS',h.ops]].map(([l,v])=>pill(l,v,'blue')).join('')}}
      </div>
      <div class="pills-counts">
        ${{[['GP',h.gp],['AB',h.ab],['R',h.r],['H',h.h],
           ['2B',h.doubles],['3B',h.triples],['HR',h.hr],['RBI',h.rbi],
           ['BB',h.bb],['SO',h.so],['SB',h.sb],['E',h.e],['OPS+',h.ops_plus]
          ].map(([l,v])=>pill(l,v)).join('')}}
      </div>`;
  }}
  if (pi) {{
    const sep=h?'padding-top:7px;border-top:1px solid #f1f5f9;margin-top:2px;':'';
    body+=`
      <div style="font-weight:700;font-size:11px;color:#1a4731;margin-bottom:5px;${{sep}}">⚾ Pitching</div>
      <div class="pills-key">
        ${{[['ERA',pi.era],['WHIP',pi.whip],['FIP-',pi.fip_minus],['ERA+',pi.era_plus]].map(([l,v])=>pill(l,v,'green')).join('')}}
      </div>
      <div class="pills-counts">
        ${{[['G',pi.g],['IP',pi.ip],['H',pi.h],['R',pi.r],
           ['ER',pi.er],['BB',pi.bb],['SO',pi.so],['HBP',pi.hbp],
           ['Pitches',pi.pitches],['Strike%',pi.spct],['BF',pi.bf],['K/BB',pi.kbb]
          ].map(([l,v])=>pill(l,v)).join('')}}
      </div>`;
  }}
  body+='</div>';
  document.getElementById('modal-box').innerHTML=body;
  document.getElementById('player-modal').classList.add('open');
}}
function closeModal(event) {{
  if (event.target===document.getElementById('player-modal'))
    document.getElementById('player-modal').classList.remove('open');
}}
document.addEventListener('keydown', e => {{
  if (e.key==='Escape') {{
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
