# VoltMind 250-kVA Hackathon Runtime

Locked model: VoltMind_250kVA_Prototype_ML_v1.0, COMPETITION_PROTOTYPE_LOCKED.
Runtime version: 1.0.0. Purpose: 250 kVA, 11 kV/433 V, three-phase ONAN Dyn11 condition-monitoring prototype. Model selection is complete; the original histogram boosting artifact and threshold are preserved.

## Quick start
Use Python 3.12 and run these commands from this folder:
```
python -m pip install -r requirements.txt
python run_voltmind_250kVA.py -h
python -m unittest discover -s tests -v
python run_voltmind_250kVA.py --input examples/example_internal_input.csv --output predictions.csv --frontend-output frontend.jsonl --history-output history.json
python run_voltmind_250kVA.py --input examples/example_organizer_input.csv --output organizer_predictions.csv --frontend-output organizer_frontend.jsonl
python examples/demo_stream_250kVA.py
```
Add --stream for row-at-a-time CSV replay. JSON and JSONL output suffixes produce corresponding canonical results; CSV output flattens telemetry fields. --report writes completion accounting. --state-in/--state-out preserve streaming state and require the same model/calibration/version.

## Input boundary
Canonical fields: timestamp, asset_id, transformer_rating_kva, voltage_r_v, voltage_y_v, voltage_b_v, current_r_a, current_y_a, current_b_a, ambient_temp_c, top_oil_temp_c, communication_available. Eight physical channels and timestamps are required for thermal assessment. Missing channels remain null/unassessed. Required measurements cannot be reconstructed from oil temperature, a single phase, rating alone or provided synthetic loading estimates.

Original BASIC headers and the documented aliases in config/250kVA_aliases.json are recognized. R/Y/B and L1/L2/L3 aliases are supported; ambiguous A/B/C phase conventions require explicit mapping. Case, spaces, encoded units, column order and irrelevant extra columns are handled at one boundary. Comma, semicolon, tab and pipe delimiters are detected safely; --delimiter and --encoding handle explicit formats. --decimal , supports a declared decimal-comma file. UTF-8/BOM is the default encoding. Multiple possible matches are rejected with AMBIGUOUS_COLUMN. No replay ID is needed; a neutral ORGANIZER_ASSET_001 identifies a single asset. Use --asset-id or an asset column for multiple assets; IDs never enter the classifier. Rating defaults to this 250-kVA component; explicit other ratings are rejected.

Units encoded by suffix _V/_kV, _A/_mA, _C/_F/_K, equivalent spaces/brackets or degree-temperature notation are accepted. Unsuffixed ambiguous signals require explicit --units. Units are never guessed from magnitudes. Inputs must measure phase-neutral low-voltage magnitudes; arbitrary line-line or high-side measurements are not interchangeable with these inputs. Line-line input returns unassessed rather than inventing phases.

Custom mapping example, canonical name -> organizer column:
```
python run_voltmind_250kVA.py --input organizer.csv --schema schema_mapping.json --units unit_mapping.json --output predictions.csv
```
unit_mapping.json can map voltage/current/temperature groups to V/A/C, or individual canonical fields. Explicit kV, mA, Fahrenheit and Kelvin conversions are supported. Asset rating is kVA. Extra truth/event/profile/fault columns are ignored and never requested by runtime.

## Timestamps and sampling
ISO, timezone-aware, timezone-naive and common date/time strings are supported. Naive timestamps default to Asia/Kolkata and are explicitly marked; --timezone overrides this. Ambiguous day/month dates require --dayfirst or --monthfirst. Numeric epochs require --timestamp-unit s/ms/us/ns. Invalid timestamps produce failed/unassessed rows. Duplicates and reverse ordering are rejected per row, do not mutate accepted history, and are preserved in output order.

The frozen model requires five-minute history. Exact five-minute input works directly. Finer telemetry is retained; only exact five-minute grid snapshots update model state, and intermediate rows are explicitly unassessed. Five-minute-multiple gaps insert missing internal slots using only prior drivers, never future interpolation; output retains exactly the original input rows. Gaps over six hours or input outages over 72 model samples reinitialize with a fresh warmup. Other incompatible intervals are marked SAMPLING_INCOMPATIBLE_WITH_FIVE_MINUTE_MODEL. No silent sorting, dropping or long-gap interpolation occurs.

## Calibration
Hierarchy: valid existing asset calibration; separate independently verified healthy commissioning; frozen reference fallback. --calibration accepts calibration JSON with rating_kva, p0_W, pload_W, rise_K, tau_min, bias_C, exponent, status and provenance. Bounds are validated. Invalid calibration falls back with an explicit warning; asset-specific calibration must match asset_id if specified.

