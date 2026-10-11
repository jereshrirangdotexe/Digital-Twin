Update: this document originally describes the 100-kVA integration. Both 100 and 250 kVA are now supported; see docs/MULTI_RATING_INTEGRATION.md for the separate 250-kVA model, 24 replays × 6,048 rows, current bases, 40-MiB/200,000-row limits and API. The existing presentation demonstrates 100 kVA; the live dashboard can demonstrate either rating.

# Four-minute live demonstration

Before presenting: install once, start Python ML + Spring Boot + React (or start_voltmind.bat), and check http://localhost:5173. Close duplicate app instances. Prepare examples/example_organizer_input.csv and examples/communication_outage.csv. Keep the hardware/model limitations visible.

0:00–0:30 — Explain that VoltMind is a 100-kVA prototype. Show the empty dashboard and source buttons. SCADA CSV is a five-minute sensor notebook, not an identified real transformer. R00–R11 are separate simulated stories, not consecutive dates.

0:30–1:45 — Select a replay, choose 60x and RUN ON LOCAL DATA. Show progress, expected versus actual oil, loading, phase measurements and the automatic 24-row assessment. At this speed a fourteen-day replay takes about 67 seconds plus overhead. Explain early unassessed blocks: the frozen thermal model first needs more than 288 history samples. Point out that the main health/risk summary is the mean of assessable scores in a historical two-hour block; live warnings are not delayed.

1:45–2:30 — After completion, open Analytics and Alerts. Use the date/time axis to explain trends. Show coverage and the Maintenance page; an alert observed in a block retains its review priority rather than being averaged away. Show that RUL and aging are unavailable. If selecting another replay, make clear that it clears previous history and starts fresh.

2:30–3:15 — Download readings CSV, summary JSON and a printable report. Open the saved HTML report and show its window summaries, measurement statistics, alert history and method/limitations. Print / Save as PDF is optional. Upload the organizer example to demonstrate measured data compatibility. No model retraining is performed.

3:15–4:00 — Summarize validation: 48,384 internal rows, preserved hardened 38/60 synthetic thermal event baseline, healthy thermal controls without thermal alarms. Mention missed events and unassessed rows. Show communication_outage.csv only if time allows: offline does not become healthy. Explain the future sensor input contract and need for physical validation and asset-specific commissioning.

Use the accompanying VoltMind_Hackathon_Demo.pptx as the short presentation. Do not claim a trained 250-kVA model is connected, all faults are detected, the score is field certified, or maintenance/failure dates are predicted.
