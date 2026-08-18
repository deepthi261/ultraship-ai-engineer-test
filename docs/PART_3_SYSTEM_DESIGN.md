# Part 3 — System Design: Carrier Match

## System Architecture Overview

Carrier Match automatically recommends the top 5 most reliable, cost-effective carriers for any newly posted load.

```
                    +---------------------------------------+
                    |        Newly Posted Freight Load      |
                    | (Origin, Dest, Equipment, Date, Rate) |
                    +---------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
| STAGE 1: Deterministic Hard Rules & Fraud Filtering (<10ms)                   |
| - Filter out fraud/high-risk MCs (Highway API status != "Approved")           |
| - Match Equipment Type & Geo-radius (Origin +/- 50mi, Dest +/- 75mi)           |
+-------------------------------------------------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
| STAGE 2: Machine Learning Ranking Engine (~30ms)                              |
| - Two-Tower Neural Network / LightGBM Ranker                                  |
| - Features: Lane frequency, DAT historical rates, QuickBooks payment score     |
| - Outputs top 20 candidate carriers with predicted acceptance probability      |
+-------------------------------------------------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
| STAGE 3: Async LLM Broker Context & Outreach Generator (<300ms)               |
| - Synthesizes 1-sentence broker rationale ("Why call this carrier?")          |
| - Pre-drafts personalized SMS/email dispatch outreach quote                   |
+-------------------------------------------------------------------------------+
                                        |
                                        v
                    +---------------------------------------+
                    | Top 5 Recommended Carriers in Broker UI |
                    +---------------------------------------+
```

---

## 1. Data Sources & Derived Feature Store

To accurately rank carrier fit, we extract structured signals across external integrations:

| Integration Source | Raw Signals Collected | Derived Engineered Features |
| :--- | :--- | :--- |
| **Highway** *(Carrier Identity & Safety)* | Fraud risk score, inspection records, double-brokering alerts, active insurance, certificate dates. | • `is_highway_approved` (Boolean hard filter)<br>• `fraud_risk_score` (Normalized 0–1)<br>• `safety_inspection_pass_rate` |
| **DAT / Truckstop** *(Load Boards & Market Data)* | Historical rate benchmarks, lane volume density, active carrier posting frequency, search origins. | • `lane_historical_rate_p50` (Market rate baseline)<br>• `carrier_lane_search_frequency_30d`<br>• `equipment_availability_index` |
| **QuickBooks** *(Financials & Accounting)* | Historical invoices paid, average days to pay, rate margin history, invoice disputes, claim history. | • `carrier_margin_contribution_avg`<br>• `payment_dispute_rate_90d`<br>• `total_loads_completed_with_brokerage` |
| **UltraShip TMS** *(Internal Operational Logs)* | Call logs, email responses, tender accept/reject rates, bounce rates, tracking compliance. | • `carrier_lane_conversion_rate` (Accepted / Tendered)<br>• `avg_lead_time_hours_before_pickup`<br>• `lane_rebound_affinity` (Home base match) |

---

## 2. LLMs vs. Classical ML vs. Plain Heuristics

Shipping AI responsibly to production requires strict boundaries between deterministic rules, predictive ML models, and LLM generative capabilities.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. HEURISTICS (Hard Filters)                                                │
│    Use Case: Safety, Legal Compliance, & Geographic Constraints            │
│    Why: Absolute zero-tolerance for failure. Cannot risk booking an un-     │
│    insured or fraudulent carrier.                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. CLASSICAL ML / LIGHTGBM (Scoring & Ranking Engine)                       │
│    Use Case: Scoring candidate carriers & predicting acceptance probability  │
│    Why: Microsecond latency (<30ms), deterministic pricing predictions,     │
│    interpretable feature attribution (SHAP values), cost-free scoring.      │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. LLMs (Unstructured Reasoning & Communication Synthesis)                   │
│    Use Case: Natural language broker summaries & automated outreach generation│
│    Why: Synthesizes messy email history & notes into actionable context.     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Tool Allocation Matrix

