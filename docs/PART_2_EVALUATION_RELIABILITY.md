# Part 2 — Evaluation & Reliability

## 1. Building the Evaluation Set & Partial Correctness Scoring

### Eval Set Construction & Ground Truth
To build an evaluation suite that reflects production reality, we need **100–200 annotated rate confirmations** sampled across key operational dimensions:
- **Format Diversity (60%)**: Documents from 20+ distinct TMS providers and carriers (e.g., McLeod, TMW, Aljex, custom PDFs, plain text email bodies, noisy scanned PDFs with OCR artifacts).
- **Edge Cases & Failure Scenarios (30%)**: Multi-stop loads, missing fields (e.g., missing weight or zip codes), ambiguous dates (e.g., `3/4/26`), multi-currency or unusual fee structures, and intentionally conflicting rate math (e.g., line haul $500 + fuel $200 ≠ total $800).
- **Synthetic Adversarial Inputs (10%)**: Malformed PDFs, prompt injection attempts disguised as driver instructions, and incomplete draft documents.

**Ground Truth Process**: Dual human annotation by experienced freight brokers with consensus resolution. Each ground truth entry contains verified key-value JSON targets and document bounding box locations.

### Partial Correctness Scoring Framework
Relying solely on binary document-level accuracy ("Exact Match") is flawed because missing a zip code is far less critical than missing the total rate or pickup date. We calculate a **Weighted Field Score (WFS)** per document:

WFS= f∈Fields∑wf⋅S(f extracted ,f ground_truth)

Where weights reflect operational criticality:
- **Tier 1 (Weight = 0.30 each)**: `total_rate`, `origin` (city/state), `destination` (city/state), `pickup_date`. *(Failure here misroutes or misprices freight)*.
- **Tier 2 (Weight = 0.10 each)**: `load_id`, `delivery_date`, `equipment_type`. *(Important for tracking and scheduling)*.
- **Tier 3 (Weight = 0.05 each)**: `weight_lbs`, `commodity`, `line_haul_rate`, `fuel_surcharge`, `zip`. *(Secondary payload details)*.

**Field-Level Scoring Functions ($S$):**
- **Categorical & Identifiers (`load_id`, `equipment`, `state`)**: Binary exact match (1.0 or 0.0).
- **Rates (`total_rate`, `line_haul`)**: Numeric tolerance — 1.0 if within $\pm \$0.01$, 0.0 otherwise.
- **Dates (`pickup_date`, `delivery_date`)**: Exact ISO match (1.0). If off by exact timezone shift (1 day), 0.5; otherwise 0.0.
- **Text (`commodity`, `city`)**: Fuzzy normalized matching (Levenshtein similarity $\ge 0.90$ yields 1.0).

---

## 2. The Core Metric for Freight Brokers: Cost Asymmetry

In freight brokerage, errors have severe asymmetric financial costs:

$$\text{Cost}(\text{False Positive / Wrong Auto-Book}) \gg \text{Cost}(\text{False Negative / Flagged for Review})$$

- **False Positive Cost (Auto-Booking Bad Extraction)**: If the system auto-populates a rate of **$500** instead of **$5,000**, or misreads a reefer load requiring $34^\circ\text{F}$ as a flatbed, the broker risks missing dispatch, claims for spoiled cargo ($10,000–$50,000+), or severe carrier rate disputes.
- **False Negative Cost (Flagging Clean Extraction for Review)**: If the system flags a valid document for human review, the cost is strictly **~20–30 seconds of a broker's time** to click "Approve".

### Primary Metric: High-Confidence Auto-Approval Precision
The single metric that matters most is **Precision on the High-Confidence Auto-Populate Bucket**:

$$\text{High-Confidence Precision} = \frac{\text{True High-Confidence Auto-Bookings}}{\text{Total Auto-Booked Loads}}$$

**Operational SLA Target**: $\ge 99.5\%$ Precision on Auto-Approved loads, with a Target Auto-Approval Rate (Recall) of $75–80\%$. 

If the confidence engine marks a document as **HIGH**, the broker MUST be able to trust it blindly without secondary auditing.

---

## 3. Detecting Drift & Regressions in Production

Model drift occurs in two forms: **Data Drift** (shippers updating PDF layouts/templates) and **Concept/Model Drift** (LLM provider updating model weights or API behavior).

### Detection Architecture
1. **Schema & Validation Exception Spikes**: Monitor the daily percentage of documents triggering Pydantic schema validation failures or date/rate reconciliation warnings. A sudden spike ($>5\%$ deviation from baseline) signals a template change by a major shipper.
2. **Confidence Score Distribution Shift**: Track the ratio of `High` vs `Medium` vs `Low` confidence extractions in 4-hour rolling windows using a Kolmogorov-Smirnov (KS) drift test. If `High` confidence drops from $80\%$ to $50\%$, alert the engineering team.
3. **Daily Golden Canary Dataset Execution**: Run a fixed evaluation suite of 50 canonical rate confirmations every night against the live LLM API. Any drop in field-level accuracy signals an unannounced model provider update or prompt regression.
4. **Human Correction Rate Telemetry**: Log every time a broker edits a pre-filled field in the UI. If a specific field (e.g. `equipment_type` for Shipper X) is edited in $>5\%$ of reviews, automatically quarantine documents from Shipper X for prompt/few-shot re-tuning.

---

## 4. Human-In-The-Loop (HITL) UI Experience

### The "Split-Screen Verify" UI Moment
When a document is extracted with **MEDIUM** or **LOW** confidence (or when a high-value load $> \$5,000$ requires forced review), the broker is presented with a streamlined Split-Screen Interface:

```
+------------------------------------+------------------------------------+
|  PDF Document Viewer (Left 50%)    |  Extracted Form Fields (Right 50%) |
|                                    |                                    |
|  [ UltraShip Rate Confirmation ]   |  Load ID: [ LD64408          ] OK  |
|  Reference ID: LD64408             |  Origin:  [ Miami, FL        ] OK  |
|                                    |  Dest:    [ San Jose, CA     ] OK  |
|  Base Carrier Rate: $500.00        |  Pickup:  [ 2026-08-03       ] OK  |
|  Carrier Charge:    $200.00        |  Rate:    [ $700.00         ] OK  |
|  Total:             $700.00        |  Weight:  [          ] ⚠️ MISSING |
|                                    |  Confidence: MEDIUM (Weight null)  |
|  [Bbox Highlight on PDF]           |  [ Approve Load (Enter) ] [Reject] |
+------------------------------------+------------------------------------+
```

### Visual & Interactive UX Principles
1. **Side-by-Side Bounding Box Sync**: Clicking any field on the right automatically scrolls and highlights the source bounding box on the original PDF on the left.
2. **Color-Coded Confidence Indicators**:
   - **Green Check**: High confidence, verified by rate arithmetic and format checks.
   - **Yellow Warning Pill**: Field missing or auto-reconciled (e.g. "Weight missing — extracted as null").
   - **Red Alert Banner**: Math mismatch or date contradiction requiring mandatory broker correction before save.
3. **Single-Keystroke Workflow**: Brokers can navigate fields using `Tab`, accept defaults with `Enter`, or hit `Esc` to flag for supervisor review. Average review time: **< 5 seconds**.
