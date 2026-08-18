"""
Confidence scoring engine for rate confirmation extraction.

Rule-based deterministic scoring matrix replacing LLM self-reported confidence.
"""

from typing import List, Tuple
from src.schema import RateConfirmation, ConfidenceLevel
from src.failure_handlers import audit_missing_and_invalid_fields


def compute_confidence(rate_con: RateConfirmation) -> Tuple[ConfidenceLevel, List[str]]:
    """
    Computes a deterministic confidence level ('high', 'medium', 'low')
    based on data completeness, mathematical consistency, spatial validation,
    and chronological sanity.

    Returns (confidence_level, list_of_audit_warnings).
    """
    warnings = list(rate_con.validation_warnings)
    field_warnings = audit_missing_and_invalid_fields(rate_con)
    all_warnings = warnings + field_warnings

    # Identify critical structural failures
    critical_failures = [
        w for w in all_warnings
        if "Missing required field: load_id" in w
        or "Incomplete origin" in w
        or "Incomplete destination" in w
        or "Missing or invalid total_rate" in w
        or "Chronological error" in w
        or "Rate discrepancy detected" in w
    ]

    # Rule 1: LOW Confidence
    # Triggered by any critical failure, chronological error, missing core address/rate, or major rate math conflict
    if critical_failures:
        return "low", all_warnings

    # Rule 2: MEDIUM Confidence
    # All core fields present, but missing secondary metadata (weight, commodity, zip)
    # or warnings like date ambiguity / rate rounding adjustments exist
    secondary_missing = [
        w for w in all_warnings
        if "Missing field: weight_lbs" in w
        or "Missing field: commodity" in w
        or "Ambiguous date format" in w
        or "Inferred missing" in w
    ]

    if secondary_missing or len(all_warnings) > 1:
        return "medium", all_warnings

    # Rule 3: HIGH Confidence
    # Complete, mathematically sound, chronologically verified extraction suitable for automated TMS booking
    return "high", all_warnings
