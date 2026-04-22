"""
Canonical list of industry categories the classifier is allowed to emit.

Kept deliberately short — the retraining loop can split a bucket later if
feedback shows systematic confusion. Aligning with common German job-board
taxonomies:
    https://www.arbeitsagentur.de/ (Berufsfelder)
"""

CATEGORIES: list[str] = [
    "IT",
    "Engineering",
    "Healthcare",
    "Sales",
    "Marketing",
    "Finance",
    "Logistics",
    "Handwerk",            # skilled trades
    "Education",
    "Hospitality",
    "Administration",
    "Retail",
    "Other",
]
