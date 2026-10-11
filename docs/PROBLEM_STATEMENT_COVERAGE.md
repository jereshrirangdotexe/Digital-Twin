Current release: 100, 250 and 630 kVA are integrated. See docs/THREE_RATING_INTEGRATION.md and reports/630_INTEGRATION_VALIDATION.md for activation, native physics-detector scope, 24 × 8,064 rows and 336 two-hour summaries per 630-kVA replay. Earlier sections remain historical rating-specific instructions.

Update: this document originally describes the 100-kVA integration. Both 100 and 250 kVA are now supported; see docs/MULTI_RATING_INTEGRATION.md for the separate 250-kVA model, 24 replays × 6,048 rows, current bases, 40-MiB/200,000-row limits and API. The existing presentation demonstrates 100 kVA; the live dashboard can demonstrate either rating.

# Problem statement coverage

Reference: supplied four-page DT Problem Statement.pdf. Only 100 kVA is integrated. The statement does not mandate 250 kVA, multiple ratings or a 3D visualization.

| Expectation | Implementation and evidence | Limit |
|---|---|---|
| Behavioral simulation | Calibrated first-order expected oil temperature from phase loading and ambient temperature; actual/expected/residual plots | Synthetic reference calibration; physical transfer unverified |
| Electrical and thermal monitoring | Three-phase voltage/current, loading, oil and ambient measurements | CSV replay rather than live connected sensors |
| Health Index | Documented per-row prototype rules, now summarized in automatic 24-row blocks with coverage | Not certified overall insulation health |
| Abnormal conditions and alerts | Locked LogisticRegression thermal classifier, independent operating/data-quality warnings, recorded active/resolved alerts | Preserved synthetic event result 38/60; prediction before actual failures unestablished |
| Maintenance guidance including timing | Highest-priority issue retained per block; prompt qualified review, sensor verification, trend review before next block or continued observation | Decision support, not an optimized maintenance date or work order |
| Interactive dashboard | Source upload/local replay, controls, charts, histories, quality, assessments, alert and maintenance pages | One selected local session |
| Reporting | CSV readings, JSON summary, printable HTML performance/trend/assessment/alert report; optional browser Print to PDF | Only retained processed browser history; no fabricated full-fleet summary |
| Source and documentation | Python, Spring Boot, React source; installation, execution, methodology and assumptions | First install needs dependencies/internet |
| Demonstration | Editable short presentation and timed live demo script | Demo is live; recorded video is not supplied |
| Extendability to utility sensors | Separated normalized input/model/API/dashboard layers; connector contract and migration plan in SENSOR_INTEGRATION.md | No hardware/protocol endpoint claimed connected |
| Remaining useful life | Explicit unavailable display and documented data requirements | Suggested architecture capability not implemented; supplied artifact cannot support a defensible lifespan |

The document lists typical architecture modules as possibilities. A working RUL estimator requires validated insulation/hot-spot/aging information and service-life assumptions beyond the supplied measured channels and thermal classifier. Adding an arbitrary remaining-years number would not close that engineering gap. Field validation, an actual sensor protocol, and asset-specific commissioning remain future work.

Submission includes the working software, documentation/source, reporting, presentation and a live demo route. Describe the product as a 100-kVA operational digital twin with thermal anomaly detection and condition-based maintenance guidance. Do not claim proven field failure prediction, calibrated failure probability or remaining-life prediction.
