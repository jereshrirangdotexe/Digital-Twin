Update: this document originally describes the 100-kVA integration. Both 100 and 250 kVA are now supported; see docs/MULTI_RATING_INTEGRATION.md for the separate 250-kVA model, 24 replays × 6,048 rows, current bases, 40-MiB/200,000-row limits and API. The existing presentation demonstrates 100 kVA; the live dashboard can demonstrate either rating.

# Input boundary and calibration

Canonical measured fields: `voltage_r_v`, `voltage_y_v`, `voltage_b_v`, `current_r_a`, `current_y_a`, `current_b_a`, `ambient_temp_c`, `top_oil_temp_c`; plus `timestamp`. Optional `asset_id`, `transformer_rating_kva`, `communication_available`, `loading_pct`.

Internal names: VR_V/VY_V/VB_V, IR_A/IY_A/IB_A, ambient_temp_C, top_oil_temp_C, timestamp_IST, replay_id. Examples of supported organizer aliases: R_voltage/Y_voltage/B_voltage, R_current/Y_current/B_current, V_R/V_Y/V_B, I_R/I_Y/I_B, Tamb/Toil, ambient_temperature/oil_temperature, recorded_at/time/datetime, transformer_id. Names are matched case-insensitively after punctuation normalization. Exact aliases are declared in `ml/runtime/schema_adapter_100kVA.py`.

Explicit recognized suffixes convert kV→V, mA→A, kA→A, F→C and K→C. Voltage must represent phase-neutral RMS, not line-line voltage; the parser cannot infer the electrical measurement convention. Unitless recognized aliases use the documented V/A/C contract and produce UNIT_CONTRACT_ASSUMED quality issues. Do not claim that assumption proves units. Ambiguous aliases, a raw column reused for different signals, unsupported units or invalid declared ratings reject.

For unfamiliar names, supply JSON mapping from canonical field to exact raw column. For example:

```json
{"timestamp":"recorded_time","top_oil_temp_c":"sensor_oil"}
```

Unit mapping example:

```json
{"voltage_r_v":"kV","current_r_a":"mA","top_oil_temp_c":"F"}
```

Every required measured channel must have a column in a website upload. Missing cells remain null/unassessed. NaN, invalid numbers and implausible values never become fabricated zeros. Plausibility ranges, oil jumps, stuck/frozen channels, communication availability and history checks are original preserved rules. Duplicates, order violations and gaps are retained and flagged; data is neither silently sorted nor interpolated. Unknown fields including truth/profile labels have no model role. Completely invalid timestamps or wholly incompatible sampling reject before a session begins. Mixed irregular sampling invokes original reset/unassessed behavior at affected rows.

Model feature order and threshold are frozen in `ml/config`. Calibration can change only the expected physical thermal response using independently verified commissioning; it does not retrain the classifier. The synthetic reference is rise34.6685/tau196.1612/bias−4/loss_ratio0.242389. It is explicitly marked REFERENCE_CALIBRATION and transfer-unverified.

An asset-specific JSON must pass the original bound/metadata policy: 100-kVA rating, supported status, independently verified healthy requirement true, ≥2,016 commissioning samples, ≥10,080 minutes, finite nonnegative RMSE and asset binding matching the selected replay. Alternatively, upload a separate healthy commissioning CSV with explicit verification; only its thermal parameters are fitted by the preserved commissioning procedure. Choose either calibration JSON or commissioning CSV, not both. The local R05/R11 reference or supplied synthetic commissioning sample cannot certify an unseen physical transformer.

CLI example (synthetic example only):

```bat
.venv\Scripts\python.exe ml\main.py --input examples\example_internal_input.csv --commissioning examples\verified_synthetic_commissioning_R05.csv --verified-healthy --output predictions.csv --commissioning-output calibration.json
```

Safe parsing and synthetic robustness tests establish compatibility behavior, not organizer detection sensitivity, specificity or false-alert rates. Those require an independently characterized organizer dataset and asset commissioning.
