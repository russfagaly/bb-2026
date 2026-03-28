"""
name_registry.py
================
Canonical player name registry for 2026 Alameda Little League Majors.

Auto-generated from all game files in games/. Maps (team, jersey_number) to
the canonical bare name (no jersey suffix) used in the stats workbook.

Usage
-----
    from pipeline.name_registry import REGISTRY, canonical_name

    # Look up a player's canonical name
    name = canonical_name("Astros", "19")   # → "Colton D"

    # Validate a raw game-file name
    raw  = "Colton D #19"
    key  = (team, raw.split('#')[1].strip())
    ok   = REGISTRY.get(key) == raw.split(' #')[0].strip()

Known special cases
-------------------
Astros jerseys #11 and #13: Lukas I and Kolin I swapped jerseys after 03/10.
  - Early games: Lukas I #11, Kolin I #13
  - Later games: Lukas I #13, Kolin I #11
  - Both players are correctly represented in the game files; the jersey swap
    is a real event, not a data error.

Yankees jerseys #7 and #47: Two different players named "Henry S" on the
  same team. They are distinct players. #47 appears in fewer games.
"""

# ---------------------------------------------------------------------------
# Registry: (team, jersey_number_string) -> canonical bare name
# ---------------------------------------------------------------------------
REGISTRY = {
    ("Astros", "10"): "Rio S",
    ("Astros", "11"): "Lukas I",       # NOTE: jersey swap — see above
    ("Astros", "12"): "Niall F",
    ("Astros", "13"): "Kolin I",       # NOTE: jersey swap — see above
    ("Astros", "19"): "Colton D",
    ("Astros", "23"): "Connor Z",
    ("Astros", "24"): "Carter F",
    ("Astros", "26"): "Benjami...",    # GameChanger truncates this name
    ("Astros", "3"):  "Jordan C",
    ("Astros", "5"):  "Julian P",
    ("Astros", "7"):  "Max H",
    ("Astros", "8"):  "Logan S",

    ("Brewers", "11"): "Reece L",
    ("Brewers", "13"): "King N",
    ("Brewers", "17"): "Zeke W",
    ("Brewers", "2"):  "Walter C",
    ("Brewers", "20"): "Huston G",
    ("Brewers", "24"): "Theo D",
    ("Brewers", "3"):  "Zach C",
    ("Brewers", "33"): "Sebasti...",   # GameChanger truncates this name
    ("Brewers", "4"):  "Luciano A",
    ("Brewers", "41"): "Oliver R",
    ("Brewers", "7"):  "Miles M",
    ("Brewers", "8"):  "Clayton L",

    ("Giants", "10"): "Thomas B",
    ("Giants", "11"): "Kai L",
    ("Giants", "12"): "Benjami...",    # GameChanger truncates this name
    ("Giants", "2"):  "Jaxon M",
    ("Giants", "22"): "Aiden G",
    ("Giants", "24"): "Jonah L",
    ("Giants", "34"): "Cameron L",
    ("Giants", "41"): "Boden N",
    ("Giants", "55"): "River A",
    ("Giants", "6"):  "Carver D",
    ("Giants", "7"):  "Michael H",
    ("Giants", "8"):  "Griffin C",

    ("Guardians", "10"): "Liam T",
    ("Guardians", "13"): "Patrick C",
    ("Guardians", "21"): "Soren K",
    ("Guardians", "22"): "Logan M",
    ("Guardians", "24"): "Conor F",
    ("Guardians", "27"): "Lockie M",
    ("Guardians", "29"): "Luke T",
    ("Guardians", "34"): "Lennon D",
    ("Guardians", "39"): "Zeke M",
    ("Guardians", "4"):  "Drew B",
    ("Guardians", "6"):  "Hunter D",
    ("Guardians", "7"):  "Carter H",

    ("Marlins", "0"):  "Nico Y",
    ("Marlins", "10"): "Kaleo P",
    ("Marlins", "11"): "Wyatt M",
    ("Marlins", "12"): "Shawn M",
    ("Marlins", "16"): "Henry B",
    ("Marlins", "17"): "Wilder E",
    ("Marlins", "23"): "Jax H",
    ("Marlins", "24"): "Cassius...",   # GameChanger truncates this name
    ("Marlins", "27"): "Andreas...",   # GameChanger truncates this name
    ("Marlins", "28"): "Frankie G",
    ("Marlins", "3"):  "Julian W",
    ("Marlins", "5"):  "Mayer H",

    ("Padres", "13"): "Orion M",
    ("Padres", "2"):  "Arthur B",
    ("Padres", "22"): "RJ F",
    ("Padres", "24"): "Miles D",
    ("Padres", "28"): "AJ L",
    ("Padres", "3"):  "Ezekiel C",
    ("Padres", "34"): "Cruz B",
    ("Padres", "4"):  "Jonah M",
    ("Padres", "44"): "Brody E",
    ("Padres", "50"): "Adrian T",
    ("Padres", "51"): "Donovan K",
    ("Padres", "7"):  "Samuel G",

    ("White Sox", "11"): "Sam E",
    ("White Sox", "14"): "Lou V",
    ("White Sox", "17"): "Philip T",
    ("White Sox", "22"): "Hudson C",
    ("White Sox", "24"): "Edward M",
    ("White Sox", "27"): "Jack G",
    ("White Sox", "3"):  "Jaiden N",
    ("White Sox", "30"): "Julius N",
    ("White Sox", "44"): "Ace B",
    ("White Sox", "5"):  "Beni R",
    ("White Sox", "6"):  "Adrien R",
    ("White Sox", "7"):  "Brayden K",

    ("Yankees", "11"): "Owen S",
    ("Yankees", "12"): "Adam H",
    ("Yankees", "13"): "Benny M",
    ("Yankees", "14"): "Max M",
    ("Yankees", "15"): "Severin...",   # GameChanger truncates this name
    ("Yankees", "17"): "Jet S",
    ("Yankees", "2"):  "Hudson P",
    ("Yankees", "26"): "Ben B",
    ("Yankees", "47"): "Henry S",     # NOTE: two different Henry S on Yankees
    ("Yankees", "5"):  "Thomas D",
    ("Yankees", "7"):  "Henry S",     # NOTE: two different Henry S on Yankees
    ("Yankees", "9"):  "Brixton L",
    ("Yankees", "99"): "Roland M",
}

