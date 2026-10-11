# VoltMind thermal twin — judge demonstration

This is a separate **synthetic illustration**, not field data or an accuracy benchmark. It uses the unchanged locked 100-kVA Logistic Regression V4 model. Original datasets and the 250/630-kVA models are unchanged.

## Run in the project

1. Start the Python ML service, Spring Boot backend and frontend as usual. Refresh the website after starting the updated service.
2. Open Data source & replay controls. Choose 100 kVA and **JUDGE DEMO · thermal twin · synthetic** in the replay selector.
3. Choose 60x and click RUN ON LOCAL DATA. The 4,032 readings take about 67 seconds plus processing overhead.
4. Open Monitor → Live Twin. Use the graph date selector to show 1 February (normal), 10 February (excess heat), then 14 February (recovery).

Each row is five minutes apart. The 4,032 sample slots cover fourteen days, 1–14 February 2026 IST; first-to-last timestamps differ by thirteen days, 23 hours and 55 minutes.

## Explain it to the judges

“The expected oil temperature responds to load and ambient temperature. During normal operation, measured oil follows it. We then inject extra heat without increasing electrical load. The measured temperature separates from the expectation and the existing detector raises a thermal condition warning. Removing the extra heat lets the transformer cool and the detector recover.”

- 1–8 February: balanced electrical load alternates between 35% and 70%; actual oil follows expected oil. There are 31 suitable healthy load-response episodes for describing Thermal DNA.
- 9–11 February: one controlled extra-heating interval approaches an additional 11 °C gradually. The first thermal alert occurs at 00:55 IST on 9 February.
- 12–14 February: extra heat is removed and temperature recovers gradually. The last day has no thermal alerts.

The first eleven rows are expected thermal warm-up, not model failures. Main condition summaries publish every 24 readings (two historical hours). Live alerts can change between these summaries. A recorded incident remains in history after recovery; its count is not the number of software errors or confirmed equipment failures.

## Files and evidence

- `100kVA_THERMAL_TWIN_DEMO_4032.csv`: monitoring readings; exactly 4,032 rows, with no missing sensor values.
- `independent_healthy_synthetic_commissioning_4032.csv`: separate healthy synthetic history, dated December 2025.
- `calibration.json`: calibration keyed to DEMO100_THERMAL_TWIN; synthetic known generator parameters with independent commissioning error recorded.
- `validation.json`: checks against the actual unchanged locked runtime, including model fingerprint.
- `chapters.json`: demonstration chapters.
- `create_thermal_judge_demo.py`: reproducible generator.

For standalone upload, provide the monitoring CSV and matching calibration JSON in advanced upload settings before starting. The bundled local replay loads its calibration automatically.

Thermal DNA describes load-response episodes; a trusted fingerprint additionally requires an independently justified healthy reference. Do not attest the entire monitoring replay as healthy: it includes injected heating. The independent commissioning file is synthetic healthy evidence only, not field verification.

## Limits

The healthy temperature generator deliberately matches the thermal model’s assumed physics. Its clean normal behavior demonstrates the user flow; it does **not** prove generalization, false-alarm rate or field accuracy. Extra heating illustrates a residual, not a diagnosis of a specific component. No training or model changes were performed. Warnings remain visible and are not suppressed for the presentation.