Never assume the organizer prefix is healthy. Commissioning requires an explicit --verified-healthy attestation, --commissioning-provenance, a separate file, one asset, complete regular five-minute measurements, at least 24 hours and sufficient load excitation. Same organizer/commissioning file or hash is rejected.
```
python run_voltmind_250kVA.py --input organizer.csv --commissioning verified_healthy.csv --verified-healthy --commissioning-provenance "Independent commissioning evidence" --output predictions.csv
python -m calibration.commission_250kVA --input verified_healthy.csv --verified-healthy --provenance "Independent commissioning evidence" --output calibration.json
```
No real independently verified commissioning file was provided. Runtime defaults to REFERENCE_CALIBRATION; its field fit RMSE is unknown. The commissioning mechanics test uses a clearly identified artificial fixture, not a claimed real calibration. Supplied calibration affects displayed Digital Twin expected oil/residual. ML nominal features remain frozen; nominalModelResidualC and ML_USES_FROZEN_REFERENCE_FEATURES identify that difference. Never interpret thermalScore as failure probability.

## Streaming and Digital Twin API
```
from runtime.streaming_runtime_250kVA import DigitalTwinMLRuntime250kVA
from runtime.digital_twin_adapter_250kVA import to_digital_twin_result
from runtime.frontend_adapter_250kVA import to_frontend_payload, to_history_point

runtime = DigitalTwinMLRuntime250kVA()
result = runtime.update(scada_row)
payload = to_frontend_payload(to_digital_twin_result(result))
history_point = to_history_point(result)
runtime.save_state("state.json")
```
Caller sends one row, never rebuilds history. Independent asset states use bounded oil/load/ambient/quality buffers. reset(asset_id) starts fresh warmup; delete idle assets explicitly. Memory grows with the number of assets, not historical rows per asset. Runtime/HTTP single-asset concurrent updates must be serialized; the provided HTTP sidecar does so.

warmupStatus is WARMING_UP until 24-hour initialization completes, then READY. thermalAlert is null when unassessed; it is never a substitute false/healthy result. GOOD/REDUCED/UNAVAILABLE data confidence is distinct from thermalState and electricalState. Reference assumptions reduce confidence. Spikes, stuck-oil evidence, invalid ranges, missing channels and outages are reported as data problems. Valid partial undervoltage evidence can still trigger an electrical warning while thermal assessment remains withheld. These warnings indicate operating conditions, not permanent damage.

## Spring Boot and React
React consumes JSON; Python performs ML. A Spring Boot controller may proxy this local sidecar:
```
python -m runtime.http_api_250kVA --host 127.0.0.1 --port 8765 --state-out state.json
```
POST /v1/250kva/infer takes one SCADA row object and returns the frontend payload. GET /health exposes the model lock/version. Use --state-in to resume. --allowed-origin enables one explicit frontend development origin if needed. examples/frontend_client.js illustrates consuming the stable envelope; REST/SSE/WebSocket transport wrappers can reuse it.

config/250kVA_frontend_contract.json documents every payload/history field, source, unit, nullable type and enum. config/250kVA_frontend_schema.json is the JSON schema. asset/telemetry/ml/diagnostics/digitalTwin are stable namespaces. Digital Twin health/risk/aging/maintenance placeholders remain null; this ML package does not invent those quantities. examples/example_frontend_payload.json, example_frontend_stream.jsonl and example_history.json demonstrate cards and chart histories without ML internals.

## Validation and limitations
Reports include all-row internal parity, timestamp-aligned events, family breakdown, event-free controls, missingness, grouped SHIFT metrics, robustness, organizer compatibility, leakage tests and fresh-environment checks. evaluation/ contains offline answer keys and reproducibility tools; runtime does not import them. Remove the entire evaluation directory and reports to deploy if desired.
```
python evaluation/validate_runtime.py
python evaluation/robustness_matrix.py
```
All frozen source data remain unchanged; organizer-style perturbations are test fixtures only. No model hunting or acceptance-set tuning was performed during runtime hardening. Five-minute histories, required physical channels and sensor observability limit arbitrary input compatibility. Missing oil/ambient/phases, unknown units, wrong rating, unsupported voltage basis, bad timestamps and insufficient history cannot support confident thermal inference. LOW_OIL_GAUGE remains UNSUPPORTED_BASIC.

FINAL STATUS: CONDITIONAL HACKATHON READY. Runtime/JSON integration is verified; real organizer generalization and real asset calibration are unavailable. Frozen thermal-event misses and SHIFT false alarms remain. Safe handling does not prove field diagnostic accuracy. See MODEL_CARD.md and reports/250kVA_final_readiness.txt. Model work stops here; no other transformer rating is included.
