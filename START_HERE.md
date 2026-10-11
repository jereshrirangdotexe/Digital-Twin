# VoltMind final integration — 11 October 2026

For current public-source setup, demo replay and licensing, see [README.md](README.md). This document records the original integration scope; the separate labelled thermal demo adds one 4,032-row replay without changing the original 60 stories.

This release selects your supplied **100 kVA V4 hardened Logistic Regression bundle** and final V4 SCADA. The 250/630 kVA models and datasets are unchanged. Earlier documents describe historical releases; this file and `docs/FINAL_INTELLIGENCE.md` take precedence for this integration.

## Start on Windows

1. Extract the complete integrated ZIP to a short writable path, such as `C:\Projects\VoltMind`. Keep all folders together. The installer checks that the project root is at most 90 characters to avoid Windows dependency path limits.
2. Install Python **3.13 64-bit**, Java **JDK 17+**, and Node.js **22+**, available on PATH.
3. Run `install_voltmind.bat` once. Its five numbered stages must finish with **Installation complete**. First installation needs internet. Failure keeps its error visible; read it before closing the window.
4. Run `start_voltmind.bat`. It starts Python, Spring Boot and React, waits for health checks, and opens **http://localhost:5173/**. `http://127.0.0.1:5173/` also works. The page opens idle.
5. Choose a rating/replay and **Run on local data**, or **Add a dataset**. Use Pause, Resume, Restart, Stop and speed controls. Run `stop_voltmind.bat` to stop launcher-owned processes.

If running manually, keep all three services open: `.venv\Scripts\python.exe ml\main.py --serve` from the root; `mvnw.cmd spring-boot:run` in backend (or Run in IntelliJ); `npm run dev` in frontend. Restart Python and Spring Boot after applying this release. Do not start duplicate servers on occupied ports.

## What is included

- 100 kVA: 60 independent synthetic stories, 4,032 five-minute rows each (241,920 total). IDs are opaque story identifiers, not times or verified physical assets. The final trained weights, thresholds and feature equations are unchanged.
- 250 kVA: original 24 × 6,048 rows; 630 kVA: original 24 × 8,064 rows. Their models/calibration/datasets remain untouched.
- Health/risk publish after every 24 processed rows (two historical hours), remain fixed between blocks and average assessable observations only. Final short blocks are marked. Alerts remain immediate. These are observation indices, not failure probabilities or remaining life.
- Intelligence Lab: separate what-if thermal projections and sensor/transformer investigation.
- Fault Investigation: source-specific persistent incident memory, maintenance entries, recurrence intervals and matched before/after evidence.
- Thermal DNA: measured load-response episodes; no healthy baseline is invented. Explicit independently verified healthy history is required to lock a reference.
- Upper-right VoltMind Insights: eight deterministic summaries over **all processed session rows**, incident evidence and JSON / printable HTML downloads. Open the HTML and choose Print / Save as PDF.
- Live Twin: white oil plot (actual black, expected orange), explanatory tooltips and independent voltage/current waveform groups. Cycles illustrate RMS magnitudes using assumed 50 Hz sinusoidal waves and 120° spacing; phase angles, harmonics and power factor are unmeasured.

## Uploaded data

100 kVA supports CSV/TSV/TXT/XLSX/JSON/JSONL/NDJSON, up to 100 MiB per request and 300,000 rows. Explicit asset identity and timestamps are required. Unknown columns are ignored; missing sensors remain missing and affected detectors abstain. Supported units are converted explicitly. Unlabeled unfamiliar units require configuration. Ambiguous names/timestamps reject rather than guess. The organiser workbook is a checklist, not timestamped SCADA, and must not be uploaded as monitoring history.

Provide matching independently verified asset calibration JSON, or a separate healthy commissioning CSV with verification attestation. Uploaded monitoring is never assumed healthy or used to fit calibration automatically. Without valid calibration, thermal assessment abstains; optional detectors can assess their available sensors with their separate experimental limitations. Five-minute cadence is required. Gaps reset temporal history; no interpolation or synthetic rows are inserted. Optional oil-level/terminal sensors are never fabricated.

## Data and limitations

Local data, commissioning and model validation are **synthetic**. `VERIFIED_COMMISSIONED` means the calibration contract passed; local provenance remains synthetic, not field-certified. Thermal, oil depletion and LV R-terminal surface heating are distinct detectors. Tank pressure, mechanical damage, internal bushing faults, short circuits, measured impedance and measured hotspot/RUL have no trained detector and are unassessed. A surface-terminal alert is not an internal bushing diagnosis. Oil depletion can resemble gauge bias.

Processed 100 kVA observations, incidents, simulations and maintenance are stored locally in `.state/intelligence.sqlite`. Upload file removal or worker restart removes temporary upload files but **does not delete this evidence memory**. Packages omit all user databases and logs. No cloud telemetry or chatbot API is configured. See `reports/FINAL_INTEGRATION_VALIDATION.md` for actual test outcomes and remaining limits.

## Troubleshooting

Ports 5173/8080/8765 must be free. Use the matching stop script for a launcher instance or stop manually started services in their terminal/IntelliJ. Logs are in `.state/logs`. Installation creates its own `.venv`, node_modules and backend target; those generated dependencies are intentionally excluded from ZIPs. `test_voltmind.bat` runs unit/build checks; HTTP workflows are documented separately and create test monitoring sessions.

Latest dashboard changes and review evidence: [UI review](docs/UI_REVIEW_20261011.md). The floating VoltMind Assistant is at the bottom right.
