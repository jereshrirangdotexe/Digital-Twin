# Final integration architecture and preservation plan

Inspected 11 October 2026. Active project: this directory. React 18/Vite 6 with Recharts calls Spring Boot 4.1.1 on 8080; Spring proxies a persistent Python HTTP/SSE service on 8765. Vite serves port 5173. Existing 250 and 630 kVA runtimes and datasets remain authoritative for those ratings.

The user supplied a final 100 kVA LR V4 hardened package and V4 SCADA archive. These are selected for 100 kVA inference. Their trained artifacts and data are copied without alteration under ml/final100 and data/final100. The previous ml/model artifact and old datasets remain unchanged. Selection of the supplied final release is an explicit integration change, not retraining or a silent retuning of the old model.

The final LR bundle contains thermal, oil and terminal heads. Supporting bridge code preserves its feature equations, thresholds, calibration guards and causal history. Local V4 commissioning calibrations are synthetic, independently generated healthy histories, not field verification. Uploaded data without suitable calibration remains thermally unassessed.

Additional intelligence lives under ml/intelligence.py, with SQLite persistence in .state/intelligence.sqlite. Only measurements and model outputs enter that store. Runtime never reads latent labels, events or generator profiles. Independent simulation does not feed monitoring. Spring allowlists its additional APIs. React renders point explanations, full processed-history summaries, evidence, maintenance, recurrence and Thermal DNA from backend outputs.

Recovery snapshot and protected hashes were taken before edits in the conversation work directory. All existing vendor250/vendor630 and old data/model files must retain their hashes. Baseline final model outputs are recorded before bridge activation and compared after integration. Historical 45/60 or 38/60 results describe older releases; they are not the final V4 model's benchmark.

The two-hour health publication policy is preserved. Urgent model and electrical alerts remain immediate. Health/risk are prototype observation indices, not failure probabilities or insulation life estimates. Five-minute RMS data cannot supply measured electrical waveforms; illustrative cycle views explicitly assume phase angles and sinusoidal shape.
