"""
CSS selectors for arbeitsagentur.de job detail pages.

Centralised here so scrapers, tests, and maintenance scripts can reference
the same selector strings.  The JobScraper __init__ still builds a local
dict, but this module is the canonical source of truth.
"""

# ── Job header ──────────────────────────────────────────────
TITLE = "#detail-kopfbereich-titel"
COMPANY = "#detail-kopfbereich-firma"
LOCATION = "#detail-kopfbereich-arbeitsort"
START_DATE = ".eintrittsdatum-tag"
JOB_TYPE = "#detail-kopfbereich-anstellungsart"
AUSBILDUNGSBERUF = "#detail-kopfbereich-ausbildungsberuf"

# ── Job body ────────────────────────────────────────────────
JOB_DESCRIPTION = "#detail-beschreibung-text-container"

# ── CAPTCHA ─────────────────────────────────────────────────
CAPTCHA_CONTAINER = "#jobdetails-kontaktdaten-block"
CAPTCHA_IMAGE = "#kontaktdaten-captcha-image"
CAPTCHA_INPUT = "#kontaktdaten-captcha-input"
CAPTCHA_SUBMIT = "#kontaktdaten-captcha-absenden-button"
CAPTCHA_RELOAD = "#kontaktdaten-captcha-reload-button"

# ── Contact info (post-CAPTCHA) ─────────────────────────────
CONTACT_PHONE = "#detail-bewerbung-telefon-Telefon"
CONTACT_EMAIL = "#detail-bewerbung-mail"
CONTACT_ADDRESS = "#detail-bewerbung-adresse"
APPLICATION_METHOD = ".bewerbungsarten li"

# ── Links (post-CAPTCHA) ────────────────────────────────────
APPLICATION_LINK = "#detail-bewerbung-url"
EXTERNAL_LINK = "#detail-bewerbung-agkontaktieren"
REF_NR = "#detail-bewerbung-chiffre"
REF_NR_FOOTER = "#detail-footer-referenznummer"

# ── Cookie consent ──────────────────────────────────────────
COOKIE_SELECTORS = [
    '[data-testid="cookie-accept"]',
    'button[aria-label*="akzeptieren"]',
    'button[aria-label*="Akzeptieren"]',
    "#onetrust-accept-btn-handler",
    ".cookie-accept",
    'button:has-text("Alle akzeptieren")',
    'button:has-text("Zustimmen")',
]

# ── Link scraper (search results page) ──────────────────────
SEARCH_RESULT_LINK = 'a[href*="/jobsuche/jobdetail/"]'
LOAD_MORE_BUTTON = 'button:has-text("Mehr Ergebnisse laden")'
CONNECTION_ERROR_MODAL = "#verbindungsfehler-modal"
CONNECTION_ERROR_RETRY = "#verbindungsfehler-erneut-versuchen"

# ── Contact scraper (external page) ─────────────────────────
CONTACT_PERSON_SELECTORS = [
    ".contact-person",
    "[itemprop='name']",
    ".ansprechpartner",
    "#contact-name",
]
APPLICATION_LINK_SELECTORS = [
    "a[href*='bewerbung']",
    "a[href*='apply']",
    "a[href*='karriere']",
    "a.btn-primary",
    "a.apply-button",
]
