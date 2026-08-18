import pytest
from src.schema import RateConfirmation, Location


def test_location_state_and_zip_cleaning():
    loc = Location(city="Chicago", state="IL, USA", zip="60601-1234")
    assert loc.city == "Chicago"
    assert loc.state == "IL"
    assert loc.zip == "60601-1234"


def test_equipment_type_normalization():
    rc1 = RateConfirmation(equipment_type="Dry Van Box Truck")
    assert rc1.equipment_type == "van"

    rc2 = RateConfirmation(equipment_type="Reefer Temp Controlled")
    assert rc2.equipment_type == "reefer"

    rc3 = RateConfirmation(equipment_type="Step Deck Flatbed")
    assert rc3.equipment_type == "flatbed"

    rc4 = RateConfirmation(equipment_type="Specialized Heavy Haul")
    assert rc4.equipment_type == "other"


def test_number_coercion():
    rc = RateConfirmation(
        line_haul_rate="$1,500.50",
        fuel_surcharge="250.00",
        total_rate=1750.50,
        weight_lbs="-"
    )
    assert rc.line_haul_rate == 1500.50
    assert rc.fuel_surcharge == 250.00
    assert rc.total_rate == 1750.50
    assert rc.weight_lbs is None


def test_to_clean_dict_structure():
    rc = RateConfirmation(
        load_id="LD100",
        origin=Location(city="Chicago", state="IL", zip="60601"),
        destination=Location(city="Dallas", state="TX", zip="75201"),
        pickup_date="2026-08-01",
        delivery_date="2026-08-03",
        equipment_type="van",
        total_rate=1200.00,
        confidence="high"
    )
    d = rc.to_clean_dict()
    assert d["load_id"] == "LD100"
    assert d["origin"]["city"] == "Chicago"
    assert d["origin"]["state"] == "IL"
    assert d["destination"]["state"] == "TX"
    assert d["confidence"] == "high"
    assert "validation_warnings" not in d
