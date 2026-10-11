# Final VoltMind integration validation — 11 October 2026

The supplied final 100 kVA V4 hardened Logistic Regression bundle and V4 SCADA are now selected by the existing React / Spring Boot / Python application. No model training, feature equation changes, threshold tuning or tournament rerun occurred. The 250/630 kVA models and datasets remain unchanged.

## Executed checks

| Check | Result | Evidence |
|---|---|---|
| Frozen model score and alert equivalence | PASS | All 241,920 rows / 60 replays, three score heads and three alert heads exactly equal to saved pre-integration outputs; zero tolerance, matching missingness |
| Original protected artifacts | PASS | 64 original model/config/data files match pre-edit SHA-256 |
| Supplied final bundle preserved | PASS | 122 copied bundle files byte-identical to supplied model ZIP entries |
| Supplied final dataset preserved | PASS | 23 deployed SCADA/commissioning/metadata files byte-identical to supplied dataset ZIP entries |
| Python suite, clean extracted environment | PASS | 79 tests, zero failures; FINAL_CLEAN_PYTHON_TESTS.xml |
| Final post-review adversarial and block checks | PASS | 20 tests after the last Thermal DNA/reference-period safeguards |
| Frontend unit checks | PASS | 9 tests, including RMS reconstruction, phase sum, period, missing sensors, report escaping and publication rules |
| Production frontend build | PASS | Clean install build and final frontend build; Vite reports a large-bundle warning (~636 kB JS), not an error |
| Spring Boot tests/package | PASS | 5 tests, zero failures; freshly compiled runnable JAR |
| Real HTTP through Spring Boot | PASS | Full 4,032-row replay, pause/resume, independent scenarios, eight summaries, evidence, downloads, maintenance persistence, 250/630 runtime activation |
| Browser waveform controls | PASS | All eight combinations for voltage and all eight for current |
| Browser summaries and downloads | PASS | All eight categories, JSON and printable HTML downloads, evidence dialog and Escape dismissal |
| Browser upload | PASS | Extra column ignored; missing oil sensor plus missing calibration produced unassessed health/risk, no invented oil readings; no browser console errors observed |
| Initial idle state | PASS | Original and clean installation opened without active replay |
| Clean Windows install | PASS | Fresh environment, dependency installation, npm ci/build and Maven tests/package from extracted ZIP in a short writable folder |
| Launcher stop/restart | PASS | Only owned processes stopped; restart produced new worker identity, no active replay, and retained maintenance records |
| Field validation / unseen judges' accuracy | UNVERIFIED | No real timestamped organiser SCADA or field measurements supplied; workbook is a reference checklist |
| Physical diagnosis, RUL, real sensor connection | UNIMPLEMENTED | Unsupported by supplied model/sensors; never fabricated |
| Actual system-printer PDF output | UNVERIFIED | Escaped printable HTML and browser download tested; user can Print / Save as PDF |

## Connected behavior

The independent maintenance simulator holds measured ambient/current ratios constant and projects two thermal states without altering monitoring or classifier output. Sensor investigation presents competing explanations, not certain diagnoses. Evidence includes onset measurements, score/threshold, quality, calibration provenance, model hash and verification steps. Stored incidents are deduplicated across replay restarts for the same asset and exact source fingerprint. Maintenance is an explicit engineer entry; matched post-repair evidence does not prove causality.

Thermal DNA searches clean natural load changes and excludes ambient variation, missing intervals and suspect sensors. It does not invent a healthy baseline. A reference requires independent healthy attestation and at least three episodes; only subsequent episodes can be compared, so a reference cannot certify itself. Descriptive drift thresholds are documented engineering screens, not trained damage estimates.

Health/risk still publish once per 24 processed rows (two historical hours). Live alarms remain immediate. Experimental oil and LV terminal alarms now trigger explicit alert conditions and inspection guidance. Their detections remain separate from the thermal/electrical numeric health score. The oil chart is white with black actual and orange expected lines. Illustrative 50 Hz waveforms use RMS × sqrt(2), assumed 120-degree separation and explicit nominal references; they do not reconstruct measured harmonics, phase angles or power factor.

## Data and model limits

Local 100 kVA SCADA and commissioning are synthetic. `VERIFIED_COMMISSIONED` checks calibration eligibility; it is not field certification. Inputs with unknown columns can be accepted, but missing necessary measurements/calibration force affected detectors to abstain. Explicit mappings/units and native five-minute timing remain necessary; this is not a promise to infer correctly from every arbitrary dataset.

The supplied fresh post-lock synthetic report records thermal detection of 22/23 events, ~0.127 false episodes per negative day and ~93.1% coverage. Oil recall including unavailable observations is ~55.2% with ~55.1% coverage; assessable-row recall is ~95.7%. These are **upstream supplied synthetic evaluation results**, not newly measured field accuracy or a new training result. See ml/final100/reports/FRESH_POST_LOCK_TEST.json.

Oil depletion and R-phase LV terminal surface heating are separate experimental detectors. Gauge bias can resemble depletion; surface heating does not diagnose internal bushing failure. Tank pressure, mechanical damage, internal short circuits, measured impedance, measured winding hotspot, insulation aging and RUL remain unassessed. The organiser checklist's illustrative 50 A current must not replace the rating-based ~133.34 A at 100 kVA/433 V.

Recurrence and reference memory are scoped to the exact source file and asset. Different files are not automatically stitched into a physical asset's life history. No maintenance records are fabricated on normal startup. Acceptance-test records exist only in an excluded test database. All delivery archives exclude user databases, virtual environments, node_modules, build caches, secrets and runtime logs.

## Installation issue found and fixed

The first clean test failed when sklearn dependency filenames exceeded Windows limits inside a deeply nested folder. The archive now uses the short inner folder `VoltMind`; installer checks the project root is at most 90 characters and explains how to fix a longer path before installing. A subsequent fresh short-path installation completed successfully. First installation needs internet and Python 3.13, JDK 17+ and Node 22+ on PATH.

## Reproduce

Run install_voltmind.bat, then test_voltmind.bat for Python/frontend/backend checks. The legacy robustness script checks the preserved old runtime separately and must not be read as field validation of V4. Start the complete app with start_voltmind.bat. For an isolated second instance, use `.venv\Scripts\python.exe scripts\launcher.py start --no-browser --ml-port 8787 --backend-port 8087 --frontend-port 5177`, then run `.venv\Scripts\python.exe tests\final_http_workflow.py --base http://127.0.0.1:8087`. The HTTP workflow explicitly creates test maintenance records; use a clean test extraction.

The default website remains http://localhost:5173/ (127.0.0.1 also works). Complete package ZIP is the recommended installation; the ML package supplies the inference service and supporting modules without the web interface. The SCADA ZIP is an exact renamed copy of the supplied final dataset archive.
