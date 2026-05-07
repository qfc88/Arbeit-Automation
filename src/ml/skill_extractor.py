"""
Skill Extraction engine for German job postings.

Hybrid approach: comprehensive dictionary + regex pattern matching.
No ML model needed — deterministic, fast, 100% precision on known skills.

Usage:
    from ml.skill_extractor import extract_skills
    skills = extract_skills(profession, job_description)
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, asdict

from .skill_dictionary import ALL_CATEGORIES, LANGUAGE_LEVELS

logger = logging.getLogger(__name__)

# Pre-compile all patterns once at import time
_COMPILED: list[tuple[str, str, re.Pattern]] = []  # (category, canonical, pattern)

for category, skills in ALL_CATEGORIES.items():
    for canonical, patterns in skills.items():
        combined = "|".join(patterns)
        try:
            _COMPILED.append((
                category,
                canonical,
                re.compile(rf"\b(?:{combined})\b", re.IGNORECASE),
            ))
        except re.error:
            # Some patterns use lookahead/lookbehind — compile individually
            for pat in patterns:
                try:
                    _COMPILED.append((
                        category,
                        canonical,
                        re.compile(rf"(?:{pat})", re.IGNORECASE),
                    ))
                except re.error as e:
                    logger.warning("Bad regex for %s / %s: %s", canonical, pat, e)

# Language level patterns
_LEVEL_COMPILED: list[tuple[str, re.Pattern]] = []
for level, patterns in LANGUAGE_LEVELS.items():
    combined = "|".join(patterns)
    _LEVEL_COMPILED.append((level, re.compile(rf"\b(?:{combined})\b", re.IGNORECASE)))


@dataclass
class ExtractedSkill:
    skill: str           # canonical name, e.g. "Python", "Führerschein B"
    category: str        # e.g. "programming", "certification"
    mentions: int        # how many times found in text
    context: str | None  # snippet around first match (max 120 chars)


def _get_context(text: str, match: re.Match, window: int = 60) -> str:
    """Extract a snippet around the match."""
    start = max(0, match.start() - window)
    end = min(len(text), match.end() + window)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    # Collapse whitespace
    return re.sub(r"\s+", " ", snippet)


def extract_skills(
    profession: str,
    job_description: str | None,
    include_soft_skills: bool = True,
) -> list[ExtractedSkill]:
    """
    Extract skills from a job posting.

    Returns deduplicated list sorted by category then mentions (desc).
    """
    text = f"{profession or ''}\n{job_description or ''}"
    if len(text.strip()) < 10:
        return []

    found: dict[str, ExtractedSkill] = {}  # canonical → ExtractedSkill

    for category, canonical, pattern in _COMPILED:
        if not include_soft_skills and category == "soft_skill":
            continue

        matches = list(pattern.finditer(text))
        if not matches:
            continue

        if canonical in found:
            found[canonical].mentions += len(matches)
        else:
            found[canonical] = ExtractedSkill(
                skill=canonical,
                category=category,
                mentions=len(matches),
                context=_get_context(text, matches[0]),
            )

    # Sort: category → mentions desc
    result = sorted(
        found.values(),
        key=lambda s: (s.category, -s.mentions),
    )
    return result


def extract_language_requirements(
    job_description: str | None,
) -> list[dict[str, str]]:
    """
    Extract language + level pairs from description.
    e.g. "Deutsch B2" → {"language": "Deutsch", "level": "B2"}
    """
    if not job_description:
        return []

    text = job_description
    results: list[dict[str, str]] = []

    # Find language mentions and look for nearby levels
    from .skill_dictionary import LANGUAGES
    for lang, patterns in LANGUAGES.items():
        combined = "|".join(patterns)
        lang_pattern = re.compile(rf"\b(?:{combined})\b", re.IGNORECASE)
        for m in lang_pattern.finditer(text):
            # Search in a window around the match for level indicators
            start = max(0, m.start() - 30)
            end = min(len(text), m.end() + 80)
            window = text[start:end]

            level_found = None
            for level, level_pat in _LEVEL_COMPILED:
                if level_pat.search(window):
                    level_found = level
                    break

            entry = {"language": lang}
            if level_found:
                entry["level"] = level_found
            # Avoid duplicates
            if entry not in results:
                results.append(entry)

    return results


def skills_to_dicts(skills: list[ExtractedSkill]) -> list[dict]:
    """Convert to JSON-serializable dicts."""
    return [asdict(s) for s in skills]


def summarize_skills(skills: list[ExtractedSkill]) -> dict[str, list[str]]:
    """Group skills by category for a compact summary."""
    groups: dict[str, list[str]] = {}
    for s in skills:
        groups.setdefault(s.category, []).append(s.skill)
    return groups
