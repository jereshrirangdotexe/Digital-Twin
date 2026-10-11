# Final intelligence contract

`ml/main.py --serve` is the authoritative persistent entry point. CLI uses the supplied hardened importer: `python ml/main.py --input measurements.csv --output predictions.csv --calibrations asset-calibrations.json --config input-config.json`. Outputs must be new paths. Configuration examples are in `ml/final100/protocol` and that runtime's documentation. The original legacy runtime stays available for archival regression tests, but is not selected for 100 kVA dashboard inference.

The bridge strips oracle labels/events/profiles and only forwards raw measured channels, timestamps, asset ID, rating and explicit availability. Each selected replay is computed causally by the frozen importer; its precomputed prefix outputs are delivered in order. Later observations never alter earlier predictions. No fitting occurs. Calibration is asset-bound. Local synthetic calibration provenance adds uncertainty only to the separate observation index; it does not change locked scores or alerts.

## APIs

Spring Boot proxies these worker routes; all require a current `sessionId`. Unknown/stale sessions reject.

- GET `/api/summary/{overall|thermal|electrical|data-quality|model|recurrence|thermal-dna|maintenance}?sessionId=...`
- GET `/api/summary/export?sessionId=...`: summary JSON and escaped printable HTML.
- GET `/api/intelligence/evidence?sessionId=...&incidentId=...`: persisted incident evidence.
- GET `/api/intelligence/maintenance` and `/api/intelligence/dna` with sessionId.
- POST `/api/intelligence/simulate`: sessionId, loadReductionPct 0–80, durationHours 0.5–24. Constant measured ambient/current ratios; independent first-order thermal projections from measured oil. No live state mutation, protection action or classifier prediction.
- POST `/api/intelligence/maintenance`: sessionId, timezone-qualified timestamp, action, component, observations, verification, followup. Explicit engineer entry; recovery is not assumed.
- POST `/api/intelligence/dna/reference`: sessionId, verifiedHealthy:true, nonempty provenance. Requires at least three clean response episodes and no thermal alert in the reference history. One reference per exact source/asset; never silently replaced.

Existing replay, dataset, history, alert and SSE routes are retained. Modules above intentionally reject other ratings; shared frontend chart improvements remain available.

## Evidence rules

SQLite schema initializes automatically in `IntelligenceStore`. Incident identity hashes exact source bytes + asset + category + onset; restart does not create false recurrence. Incident memory can include previously processed history of the same exact source, clearly scoped separately from this session's processed-row counts. Independent replays never form a fabricated asset timeline. Communication/missing-sensor interruption closes a detector episode as evidence interrupted, not confirmed recovery.

Sensor investigator presents abrupt jumps, stuck readings, residual drift and competing physical/sensor explanations. It cannot distinguish slow bias from excess heating with one temperature probe. Its evidence does not overwrite classifier output.

Repair comparison matches pre/post 24h readings within 10 load percentage points and 2°C ambient, requiring six pre peers per post row and at least 24 matched post rows. A residual reduction of 2°C provides observational improvement evidence, not causal proof. Returned thermal incidents are reported separately.

Thermal DNA uses clean, consecutive five-minute load steps of at least 15 percentage points, stable post-step load (std ≤8), ambient span ≤2°C and non-overlapping two-hour responses. Compare direction, initial oil-minus-ambient rise within 3K and step magnitude within 10 points against at least three verified reference episodes. Only new episodes after the locked reference period are compared; the baseline cannot certify itself. At least three comparable observations are needed; drift requires at least three differences above max(8K,3 reference standard deviations). These are transparent descriptive engineering screens, not trained damage thresholds or a fitted thermal time constant.

## Scope against organiser documents

Voltage/current/loading/oil/ambient, trends, health index, alerts, maintenance suggestions and downloadable evidence are connected. The 35-row organiser workbook supplies monitoring concepts/reference examples, not a time series or universal limits. A 50A example must not replace the 100 kVA / 433V rated-current calculation (~133.34A). Real sensor connections, field validation, insulation aging/RUL, internal-fault diagnosis and unsupported optional measurements remain unavailable.
