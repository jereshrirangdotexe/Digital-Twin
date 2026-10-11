Historical validation record for the 100-kVA release. The current combined release is validated in MULTI_RATING_VALIDATION.md; do not interpret this historical report as a 250-kVA evaluation.

# Final validation — VoltMind 100-kVA

**Update note (2026-10-08):** This package now includes automatic 24-row/two-hour assessment summaries, report downloads and submission materials. See `TWO_HOUR_UPDATE_VALIDATION.md` for the executed update checks and activation step. The full integration/fresh-folder evidence below describes the base package before this additive update; the original fresh-folder run did not include the new display/report features. Locked model/runtime/configuration and per-row predictions remain unchanged.

**Final status: CONDITIONAL HACKATHON READY.** The full local application works and preserves its supplied runtime exactly. Field validation and organizer accuracy remain unestablished; health/risk are transparent prototype indices and RUL is unavailable.

## Required final report

| Item | Executed result |
|---|---|
| Frontend used | Existing Frontend2 React18/Vite6 JSX/CSS design |
| Backend used | Existing DTBackend Spring Boot4.1.1/Java/Maven project |
| SCADA dataset | data/100kVA_SCADA_V2_BASIC.csv |
| Locked model | VoltMind_100kVA_Final_Selected_v3, LogisticRegression pipeline |
| Model hash unchanged | YES: e28ca99b1a9be248cea992362ec096bee137bdda321b3476471f4d448afbe831 |
| Model retrained | NO |
| Original vs integrated predictions | PASS: all48,384 batch dictionaries exactly equal |
| Performance preserved | PASS against supplied hardened runtime; historical unbounded benchmark remains a distinct conditional comparison |
| 100-kVA internal SCADA | PASS: 48,384 processed rows, zero failed, 15,848 explicitly unassessed |
| 12-replay completeness | PASS: R00–R11, 4,032rows each; none missing |
| Healthy controls | PASS: R05 3,661 assessable/zero thermal alerts; R11 3,672 assessable/zero thermal alerts |
| Event-level regression | PASS: supplied baseline38/60, integrated38/60;22 abnormal-rise +16 degradation events |
| Initial empty website | PASS: no inference/session/history/indices merely from visiting |
| RUN ON LOCAL DATA | PASS: real local source, asset selector and replay |
| ADD A DATASET | PASS: browser upload→backend validation→real model replay |
| Actual ML inference | PASS: genuine frozen pipeline; no frontend substitute model |
| Backend connection | PASS: real Spring Boot/Python request and SSE chain |
| Digital Twin | PASS for documented prototype behavior; CONDITIONAL field interpretation |
| Health/risk/maintenance | PASS for formulas/null handling/explanations; CONDITIONAL engineering validation |
| Streaming | PASS: single retained reading and heartbeat-only paused reconnect immediately delivered without inference repeats |
| Organizer compatibility | PASS for supported formats and safe failures; CONDITIONAL accuracy on unseen physical data |
| React dashboard | PASS: actual telemetry, navigation, time ranges, metric selectors, backend alerts and recommendations |
| Production frontend build | PASS; advisory existing large Recharts bundle warning |
| Fresh-folder test | PASS: clean extraction, fresh venv/npm/Java build, real startup, actualHTTP and browser workflows |
| Complete ZIP | outputs/VoltMind_100kVA_COMPLETE_FINAL.zip; source/model/data/tests/docs/reports, generated dependencies/caches excluded |
| One-time installation | install_voltmind.bat |
| Startup command | start_voltmind.bat |
| Shutdown command | stop_voltmind.bat |
| Verified localhost | http://127.0.0.1:5173 |

## Frozen behavior and historical reference

All supplied model/runtime/config/calibration files are byte-identical. Model SHA, feature order, preprocessing, strict decision-margin threshold13.297415516625 and original calibration policy are unchanged. Source Desktop folders were preserved. Integrated batch comparison is exact. Single-row versus vectorized scoring differs only in thermal margin at maximum 1.009e-12 and thermal score at 1.628e-13; alert decisions, quality states, calibration and other fields match exactly.

