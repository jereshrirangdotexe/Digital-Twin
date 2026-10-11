# VoltMind 250-kVA Prototype ML v1.0
Status: LOCKED. Winner: hist_boosting; runner-up: logistic_250.
Target: condition_excess_thermal_response. Hierarchical outputs: binary thermal condition plus independent electrical condition screens and data-quality warnings. The pipeline includes TRAIN-fitted median imputation and scaling. Supervised TRAIN labels are targets only, as explicitly authorized by the user.

Official group partitions; no random row split. Selection uses validation mean event recall across three seeds, worst event recall, row recall, false alarms; seed 250 is fixed in advance. Threshold constrains assessed negative-row false alarm rate to at most 1% in every validation replay using a strict greater-than comparison. This is a validation operating point, not a field guarantee. Probabilities are uncalibrated scores; Brier/ECE/PR-AUC are reported on assessed rows. No confidence claim is made.

Features (13): mean_phase_voltage_V, voltage_imbalance_pct, loading_pct, max_phase_loading_pct, current_imbalance_pct, oil_rise_K, oil_change_30min_C, oil_change_60min_C, past_loading_mean_180min_pct, past_ambient_mean_180min_C, past_loading_mean_360min_pct, past_ambient_mean_360min_C, nominal_oil_residual_C.
Threshold: 0.962225144456; persistence: 1 samples. Electrical screens: any phase >110% rated current for three samples, any phase voltage <90% nominal, current magnitude imbalance >15% for three samples. Gauge remains unsupported.

## Reported limitations
All measured performance is synthetic. Independent field validation and verified healthy commissioning: NOT AVAILABLE IN PROVIDED PACKAGE. The nominal thermal twin uses global assumed 280 W no-load loss, 2200 W load loss, 33 K rise, exponent 0.8 and 155.531 min time constant. These are reference assumptions, not any replay's hidden calibration. Weather-dependent cooling, solar heat, asset variability and sensor bias are not separately observable. Residuals therefore confound physical degradation and model mismatch.

The thermal classifier predicts an observable excess-temperature condition, not a root cause, future failure, RUL or maintenance action. Sensor faults can still contaminate thermal alarms; the quality guard does not guarantee sensor diagnosis. Mild and slowly evolving faults can be missed. The first 24 hours and quality holdoffs are unassessed, not healthy. Full-population recall counts these abstentions as misses. A single incoming row cannot initialize the history-based model into a valid health verdict.

LOW_OIL_GAUGE has zero coupling to BASIC sensors and is explicitly unsupported. Labeled voltage/current sensor problems: NOT AVAILABLE IN PROVIDED PACKAGE. Missing or invalid inputs produce nullable condition flags; positive electrical evidence on an available phase is retained. A normal output means no supported screen fired, not that the transformer is fault-free.

The streaming adapter preserves exact history and batch parity but its memory and update cost grow with uptime; it is a reference prototype implementation. Histories must be reset deliberately when an asset changes. Long communication outages can leave nominal-state uncertainty beyond the fixed one-hour holdoff. No automatic protective switching is implemented. Additional field commissioning is outside this frozen ML-only task.

Nominal expected oil uses previous-interval observed drivers and a causal zero-order-hold recursion. The simulator records interval-end oil using current-interval drivers; this convention difference is an approximation. Physical sequence and rolling history are permitted; calendar/time-of-day/replay labels never enter the estimator. Sensor quantization and synthetic event shapes can still provide distribution-specific fingerprints. Model comparison cannot prove their absence.


## Runtime v1.0.0
The locked classifier, its 13 features and threshold remain byte-for-byte unchanged. The incremental runtime matches all 145,152 frozen rows and the original scores. Official TRAIN R01–R12, VALIDATION R13–R16, IID R17–R20 and SHIFT R21–R24 remain unchanged. No acceptance data retuning or new model hunting was performed.

Organizer schema adaptations are input plumbing, not evidence of organizer accuracy. The compatibility matrix tests explicit schema/unit normalization, nullable missing inputs, time-grid safety and serialization. Safe-handling PASS does not mean every plausible sensor fault was diagnosed. Physical accuracy remains limited by the frozen synthetic evaluation, including missed thermal events and SHIFT false alarms. New real organizer/field accuracy is NOT AVAILABLE IN PROVIDED PACKAGE.

Reference calibration is a global assumption and reduces data confidence. Valid supplied calibration or verified separate commissioning affects displayed expected temperature and residual; classifier features remain tied to their frozen nominal reference. nominalModelResidualC exposes the classifier residual. ML_USES_FROZEN_REFERENCE_FEATURES makes this distinction explicit. Changing displayed calibration is not retraining or calibrating failure probabilities.

Temperature/current/voltage plausibility rejection is a data-quality guard, not fault diagnosis. Plausible in-range sensor corruption may remain undetected. Exact one-hour oil flatlines require nominal movement before suspicion; stable low-excitation stuck sensors can remain indistinguishable from steady operation. Raw spikes and communication failure never force a thermal fault. A 12-sample quality holdoff and 24-hour warmup suppress unsupported thermal assessments. Long gaps/outages reinitialize safely.

Five-minute snapshots are the model's actual temporal requirement. Finer rows are retained but off-grid thermal results are unassessed. Coarser/irregular intervals cannot be interpreted as trained five-minute dynamics; bounded missing slots are explicit, and long gaps rewarm. No future interpolation is performed. Unavailable measurements are null, never fabricated. Canonical NORMAL means the supported condition screens did not trigger at that row; it is not proof of no faults.
