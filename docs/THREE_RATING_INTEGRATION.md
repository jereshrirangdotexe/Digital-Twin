# VoltMind — 100, 250 and 630 kVA

The existing React + Spring Boot + persistent Python project now includes the exact supplied 630-kVA SCADA dataset and detector. Select 630 kVA in Transformer rating, wait for LOCAL DATA READY, choose an asset/replay, and Run on local data. The same worker serves all three ratings.

## Activate your existing project

The verified source update is copied into <project>. Restart the Python worker once after upgrading:

```bat
cd /d <project>
.venv\Scripts\python.exe ml\main.py --serve
```

Refresh http://localhost:5173/. Existing npm run dev receives the source changes. Spring Boot's proxy routes and limits already support this addition; no Java source change or new dependency installation is needed. A fresh extraction still uses install_voltmind.bat then start_voltmind.bat. Do not start an additional independent 630-kVA server beside the integrated worker.

## Dataset

The 630-kVA input is scada/630kVA_SCADA_MAIN.csv from 630KVA FINAL SCDA DATASET.zip, copied as data/630kVA_SCADA_MAIN.csv. It is byte identical to the same CSV inside 630kvA ml model.zip. There are 193,536 rows in 24 synthetic assets/replays: TX-630-01 / R01 through TX-630-24 / R24. Each replay has 8,064 five-minute rows representing 28 days. Start dates are staggered from January through July 2025 in the dataset; all source times are UTC. Display time follows the user's browser timezone. These dates are historical sample times, not the current clock.

The combined selector includes the asset and replay to keep different assets or repeated replay IDs isolated. The physical synthetic asset ID remains available as asset.id; source.replayId identifies the selected combination. Duplicate asset/replay streams are not joined across resets. Truth, training annotations, event and profile files are excluded from inference and the delivered runtime data.

The 40-MiB/200,000-row upload limits cover the supplied 22,228,907-byte CSV. The 10,000-row history retains either complete replay. No upload is needed for the bundled local data. The first full 630-kVA validation took about 10 seconds in the test setup; elapsed time depends on this computer and concurrent work. UI loading and LOCAL DATA READY states are explicit. Per-worker memory caching makes subsequent local selections faster; restarting Python clears that cache.

## Detector and calibration

The selected source artifact is **PersistentPhysics**, the supplied persistent first-order physics baseline. Statistical tournament candidates were rejected in the source package. Its causal score is the mean residual over a past 120-minute window divided by 20 and clipped to [0,1], with source threshold 0.4 and 15-minute persistence. The locked algorithm, thresholds, sensor checks and resets are preserved. The 433-V rated current is 840.024641 A.

Known local synthetic assets use the supplied synthetic_assets.json, matching the source package's local-service behavior. This is known simulation calibration, not measured commissioning. Uploaded datasets default to REFERENCE_PROVISIONAL, even when IDs happen to match known simulation assets. Explicit calibration uses the source assets JSON structure, including validated=true, rating_kva=630 and bounded thermal parameters. Invalid explicit calibration is rejected. Asset binding is checked before starting.

Warm-up is **three times the larger configured oil time constant**, measured in clean historical minutes. The uncommissioned reference requires 900 minutes; TX-630-01's synthetic calibration requires about 983.6 minutes, reached after 198 chronological five-minute samples. Outages, gaps and invalid readings reset this history as defined by the supplied runtime. The source detector also supports other sampling intervals, but this integrated 24-row/two-hour workflow requires five-minute data to keep the published period honest.

Optional commissioning uses the original source routine after adapting the user-declared schema/units: separate independently declared healthy data, at least 1,000 observations and seven days, suitable loading diversity, bounded parameters and diagnostic fit limits. Software does not verify the user's healthy declaration. No automatic calibration from monitoring data occurs.

## Health summary and model output

Exactly 24 processed rows publish one two-hour summary. A complete 630-kVA replay produces **336 summaries**. Mean health/risk, condition and maintenance stay fixed until the next boundary; measurements and live alerts continue. Coverage is explicit and unassessable rows are excluded.

The source 630-kVA detector provides null health, risk, aging and maintenance indices. This integration adds the same transparent prototype observation rules already used for 100/250 kVA, using the correct 630-kVA current base and retaining a synthetic/reference uncertainty contribution. These added indices are not a validated 630-kVA prediction or failure probability. Source digitalTwin is preserved separately as sourceDigitalTwin. All original native ML, sensorState, electricalWarnings, qualityReasons, calibrationStatus and confidence fields remain unchanged. Common flags are derived from the source warnings for dashboard compatibility. A thermal deviation may represent physical change or gradual sensor bias; independent inspection is required to distinguish them. Aging and RUL stay unavailable.

Reports identify the chosen rating/model. Expected/actual oil, residual, score, electrical warnings, health summaries, maintenance context and CSV/JSON/HTML downloads use the selected runtime only. Opening the current overview asset navigates to Live Twin without restarting its replay or clearing the health window.

## Frozen provenance and module compatibility

Original model SHA256: 45b3995932df7fba39eeed8524975f9a351f4e82e7f103c2aacd64c77f12966f.

Dataset SHA256: de38cf4c8d223fbb0130fa0a02e4a6c4658a5727af8a05d9d431f74bc53c3710.

Model, configuration, calibration, input adapter, thermal equations, decision persistence and interpretation are unchanged. Three vendor Python files have import paths changed to relative imports so the three runtimes can coexist; streaming_runtime.py also accepts an already-validated calibration dictionary in addition to its original file transport. Original versions of these files are retained under ml/vendor630/source_original. No feature/decision algorithm is changed. Full native per-row results were compared against hashes generated from the unmodified original runtime on all 8,064 R01 rows. Original 100- and 250-kVA frozen files remain byte identical. The source model card and tournament/hardening reports are included under ml/vendor630.

GET /api/health now returns supportedRatings [100,250,630] and three model entries. Existing dataset/replay routes accept ratingKVA:630. Top-level legacy model fields continue describing the 100-kVA default; clients use the models array for other ratings. CLI batch mode remains the original 100-kVA tool; all ratings are connected in --serve mode and the dashboard.

For 630 kVA, the native loading percentage is maximum phase current divided by rated current (840.0246 A). The 100/250-kVA runtimes use their original apparent-power loading basis. The electrical telemetry and report values preserve each source model's definition.
