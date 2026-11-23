# CDR/IPDR Intelligence Platform
**AI-Assisted Communication & Network Analysis Platform**
*Hackathon Prototype - Version 1.0 (with Excel & CSV Support)*

A lightweight, self-contained web application built with Streamlit, Pandas, NetworkX, and Plotly to standardise, inspect, correlate, and analyse Call Detail Records (CDR) and Internet Protocol Detail Records (IPDR).

---

## 🚀 Features

- **Multi-Format Ingestion**: Full support for uploading both **CSV (`.csv`)** and **Excel (`.xlsx`, `.xls`)** files, including multi-worksheet workbook selection.
- **Automated Data Standardisation**: Maps diverse provider column aliases (`A Party`, `B Party`, `start_time`, `bytes_up`, `site_id`, etc.) into a canonical schema.
- **Data Validation & Quality Flagging**: Automatically validates timestamps, phone identifiers, durations, byte counts, and assigns `VALID` or `REVIEW` status.
- **Interactive Overview Dashboard**: High-level KPIs, daily call distribution, protocol volume analysis, and quality health scores.
- **Deep Pattern Analysis**: Hourly communication heatmaps, caller activity rankings, counterparty diversity, and statistical daily anomaly detection (mean + 2σ baseline).
- **Network Relationship Graph**: Interactive node-edge visualization with NetworkX spring layout and Plotly, showing call relationships, degree centrality, and interaction frequency filters.
- **Chronological Activity Timeline**: Per-identifier call timelines (role, counterparty, duration, tower ID) and per-subscriber IPDR data session tables.
- **Deterministic AI Assistant**: Natural language query router executing reproducible local Pandas queries without transmitting data to external services.
- **Evidence & Multi-Format Export**: Standardised CSV & Excel (`.xlsx`) data exports, JSON summary audit reports, and dataset provenance details.

---

## 📁 Project Structure

```text
cdr_ipdr_hackathon/
├── app.py                  # Main Streamlit web application & UI views
├── engine.py               # Core data standardisation, validation, graph, & assistant logic
├── requirements.txt        # Python package dependencies
├── README.md               # Quick-start instructions & documentation
├── data/
│   ├── sample_cdr.csv      # 220 synthetic CDR events (Nov 2026, 8 identifiers)
│   ├── sample_ipdr.csv     # 100 synthetic IPDR sessions (Nov 2026, 5 subscribers)
│   ├── test_cdr.xlsx       # Sample multi-sheet Excel CDR test file
│   └── test_ipdr.xlsx      # Sample Excel IPDR test file
├── scripts/
│   └── generate_samples.py # Script generating synthetic demo datasets
└── tests/
    └── test_acceptance.py  # 12 automated acceptance tests (T01–T12)
```

---

## 🛠️ Quick Start & Installation

### 1. Prerequisites
- Python 3.10 or newer (tested on Python 3.11, 3.12, 3.14)
- Web browser (Chrome, Edge, Firefox, Safari)

### 2. Setup Virtual Environment (Recommended)

**On Windows:**
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**On macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Run the Application

```bash
streamlit run app.py
```

The application will start and automatically open in your default browser at:
`http://localhost:8501`

---

## 🧪 Testing Acceptance Criteria

- **T01 - Bundled sample files**: Loads default synthetic CDR and IPDR datasets.
- **T02 - Upload valid CDR CSV**: Recognises aliases and standardises data.
- **T03 - Upload valid IPDR CSV**: Recognises IPDR headers and cleans byte counts.
- **T04 - Missing required fields**: Alerts the user when critical columns cannot be resolved.
- **T05 - Invalid timestamp rows**: Correctly flags malformed rows with `REVIEW` instead of dropping data.
- **T06 - Relationship Graph**: Renders network connections with interaction thresholds.
- **T07 - Activity Timeline**: Sorts chronological events by identifier with counterparty identification.
- **T08 - AI Assistant**: Answers queries like `"Show top callers"`, `"Show timeline for 9000000001"`, and `"Find common contacts between 9000000001 and 9000000002"`.
- **T09 & T10 - Exports**: Downloads standardised CSVs and complete audit JSON summary.
- **T11 - Excel CDR Upload (.xlsx)**: Reads Excel workbooks, handles sheet selection, and normalises Excel float formats.
- **T12 - Excel IPDR Upload & Export (.xlsx)**: Reads Excel IPDR sessions and generates binary `.xlsx` export files.

To run the test suite:
```bash
python tests/test_acceptance.py
```

---

## 🔒 Scope & Responsible-Use Notice

This application is an educational proof-of-concept developed for hackathon demonstration. It processes metadata only and does **not** intercept communications, track live devices, inspect message/call content, or infer subscriber identities. Bundled datasets are 100% fictional and synthetic.
