from typing import Literal, Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator


EquipmentType = Literal["van", "reefer", "flatbed", "other"]
ConfidenceLevel = Literal["high", "medium", "low"]


class Location(BaseModel):
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None

    @field_validator("state", mode="before")
    @classmethod
    def clean_state(cls, v: Any) -> Optional[str]:
        if not v or not isinstance(v, str):
            return None
        v_clean = v.strip().upper()
        # Extract 2-letter state code if embedded in longer string (e.g., "CA, USA" -> "CA")
        if len(v_clean) > 2:
            import re
            match = re.search(r'\b([A-Z]{2})\b', v_clean)
            if match:
                return match.group(1)
        return v_clean if len(v_clean) == 2 else v_clean[:2] if len(v_clean) > 2 else v_clean

    @field_validator("zip", mode="before")
    @classmethod
    def clean_zip(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        v_str = str(v).strip()
        if not v_str or v_str in ["-", "N/A", "null", "None"]:
            return None
        import re
        match = re.search(r'\b\d{5}(?:-\d{4})?\b', v_str)
        return match.group(0) if match else v_str


class RateConfirmation(BaseModel):
    load_id: Optional[str] = None
    origin: Location = Field(default_factory=Location)
    destination: Location = Field(default_factory=Location)
    pickup_date: Optional[str] = None  # Format YYYY-MM-DD
    delivery_date: Optional[str] = None  # Format YYYY-MM-DD
    equipment_type: Optional[EquipmentType] = None
    line_haul_rate: Optional[float] = None
    fuel_surcharge: Optional[float] = None
    total_rate: Optional[float] = None
    weight_lbs: Optional[float] = None
    commodity: Optional[str] = None
    confidence: ConfidenceLevel = "low"
    validation_warnings: List[str] = Field(default_factory=list)

    @field_validator("equipment_type", mode="before")
    @classmethod
    def normalize_equipment(cls, v: Any) -> Optional[EquipmentType]:
        if not v or not isinstance(v, str):
            return None
        v_lower = v.strip().lower()
        if "flat" in v_lower:
            return "flatbed"
        elif "reefer" in v_lower or "refrigerated" in v_lower or "temp" in v_lower:
            return "reefer"
        elif "van" in v_lower or "box" in v_lower or "dry" in v_lower:
            return "van"
        elif v_lower in ["van", "reefer", "flatbed", "other"]:
            return v_lower  # type: ignore
        return "other"

    @field_validator("line_haul_rate", "fuel_surcharge", "total_rate", "weight_lbs", mode="before")
    @classmethod
    def parse_number(cls, v: Any) -> Optional[float]:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            v_str = v.strip().replace("$", "").replace(",", "")
            if not v_str or v_str in ["-", "N/A", "null", "None", "g"]:
                return None
            try:
                return float(v_str)
            except ValueError:
                return None
        return None

    def to_clean_dict(self) -> Dict[str, Any]:
        """Returns the dictionary strictly matching the prompt's required JSON output schema."""
        return {
            "load_id": self.load_id,
            "origin": {
                "city": self.origin.city if self.origin else None,
                "state": self.origin.state if self.origin else None,
                "zip": self.origin.zip if self.origin else None,
            },
            "destination": {
                "city": self.destination.city if self.destination else None,
                "state": self.destination.state if self.destination else None,
                "zip": self.destination.zip if self.destination else None,
            },
            "pickup_date": self.pickup_date,
            "delivery_date": self.delivery_date,
            "equipment_type": self.equipment_type,
            "line_haul_rate": self.line_haul_rate,
            "fuel_surcharge": self.fuel_surcharge,
            "total_rate": self.total_rate,
            "weight_lbs": self.weight_lbs,
            "commodity": self.commodity,
            "confidence": self.confidence,
        }