# ---------------------------------------------------------------------------
# Aliases: alternate name strings that should be treated as the canonical form
# Used by validate.py to catch old-format names in new game extractions.
# ---------------------------------------------------------------------------
ALIASES = {
    # Marlins — GameChanger used First-Initial Last-Name format on 03/07
    "K Pontemayor": "Kaleo P",
    "M Hemberg":    "Mayer H",
    "W Eula":       "Wilder E",
    "N Yuen":       "Nico Y",
    "S Medina":     "Shawn M",
    "F Goray":      "Frankie G",
    "W Musa":       "Wyatt M",
    "A Satter":     "Andreas...",
    "C Ward":       "Cassius...",
    "K Ponte":      "Kaleo P",
    # Brewers — GameChanger used First-Initial Last-Name format on 03/09
    "O Rowe":       "Oliver R",
    "M Moyer":      "Miles M",
    "L Arce":       "Luciano A",
    "R Lau":        "Reece L",
    # Padres — GameChanger used First-Initial Last-Name on 03/14
    "S Gilmore":    "Samuel G",
    "M Denman":     "Miles D",
    "D Kim":        "Donovan K",
}

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def canonical_name(team: str, jersey: str):
    """Return canonical bare name for (team, jersey), or None if unknown."""
    return REGISTRY.get((team, str(jersey)))


def normalize(raw_name: str) -> str:
    """
    Given a raw name like 'Colton D #19', return the canonical bare name.
    First strips jersey, then checks ALIASES for old-format corrections.
    """
    bare = raw_name.split(' #')[0].strip()
    return ALIASES.get(bare, bare)
