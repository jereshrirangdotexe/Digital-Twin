# VoltMind 100 kVA LR V4: hardened dataset importer

This release adds an input adapter to the trained Logistic Regression bundle. Model weights, decision thresholds, feature equations and SCADA V4 data remain unchanged. The original trained model and full dataset are included. No live app or service has been replaced.

## Improvements

- CSV, TSV, delimiter-detected TXT, JSON row arrays/records, JSONL/NDJSON, and a selected XLSX sheet are supported. Decimal-comma CSV requires --decimal , . XLS files and arbitrary document layouts are unsupported.
- Familiar R/Y/B names and explicit unit suffixes are recognized. Arbitrary names require an exact schema mapping. ABC or line-to-line voltage sources require an explicit engineering mapping/conversion; phases and voltage reference are not guessed.
- V/kV, A/mA/kA, C/F/K, and oil fraction/percent conversions are explicit. A name without a unit needs a units declaration. Declared units override suffixes and are recorded in the audit.
- Timezone-naive dates require a timezone. Numeric epochs require s/ms/us/ns. Day/month strings require a timestamp format. Ambiguous date and daylight-saving interpretations are rejected.
- Separate assets have separate histories and asset-bound calibrations. Missing five-minute samples reset ALL feature histories, without inserting measurements or interpolation. A ten-minute data source cannot satisfy the model's five-minute history; its segments remain unassessed rather than being resampled silently.
- Out-of-order data is rejected unless sorting is explicitly requested. Duplicate asset timestamps and ambiguous duplicate aliases are rejected. Explicit schema selection can resolve alias ambiguity.
- Missing sensors and corrupt readings produce unavailable assessments. Extra columns, labels and unknown measurements are ignored and listed in the audit. Availability flags override supplied measurements.
- Very low positive voltage readings below 10 V trigger scale/measurement review and thermal abstention. This deliberately does not decide whether the reading is a real extreme voltage collapse or unconverted kV. It resets the thermal history around that reading. It is an input validity check, not short-circuit protection.
- File row/column/size limits, duplicate header checks and output overwrite protection are enforced. Every successful import produces an audit with resolved mappings/units, ignored columns, missing measurements, gap resets and assessment coverage.

## Verified results

81 compatibility/regression checks passed with zero failures. All 311,040 original V4 primary and oil-control rows were processed. Every supported score and alarm decision matches the prior runtime to 1e-12 numeric tolerance, including missing outputs. The renamed/unit-converted command-line example also matches the original model output. Existing result files cannot be silently overwritten.

The earlier training release's 480 checks and fresh synthetic test metrics are preserved in reports/ and ORIGINAL_TRAINING_README.md. This hardening adds compatibility checks; it does not improve event recall, reduce the measured false-alarm rate, or increase oil coverage. Do not add the old and new check counts and call the sum independent experiments.

## Run

Install requirements.txt in an isolated Python 3.13 environment. From this model folder:

    python runtime/voltmind_v4_input_adapter.py --input examples/renamed_units_input.csv --config examples/renamed_units_config.json --calibrations examples/asset_calibrations.json --output my_predictions.csv

This example deliberately uses renamed columns, kV, mA, Fahrenheit and percentage oil level. The config converts them into the trained model's canonical physical inputs. my_predictions.audit.json explains the import. Choose a new output filename for each run.

For canonical SCADA:

    python runtime/voltmind_v4_input_adapter.py --input your_data.csv --calibrations your_asset_calibrations.json --output your_predictions.csv

For XLSX, select the actual single sensor table with --sheet SheetName if there is more than one sheet. First row must contain unique headers. Do not supply the organisers' checklist as a sensor history.

## Configuration

The examples provide an exact mapping. schema maps CANONICAL field to RAW column name. units uses canonical keys. Supported additional options:

    {"timezone":"Asia/Kolkata", "timestamp_format":"%d/%m/%Y %H:%M:%S", "sort":true}

Use epoch_unit instead of timestamp_format when timestamps are numeric epochs. asset_id is an explicit override when no input identifier is present; it cannot contradict an existing identifier. rating_kva may declare 100 when a source lacks a rating column; this declaration does not independently verify the physical transformer.

Canonical signals: replay_id, timestamp_IST, VR_V, VY_V, VB_V, IR_A, IY_A, IB_A, ambient_temp_C, top_oil_temp_C, optional oil_level_fraction and terminal_R_surface_temp_C. Availability fields: communication_available, oil_level_sensor_available and terminal_sensor_available. An absent communication flag is treated as not explicitly unavailable; missing numeric readings still abstain.

The calibrations JSON maps each asset ID to that asset's independently verified healthy thermal commissioning calibration. Example calibration is synthetic and only matches the bundled example. No calibration or a mismatched calibration leaves thermal output unassessed. Optional oil/terminal results remain explicitly synthetic-research assessments using the original assumed gauge/terminal physics; measured hardware calibration is still required before operational use.

## Limits that remain

The model cannot handle every arbitrary dataset. A checklist, missing timestamps, an unsupported sampling cadence, unknown measurement definitions, transformer rating differences or incorrect units cannot be repaired by inventing sensor readings. Plausible but incorrect declared units may still pass physical range checks. Missing measurements are never guaranteed to yield a prediction.

The supplied organiser workbook was checked read-only and rejected as a non-SCADA table. Its reference examples were not turned into training observations. Actual judges' sensor histories have not been supplied for end-to-end verification.

All model performance evidence remains synthetic. Oil monitoring still has about 55% coverage on the fresh test and gauge bias can resemble depletion. Thermal false alarms remain higher than the original deployed model in that test. No trained pressure, internal-bushing, mechanical-vibration, internal-short-circuit, measured-hotspot or measured-impedance detector was added.

This is an offline importer/model package. The live website continues to use its existing deployed model until this package is deliberately integrated.
