"""
compile_sheets.py
=================
Pushes 2026 ALL MAJORS STATS to a live Google Sheet.

Usage
-----
    cd mnt/Stats
    python3 pipeline/compile_sheets.py

Creates the spreadsheet on first run inside the configured Drive folder.
On subsequent runs it finds the existing sheet by name and updates it in place —
your co-manager's link stays the same forever.

Requirements
------------
    pip install gspread google-auth --break-system-packages
    pipeline/credentials.json   ← service account key file
"""

import os, sys, re, importlib.util, time
from collections import defaultdict
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

THIS_DIR   = os.path.dirname(os.path.abspath(__file__))
STATS_DIR  = os.path.dirname(THIS_DIR)
GAMES_DIR  = os.path.join(STATS_DIR, "games")
CREDS_FILE = os.path.join(THIS_DIR, "credentials.json")

# The live Google Sheet (created manually by Russ, shared with service account)
SHEET_ID   = "1wvF3cMIxd_XeI71QNM6gkyrK192QEc_uMm4hSUG67Ms"
SHEET_NAME = "2026 ALL MAJORS STATS"

# =============================================================================
# 1. CONNECT TO GOOGLE SHEETS
# =============================================================================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def connect():
    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
    return gspread.authorize(creds)

# =============================================================================
# 2. LOAD ALL GAME FILES  (identical logic to compile.py)
# =============================================================================
all_hitting  = []
all_pitching = []

game_files = sorted(f for f in os.listdir(GAMES_DIR) if f.endswith('.py'))
if not game_files:
    sys.exit(f"No game files found in {GAMES_DIR}")

