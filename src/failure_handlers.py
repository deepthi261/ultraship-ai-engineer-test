"""
Failure handlers for rate confirmation data extraction.

Handles:
1. Missing fields (flagging & graceful null fallback)
2. Conflicting totals (line haul + fuel surcharge vs total rate reconciliation)
3. Ambiguous date parsing (e.g., "3/4/26", "28-Jul-2026", "07/30/2026")
"""

import re
from datetime import datetime
from typing import Tuple, List, Optional
from src.schema import RateConfirmation


US_STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", 
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", 
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", 
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", 
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC"
}


def parse_ambiguous_date(date_str: Optional[str], reference_year: int = 2026) -> Tuple[Optional[str], Optional[str]]:
    """
    Parses ambiguous date formats into ISO standard format (YYYY-MM-DD).
    Returns (parsed_date_iso, warning_if_ambiguous).
    """
    if not date_str or not isinstance(date_str, str):
        return None, None

    date_clean = date_str.strip()
    if not date_clean or date_clean in ["-", "N/A", "null", "None"]:
        return None, None

    # Format YYYY-MM-DD
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_clean):
        try:
            dt = datetime.strptime(date_clean, "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d"), None
        except ValueError:
            return None, f"Invalid calendar date string: {date_clean}"

    # Format DD-Mon-YYYY or D-Mon-YYYY (e.g. 28-Jul-2026, 3-Aug-2026)
    match_mon = re.match(r'^(\d{1,2})[-/\s]([A-Za-z]{3})[-/\s](\d{2,4})$', date_clean)
    if match_mon:
        day, mon, yr = match_mon.groups()
        yr_full = int(yr) + 2000 if len(yr) == 2 else int(yr)
        try:
            dt = datetime.strptime(f"{day}-{mon}-{yr_full}", "%d-%b-%Y")
            return dt.strftime("%Y-%m-%d"), None
        except ValueError:
            pass

    # Format MM/DD/YYYY or DD/MM/YYYY or M/D/YY (e.g., 07/30/2026, 3/4/26)
    match_num = re.match(r'^(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})$', date_clean)
    if match_num:
        part1, part2, yr_str = match_num.groups()
        has_full_year = (len(yr_str) == 4)
        yr_full = int(yr_str) if has_full_year else int(yr_str) + 2000
        n1, n2 = int(part1), int(part2)

        # Case A: n1 > 12 -> must be DD/MM/YYYY
        if n1 > 12 and n2 <= 12:
            try:
                dt = datetime(yr_full, n2, n1)
                return dt.strftime("%Y-%m-%d"), None
            except ValueError:
                return None, f"Invalid date: {date_clean}"

        # Case B: n2 > 12 -> must be MM/DD/YYYY
        if n2 > 12 and n1 <= 12:
            try:
                dt = datetime(yr_full, n1, n2)
                return dt.strftime("%Y-%m-%d"), None
            except ValueError:
                return None, f"Invalid date: {date_clean}"

        # Case C: Both n1 <= 12 and n2 <= 12 (e.g. 3/4/26 vs 08/01/2026)
        try:
            dt = datetime(yr_full, n1, n2)
            # Only issue warning if 2-digit year (e.g. 3/4/26) where format ambiguity is high
            warning = None
            if not has_full_year:
                warning = f"Ambiguous 2-digit year date format '{date_clean}' resolved to US standard MM/DD/YYYY ({dt.strftime('%Y-%m-%d')})"
            return dt.strftime("%Y-%m-%d"), warning
        except ValueError:
            return None, f"Could not parse numeric date: {date_clean}"

    return None, f"Unrecognized date format: '{date_clean}'"


def reconcile_rate_totals(rate_con: RateConfirmation) -> Tuple[RateConfirmation, List[str]]:
    """
    Validates and reconciles rate financial math: line_haul_rate + fuel_surcharge == total_rate.
    Returns updated RateConfirmation and list of validation warning messages.
    """
    warnings: List[str] = []

    line_haul = rate_con.line_haul_rate
    fuel = rate_con.fuel_surcharge
    total = rate_con.total_rate

    # Case 1: Total missing, but line haul present
    if total is None and line_haul is not None:
        calculated = line_haul + (fuel or 0.0)
        rate_con.total_rate = round(calculated, 2)
        warnings.append(f"Inferred missing total_rate (${rate_con.total_rate:.2f}) from line_haul + fuel.")
        total = rate_con.total_rate

    # Case 2: Line haul missing, total present
    if line_haul is None and total is not None:
        if fuel is not None and fuel <= total:
            rate_con.line_haul_rate = round(total - fuel, 2)
            warnings.append(f"Inferred missing line_haul_rate (${rate_con.line_haul_rate:.2f}) from total - fuel.")
        else:
            rate_con.line_haul_rate = round(total, 2)
            if fuel is None:
                rate_con.fuel_surcharge = 0.0
        line_haul = rate_con.line_haul_rate

    # Case 3: Line haul equals total, fuel is None -> set fuel = 0.0 quietly
    if line_haul is not None and total is not None and abs(line_haul - total) < 0.01 and fuel is None:
        rate_con.fuel_surcharge = 0.0
        fuel = 0.0

    # Case 4: All rates present - check for arithmetic mismatch
    if line_haul is not None and total is not None:
        effective_fuel = fuel if fuel is not None else 0.0
        sum_rates = round(line_haul + effective_fuel, 2)
        diff = abs(sum_rates - round(total, 2))

        if diff > 0.01:
            warnings.append(
                f"Rate discrepancy detected: line_haul (${line_haul:.2f}) + fuel (${effective_fuel:.2f}) "
                f"= ${sum_rates:.2f}, but total_rate is specified as ${total:.2f} (diff: ${diff:.2f})."
            )

    return rate_con, warnings


def audit_missing_and_invalid_fields(rate_con: RateConfirmation) -> List[str]:
    """
    Audits rate confirmation fields for missing required data or invalid formats.
    """
    warnings: List[str] = []

    if not rate_con.load_id:
        warnings.append("Missing required field: load_id")

    if not rate_con.origin or not rate_con.origin.city or not rate_con.origin.state:
        warnings.append("Incomplete origin address: missing city or state")
    elif rate_con.origin.state and rate_con.origin.state not in US_STATE_CODES:
        warnings.append(f"Non-standard US origin state code: '{rate_con.origin.state}'")

    if not rate_con.destination or not rate_con.destination.city or not rate_con.destination.state:
        warnings.append("Incomplete destination address: missing city or state")
    elif rate_con.destination.state and rate_con.destination.state not in US_STATE_CODES:
        warnings.append(f"Non-standard US destination state code: '{rate_con.destination.state}'")

    if not rate_con.pickup_date:
        warnings.append("Missing pickup_date")
    if not rate_con.delivery_date:
        warnings.append("Missing delivery_date")

    # Chronology validation
    if rate_con.pickup_date and rate_con.delivery_date:
        try:
            p_dt = datetime.strptime(rate_con.pickup_date, "%Y-%m-%d")
            d_dt = datetime.strptime(rate_con.delivery_date, "%Y-%m-%d")
            if d_dt < p_dt:
                warnings.append(f"Chronological error: delivery_date ({rate_con.delivery_date}) is prior to pickup_date ({rate_con.pickup_date})")
        except ValueError:
            pass

    if rate_con.total_rate is None or rate_con.total_rate <= 0:
        warnings.append("Missing or invalid total_rate")

    if rate_con.weight_lbs is None:
        warnings.append("Missing field: weight_lbs")

    if not rate_con.commodity:
        warnings.append("Missing field: commodity")

    return warnings
