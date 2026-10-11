# Transparent prototype interpretation

Version: `VoltMind_Operational_Observation_v1.0`. Implementation: `ml/digital_twin.py`. It consumes locked ML output and never changes model state, features, calibration, weights, thresholds or decisions.

Rated current is `100000 / (sqrt(3) × 433) = 133.3372446165 A`. Maximum phase loading is `100 × max(IR,IY,IB) / rated current`, available only when all phase currents are available. ML-derived total utilization remains the original phase V×I calculation and is a distinct quantity.

Numeric indices require `thermalAssessable = true`, confidence other than UNAVAILABLE, and condition other than SENSOR_SUSPECT. Otherwise health/risk values are null, bands UNASSESSED, and recommendations reflect the unavailable data or known independent electrical warning.

Risk components on an assessable row:

| Component | Exact rule |
|---|---|
| observation uncertainty | 10 points (prototype reserve, not a measured uncertainty probability) |
| reference calibration uncertainty | 10 if REFERENCE_CALIBRATION, otherwise 0 |
| locked model thermal alert | 40 if thermalAlert is true, otherwise 0 |
| electrical warnings | 10 per true phase-loading, undervoltage and imbalance warning |
| loading stress | min(15, max(0, maximum phase loading % − 100) × 0.3) |
| positive residual stress | min(15, max(0, oil residual °C) × 1.5) |

`riskScore = round(min(100, sum(components)), 1)`; `healthIndex = round(100 − riskScore, 1)`. Component values are exposed in every assessed payload for review. These choices are engineering interpretation rules for this prototype, not learned or field-calibrated failure relationships.

Risk bands: LOW <30, MODERATE <50, HIGH <75, CRITICAL otherwise. Health bands: OBSERVED_STABLE ≥75, WATCH ≥55, ELEVATED_STRESS ≥35, HIGH_STRESS otherwise. A stable band is not a health certificate. Reference transfer limitations are displayed with every assessed explanation.

Maintenance precedence: unavailable communications → RESTORE_TELEMETRY; sensor evidence → VERIFY_SENSORS; assessable thermal alarm → PROMPT_INSPECTION; independent electrical warning → REVIEW_OPERATING_WARNING; assessed risk ≥30 → TREND_REVIEW; assessed remaining rows → ROUTINE_OBSERVATION; unavailable assessment → DATA_REQUIRED. Actual measured deviation, engineering warnings and reliability drive explanation text and urgency. No automated protection, maintenance work order or remaining-life claim is generated.

`agingState` and `rulEstimate` are always null: there is no validated winding hot-spot/insulation aging, oil chemistry, dissolved-gas, moisture or field-life model in this supplied artifact. The UI explicitly shows these unavailable states. Categorical data confidence (GOOD/REDUCED/UNAVAILABLE) describes evidence reliability separately from asset condition and from prototype health.

## Automatic two-hour display summary

The original `digitalTwin` and `ml` per-row fields above remain unchanged. `ml/assessment_window.py` adds a separate `assessment` field in live payloads. `assessment.latest` is immutable between publications and contains the last completed nonoverlapping 24-row block. The backend, not React, computes it. The main dashboard health, risk, block condition and maintenance use this published summary; live engineering measurements, data quality and alerts remain per-row.

Block health is the arithmetic mean of numeric per-row health indices, rounded to one decimal. Block risk is 100 minus that rounded mean. No numeric mean is returned without any assessable row. Valid/total rows and coverage are always exposed; unassessed rows never count as healthy or as zero health. Band boundaries retain the documented prototype rules. The highest-priority maintenance evidence is retained with this explicit ordering: thermal inspection, sensor verification, communications restoration, electrical operating review, trend review, routine observation, data required. This is display interpretation only and cannot alter a frozen ML alert.

Block condition retains thermal alert evidence first, then suspect-sensor evidence, electrical warnings, communication interruption, no thermal assessment, or no observed alert. Counts for thermal-alert, electrical-warning, offline and sensor-suspect rows remain available even when more than one category occurred. The representative maintenance reason can therefore differ from the condition label; neither is a certified physical failure diagnosis. Review timing is qualitative prototype guidance, not a predicted failure or maintenance date.

Partial final uploaded blocks publish once with `partial=true`. Actual first/end timestamps are shown. Twenty-four rows represent two hours nominally at five-minute sampling; nonregular data cannot establish continuous two-hour coverage. A new/restarted replay creates a new publisher and resets the summary. Charts show one health/risk point per publication; an unassessed block leaves a gap. Streaming reconnection can recover retained block payloads without repeating model inference.
