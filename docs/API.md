Current release: 100, 250 and 630 kVA are integrated. See docs/THREE_RATING_INTEGRATION.md and reports/630_INTEGRATION_VALIDATION.md for activation, native physics-detector scope, 24 × 8,064 rows and 336 two-hour summaries per 630-kVA replay. Earlier sections remain historical rating-specific instructions.

Update: this document originally describes the 100-kVA integration. Both 100 and 250 kVA are now supported; see docs/MULTI_RATING_INTEGRATION.md for the separate 250-kVA model, 24 replays × 6,048 rows, current bases, 40-MiB/200,000-row limits and API. The existing presentation demonstrates 100 kVA; the live dashboard can demonstrate either rating.

# API and streaming contract

The health response now includes `assessmentPolicy: 24_ROWS_2_HOURS`. Each current/history/SSE reading adds `assessment` alongside the original `ml` and `digitalTwin` fields. The original per-row fields retain their original meaning and precision. Use `assessment.latest.digitalTwin` for the main published Health Index/risk/maintenance, and `assessment.latest.condition` for the block condition. `assessment.latest` is null before the first publication. It remains unchanged between block boundaries. `publishedOnThisRow`, `pendingRows`, `targetRows`, and `nextUpdateAfterRows` describe publication progress. `latest` contains timestamps, row bounds, assessable/total rows, coverage and warning/outage counts. Final short blocks set `partial=true`. Restart/source changes reset all published assessment state.

Use the website origin `http://127.0.0.1:5173/api`; Vite proxies to Spring Boot, which forwards to loopback Python. All responses are JSON and no-store, except SSE. Errors contain `error` and `status: FAILED`. Request size limit is 20 MiB.

| Method | Route | Input / result |
|---|---|---|
| GET | /health | model identity/hash, worker instance, engineering context, inference counter, active ID |
| GET | /datasets/local | actual local filename, validation steps, replay IDs/counts; no inference |
| POST | /replay/local/start | replayId, speed, optional options/schema/units/calibration; creates session |
| POST | /datasets/upload | multipart file, optional JSON options, separate commissioning CSV; returns202 datasetId/status |
| GET | /datasets/status?datasetId=… | validation stage or READY/FAILED with reason |
| POST | /replay/uploaded/start | datasetId, replayId, speed; creates session |
| POST | /replay/play, /replay/pause, /replay/resume | sessionId |
| POST | /replay/restart | sessionId; returns new sessionId |
| POST | /replay/stop | sessionId; clears active selection |
| POST | /replay/speed | sessionId, speed in1/5/10/30/60 |
| POST | /replay/cancel | clientId/generation cancels that client's preparation selection |
| POST | /datasets/delete | datasetId; owned upload only, stop first |
| GET | /replay/status?sessionId=… | status, source, cursor/progress, speed |
| GET | /transformers/current?sessionId=… | most recent actual payload, null before first row |
| GET | /transformers/history?sessionId=…&after=0&limit=10000 | retained history with original ML and Twin outputs |
| GET | /transformers/alerts?sessionId=… | backend alert transitions, evidence and ACTIVE/RESOLVED state |
| GET | /transformers/maintenance?sessionId=… | current Digital Twin recommendation and evidence |
| GET | /replay/stream?sessionId=…&after=0 | SSE reading/status/ended, heartbeat comments |

Source starts can carry clientId and positive integer generation; older generation requests reject409. Current session ID is required for controls/history/stream. Replaced IDs reject409; absent session404. Worker failure503 is explicit through Spring Boot.

Reading payload extends the preserved `contractVersion:1.0` with `sessionId`, `sequence`, `source`, `processedAt`, and `replay`. It retains asset, timestamp, telemetry, ml, calibration and quality without numerical rewrites. `digitalTwin` adds the documented observation index/rule fields. Refer to the actual `examples/frontend_payload.json` and `examples/streaming_output.txt`.

SSE event ID equals processedRows. Reading events are emitted once per retained computed row; Last-Event-ID takes precedence over the query cursor on reconnect. Status events report RUNNING/PAUSED/COMPLETE/FAILED/STOPPED. Ended reports completion or SESSION_REPLACED. Reconnect recovers existing retained outputs; it is never a model replay/restart. Buffer retention is 10,000 rows.
