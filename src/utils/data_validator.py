"""
Data validation utilities for scraped job data.

Wraps the validation logic in models.job_model.JobModel so that other
modules can import a single entry-point without reaching into the model
layer directly.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from models.job_model import (
    JobModel,
    JobModelValidator,
    ValidationLevel,
    ValidationResult,
)

logger = logging.getLogger(__name__)

# Pre-compiled patterns for fast field-level checks
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
_PHONE_RE = re.compile(r"[\d\s\-/+()]{7,20}")
_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


class DataValidator:
    """Stateful validator that collects stats across multiple calls."""

    def __init__(self, level: str = "moderate"):
        lvl_map = {
            "strict": ValidationLevel.STRICT,
            "moderate": ValidationLevel.MODERATE,
            "lenient": ValidationLevel.LENIENT,
        }
        self._level = lvl_map.get(level, ValidationLevel.MODERATE)
        self._inner = JobModelValidator(self._level)

    # ── single-record helpers ───────────────────────────────────

    def validate_job(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate a single scraped-job dict."""
        model = JobModel(**{k: v for k, v in data.items() if hasattr(JobModel, k)})
        return model.validate(self._level)

    def validate_and_clean(self, data: Dict[str, Any]) -> Tuple[Dict[str, Any], ValidationResult]:
        """Validate + apply lightweight cleaning, return cleaned dict + result."""
        cleaned = dict(data)

        # trim whitespace on all string values
        for k, v in cleaned.items():
            if isinstance(v, str):
                cleaned[k] = v.strip()

        # normalise empty → None
        for k in ("email", "telephone", "salary", "start_date"):
            if k in cleaned and not cleaned[k]:
                cleaned[k] = None

        # basic email format guard
        email = cleaned.get("email")
        if email and not _EMAIL_RE.match(email):
            cleaned["email"] = None

        result = self.validate_job(cleaned)
        return cleaned, result

    # ── batch helpers ───────────────────────────────────────────

    def validate_batch(
        self, records: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
        """
        Validate a list of scraped-job dicts.

        Returns (valid_records, invalid_records, stats).
        """
        valid, invalid = [], []
        for rec in records:
            cleaned, result = self.validate_and_clean(rec)
            if result.is_valid:
                valid.append(cleaned)
            else:
                invalid.append({**cleaned, "_errors": result.errors})

        stats = self._inner.get_validation_report()
        stats["batch_valid"] = len(valid)
        stats["batch_invalid"] = len(invalid)
        return valid, invalid, stats

    # ── field-level utilities ───────────────────────────────────

    @staticmethod
    def is_valid_email(email: Optional[str]) -> bool:
        return bool(email and _EMAIL_RE.match(email))

    @staticmethod
    def is_valid_phone(phone: Optional[str]) -> bool:
        return bool(phone and _PHONE_RE.search(phone))

    @staticmethod
    def is_valid_url(url: Optional[str]) -> bool:
        return bool(url and _URL_RE.match(url))
