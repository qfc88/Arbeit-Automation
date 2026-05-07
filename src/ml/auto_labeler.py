"""
Auto-label jobs from the DB using keyword rules.
Produces training.jsonl for the ML classifier.

Usage:
    python -m src.ml.auto_labeler
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path

from .categories import CATEGORIES
from .db import get_pool, close_pool

logger = logging.getLogger(__name__)

# Keyword rules: category -> list of regex patterns (case-insensitive, German+English)
RULES: dict[str, list[str]] = {
    "IT": [
        r"\b(software|developer|entwickler|programmierer|devops|sysadmin|"
        r"it[-\s]?admin|daten\w*|data\s?(scientist|engineer|analyst)|"
        r"informatik|web[-\s]?develop|frontend|backend|full[-\s]?stack|"
        r"cloud|cyber|security|netzwerk|network|java|python|c\+\+|"
        r"sap\b|erp|system\w*admin|it[-\s]?support|it[-\s]?berater|"
        r"fachinformatik|anwendungsentwick|systemintegrat)\b",
    ],
    "Engineering": [
        r"\b(ingenieur|engineer|maschinenbau|elektrotechnik|"
        r"konstrukt|techniker|meister|cad|cnc|mechatronik|"
        r"verfahrenstechnik|automatisierung|fertigungs|produktions\w*tech|"
        r"quality\s?engineer|bauingenieur|statik|technische[rs]?\s+zeichn|"
        r"werkzeug\w*|industrial\s?engineer)\b",
    ],
    "Healthcare": [
        r"\b(pflege|krankenpflege|gesundheit|arzt|ärztin|medizin|"
        r"altenpflege|therapeut|pharma|apothek|zahnarzt|zahnmedizin|"
        r"rettung|sanitäter|hebamme|klinik|krankenhaus|praxis|"
        r"physiotherap|ergotherap|logopäd|psycholog|nurse|"
        r"pflegefachkraft|pflegefach\w+|medizinische[rs]?\s+fach)\b",
    ],
    "Sales": [
        r"\b(vertrieb|sales|außendienst|account\s?manager|"
        r"business\s?develop|kundenberater|key\s?account|"
        r"vertriebsmitarbeiter|handelsvertreter|"
        r"akquise|verkauf\w*berater|sales\s?manager)\b",
    ],
    "Marketing": [
        r"\b(marketing|social\s?media|content|seo|sem|"
        r"brand|kommunikation|pr[-\s]?manager|public\s?relation|"
        r"online[-\s]?marketing|kampagne|werbung|grafik\w*design|"
        r"ux|ui[-\s]?design|creative\s?director)\b",
    ],
    "Finance": [
        r"\b(finanzen|finance|buchhalter|buchhaltung|accounting|"
        r"steuerberater|wirtschaftsprüf|controller|controlling|"
        r"finanz\w*berater|bank\w*kaufm|versicherung|"
        r"rechnungswesen|bilanz|audit|treasury)\b",
    ],
    "Logistics": [
        r"\b(logistik|logistics|lager\w*|warehouse|spedition|"
        r"transport|berufskraftfahrer|lkw[-\s]?fahrer|"
        r"supply\s?chain|disponier|versand|kommissionier|"
        r"fachkraft\s+für\s+lagerlogistik|einkauf|procurement)\b",
    ],
    "Handwerk": [
        r"\b(handwerk|schreiner|tischler|maler|lackierer|"
        r"elektriker|elektroinstall|installateur|klempner|"
        r"dachdecker|maurer|zimmerer|anlagenmechanik|"
        r"metallbauer|schweißer|schlosser|kfz[-\s]?mechatronik|"
        r"friseur|bäcker|konditor|fleischer|metzger|"
        r"sanitär|heizung|gebäudetechnik)\b",
    ],
    "Education": [
        r"\b(lehrer|pädagog|erzieh|bildung|dozent|"
        r"ausbilder|trainer|professor|schule|kindergarten|"
        r"kita|kinderpflege|sozialpädagog|schulung|"
        r"wissenschaftlich\w*\s+mitarbeit|forschung)\b",
    ],
    "Hospitality": [
        r"\b(hotel|gastronom|restaurant|koch|köchin|"
        r"kellner|service\w*kraft|rezeption|housekeeping|"
        r"tourismus|reise|event\s?manage|catering|"
        r"bäckereifachverkäuf|barkeeper|küche)\b",
    ],
    "Administration": [
        r"\b(verwaltung|büro\w*|sekretär|assistenz|"
        r"office\s?manage|sachbearbeit|empfang|"
        r"personalsachbearbeit|hr[-\s]?(manager|business|partner)|"
        r"human\s?resource|recruiting|payroll|"
        r"kaufm\w+\s+angestellte|bürokaufm|verwaltungsfach)\b",
    ],
    "Retail": [
        r"\b(einzelhandel|retail|verkäuf|kassierer|"
        r"filialleiter|store\s?manager|kaufmann\s+im\s+einzelhandel|"
        r"handelsfachwirt|marktleiter|warenverräum)\b",
    ],
}


def classify_job(profession: str, job_description: str) -> tuple[str, float] | None:
    """Return (category, confidence) or None if no rule matches."""
    text = f"{profession}\n{job_description}".lower()

    scores: dict[str, int] = {}
    for cat, patterns in RULES.items():
        count = 0
        for pat in patterns:
            count += len(re.findall(pat, text, re.IGNORECASE))
        if count > 0:
            scores[cat] = count

    if not scores:
        return None

    best = max(scores, key=scores.get)
    total = sum(scores.values())
    confidence = scores[best] / total if total > 0 else 0.0

    # Only label if reasonably confident
    if scores[best] >= 1:
        return best, round(min(confidence, 1.0), 3)
    return None


async def generate_training_data(output_path: Path | None = None) -> int:
    """Pull jobs from DB, auto-label, write JSONL."""
    if output_path is None:
        output_path = Path("data/ml/training.jsonl")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pool = await get_pool()
    rows = await pool.fetch("""
        SELECT profession, job_description
        FROM jobs
        WHERE job_description IS NOT NULL AND LENGTH(job_description) > 50
    """)

    labeled = 0
    stats: dict[str, int] = {}
    with output_path.open("w", encoding="utf-8") as fh:
        for row in rows:
            profession = row["profession"]
            description = row["job_description"]
            result = classify_job(profession or "", description or "")
            if result is None:
                continue
            cat, conf = result
            record = {
                "text": profession or "",
                "description": description[:3000] if description else "",
                "label": cat,
                "confidence": conf,
            }
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            labeled += 1
            stats[cat] = stats.get(cat, 0) + 1

    logger.info("Labeled %d / %d jobs", labeled, len(rows))
    for cat, count in sorted(stats.items(), key=lambda x: -x[1]):
        logger.info("  %s: %d", cat, count)

    return labeled


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    n = asyncio.run(generate_training_data())
    print(f"\nGenerated {n} training samples → data/ml/training.jsonl")