for fname in game_files:
    path = os.path.join(GAMES_DIR, fname)
    spec = importlib.util.spec_from_file_location("gf", path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    team = mod.TEAM; date = mod.DATE
    for row in getattr(mod, 'hitting',  []): all_hitting.append({**row, 'team': team, 'date': date})
    for row in getattr(mod, 'pitching', []): all_pitching.append({**row, 'team': team, 'date': date})

print(f"Loaded {len(game_files)} game files: "
      f"{len(all_hitting)} hitting rows, {len(all_pitching)} pitching rows")

# ── Compute timestamps for the "last updated" indicator ──────────────────────
_all_dates = set(row['date'] for row in all_hitting) | set(row['date'] for row in all_pitching)
MOST_RECENT_GAME = max(_all_dates) if _all_dates else "N/A"
# Format: "March 25, 2026 at 11:45 AM"
COMPILED_AT = datetime.now().strftime("%-m/%-d/%Y at %-I:%M %p")
STAMP = f"Most recent game data: {MOST_RECENT_GAME}     ·     Last compiled: {COMPILED_AT}"

# =============================================================================
# 3. HELPERS
# =============================================================================
def display_name(raw):   return raw.split(' #')[0].strip()

def ip_to_dec(ip_str):
    s = str(ip_str)
    if '.' not in s: return float(s)
    w, f = s.split('.'); return int(w) + int(f) / 3.0

def dec_to_ip(dec):
    w = int(dec); thirds = 0 if (dec-w)<0.01 else (1 if (dec-w)<0.5 else 2)
    return f"{w}.{thirds}"

def pct(n, d): return n/d if d else 0

# =============================================================================
# 4. AGGREGATION
# =============================================================================
h_totals = defaultdict(lambda: {'team':'','games':0,'ab':0,'r':0,'h':0,'rbi':0,
    'bb':0,'so':0,'sb':0,'cs':0,'e':0,'doubles':0,'triples':0,'hr':0})
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

hitting_players  = sorted([(d,p) for (d,_t),p in h_totals.items()],  key=lambda x:(x[1]['team'],x[0]))
pitching_players = sorted([(d,p) for (d,_t),p in p_totals.items()], key=lambda x:(x[1]['team'],x[0]))

qual_hitters  = [(n,p) for n,p in hitting_players  if p['ab'] >= 10]
all_hitters   = hitting_players
sb_hitters    = [(n,p) for n,p in hitting_players  if p['sb']+p['cs'] >= 1]
qual_pitchers = [(n,p) for n,p in pitching_players if p['ip_dec'] >= 6.0]
all_pitchers  = pitching_players
kbb_pitchers  = [(n,p) for n,p in pitching_players if p['bb'] > 0 and p['ip_dec'] >= 3.0]

# stat fns
def h_avg(p):      return pct(p['h'], p['ab'])
def h_obp(p):      return pct(p['h']+p['bb'], p['ab']+p['bb'])
def h_slg(p):      return pct(p['h']+p['doubles']+2*p['triples']+3*p['hr'], p['ab'])
def h_ops(p):      return h_obp(p) + h_slg(p)
def h_tb(p):       return p['h']+p['doubles']+2*p['triples']+3*p['hr']
def h_xbh(p):      return p['doubles']+p['triples']+p['hr']
def h_sb_pct(p):   return pct(p['sb'], p['sb']+p['cs'])
def h_walk_pct(p): return pct(p['bb'], p['ab']+p['bb'])
def h_so_pct(p):   return pct(p['so'], p['ab']+p['bb'])
def p_era(p):      return p['er']*9/p['ip_dec']         if p['ip_dec']>0.01 else 99.0
def p_whip(p):     return (p['h']+p['bb'])/p['ip_dec']  if p['ip_dec']>0.01 else 99.0
def p_spct(p):     return pct(p['strikes'], p['pitches'])
def p_h6(p):       return 6*p['h']/p['ip_dec']          if p['ip_dec']>0 else 0
def p_bb6(p):      return 6*p['bb']/p['ip_dec']         if p['ip_dec']>0 else 0
def p_k6(p):       return 6*p['so']/p['ip_dec']         if p['ip_dec']>0 else 0
def p_wpct(p):     return pct(p['bb'], p['bf'])
def p_kpct(p):     return pct(p['so'], p['bf'])
def p_kbb(p):      return pct(p['so'], p['bb'])

# League averages for OPS+ and ERA+
_lg_h   = sum(p['h']  for _, p in hitting_players)
_lg_bb  = sum(p['bb'] for _, p in hitting_players)
_lg_ab  = sum(p['ab'] for _, p in hitting_players)
_lg_tb  = sum(p['h'] + p['doubles'] + 2*p['triples'] + 3*p['hr'] for _, p in hitting_players)
_lg_obp = (_lg_h + _lg_bb) / (_lg_ab + _lg_bb) if (_lg_ab + _lg_bb) > 0 else 1
_lg_slg = _lg_tb / _lg_ab                       if _lg_ab > 0           else 1
_lg_er     = sum(p['er']     for _, p in pitching_players)
_lg_ip     = sum(p['ip_dec'] for _, p in pitching_players)
_lg_era    = _lg_er * 9 / _lg_ip                if _lg_ip > 0           else 0
_lg_bb_pit = sum(p['bb']     for _, p in pitching_players)
_lg_so_pit = sum(p['so']     for _, p in pitching_players)
_fip_const = _lg_era - (3*_lg_bb_pit - 2*_lg_so_pit) / _lg_ip if _lg_ip > 0 else 0

def h_ops_plus(p):
    obp = (p['h']+p['bb']) / (p['ab']+p['bb']) if (p['ab']+p['bb']) > 0 else 0
    slg = (p['h']+p['doubles']+2*p['triples']+3*p['hr']) / p['ab'] if p['ab'] > 0 else 0
    return round(100 * (obp / _lg_obp + slg / _lg_slg - 1)) if _lg_obp > 0 and _lg_slg > 0 else 100

def p_era_plus(p):
    if p['ip_dec'] <= 0.01: return 0
    era = p['er'] * 9 / p['ip_dec']
    if era == 0:  return 999
    return round(100 * _lg_era / era) if _lg_era > 0 else 0

def p_fip_minus(p):
    if p['ip_dec'] <= 0.01: return 0.0
    return round((3*p['bb'] - 2*p['so']) / p['ip_dec'] + _fip_const, 2)

def p_kbb_ratio(p):
    if p['bb'] == 0: return 99.0 if p['so'] > 0 else 0.0
    return round(p['so'] / p['bb'], 2)

# =============================================================================
# 5. GOOGLE SHEETS FORMATTING HELPERS
# =============================================================================
def rgb(hex_color):
    """'1F4E79' → {'red': 0.122, 'green': 0.306, 'blue': 0.475}"""
    h = hex_color.lstrip('#')
    return {'red': int(h[0:2],16)/255, 'green': int(h[2:4],16)/255, 'blue': int(h[4:6],16)/255}

def cell_fmt(bg=None, bold=False, italic=False, color='000000', size=10,
             halign='CENTER', valign='MIDDLE', fmt_pattern=None):
    f = {
        'textFormat': {
            'bold': bold, 'italic': italic,
            'foregroundColor': rgb(color),
            'fontSize': size,
            'fontFamily': 'Arial',
        },
        'horizontalAlignment': halign,
        'verticalAlignment': valign,
    }
    if bg:
        f['backgroundColor'] = rgb(bg)
    if fmt_pattern:
        f['numberFormat'] = {'type': 'NUMBER', 'pattern': fmt_pattern}
    return f

def range_fmt_req(sheet_id, r1, c1, r2, c2, fmt):
    """Build a repeatCell request for the Sheets batchUpdate API."""
    fields = 'userEnteredFormat(' + ','.join([
        'backgroundColor','textFormat','horizontalAlignment',
        'verticalAlignment','numberFormat'
    ]) + ')'
    return {
        'repeatCell': {
            'range': {
                'sheetId': sheet_id,
                'startRowIndex': r1, 'endRowIndex': r2,
                'startColumnIndex': c1, 'endColumnIndex': c2,
            },
            'cell': {'userEnteredFormat': fmt},
            'fields': fields,
        }
    }

def merge_req(sheet_id, r1, c1, r2, c2):
    return {
        'mergeCells': {
            'range': {
                'sheetId': sheet_id,
                'startRowIndex': r1, 'endRowIndex': r2,
                'startColumnIndex': c1, 'endColumnIndex': c2,
            },
            'mergeType': 'MERGE_ALL',
        }
    }

def col_width_req(sheet_id, col_idx, px):
    return {
        'updateDimensionProperties': {
            'range': {
                'sheetId': sheet_id,
                'dimension': 'COLUMNS',
                'startIndex': col_idx,
                'endIndex': col_idx + 1,
            },
            'properties': {'pixelSize': px},
            'fields': 'pixelSize',
        }
    }

def row_height_req(sheet_id, row_idx, px):
    return {
        'updateDimensionProperties': {
            'range': {
                'sheetId': sheet_id,
                'dimension': 'ROWS',
                'startIndex': row_idx,
                'endIndex': row_idx + 1,
            },
            'properties': {'pixelSize': px},
            'fields': 'pixelSize',
        }
    }

def freeze_req(sheet_id, rows=0, cols=0):
    return {
        'updateSheetProperties': {
            'properties': {
                'sheetId': sheet_id,
                'gridProperties': {'frozenRowCount': rows, 'frozenColumnCount': cols},
            },
            'fields': 'gridProperties.frozenRowCount,gridProperties.frozenColumnCount',
        }
    }

def basic_filter_req(sheet_id, num_cols):
    # No endRowIndex = filter extends to end of sheet, enabling sort across all data rows
    return {
        'setBasicFilter': {
            'filter': {
                'range': {
                    'sheetId': sheet_id,
                    'startRowIndex': 2,   # 0-based: row 3 (header row)
                    'startColumnIndex': 0,
                    'endColumnIndex': num_cols,
                }
            }
        }
    }

def tab_color_req(sheet_id, hex_color):
    return {
        'updateSheetProperties': {
            'properties': {
                'sheetId': sheet_id,
                'tabColorStyle': {'rgbColor': rgb(hex_color)},
            },
            'fields': 'tabColorStyle',
        }
    }

# =============================================================================
# 6. LEADERBOARD GRID BUILDER
#    Returns (grid_data, format_requests, merge_requests) for one leaderboard sheet
# =============================================================================
TOP_N        = 10
BLOCK_HEIGHT = TOP_N + 2   # title + header + 10 rows = 12
ROW_GAP      = 2
BLOCK_COLS_0 = [0, 5, 10, 15, 20, 25]  # 0-indexed col starts

def build_lb_grid(categories, sheet_id, start_row_0, subhdr_hex, row1_hex):
    """
    Build a 3-row × 6-col leaderboard grid.
    Returns (data_2d, fmt_reqs, merge_reqs).
    data_2d is a list of rows (each row = list of cell values, '' for empty).
    start_row_0: 0-indexed row where the grid starts (after the title rows).
    """
    # Calculate total rows needed
    total_rows = 3 * BLOCK_HEIGHT + 2 * ROW_GAP
    total_cols = 29   # cols 0-28

    data = [['' for _ in range(total_cols)] for _ in range(total_rows)]
    fmt_reqs  = []
    merge_reqs = []

    for grid_row in range(3):
        r0 = grid_row * (BLOCK_HEIGHT + ROW_GAP)   # relative to grid start
        abs_r0 = start_row_0 + r0                  # absolute 0-indexed row

        for grid_col in range(6):
            cat_idx = grid_row * 6 + grid_col
            if cat_idx >= len(categories): break
            cat    = categories[cat_idx]
            title, pool, sort_fn, fmt_pat, higher_better = cat[:5]
            disp_fn = cat[5] if len(cat) > 5 else None
            c0 = BLOCK_COLS_0[grid_col]

            # Title row (merged across 4 cols)
            data[r0][c0] = title
            merge_reqs.append(merge_req(sheet_id, abs_r0, c0, abs_r0+1, c0+4))
            fmt_reqs.append(range_fmt_req(sheet_id, abs_r0, c0, abs_r0+1, c0+4,
                cell_fmt(bg=subhdr_hex, bold=True, color='FFFFFF', size=9)))

            # Header row
            for i, h in enumerate(['Rk','Player','Team','Stat']):
                data[r0+1][c0+i] = h
            fmt_reqs.append(range_fmt_req(sheet_id, abs_r0+1, c0, abs_r0+2, c0+4,
                cell_fmt(bg=subhdr_hex, bold=True, color='FFFFFF', size=9)))

            # Data rows
            sorted_pool = sorted(pool, key=lambda x: sort_fn(x[1]),
                                  reverse=higher_better)[:TOP_N]
            for rank, (name, p) in enumerate(sorted_pool, 1):
                dr   = r0 + 1 + rank
                abs_dr = abs_r0 + 1 + rank
                raw  = sort_fn(p)
                disp = disp_fn(raw) if disp_fn else raw
                bg   = row1_hex if rank % 2 == 1 else 'FFFFFF'

                # Format stat cell value
                if fmt_pat and disp_fn is None:
                    if '%' in fmt_pat:
                        stat_val = f"{raw:.1%}"
                    elif '000' in fmt_pat:
                        stat_val = f"{raw:.3f}"
                    elif '00' in fmt_pat:
                        stat_val = f"{raw:.2f}"
                    else:
                        stat_val = raw
                else:
                    stat_val = disp

                data[dr][c0]   = rank
                data[dr][c0+1] = name
                data[dr][c0+2] = p['team']
                data[dr][c0+3] = stat_val

                fmt_reqs.append(range_fmt_req(sheet_id, abs_dr, c0, abs_dr+1, c0+4,
                    cell_fmt(bg=bg, size=9)))
                # Player name left-aligned
                fmt_reqs.append(range_fmt_req(sheet_id, abs_dr, c0+1, abs_dr+1, c0+2,
                    cell_fmt(bg=bg, size=9, halign='LEFT')))

    return data, fmt_reqs, merge_reqs


# =============================================================================
# 7. GET OR CREATE SPREADSHEET
# =============================================================================
def get_or_create_spreadsheet(gc):
    """Open the spreadsheet by its fixed ID."""
    print(f"Opening sheet {SHEET_ID}...")
    sh = gc.open_by_key(SHEET_ID)
    print(f"Opened: {sh.title}")
    return sh


# =============================================================================
# 8. BUILD EACH TAB
# =============================================================================
TAB_DEFS = [
    {"title": "🏆 Hitting Leaders",  "tab_color": "2E75B6"},
    {"title": "⚾ Pitching Leaders", "tab_color": "375623"},
    {"title": "📊 Team Hitting",     "tab_color": "595959"},
    {"title": "📊 Team Pitching",    "tab_color": "595959"},
    {"title": "🥎 Player Hitting",   "tab_color": "2E75B6"},
    {"title": "🎯 Player Pitching",  "tab_color": "375623"},
]

def setup_worksheets(sh):
    """Ensure all 6 tabs exist in the right order, clearing old data."""
    existing = {ws.title: ws for ws in sh.worksheets()}

    # Add missing tabs
    for td in TAB_DEFS:
        if td["title"] not in existing:
            sh.add_worksheet(title=td["title"], rows=200, cols=30)

    # Remove any sheet not in our list (e.g., default "Sheet1")
    wanted = {td["title"] for td in TAB_DEFS}
    for ws in sh.worksheets():
        if ws.title not in wanted:
            sh.del_worksheet(ws)

    # Reorder tabs to match TAB_DEFS order
    sh.reorder_worksheets([sh.worksheet(td["title"]) for td in TAB_DEFS])

    # Return dict of title → worksheet
    return {ws.title: ws for ws in sh.worksheets()}


def push_hitting_leaders(sh, ws):
    sid = ws.id
    HIT_CATS = [
        ("Batting Avg (AVG)",  qual_hitters, h_avg,                 '0.000', True),
        ("On-Base Pct (OBP)",  qual_hitters, h_obp,                 '0.000', True),
        ("Slugging Pct (SLG)", qual_hitters, h_slg,                 '0.000', True),
        ("OPS",                qual_hitters, h_ops,                 '0.000', True),
        ("Hits (H)",           all_hitters,  lambda p: p['h'],       None,   True),
        ("RBI",                all_hitters,  lambda p: p['rbi'],     None,   True),
        ("Runs Scored (R)",    all_hitters,  lambda p: p['r'],       None,   True),
        ("Total Bases (TB)",   all_hitters,  h_tb,                   None,   True),
        ("Walks (BB)",         all_hitters,  lambda p: p['bb'],      None,   True),
        ("Doubles (2B)",       all_hitters,  lambda p: p['doubles'], None,   True),
        ("Triples (3B)",       all_hitters,  lambda p: p['triples'], None,   True),
        ("Home Runs (HR)",     all_hitters,  lambda p: p['hr'],      None,   True),
        ("Stolen Bases (SB)",  all_hitters,  lambda p: p['sb'],      None,   True),
        ("SB% (min 1 att)",    sb_hitters,   h_sb_pct,               '0.0%', True),
        ("Walk % (min 10 AB)", qual_hitters, h_walk_pct,             '0.0%', True),
        ("K% Fewest (min 10)", qual_hitters, h_so_pct,               '0.0%', False),
        ("Extra Base Hits",    all_hitters,  h_xbh,                  None,   True),
        ("Errors (Most)",      all_hitters,  lambda p: p['e'],       None,   True),
    ]

    # Title rows
    title_row  = ["2026 Alameda Little League Majors — HITTING LEADERBOARD"] + ['']*28
    subttl_row = [f"Min 10 AB for rate stats.  Min 1 SB attempt for SB%.     {STAMP}"] + ['']*28

    grid_data, fmt_reqs, merge_reqs = build_lb_grid(HIT_CATS, sid, 2, '2E75B6', 'D6E4F0')

    all_data = [title_row, subttl_row] + grid_data
    ws.clear()
    # Unmerge BEFORE writing data — stale merges silently drop writes to non-first cells
    sh.batch_update({'requests': [{'unmergeCells': {'range': {
        'sheetId': sid,
        'startRowIndex': 0, 'endRowIndex': 60,
        'startColumnIndex': 0, 'endColumnIndex': 29,
    }}}]})
    ws.update(all_data, 'A1', value_input_option='USER_ENTERED')

    reqs = []
    # Title formatting
    reqs.append(merge_req(sid, 0, 0, 1, 29))
    reqs.append(range_fmt_req(sid, 0, 0, 1, 29,
        cell_fmt(bg='1F4E79', bold=True, color='FFFFFF', size=16)))
    reqs.append(merge_req(sid, 1, 0, 2, 29))
    reqs.append(range_fmt_req(sid, 1, 0, 2, 29,
        cell_fmt(bg='2E75B6', italic=True, color='FFFFFF', size=9)))
    reqs.extend(merge_reqs)
    reqs.extend(fmt_reqs)
    reqs.append(freeze_req(sid, rows=3))
    reqs.append(tab_color_req(sid, '2E75B6'))
    # Column widths: Rk=40, Player=130, Team=90, Stat=70, gap=18
    for bc in BLOCK_COLS_0:
        reqs += [col_width_req(sid, bc, 40), col_width_req(sid, bc+1, 130),
                 col_width_req(sid, bc+2, 90), col_width_req(sid, bc+3, 70)]
        if bc < BLOCK_COLS_0[-1]:
            reqs.append(col_width_req(sid, bc+4, 18))

    sh.batch_update({'requests': reqs})


def push_pitching_leaders(sh, ws):
    sid = ws.id
    PIT_CATS = [
        ("Innings Pitched",        all_pitchers,  lambda p: p['ip_dec'],  None,   True, dec_to_ip),
        ("ERA (min 6 IP)",         qual_pitchers, p_era,                  '0.00', False),
        ("Hits Allowed (Fewest, min 6 IP)",  qual_pitchers,  lambda p: p['h'],       None,   False),
        ("Runs Allowed (Most)",    all_pitchers,  lambda p: p['r'],       None,   True),
        ("Earned Runs (Most)",     all_pitchers,  lambda p: p['er'],      None,   True),
        ("Walks",                  all_pitchers,  lambda p: p['bb'],      None,   True),
        ("Strikeouts (SO)",        all_pitchers,  lambda p: p['so'],      None,   True),
        ("Pitches Thrown",         all_pitchers,  lambda p: p['pitches'], None,   True),
        ("Strike % (min 6 IP)",    qual_pitchers, p_spct,                 '0.0%', True),
        ("HBP Most",               all_pitchers,  lambda p: p['hbp'],     None,   True),
        ("WHIP (min 6 IP)",        qual_pitchers, p_whip,                 '0.00', False),
        ("H per 6 IP (min 6 IP)",  qual_pitchers, p_h6,                   '0.00', False),
        ("BB per 6 IP (min 6 IP)", qual_pitchers, p_bb6,                  '0.00', False),
        ("K per 6 IP (min 6 IP)",  qual_pitchers, p_k6,                   '0.00', True),
        ("Walk % (min 6 IP)",      qual_pitchers, p_wpct,                 '0.0%', False),
        ("K% (min 6 IP)",          qual_pitchers, p_kpct,                 '0.0%', True),
        ("Batters Faced (BF)",     all_pitchers,  lambda p: p['bf'],      None,   True),
        ("K/BB Ratio (min 6 IP)",  kbb_pitchers,  p_kbb,                  '0.00', True),
    ]

    title_row  = ["2026 Alameda Little League Majors — PITCHING LEADERBOARD"] + ['']*28
    subttl_row = [f"Min 6 IP for rate stats.  Min 1 BB for K/BB ratio.     {STAMP}"] + ['']*28

    grid_data, fmt_reqs, merge_reqs = build_lb_grid(PIT_CATS, sid, 2, '375623', 'D9EAD3')

    all_data = [title_row, subttl_row] + grid_data
    ws.clear()
    # Unmerge BEFORE writing data — stale merges silently drop writes to non-first cells
    sh.batch_update({'requests': [{'unmergeCells': {'range': {
        'sheetId': sid,
        'startRowIndex': 0, 'endRowIndex': 60,
        'startColumnIndex': 0, 'endColumnIndex': 29,
    }}}]})
    ws.update(all_data, 'A1', value_input_option='USER_ENTERED')

    reqs = []
    reqs.append(merge_req(sid, 0, 0, 1, 29))
    reqs.append(range_fmt_req(sid, 0, 0, 1, 29,
        cell_fmt(bg='1E4620', bold=True, color='FFFFFF', size=16)))
    reqs.append(merge_req(sid, 1, 0, 2, 29))
    reqs.append(range_fmt_req(sid, 1, 0, 2, 29,
        cell_fmt(bg='375623', italic=True, color='FFFFFF', size=9)))
    reqs.extend(merge_reqs)
    reqs.extend(fmt_reqs)
    reqs.append(freeze_req(sid, rows=3))
    reqs.append(tab_color_req(sid, '375623'))
    for bc in BLOCK_COLS_0:
        reqs += [col_width_req(sid, bc, 40), col_width_req(sid, bc+1, 130),
                 col_width_req(sid, bc+2, 90), col_width_req(sid, bc+3, 70)]
        if bc < BLOCK_COLS_0[-1]:
            reqs.append(col_width_req(sid, bc+4, 18))

    sh.batch_update({'requests': reqs})


def push_team_hitting(sh, ws):
    sid = ws.id
    headers = ['Team','G','AB','R','H','2B','3B','HR','RBI','BB','SO','SB','CS','E','AVG','OBP','SLG']
    rows = [["2026 Alameda Little League Majors — TEAM HITTING STATISTICS"] + ['']*16,
            [STAMP] + ['']*16,
            headers]

    for team in TEAMS:
        th = team_hit[team]; g = len(team_hit_dates[team])
        ab=th['ab']; h_=th['h']; bb=th['bb']; d=th['doubles']; t_=th['triples']; hr=th['hr']
        avg = f"{h_/ab:.3f}" if ab>0 else ".000"
        obp = f"{(h_+bb)/(ab+bb):.3f}" if (ab+bb)>0 else ".000"
        slg = f"{(h_+d+2*t_+3*hr)/ab:.3f}" if ab>0 else ".000"
        rows.append([team,g,ab,th['r'],h_,d,t_,hr,th['rbi'],bb,th['so'],
                     th['sb'],th['cs'],th['e'],avg,obp,slg])

    ws.clear()
    ws.update(rows, 'A1', value_input_option='USER_ENTERED')

    reqs = []
    reqs.append(merge_req(sid, 0, 0, 1, 17))
    reqs.append(range_fmt_req(sid, 0, 0, 1, 17, cell_fmt(bg='404040', bold=True, color='FFFFFF', size=14)))
    reqs.append(merge_req(sid, 1, 0, 2, 17))
    reqs.append(range_fmt_req(sid, 1, 0, 2, 17, cell_fmt(bg='595959', italic=True, color='FFFFFF', size=9)))
    reqs.append(range_fmt_req(sid, 2, 0, 3, 17, cell_fmt(bg='595959', bold=True, color='FFFFFF', size=10)))
    for i, team in enumerate(TEAMS):
        bg = 'F2F2F2' if i%2==0 else 'FFFFFF'
        abs_r = 3 + i
        reqs.append(range_fmt_req(sid, abs_r, 0, abs_r+1, 17, cell_fmt(bg=bg, size=10)))
        reqs.append(range_fmt_req(sid, abs_r, 0, abs_r+1, 1,  cell_fmt(bg=bg, size=10, halign='LEFT')))
    reqs.append(basic_filter_req(sid, 17))
    reqs.append(freeze_req(sid, rows=3))
    reqs.append(tab_color_req(sid, '595959'))
    widths = [120,40,55,50,50,50,50,50,50,50,50,50,50,50,65,65,65]
    for i, w in enumerate(widths): reqs.append(col_width_req(sid, i, w))
    sh.batch_update({'requests': reqs})


def push_team_pitching(sh, ws):
    sid = ws.id
    headers = ['Team','G','IP','H','R','ER','BB','SO','HBP','BF','ERA','WHIP','K/IP','Pitches','Strikes','Strike%']
    rows = [["2026 Alameda Little League Majors — TEAM PITCHING STATISTICS"] + ['']*15,
            [STAMP] + ['']*15,
            headers]

    for team in TEAMS:
        tp = team_pit[team]; g = len(team_pit_dates[team]); ip_d = tp['ip_dec']
        era    = f"{tp['er']*9/ip_d:.2f}"       if ip_d>0          else "0.00"
        whip   = f"{(tp['h']+tp['bb'])/ip_d:.2f}" if ip_d>0        else "0.00"
        kip    = f"{tp['so']/ip_d:.2f}"          if ip_d>0          else "0.00"
        spct   = f"{tp['strikes']/tp['pitches']:.1%}" if tp['pitches']>0 else "0.0%"
        rows.append([team, g, dec_to_ip(ip_d), tp['h'], tp['r'], tp['er'],
                     tp['bb'], tp['so'], tp['hbp'], tp['bf'],
                     era, whip, kip, tp['pitches'], tp['strikes'], spct])

    ws.clear()
    ws.update(rows, 'A1', value_input_option='USER_ENTERED')

    reqs = []
    reqs.append(merge_req(sid, 0, 0, 1, 16))
    reqs.append(range_fmt_req(sid, 0, 0, 1, 16, cell_fmt(bg='404040', bold=True, color='FFFFFF', size=14)))
    reqs.append(merge_req(sid, 1, 0, 2, 16))
    reqs.append(range_fmt_req(sid, 1, 0, 2, 16, cell_fmt(bg='595959', italic=True, color='FFFFFF', size=9)))
    reqs.append(range_fmt_req(sid, 2, 0, 3, 16, cell_fmt(bg='595959', bold=True, color='FFFFFF', size=10)))
    for i, team in enumerate(TEAMS):
        bg = 'F2F2F2' if i%2==0 else 'FFFFFF'
        abs_r = 3 + i
        reqs.append(range_fmt_req(sid, abs_r, 0, abs_r+1, 16, cell_fmt(bg=bg, size=10)))
        reqs.append(range_fmt_req(sid, abs_r, 0, abs_r+1, 1,  cell_fmt(bg=bg, size=10, halign='LEFT')))
    reqs.append(basic_filter_req(sid, 16))
    reqs.append(freeze_req(sid, rows=3))
    reqs.append(tab_color_req(sid, '595959'))
    widths = [120,40,55,50,50,50,50,50,50,50,65,65,65,70,70,70]
    for i, w in enumerate(widths): reqs.append(col_width_req(sid, i, w))
    sh.batch_update({'requests': reqs})


def push_player_hitting(sh, ws):
    sid = ws.id
    headers = ['Player','Team','GP','AB','R','H','2B','3B','HR','RBI',
               'BB','SO','SB','CS','E','AVG','OBP','SLG','OPS','OPS+']
    rows = [["2026 Alameda Little League Majors — PLAYER HITTING STATISTICS"] + ['']*19,
            [STAMP] + ['']*19,
            headers]

    for name, p in hitting_players:
        ab=p['ab']; h_=p['h']; bb=p['bb']; d=p['doubles']; t_=p['triples']; hr=p['hr']
        avg = f"{h_/ab:.3f}"               if ab>0        else ".000"
        obp = f"{(h_+bb)/(ab+bb):.3f}"     if (ab+bb)>0   else ".000"
        slg = f"{(h_+d+2*t_+3*hr)/ab:.3f}" if ab>0        else ".000"
        ops_v = (h_+bb)/(ab+bb) + (h_+d+2*t_+3*hr)/ab if (ab>0 and (ab+bb)>0) else 0
        ops = f"{ops_v:.3f}"
        ops_plus = h_ops_plus(p)
        rows.append([name, p['team'], p['games'], ab, p['r'], h_,
                     d, t_, hr, p['rbi'], bb, p['so'],
                     p['sb'], p['cs'], p['e'], avg, obp, slg, ops, ops_plus])

    ws.clear()
    ws.update(rows, 'A1', value_input_option='USER_ENTERED')

    reqs = []
    reqs.append(merge_req(sid, 0, 0, 1, 20))
    reqs.append(range_fmt_req(sid, 0, 0, 1, 20, cell_fmt(bg='1F4E79', bold=True, color='FFFFFF', size=14)))
    reqs.append(merge_req(sid, 1, 0, 2, 20))
    reqs.append(range_fmt_req(sid, 1, 0, 2, 20, cell_fmt(bg='2E75B6', italic=True, color='FFFFFF', size=9)))
    reqs.append(range_fmt_req(sid, 2, 0, 3, 20, cell_fmt(bg='2E75B6', bold=True, color='FFFFFF', size=10)))
    for i in range(len(hitting_players)):
        bg = 'D6E4F0' if i%2==0 else 'FFFFFF'
        abs_r = 3 + i
        reqs.append(range_fmt_req(sid, abs_r, 0, abs_r+1, 20, cell_fmt(bg=bg, size=10)))
        reqs.append(range_fmt_req(sid, abs_r, 0, abs_r+1, 2,  cell_fmt(bg=bg, size=10, halign='LEFT')))
    reqs.append(basic_filter_req(sid, 20))
    reqs.append(freeze_req(sid, rows=3))
    reqs.append(tab_color_req(sid, '2E75B6'))
    widths = [150,100,40,45,45,45,45,45,45,45,45,45,45,45,45,65,65,65,65,55]
    for i, w in enumerate(widths): reqs.append(col_width_req(sid, i, w))
    sh.batch_update({'requests': reqs})


def push_player_pitching(sh, ws):
    sid = ws.id
    headers = ['Player','Team','G','IP','H','R','ER','BB','SO','HBP',
               'Pitches','Strikes','Strike%','BF','ERA','WHIP','K/IP','K/BB','FIP-','ERA+']
    rows = [["2026 Alameda Little League Majors — PLAYER PITCHING STATISTICS"] + ['']*19,
            [STAMP] + ['']*19,
            headers]

    for name, p in pitching_players:
        ip_d = p['ip_dec']
        spct      = f"{p['strikes']/p['pitches']:.1%}" if p['pitches']>0 else "0.0%"
        era       = f"{p['er']*9/ip_d:.2f}"            if ip_d>0         else "0.00"
        whip      = f"{(p['h']+p['bb'])/ip_d:.2f}"     if ip_d>0         else "0.00"
        kip       = f"{p['so']/ip_d:.2f}"              if ip_d>0         else "0.00"
        era_plus  = p_era_plus(p)
        fip_minus = p_fip_minus(p)
        kbb       = p_kbb_ratio(p)
        rows.append([name, p['team'], p['games'], dec_to_ip(ip_d),
                     p['h'], p['r'], p['er'], p['bb'], p['so'], p['hbp'],
                     p['pitches'], p['strikes'], spct, p['bf'], era, whip, kip,
                     kbb, fip_minus, era_plus])

    ws.clear()
    ws.update(rows, 'A1', value_input_option='USER_ENTERED')

    reqs = []
    reqs.append(merge_req(sid, 0, 0, 1, 20))
    reqs.append(range_fmt_req(sid, 0, 0, 1, 20, cell_fmt(bg='1E4620', bold=True, color='FFFFFF', size=14)))
    reqs.append(merge_req(sid, 1, 0, 2, 20))
    reqs.append(range_fmt_req(sid, 1, 0, 2, 20, cell_fmt(bg='375623', italic=True, color='FFFFFF', size=9)))
    reqs.append(range_fmt_req(sid, 2, 0, 3, 20, cell_fmt(bg='375623', bold=True, color='FFFFFF', size=10)))
    for i in range(len(pitching_players)):
        bg = 'D9EAD3' if i%2==0 else 'FFFFFF'
        abs_r = 3 + i
        reqs.append(range_fmt_req(sid, abs_r, 0, abs_r+1, 20, cell_fmt(bg=bg, size=10)))
        reqs.append(range_fmt_req(sid, abs_r, 0, abs_r+1, 2,  cell_fmt(bg=bg, size=10, halign='LEFT')))
    reqs.append(basic_filter_req(sid, 20))
    reqs.append(freeze_req(sid, rows=3))
    reqs.append(tab_color_req(sid, '375623'))
    widths = [150,100,40,55,45,45,45,45,45,45,70,70,70,45,65,65,65,55,65,65]
    for i, w in enumerate(widths): reqs.append(col_width_req(sid, i, w))
    sh.batch_update({'requests': reqs})


# =============================================================================
# 9. MAIN
# =============================================================================
if __name__ == "__main__":
    print("Connecting to Google Sheets...")
    gc = connect()

    print("Opening/creating spreadsheet...")
    sh = get_or_create_spreadsheet(gc)

    print("Setting up worksheets...")
    tabs = setup_worksheets(sh)

    pushers = [
        ("🏆 Hitting Leaders",  push_hitting_leaders),
        ("⚾ Pitching Leaders", push_pitching_leaders),
        ("📊 Team Hitting",     push_team_hitting),
        ("📊 Team Pitching",    push_team_pitching),
        ("🥎 Player Hitting",   push_player_hitting),
        ("🎯 Player Pitching",  push_player_pitching),
    ]

    for tab_title, pusher in pushers:
        print(f"  Writing {tab_title}...")
        pusher(sh, tabs[tab_title])
        time.sleep(1)   # stay comfortably under Sheets API rate limits

    print(f"\n✅  Done!")
    print(f"    Sheet: https://docs.google.com/spreadsheets/d/{sh.id}")
    print(f"    Share this link with your co-manager.")