- **Plain Heuristics (Rule Engine)**:
  - **Where used**: Hard filtering out fraud MC numbers from Highway, matching equipment types (Flatbed $\rightarrow$ Flatbed), and enforcing geographic proximity (Origin within 50 miles).
  - **Why**: Zero model latency ($< 1\text{ms}$), $100\%$ deterministic compliance. An LLM should **never** decide if a carrier's insurance is valid.
- **Classical ML (LightGBM / Two-Tower Vector Search)**:
  - **Where used**: Candidate retrieval and ranking probability score calculation $P(\text{Carrier } C \text{ accepts Load } L \text{ at Rate } R)$.
  - **Why**: Runs in $< 30\text{ms}$ over 50,000 carrier profiles, costs $\$0.00$ per inference token, and provides exact feature importance (e.g., "Ranked #1 because carrier ran Chicago $\rightarrow$ NY 4x last month").
- **LLMs (Gemini 2.5 Flash / GPT-4o-mini)**:
  - **Where used**:
    1. Parsing unstructured carrier email quotes and phone call transcripts.
    2. Generating 1-sentence human-readable broker justifications: *"Dispatched this lane 3x in July at \$2.10/mi; highly reliable on weekend pickups."*
    3. Auto-drafting personalized SMS/Email outreach messages to the top 5 carriers.
  - **Why**: LLMs excel at language synthesis and unstructured communication, but are too slow, expensive, and non-deterministic for raw mathematical ranking.

---

## 3. Cold-Start Strategy for a New Brokerage

A new brokerage lacks historical transaction logs in QuickBooks or TMS tender history. We resolve cold start via a **3-Phase Data Bootstrap**:

1. **Phase 1: External Benchmark Ingestion (DAT + Highway)**:
   - Leverage Highway's national network graph to import verified carrier home bases, preferred lanes, and safety statuses.
   - Query DAT rate benchmarks to establish initial market pricing for the lane.
2. **Phase 2: Onboarding Preference Intake Wizard**:
   - When onboarding a new carrier, capture explicit lane preferences (e.g., "We run Midwest to Southeast weekly") and target rate per mile (\$2.20/mi). Store these as explicit preference vectors.
3. **Phase 3: Fallback Distance & Capacity Heuristics**:
   - Score carriers primarily by **Geographic Home Base Proximity** (is the carrier's drop-off point within 30 miles of the new load's pickup point?) and **Equipment Fit**.
   - As soon as the brokerage completes its first 50 loads, transition from distance heuristics to the LightGBM ranking model.

---

## 4. Latency, Cost, & Multi-Tier Caching Architecture

### Latency Budget (Target: Total Response < 200ms)
- **Geospatial & Safety Pre-filtering (PostGIS + Redis)**: $10\text{ms}$
- **Feature Store Retrieval (Feast / Redis)**: $15\text{ms}$
- **LightGBM Ranking Inference (C++ / ONNX Runtime)**: $15\text{ms}$
- **LLM Summary & Outreach Generation (Async Parallel Stream)**: $< 300\text{ms}$ *(Rendered progressively in UI)*

### Cost & Multi-Tier Caching Strategy
1. **Tier 1: Feature Vector Cache (Redis)**:
   - Cache carrier state vectors (home base, Highway fraud status, recent search activity) in Redis with a 1-hour TTL.
   - Avoids hitting QuickBooks or Highway APIs on every load post.
2. **Tier 2: Lane Benchmark Cache (Memcached)**:
   - Cache DAT rate benchmarks by origin/destination 3-digit zip code pair (e.g., `606-100`) updated daily.
3. **Tier 3: Asynchronous LLM Generation**:
   - The top 5 carrier recommendations display instantly ($< 50\text{ms}$) in the broker UI with ML confidence scores.
   - The LLM-generated broker summaries and draft outreach emails stream in asynchronously via WebSockets ($< 300\text{ms}$), eliminating API blocking.
