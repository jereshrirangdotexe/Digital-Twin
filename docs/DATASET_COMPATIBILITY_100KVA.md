# 100 kVA external dataset compatibility

The existing locked model now has a broader input adapter. This update changes file handling and representation; it does not retrain the model or prove accuracy on unseen judge data. The tournament research model remains separate.

## Website
Select 100 kVA, then ADD A DATASET. Supported formats: CSV, semicolon CSV, TSV, pipe-separated text, XLSX, JSON row arrays, a JSON object containing only a records array, and JSON Lines. The first row in text/Excel must contain column names. Multiple-sheet workbooks require an explicit sheet selection. The upload limit remains 40 MiB through the website.

Recognized phase R/Y/B and L1/L2/L3 column names map automatically. Explicit physical unit suffixes support V/kV, A/mA/kA and Celsius/Fahrenheit/Kelvin. Unlabeled units use the documented V/A/C contract and are reported as assumptions. Unknown columns, including truth/event/label columns, never become model features.

Use Schema mapping JSON for unfamiliar column names and Unit mapping JSON for explicit units. Mapping keys are voltage_r_v, voltage_y_v, voltage_b_v, current_r_a, current_y_a, current_b_a, ambient_temp_c, top_oil_temp_c, timestamp and asset_id. Do not map line-to-line voltage to phase-neutral voltage or HV current to LV current; those require independently established electrical transformations. ABC phase naming should be explicitly mapped because B has a different meaning in RYB naming.

Use File and time settings JSON when needed. Example:
```json
{
  "sheet": "Readings",
  "timestamp_format": "%d/%m/%Y %H:%M:%S",
  "sampling": "five_minute_last",
  "sort": true
}
```
Other options: delimiter (comma, semicolon, tab or pipe), decimal (for example comma), encoding, epoch_unit (s/ms/us/ns). Epoch units and timestamp_format are mutually exclusive. Epoch timestamps are UTC; naive formatted timestamps use the chosen timezone. Ambiguous dates are rejected unless their format is declared.

## Time history and missing measurements
The model still requires a five-minute time history. Default strict mode accepts five-minute observations and occasional whole-interval gaps. Out-of-order observations need explicit sort=true. Duplicate asset/timestamp keys are rejected.

For faster measurements, sampling=five_minute_last takes the latest observed row in each CLOSED five-minute interval, anchored at the first reading. Empty intervals keep missing sensor values and communication unavailable. It never interpolates temperatures or carries values across an empty interval. Trailing readings in an unfinished interval are excluded and counted in the compatibility report. This representation may miss short transients; it is not a fast short-circuit classifier. Coarser typical measurements are rejected because a five-minute history cannot be recovered from them reliably. Different cadence support needs further model validation/training.

All eight measured signals are required as columns: three LV phase-neutral voltages, three LV phase currents, ambient temperature and top-oil temperature. Missing row values are retained for runtime abstention. No invented sensor values or labels are supplied. Separate assets retain separate histories. Warm-up, sensor checks and the existing model's decision logic remain active.

The organiser workbook is a condition-monitoring checklist/reference fixture, not a complete measured time series; it cannot produce trustworthy thermal ML predictions. A suitable judge dataset can be imported, but arbitrary tables cannot.

## Offline import and prediction
From the project folder:
```
.venv\Scripts\python.exe ml\import_dataset.py --input judge.xlsx --output normalized.csv --settings examples\external_dataset_settings.json --predictions predictions.csv
```
Edit or omit settings to match the file. The converter writes a normalized CSV and a compatibility JSON report. Use --calibration with a verified asset-specific calibration when available. Without it, prediction uses the existing explicitly labeled synthetic reference calibration; results on real transformers remain unvalidated. Never assume the uploaded monitoring rows are healthy commissioning data.

The website's existing separate healthy commissioning upload remains CSV and requires independent healthy verification. Its schema settings must match that separate file too. This update is limited to 100 kVA input compatibility; 250/630 kVA upload formats remain CSV.

## Validation and activation
Automated checks cover format parsing, conversions, time ordering, duplicate/ambiguous inputs, causal resampling, unknown labels, unchanged existing predictions, multi-asset isolation and service uploads. Isolated HTTP tests exercise JSON and XLSX multipart uploads. Frontend production build passes. The model artifact hash is unchanged.

Restart the Python ML service if it was already running when these files were edited. React development mode normally reloads the changed source; a deployed frontend needs the rebuilt frontend/dist files. No model training or model replacement is included.
