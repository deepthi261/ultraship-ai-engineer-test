# UltraShip AI Engineer Skill Test

Production-grade implementation for the **UltraShip AI Engineer Skill Test**, featuring an LLM document extraction pipeline with strict schema enforcement, deterministic rule-based confidence scoring, explicit failure case handlers, an automated test suite, and written engineering design documents for evaluation strategy and Carrier Match system design.

---

## Deliverables Summary

1. **Part 1 — Document Extraction Pipeline**: Python pipeline (`src/pipeline.py`, `cli.py`, `tests/`) using Pydantic v2 schema enforcement, retry logic, date parsing, rate math reconciliation, and rule-based confidence scoring.
2. **Part 2 — Evaluation & Reliability Writeup**: Located in [`docs/PART_2_EVALUATION_RELIABILITY.md`](docs/PART_2_EVALUATION_RELIABILITY.md).
3. **Part 3 — System Design: Carrier Match**: Located in [`docs/PART_3_SYSTEM_DESIGN.md`](docs/PART_3_SYSTEM_DESIGN.md).

---

## Quickstart & Execution

### 1. Environment Setup
```bash
# Create Python 3.12 virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure API Keys (Optional)
The pipeline supports **Google Gemini**, **OpenAI**, or a zero-dependency **Mock Provider** for offline testing.

Create a `.env` file or export your API key:
```bash
# For Google Gemini
export GEMINI_API_KEY="your-gemini-api-key"

# For OpenAI
export OPENAI_API_KEY="your-openai-api-key"
```
*Note: If no API key is provided, the system automatically uses the offline `MockLLMProvider`.*

### 3. Run Document Extraction CLI
```bash
# Process all sample rate confirmations
python cli.py --all

# Process a single sample rate confirmation (1, 2, or 3)
python cli.py --sample 1

# Process a custom text document
python cli.py --file /path/to/rate_confirmation.txt --provider gemini
```

### 4. Run Automated Test Suite
```bash
pytest -v
```

---

## Part 1 — Document Extraction Architecture

```
Raw Document Text (PDF / Email / Scan)
                 │
                 ▼
 ┌───────────────────────────────┐
 │ 1. Structured LLM Provider    │ (Gemini 2.5 Flash / GPT-4o-mini / Mock)
 └───────────────┬───────────────┘
                 │ Raw JSON
                 ▼
 ┌───────────────────────────────┐
 │ 2. Pydantic v2 Validation     │ (Schema parsing, type coercion, state/zip cleaning)
 └───────────────┬───────────────┘
                 │ Rate Confirmation Model
                 ▼
 ┌───────────────────────────────┐
 │ 3. Failure Handlers           │ (Ambiguous date parsing, rate math reconciliation)
 └───────────────┬───────────────┘
                 │ Validated Model + Audit Warnings
                 ▼
 ┌───────────────────────────────┐
 │ 4. Rule-Based Confidence      │ (Deterministic scoring matrix: High / Medium / Low)
 └───────────────┬───────────────┘
                 │
                 ▼
     Clean JSON Output Payload
```

### Rule-Based Confidence Scoring Logic
Confidence is **never based on LLM self-reported "vibes"**. Instead, it is computed via a deterministic audit matrix (`src/confidence.py`):

- **`HIGH` Confidence**:
  - All critical fields present (`load_id`, `origin.city/state`, `destination.city/state`, `pickup_date`, `delivery_date`, `total_rate`).
  - Rate math strictly checks out (`line_haul + fuel_surcharge == total_rate` within $\pm \$0.01$).
  - Chronology verified (`pickup_date <= delivery_date`).
  - Valid US state codes (2-letter postal abbreviations).
  - *Suitable for automated TMS booking without manual review.*
- **`MEDIUM` Confidence**:
  - All core fields present, but minor secondary metadata is missing (e.g. `weight_lbs` missing or `zip` missing).
  - Ambiguous date format resolved via 2-digit year fallback (e.g. `3/4/26`).
  - Minor rate reconciliation applied (e.g., inferring missing `line_haul` from `total - fuel`).
  - *Flagged for quick 5-second broker verification.*
- **`LOW` Confidence**:
  - Core critical fields missing (`origin`, `destination`, or `total_rate` null).
  - Unreconcilable rate contradiction (`line_haul + fuel != total` with diff $> \$0.01$).
  - Chronological error (`delivery_date < pickup_date`).
  - *Quarantined for mandatory manual broker review.*

---

## Failure Case Handling Strategy

The pipeline explicitly handles failure cases via dedicated modules (`src/failure_handlers.py`):

1. **Missing Fields**: Fields like missing `weight_lbs`, `fuel_surcharge`, or `zip` are safely coerced to `null` without throwing exceptions or crashing the pipeline. Audit flags are recorded in `validation_warnings`.
2. **Conflicting Totals (`line_haul + fuel != total`)**:
   - If `total_rate` is missing but `line_haul` and `fuel` are present, the pipeline infers `total_rate`.
   - If `line_haul` is missing, it infers `line_haul = total - fuel`.
   - If all 3 rates are explicitly provided and conflict (e.g. $500 + $200 = $700 vs total $800), the pipeline flags a rate discrepancy warning and sets confidence to **`LOW`**.
3. **Ambiguous Dates (`3/4/26`, `28-Jul-2026`, `07/30/2026`)**:
   - Dates are normalized to ISO standard `YYYY-MM-DD`.
   - Formats like `28-Jul-2026` or `07/30/2026` (where 30 > 12) parse unambiguously.
   - 2-digit year numeric dates like `3/4/26` are resolved using US freight standards (MM/DD/YYYY $\rightarrow$ `2026-03-04`), generate an audit warning, and adjust confidence accordingly.

---

## Directory Structure

```
ultraship_skill_test/
├── README.md                            # Main project overview & quickstart
├── requirements.txt                     # Dependencies (pydantic, pytest, google-genai, etc.)
├── cli.py                               # Command-line runner
├── docs/
│   ├── PART_2_EVALUATION_RELIABILITY.md # Part 2: Eval metrics, cost asymmetry, drift, HITL UI
│   └── PART_3_SYSTEM_DESIGN.md         # Part 3: Carrier Match multi-stage architecture
├── samples/
│   ├── rate_con_sample_1.txt            # Sample 1: Single stop load LD64392
│   ├── rate_con_sample_2.txt            # Sample 2: Multi-stop load LD64408 (missing weight)
│   └── rate_con_sample_3.txt            # Sample 3: Single stop load LD64407
├── src/
│   ├── __init__.py
│   ├── schema.py                        # Pydantic v2 data models
│   ├── confidence.py                    # Deterministic confidence engine
│   ├── failure_handlers.py              # Math reconciliation & ambiguous date parsing
│   ├── llm_provider.py                  # LLM providers (Gemini, OpenAI, Mock)
│   └── pipeline.py                      # Main extraction pipeline orchestrator
└── tests/
    ├── test_schema.py                   # Schema & normalization tests
    ├── test_confidence.py               # Confidence level calculation tests
    ├── test_failure_handlers.py         # Date ambiguity & math reconciliation tests
    └── test_pipeline.py                 # End-to-end extraction pipeline tests
```
