import pytest
from src.schema import RateConfirmation, Location
from src.confidence import compute_confidence


def test_high_confidence_clean_extraction():
    rc = RateConfirmation(
        load_id="LD64392",
        origin=Location(city="Chicago", state="IL", zip="60601"),
        destination=Location(city="New York", state="NY", zip="10012"),
        pickup_date="2026-07-30",
        delivery_date="2026-08-01",
        equipment_type="flatbed",
        line_haul_rate=50.0,
        fuel_surcharge=0.0,
        total_rate=50.0,
        weight_lbs=182.0,
        commodity="Ceramics"
    )
    level, warnings = compute_confidence(rc)
    assert level == "high"


def test_medium_confidence_missing_weight():
    rc = RateConfirmation(
        load_id="LD64408",
        origin=Location(city="Miami", state="FL"),
        destination=Location(city="San Jose", state="CA"),
        pickup_date="2026-07-28",
        delivery_date="2026-08-05",
        equipment_type="flatbed",
        line_haul_rate=500.0,
        fuel_surcharge=200.0,
        total_rate=700.0,
        weight_lbs=None,  # Missing weight
        commodity="Ceramics"
    )
    level, warnings = compute_confidence(rc)
    assert level == "medium"
    assert any("Missing field: weight_lbs" in w for w in warnings)


def test_low_confidence_missing_total_rate():
    rc = RateConfirmation(
        load_id="LD999",
        origin=Location(city="Chicago", state="IL"),
        destination=Location(city="Dallas", state="TX"),
        pickup_date="2026-08-01",
        delivery_date="2026-08-03",
        total_rate=None  # Missing rate!
    )
    level, warnings = compute_confidence(rc)
    assert level == "low"
    assert any("Missing or invalid total_rate" in w for w in warnings)
