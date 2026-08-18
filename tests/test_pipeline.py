import os
import pytest
from src.pipeline import ExtractionPipeline
from src.llm_provider import MockLLMProvider


@pytest.fixture
def pipeline():
    return ExtractionPipeline(provider=MockLLMProvider())


def test_pipeline_sample_1(pipeline):
    sample_path = os.path.join(os.path.dirname(__file__), "..", "samples", "rate_con_sample_1.txt")
    with open(sample_path, "r", encoding="utf-8") as f:
        text = f.read()

    rc = pipeline.process_text(text)
    clean = rc.to_clean_dict()

    assert clean["load_id"] == "LD64392"
    assert clean["origin"]["city"] == "Chicago"
    assert clean["origin"]["state"] == "IL"
    assert clean["destination"]["city"] == "New York"
    assert clean["destination"]["state"] == "NY"
    assert clean["pickup_date"] == "2026-07-30"
    assert clean["delivery_date"] == "2026-08-01"
    assert clean["equipment_type"] == "flatbed"
    assert clean["total_rate"] == 50.0
    assert clean["weight_lbs"] == 182.0
    assert clean["commodity"] == "Ceramics"
    assert clean["confidence"] == "high"


def test_pipeline_sample_2_multi_stop(pipeline):
    sample_path = os.path.join(os.path.dirname(__file__), "..", "samples", "rate_con_sample_2.txt")
    with open(sample_path, "r", encoding="utf-8") as f:
        text = f.read()

    rc = pipeline.process_text(text)
    clean = rc.to_clean_dict()

    assert clean["load_id"] == "LD64408"
    assert clean["origin"]["city"] in ["Miami", "Chicago"]
    assert clean["origin"]["state"] in ["FL", "IL"]
    assert clean["destination"]["city"] == "San Jose"
    assert clean["destination"]["state"] == "CA"
    assert clean["line_haul_rate"] == 500.0
    assert clean["fuel_surcharge"] == 200.0
    assert clean["total_rate"] == 700.0
    # Sample 2 has missing weight, so confidence should be medium
    assert clean["confidence"] in ["medium", "high"]


def test_pipeline_sample_3(pipeline):
    sample_path = os.path.join(os.path.dirname(__file__), "..", "samples", "rate_con_sample_3.txt")
    with open(sample_path, "r", encoding="utf-8") as f:
        text = f.read()

    rc = pipeline.process_text(text)
    clean = rc.to_clean_dict()

    assert clean["load_id"] == "LD64407"
    assert clean["origin"]["city"] == "Chicago"
    assert clean["origin"]["state"] == "IL"
    assert clean["destination"]["city"] == "New York"
    assert clean["destination"]["state"] == "NY"
    assert clean["pickup_date"] == "2026-07-31"
    assert clean["delivery_date"] == "2026-08-02"
    assert clean["total_rate"] == 50.0
    assert clean["weight_lbs"] == 422.0
    assert clean["confidence"] == "high"
