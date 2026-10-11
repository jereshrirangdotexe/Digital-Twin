# VoltMind: 100 and 250 kVA

The same React dashboard, Spring Boot API and persistent Python worker now support both supplied frozen models. Use the Transformer rating selector, choose a replay, then Run on local data. Adding a CSV uses the selected rating; when the CSV omits its rating, your explicit selection supplies it. A CSV that declares a conflicting rating is rejected. Mixed-rating files must be split.

## Activate in your existing project

Changes have been copied to <project>. Stop the Python CMD with Ctrl+C and restart:

```bat
cd /d <project>
.venv\Scripts\python.exe ml\main.py --serve
```

Stop and Run Spring Boot again in IntelliJ so the new 40-MiB request limit is active. Refresh http://localhost:5173/. Existing npm run dev can load the source changes. If you use a production preview, rebuild the frontend first. No new Python or npm dependencies are required.

For a fresh extraction, use the existing install_voltmind.bat and start_voltmind.bat. One worker serves both ratings; do not launch a second ML server for 250 kVA.

## Independent models and datasets

| Property | 100 kVA | 250 kVA |
|---|---|---|
| Frozen version | VoltMind_100kVA_Final_Selected_v3 | VoltMind_250kVA_Prototype_ML_v1.0 |
| Model | Supplied logistic model | Supplied histogram gradient boosting model |
| Rated phase current at 433 V line-to-line | 133.337 A | 333.343 A |
| Local CSV | data/100kVA_SCADA_V2_BASIC.csv | data/250kVA_SCADA_FINAL_BASIC.csv |
| Replay IDs | R00–R11 (12) | R01–R24 (24) |
| Rows per replay | 4,032 | 6,048 |
| Total measured rows | 48,384 | 145,152 |
| Historical dates | April 5–18, 2026 | April 1–21, 2026 |
| Sample interval | 5 minutes | 5 minutes |
| Two-hour blocks per replay | 168 | 252 |

IDs refer to separate synthetic replay stories, not identified physical transformers. The same R01 in different ratings is a different source. Source payloads and reports include ratingKVA to distinguish them.

The 250-kVA BASIC dataset was taken from final_challenge/250kVA_CHALLENGE_REBUILT_BASIC.csv in the supplied final SCADA archive. Its SHA256 is 6cc1e5d2545fc21906d5f2942040762e9bb787da5acd03a359c8ad87065778a1 and matches evaluation/data/BASIC.csv in the model archive byte for byte. Truth, event, profile and optional-meter files are not runtime inputs or bundled monitoring sensors.

The 250-kVA model SHA256 is bbca8e0e054b4162145b77fd834a7a8e4936b851892f536ee2fd32fac1fb018f. Vendor runtime, calibration, config and model files are preserved byte for byte under ml/vendor250. Its original README and model card describe standalone usage and source limitations. The integrated service uses the outer ml/main.py entry point. The original 100-kVA runtime and model remain unchanged. No model is retrained or thresholds altered.

## Replay and summary behavior

Rating changes stop the old session, clear its readings, alerts and summaries, clear rating-specific configuration, and load the matching replay list. Replay changes also create fresh model history. There is one active session per worker, so two browser tabs can replace each other's sessions.

Both models retain their original warm-up, communication and sensor handling. A summary publishes every 24 processed rows, using the mean of assessable per-row prototype health indices and explicit coverage. Health, risk, condition and maintenance remain fixed until the next block. Raw measurements and alarms continue updating. Missing scores remain unassessed. A complete 250-kVA replay produces 252 summaries, with the last summary covering the last two hours, not the whole 21-day average.

The first 250-kVA dataset validation processed all 145,152 rows in about 68 seconds on this computer; later local selections use a cache. The dashboard displays PREPARING while loading. Replay at 60x has a nominal minimum of 101 seconds for 6,048 rows, plus inference and rendering overhead. Playback speed does not change historical sampling or model inputs.

## Calibration and contract

Each rating uses its own supplied synthetic reference calibration by default. The 250-kVA calibration JSON uses the source model's status, rating_kva, rise_K, tau_min, bias_C, p0_W, pload_W and exponent fields. Do not reuse 100-kVA calibration JSON for 250 kVA. Invalid explicit calibration is rejected rather than silently replaced. Separate commissioning can be fitted through the source 250-kVA routine only with independently verified healthy data, sufficient duration and load excitation; the integrated UI records the user's attestation as provenance. It never automatically treats monitoring data as healthy.

The 250-kVA frontend adapter preserves all source ML and telemetry fields and adds the common quality/calibration contract for the existing dashboard. thermalAssessable follows availability of the original model score and failed flag. The 100-kVA-only residual fields remain null for 250 kVA; native 250-kVA residual fields remain available in JSON. The shared observation index uses the selected rating's current base and does not feed back into ML. Model scores from different model families should not be compared as a common failure probability. RUL, insulation aging and low-oil gauge inference remain unsupported by BASIC sensors.

CSV uploads now allow 40 MiB at React, Spring Boot and Python boundaries and up to 200,000 rows, sufficient for the supplied 22.97-MB 250-kVA BASIC file. Existing per-session history retains 10,000 rows, sufficient for either complete replay. Exported HTML, JSON and CSV carry rating context.

## API additions

GET /api/health includes supportedRatings [100,250] and models with independent version, hash and engineering bases. Legacy top-level model fields describe the 100-kVA default for compatibility; new clients use models.

GET /api/datasets/local?ratingKVA=250 loads 250-kVA metadata. Omitting ratingKVA keeps the 100-kVA default.

POST /api/replay/local/start accepts ratingKVA:250 along with replayId and speed. POST /api/datasets/upload accepts options.ratingKVA:250. Dataset and source metadata return ratingKVA. Uploaded replay start/restart retains its validated rating automatically.

The CLI batch mode remains the existing 100-kVA tool. Both ratings are integrated in --serve mode and the dashboard.