The authoritative supplied ZIP contains the already hardened runtime with60-minute driver-hold expiry and288-sample rewarm-up after prolonged loss. Its reproduced baseline is38/60 thermal events, exactly preserved here. The older v3 unbounded-driver report was45/60 (75%); this integration does not claim that figure for the supplied hardened runtime or silently weaken its missing-history policy to recover it. Detection is any thermal alarm in the full injection interval, never symptom-conditioned recall. All60 event IDs and misses remain in event_regression.csv; labels were loaded only after predictions were saved and are absent from the deployed runtime.

Event family details: {"ABNORMAL_THERMAL_RISE": {"events": 30, "detected": 22, "missed": 8, "meanInjectionDelayMin": 156.5909090909091}, "THERMAL_DEGRADATION": {"events": 30, "detected": 16, "missed": 14, "meanInjectionDelayMin": 168.75}}. R05/R11 zero thermal alarms are the healthy-control result; ordinary electrical operating warnings can still occur on healthy thermal controls and are not counted as thermal-model false alarms.

## Executed checks

28 Python tests passed (both package and fresh folder),5 Java tests passed,2 Node history tests passed,51 real adapter/runtime robustness scenarios passed. Tests include causal/future independence, streaming/batch equivalence, artifact corruption and absence, persisted runtime restart, inert offline columns, duplicates/gaps/missing cells/communication/sensor quality, schema/rating/cadence rejection, separate verified commissioning and asset binding, session controls, stale selection generations, prototype formulas and no ML feedback.

RealHTTP workflow passed through Vite→Spring→Python: metadata without inference, all five speeds, Pause/Resume, Restart with new ID, stale-ID rejection, single-row SSE recovery, heartbeat-only reconnect without model calls, organizer upload completion of360rows, genuine assessed Twin output, history/alerts, Stop and owned upload deletion. Java bridge restart preserved the same intentionally paused worker session/cursor without repeated inference. ML worker restart cleared frontend current/history/alerts and displayed an explicit failure. Browser refresh returned to idle. A–H evidence is in browser_workflow.json, with actual screenshots.

The clean-folder workflow exposed and fixed two integration defects: vendor Java PATH shims could leave child processes behind on Stop, and asynchronous servlet streaming could delay tiny paused-session events until its body completed. The launcher now resolves the real JDK executable and stops only verified owned process trees. SSE now commits servlet headers and complete events explicitly. The exact final source was retested after both fixes; fresh-folder source equality is recorded in fresh_folder.json.

## Remaining limits

- Synthetic benchmark results do not establish organizer/field accuracy; commissioned asset transfer must be validated independently.
- The deployed reference calibration is approximate synthetic calibration, not independently certified physical-transformer calibration. Data confidence remains reduced under that reference.
- Observation health/risk weights and bands are transparent prototype rules, not certified insulation health or calibrated failure probabilities. Aging and RUL are null.
- Missing measurements are never invented. Missing required upload columns reject; missing cells, outages, irregular intervals and sensor-suspect periods can withhold assessments and reset warm-up. Voltage input must be phase-neutral RMS; the parser cannot infer a wrong electrical convention from numbers alone.
- One active monitoring session per local worker;10,000-row history retention;20MiB request limit,100,000row cap,ten usable upload datasets. Multiple tabs replace one another's selected session. No authentication, remote multi-user deployment or automatic protection is implemented; services bind to loopback.
- Session state/history are in memory. Refresh is idle and unload attempts to stop its session; abrupt browser crashes may leave a replay running until Stop/service restart. No restart auto-restores stale sessions.
- First installation needs internet and installed64-bit Python3.13, JDK17+ and Node22+. This ZIP includes source, model and data, not offline language runtimes or node_modules. Registry caches were reused in the clean-folder test.
- Frontend retains the supplied React/Recharts design. Vite reports an advisory approximately592kB bundle warning; build and operation passed.

## Evidence files

model_regression.json, model_preservation_audit.json, integrated_predictions.csv, event_regression.csv, organizer_robustness.csv, organizer_compatibility.json, python_tests.xml, fresh_python_tests.xml, backend_TEST-*.xml, http_workflow.json, restart_checks.json, frontend_results.json, digital_twin_results.json, browser_workflow.json and fresh_folder.json.
