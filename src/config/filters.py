"""
Filter definitions for arbeitsagentur.de dynamic URL construction.
German labels → English labels → URL parameter values.
"""

BASE_SEARCH_URL = "https://www.arbeitsagentur.de/jobsuche/suche"

# ── Published Since ──────────────────────────────────────────
PUBLISHED_SINCE = {
    "param": "veroeffentlichtseit",
    "label": "Published Since",
    "options": [
        {"label": "Any time",   "value": ""},
        {"label": "Today",      "value": "1"},
        {"label": "Yesterday",  "value": "3"},
        {"label": "1 Week",     "value": "7"},
        {"label": "2 Weeks",    "value": "14"},
        {"label": "4 Weeks",    "value": "30"},
    ],
}

# ── Working Hours ────────────────────────────────────────────
WORKING_HOURS = {
    "param": "arbeitszeit",
    "label": "Working Hours",
    "multi": True,
    "options": [
        {"label": "Full-time",              "value": "vz"},
        {"label": "Part-time",              "value": "tz"},
        {"label": "Shift / Night / Weekend","value": "snw"},
        {"label": "Minijob",                "value": "mj"},
    ],
}

# ── Contract Type ────────────────────────────────────────────
CONTRACT_TYPE = {
    "param": "befristung",
    "label": "Contract Type",
    "options": [
        {"label": "Any",        "value": ""},
        {"label": "Fixed-term", "value": "1"},
        {"label": "Permanent",  "value": "2"},
    ],
}

# ── Offer Type ───────────────────────────────────────────────
OFFER_TYPE = {
    "param": "angebotsart",
    "label": "Offer Type",
    "options": [
        {"label": "Any",             "value": ""},
        {"label": "Employment",      "value": "1"},
        {"label": "Self-employment", "value": "4"},
    ],
}

# ── Sort ─────────────────────────────────────────────────────
SORT_BY = {
    "param": "sort",
    "label": "Sort By",
    "options": [
        {"label": "Relevance", "value": "relevanz"},
        {"label": "Date",      "value": "veroeffdatum"},
        {"label": "Distance",  "value": "entfernung"},
    ],
}

# ── Radius ───────────────────────────────────────────────────
RADIUS = {
    "param": "umkreis",
    "label": "Radius (km)",
    "options": [
        {"label": "Any",    "value": ""},
        {"label": "25 km",  "value": "25"},
        {"label": "50 km",  "value": "50"},
        {"label": "100 km", "value": "100"},
        {"label": "200 km", "value": "200"},
    ],
}

# ── Top Cities (for location dropdown) ───────────────────────
TOP_CITIES = [
    "Berlin", "Hamburg", "München", "Köln", "Frankfurt am Main",
    "Bremen", "Düsseldorf", "Nürnberg", "Hannover", "Stuttgart",
    "Leipzig", "Dresden", "Essen", "Dortmund", "Duisburg",
    "Karlsruhe", "Mannheim", "Augsburg", "Münster", "Bonn",
    "Kiel", "Magdeburg", "Bochum", "Kassel", "Bielefeld",
    "Braunschweig", "Erfurt", "Rostock", "Regensburg", "Chemnitz",
]

# ── All filter groups for API export ─────────────────────────
ALL_FILTERS = {
    "published_since": PUBLISHED_SINCE,
    "working_hours":   WORKING_HOURS,
    "contract_type":   CONTRACT_TYPE,
    "offer_type":      OFFER_TYPE,
    "sort_by":         SORT_BY,
    "radius":          RADIUS,
}


def build_search_url(filters: dict) -> str:
    """Build arbeitsagentur.de search URL from a filter dict.

    Expected keys (all optional):
        was              – keyword (free text)
        wo               – location (city name)
        umkreis          – radius value
        arbeitszeit      – str or list[str]
        veroeffentlichtseit – str
        befristung       – str
        angebotsart      – str
        sort             – str
    """
    from urllib.parse import urlencode

    params: list[tuple[str, str]] = []

    simple = ["was", "wo", "umkreis", "veroeffentlichtseit",
              "befristung", "angebotsart", "sort"]
    for key in simple:
        val = filters.get(key)
        if val:
            params.append((key, str(val)))

    # arbeitszeit can be multi-select → joined with semicolons
    az = filters.get("arbeitszeit")
    if az:
        if isinstance(az, list):
            params.append(("arbeitszeit", ";".join(az)))
        else:
            params.append(("arbeitszeit", str(az)))

    if not params:
        return BASE_SEARCH_URL

    return f"{BASE_SEARCH_URL}?{urlencode(params, safe=';')}"
