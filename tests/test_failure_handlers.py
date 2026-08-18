import pytest
from src.schema import RateConfirmation, Location
from src.failure_handlers import parse_ambiguous_date, reconcile_rate_totals, audit_missing_and_invalid_fields


def test_parse_ambiguous_date_formats():
    # Standard YYYY-MM-DD
    dt, warn = parse_ambiguous_date("2026-07-30")
    assert dt == "2026-07-30"
    assert warn is None

    # Standard Month Abbr 28-Jul-2026
    dt, warn = parse_ambiguous_date("28-Jul-2026")
    assert dt == "2026-07-28"
    assert warn is None

    # Numeric US MM/DD/YYYY
    dt, warn = parse_ambiguous_date("07/30/2026")
    assert dt == "2026-07-30"
    assert warn is None

    # Ambiguous numeric 3/4/26 -> default to US MM/DD/YYYY (2026-03-04) with warning
    dt, warn = parse_ambiguous_date("3/4/26")
    assert dt == "2026-03-04"
    assert warn is not None
    assert "Ambiguous 2-digit year" in warn


def test_reconcile_rate_totals_missing_total():
    rc = RateConfirmation(line_haul_rate=500.0, fuel_surcharge=200.0, total_rate=None)
    rc, warnings = reconcile_rate_totals(rc)
    assert rc.total_rate == 700.0
    assert any("Inferred missing total_rate" in w for w in warnings)


def test_reconcile_rate_totals_conflict():
    rc = RateConfirmation(line_haul_rate=500.0, fuel_surcharge=200.0, total_rate=800.0)
    rc, warnings = reconcile_rate_totals(rc)
    assert rc.total_rate == 800.0
    assert any("Rate discrepancy detected" in w for w in warnings)


def test_audit_chronological_error():
    rc = RateConfirmation(
        load_id="LD101",
        origin=Location(city="Chicago", state="IL"),
        destination=Location(city="New York", state="NY"),
        pickup_date="2026-08-05",
        delivery_date="2026-08-01",  # Chronological error: delivery before pickup!
        total_rate=500.0
    )
    warnings = audit_missing_and_invalid_fields(rc)
    assert any("Chronological error" in w for w in warnings)
