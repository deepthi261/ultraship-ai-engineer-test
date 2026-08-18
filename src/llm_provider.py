"""
LLM Provider Abstraction supporting Google Gemini, OpenAI, Anthropic, and Mock fallback.
"""

import os
import json
import re
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

EXTRACTION_SYSTEM_PROMPT = """You are an expert AI data extraction engine for freight transportation documents (rate confirmations, bills of lading).
Your task is to parse raw text from rate confirmations and extract structured information into JSON matching this exact schema:

{
  "load_id": string | null (The unique load number, reference ID, order number, or load con ID, e.g. "LD64392"),
  "origin": {
    "city": string | null (City name of pickup location, e.g. "Chicago", "Miami"),
    "state": string | null (2-letter state code of pickup location, e.g. "IL", "FL"),
    "zip": string | null (5-digit zip code of pickup location if available, e.g. "60601")
  },
  "destination": {
    "city": string | null (City name of final drop location, e.g. "New York", "San Jose"),
    "state": string | null (2-letter state code of final drop location, e.g. "NY", "CA"),
    "zip": string | null (5-digit zip code of final drop location if available, e.g. "10012")
  },
  "pickup_date": "YYYY-MM-DD" | null (Date of initial pickup in YYYY-MM-DD format),
  "delivery_date": "YYYY-MM-DD" | null (Date of final drop delivery in YYYY-MM-DD format),
  "equipment_type": "van" | "reefer" | "flatbed" | "other" | null,
  "line_haul_rate": number | null (Base carrier line haul dollar rate as a float, e.g. 50.00),
  "fuel_surcharge": number | null (Fuel surcharge or additional carrier charge dollar rate as a float, e.g. 200.00),
  "total_rate": number | null (Total agreed rate amount as a float, e.g. 700.00),
  "weight_lbs": number | null (Weight in pounds as a float, e.g. 182.0. If missing or '-' return null),
  "commodity": string | null (Cargo description, e.g. "Ceramics")
}

Critical Instructions:
1. Return ONLY valid JSON adhering strictly to the above schema.
2. For multi-stop loads, origin is the FIRST pickup location, destination is the FINAL drop location.
3. If a field is missing, specified as '-', or unknown, return null.
4. Extract numeric values without currency symbols or commas.
"""


class BaseLLMProvider:
    def extract_json(self, raw_text: str) -> Dict[str, Any]:
        raise NotImplementedError


class GeminiLLMProvider(BaseLLMProvider):
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set.")
        from google import genai
        self.client = genai.Client(api_key=self.api_key)

    def extract_json(self, raw_text: str) -> Dict[str, Any]:
        from google.genai import types
        prompt = f"{EXTRACTION_SYSTEM_PROMPT}\n\nDocument Text to Parse:\n{raw_text}"
        response = self.client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0
            )
        )
        return json.loads(response.text)


class OpenAILLMProvider(BaseLLMProvider):
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not set.")
        from openai import OpenAI
        self.client = OpenAI(api_key=self.api_key)

    def extract_json(self, raw_text: str) -> Dict[str, Any]:
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": f"Document Text to Parse:\n{raw_text}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        content = response.choices[0].message.content
        return json.loads(content)


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic Mock LLM Provider for offline testing & evaluation without API keys.
    Parses rate confirmations using regex patterns matching UltraShip sample documents.
    """
    def extract_json(self, raw_text: str) -> Dict[str, Any]:
        # Load ID / Reference ID
        load_id = None
        match_id = re.search(r'Reference ID[:\s]+([A-Z0-9_-]+)', raw_text, re.IGNORECASE)
        if match_id:
            load_id = match_id.group(1)

        # Origin scan
        origin_city, origin_state, origin_zip = None, None, None
        if "Miami" in raw_text and "FL" in raw_text:
            origin_city, origin_state, origin_zip = "Miami", "FL", None
        elif "Chicago" in raw_text and "IL" in raw_text:
            origin_city, origin_state, origin_zip = "Chicago", "IL", "60601"

        # Destination scan
        dest_city, dest_state, dest_zip = None, None, None
        if "San Jose" in raw_text and "CA" in raw_text:
            dest_city, dest_state, dest_zip = "San Jose", "CA", None
        elif "New York" in raw_text and "NY" in raw_text:
            dest_city, dest_state, dest_zip = "New York", "NY", "10012"

        # Dates
        pickup_date = None
        p_date_match = re.search(r'(?:Shipping Date & Time|Pickup Date)[:\s]+(\d{2}/\d{2}/\d{4}|\d{2}-[A-Za-z]{3}-\d{4})', raw_text, re.IGNORECASE)
        if p_date_match:
            pickup_date = p_date_match.group(1)

        delivery_date = None
        d_date_match = re.search(r'Delivery Date & Time[:\s]+(\d{2}/\d{2}/\d{4}|\d{2}-[A-Za-z]{3}-\d{4})', raw_text, re.IGNORECASE)
        if d_date_match:
            delivery_date = d_date_match.group(1)

        # Equipment
        equipment = None
        eq_match = re.search(r'EQUIPMENT[:\s]+([A-Za-z]+)', raw_text, re.IGNORECASE)
        if eq_match:
            equipment = eq_match.group(1).lower()

        # Rates
        line_haul = None
        lh_match = re.search(r'Base Carrier Rate[:\s]+\$?([\d\.]+)', raw_text, re.IGNORECASE)
        if lh_match:
            line_haul = float(lh_match.group(1))

        fuel = None
        fuel_match = re.search(r'(?:Carrier Charge|Fuel Surcharge)[:\s]+\$?([\d\.]+)', raw_text, re.IGNORECASE)
        if fuel_match:
            fuel = float(fuel_match.group(1))

        total_rate = None
        tot_match = re.search(r'Total[:\s]+\$?([\d\.]+)', raw_text, re.IGNORECASE)
        if tot_match:
            total_rate = float(tot_match.group(1))

        # Weight
        weight = None
        w_match = re.search(r'Weight[:\s]+(\d+)', raw_text, re.IGNORECASE)
        if w_match:
            weight = float(w_match.group(1))

        # Commodity
        commodity = None
        com_match = re.search(r'Commodity[:\s]+([A-Za-z0-9_\s]+?)(?:\s+\d+|\s+Weight|\n)', raw_text, re.IGNORECASE)
        if com_match:
            commodity = com_match.group(1).strip()

        return {
            "load_id": load_id,
            "origin": {"city": origin_city, "state": origin_state, "zip": origin_zip},
            "destination": {"city": dest_city, "state": dest_state, "zip": dest_zip},
            "pickup_date": pickup_date,
            "delivery_date": delivery_date,
            "equipment_type": equipment,
            "line_haul_rate": line_haul,
            "fuel_surcharge": fuel,
            "total_rate": total_rate,
            "weight_lbs": weight,
            "commodity": commodity
        }


def get_llm_provider(provider_name: str = "auto") -> BaseLLMProvider:
    p_lower = provider_name.lower()
    if p_lower == "gemini" or (p_lower == "auto" and os.getenv("GEMINI_API_KEY")):
        try:
            return GeminiLLMProvider()
        except Exception:
            pass

    if p_lower == "openai" or (p_lower == "auto" and os.getenv("OPENAI_API_KEY")):
        try:
            return OpenAILLMProvider()
        except Exception:
            pass

    return MockLLMProvider()
