"""
Document Extraction Pipeline for Freight Rate Confirmations.

Coordinates:
1. LLM extraction with structured JSON schema
2. Pydantic schema validation & coercion
3. Date ambiguity parsing and chronology validation
4. Financial rate total math reconciliation
5. Rule-based confidence scoring engine
"""

from typing import Dict, Any, Optional
from src.schema import RateConfirmation, Location
from src.failure_handlers import parse_ambiguous_date, reconcile_rate_totals
from src.confidence import compute_confidence
from src.llm_provider import get_llm_provider, BaseLLMProvider


class ExtractionPipeline:
    def __init__(self, provider: Optional[BaseLLMProvider] = None, provider_name: str = "auto"):
        self.provider = provider or get_llm_provider(provider_name)

    def process_text(self, raw_text: str) -> RateConfirmation:
        """
        Processes raw text of a rate confirmation document and produces a validated RateConfirmation model.
        """
        # Step 1: LLM Extraction
        extracted_dict = self.provider.extract_json(raw_text)

        # Step 2: Initial Pydantic Schema Parsing
        warnings = []
        
        # Extract location sub-dicts safely
        origin_dict = extracted_dict.get("origin") or {}
        dest_dict = extracted_dict.get("destination") or {}

        rate_con = RateConfirmation(
            load_id=extracted_dict.get("load_id"),
            origin=Location(**origin_dict) if isinstance(origin_dict, dict) else Location(),
            destination=Location(**dest_dict) if isinstance(dest_dict, dict) else Location(),
            pickup_date=extracted_dict.get("pickup_date"),
            delivery_date=extracted_dict.get("delivery_date"),
            equipment_type=extracted_dict.get("equipment_type"),
            line_haul_rate=extracted_dict.get("line_haul_rate"),
            fuel_surcharge=extracted_dict.get("fuel_surcharge"),
            total_rate=extracted_dict.get("total_rate"),
            weight_lbs=extracted_dict.get("weight_lbs"),
            commodity=extracted_dict.get("commodity")
        )

        # Step 3: Date Ambiguity & Format Normalization
        p_iso, p_warn = parse_ambiguous_date(rate_con.pickup_date)
        if p_iso:
            rate_con.pickup_date = p_iso
        if p_warn:
            warnings.append(p_warn)

        d_iso, d_warn = parse_ambiguous_date(rate_con.delivery_date)
        if d_iso:
            rate_con.delivery_date = d_iso
        if d_warn:
            warnings.append(d_warn)

        # Step 4: Rate Breakdown Math Reconciliation
        rate_con, math_warnings = reconcile_rate_totals(rate_con)
        warnings.extend(math_warnings)

        # Record warnings into rate_con internal audit
        rate_con.validation_warnings.extend(warnings)

        # Step 5: Rule-Based Confidence Scoring Engine
        conf_level, final_audit = compute_confidence(rate_con)
        rate_con.confidence = conf_level
        rate_con.validation_warnings = final_audit

        return rate_con

    def extract_to_json_dict(self, raw_text: str) -> Dict[str, Any]:
        """
        Executes pipeline and returns exact JSON dict structure required by assignment prompt.
        """
        rate_con = self.process_text(raw_text)
        return rate_con.to_clean_dict()
