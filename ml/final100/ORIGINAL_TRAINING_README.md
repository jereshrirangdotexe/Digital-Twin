# VoltMind 100 kVA Logistic Regression V4

Training completed on 11 October 2026 using the approved SCADA V4 dataset. The user authorized this training after dataset creation. The frozen dataset's historical stage fields still say training was not authorized at dataset-freeze time; this release records the later authorization without modifying the dataset.

## What is trained

One locked model bundle contains three separately fitted Logistic Regression detectors:

| Detector | Selected model | Features | Meaning |
|---|---|---:|---|
| Thermal | LR_four_feature_control | 4 | Excess top-oil temperature against independently commissioned expected behavior |
| Oil | LR_C0.03_negative1 | 8 | Suspected oil-inventory depletion under V4's configured gauge geometry |
| Terminal | LR_C0.03_negative3 | 5 | Suspected R-phase LV terminal contact heating |

The thermal winner uses residual, residual mean over 30 minutes, residual mean over 60 minutes, and residual change over 30 minutes. Eighteen-feature thermal challengers were also trained; they did not win the frozen validation ranking. The original thermal feature representation was therefore retained and refitted. Logistic Regression is retrained on the V4 train partition, rather than appending coefficients from unrelated conditions to the original binary classifier.

Added oil inputs: estimated inventory deficit, changes over 115 and 30 minutes, inventory mean and variation over 60 minutes, observed level fraction, top-oil temperature, and consecutive flat-level count. These estimates use the observed level and temperature, never latent inventory.

Added terminal inputs: terminal-to-ambient rise, R-phase current squared, terminal change over 30 minutes, ambient temperature, and terminal excess above the assumed nominal current-heating relation.

Eight raw core measurements and two optional measured channels underlie these derived inputs. Existing loading, imbalance and undervoltage warnings remain engineering rules, not new learned fault detectors. Hotspot estimates are not measured hotspot evidence.

Pressure, internal bushing dielectric faults, calibrated mechanical vibration, internal short circuits, measured impedance changes and measured hotspots remain UNASSESSED. V4 has no target measurements to train these. Other-rating reference measurements and fast waveform benchmarks were excluded from training.

## Training and tournament

- Primary train partition: 145,152 rows in 36 histories / 12 parameter groups.
- Additional train oil controls: 41,472 rows in 72 histories, sharing those groups.
- Validation: four separate parameter groups; only these select model settings.
- Fixed tournament: 7 thermal LR configurations, 6 oil LR configurations and 6 terminal LR configurations. Each searches 8 fixed thresholds and 2 persistence choices on validation only.
- Training-only imputation, scaling, class balancing and negative weighting. No IDs, timestamps, scenario names, latent profiles, latent fault labels or external reference records are predictors.
- All three winners were locked before a new test was generated. No weights, feature selection, thresholds or persistence were changed after testing.
- The older sealed_acceptance partition has been used in earlier development. It is regression evidence, not a fresh test.
- Fresh test: six newly sampled profiles, 12 primary histories (48,384 rows) and 36 oil-control histories (20,736 rows), generated after lock. Independent seeds/profiles, SAME simulator and assumptions; no field validation.

## Fresh synthetic test: honest comparison

| Thermal measurement | Original deployed LR + runtime | V4 selected LR + runtime |
|---|---:|---:|
| Events detected | 20 / 23 (86.96%) | 22 / 23 (95.65%) |
| Median onset delay among detected events | 162.5 minutes | 82.5 minutes |
| False episodes per negative-truth day | 0.0705 | 0.1269 |
| Assessed rows | 74.84% | 93.12% |
| Positive-row precision | 96.79% | 91.33% |

V4 detected more events sooner, with MORE false alarms and lower precision. It is not uniformly better. Runtime history/warmup policies differ, so this is a system comparison; increased coverage is not solely a model-weight improvement. Severe events: original missed 3; V4 missed 1. Long-tail delays remain substantial (V4 p90 218 minutes).

Oil: 97.88% precision, 95.73% recall on assessable positive rows, BUT 55.24% recall including unassessed positive rows and 55.08% overall coverage. Continuous 24-reading history and missing measurements substantially limit oil monitoring. Gauge-bias controls still generated 471 false-positive rows; stable gauge bias and actual depletion can be observationally ambiguous. This detector reports suspected depletion, not confirmed leakage, leak rate or cause.

Terminal: 97.32% precision, 95.25% recall on assessable positives, 82.06% recall including unassessed positives, 83.40% coverage. Only R-phase LV contact heating is supported; this does not diagnose internal HV bushing faults.

All heads pass their prospectively declared synthetic gates. Optional gates apply to precision and recall among assessable rows; they do NOT establish comprehensive sensor coverage. Gate passage does not establish deployment readiness or field accuracy. The oil coverage issue and higher thermal false alarm rate remain development priorities.

## Kill-first and integrity

480 checks passed, including dataset-file hashes, key alignment, group isolation, causal prefix/suffix attacks, truth-column exclusion, missing sensors, invalid values, availability overrides, communication loss, missing-history breaks, calibration mismatch, cadence corruption, model serialization and tamper rejection. Most checks validate integrity and alignment; this is not a count of 480 independent fault experiments.

The locked model hash is recorded in LOCK_MANIFEST.json. Scores are uncalibrated detector scores, not failure probabilities. Training is deterministic under the recorded runtime and seeds; this release does not claim a second independently rerun training verification. Dataset generation reproducibility is documented in the unchanged V4 dataset package.

## Run the trained model offline

Use Python 3.13 and install requirements.txt in an isolated environment. From this folder:

    python runtime/voltmind_v4_lr_runtime.py --input examples/v4_input.csv --calibration examples/calibration.json --output predictions.csv

For your own input, supply the canonical columns replay_id (or asset_id) and timestamp_IST, ordered at five-minute intervals. Measurements use volts, amperes, Celsius, and oil level as a 0-to-1 fraction. Other schemas/units need an explicit adapter; the runtime does not guess them. Split multiple asset histories into groups; one calibration JSON must match each asset. Without suitable verified asset-specific healthy commissioning, thermal output abstains. The examples' calibration is synthetic and only matches that example asset.

Missing optional oil/terminal columns yield unassessed optional outputs while available thermal inputs can still be evaluated. Missing core measurements cause thermal abstention. Extra columns are ignored. Blank results mean unavailable or insufficient history, not healthy. No pressure/bushing/internal-short prediction is silently filled with normal.

Oil geometry (190 L reference, 30 L effective gauge, expansion coefficient 0.000725/K) and nominal terminal heating are simulator assumptions. The offline optional outputs retain a synthetic-research status. Do not use them operationally without sensor/geometry calibration and measured validation.

## Package and application status

models/100kVA_LR_V4_LOCKED.joblib is the final locked LR bundle for this round. runtime/ contains the offline predictor; calibration/ contains synthetic asset-bound calibration examples; reports/ contains all comparisons, tournament rankings, test metrics, failures and limitations. Candidate models are retained for audit.

reproduce/ contains the actual training and generator scripts. The training audit script retains the original workspace paths and depends on the previous tournament's cached baseline comparisons/calibration and runtime; it is an audit source, not a one-command portable trainer. Offline inference is portable with the included runtime, model and requirements.

The full delivery ZIP also includes the unchanged SCADA V4 dataset ZIP with its source documents and provenance. The live app, Spring Boot service and deployed model have NOT been replaced. This trained three-head bundle uses a different interface from the old four-feature artifact and needs a deliberate app integration before the website displays its outputs.
