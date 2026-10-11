Current release: 100, 250 and 630 kVA are integrated. See docs/THREE_RATING_INTEGRATION.md and reports/630_INTEGRATION_VALIDATION.md for activation, native physics-detector scope, 24 × 8,064 rows and 336 two-hour summaries per 630-kVA replay. Earlier sections remain historical rating-specific instructions.

Update: this document originally describes the 100-kVA integration. Both 100 and 250 kVA are now supported; see docs/MULTI_RATING_INTEGRATION.md for the separate 250-kVA model, 24 replays × 6,048 rows, current bases, 40-MiB/200,000-row limits and API. The existing presentation demonstrates 100 kVA; the live dashboard can demonstrate either rating.

# The dataset and dashboard, in simple words

Think of a transformer as a little machine that gets warm while doing work. The dataset is its notebook. Every five minutes, someone writes down how hard it is working, how hot its oil is, and how warm the outside air is. One notebook entry is one CSV row.

The correct term is SCADA: Supervisory Control and Data Acquisition. The supplied CSV is simulated SCADA-style data, not an identified physical utility transformer recording. It was supplied with the project; this integration did not regenerate it or change its measurements.

## R00 through R11

These are twelve separate simulated replay stories. They are not timestamps and are not evidence of twelve identified real transformers. Each story contains 4,032 rows at five-minute intervals, covering April 5, 2026 at 00:00 through April 18 at 23:55 IST. R01 does not happen after R00. All twelve cover the same dates with different measurements and operating events. R05 and R11 were used as healthy thermal controls; zero thermal alarms does not mean zero electrical warnings.

12 rows = one historical hour. 24 rows = two historical hours. 288 rows = one historical day. 4,032 rows = fourteen days of five-minute sample slots. The elapsed time between the first and last recorded sample is thirteen days, 23 hours, 55 minutes because there is no extra sample at the start of day fifteen. Dataset total: 48,384 rows.

## The two clocks

Historical time is the time written in the CSV. Playback time is how quickly your computer examines it. At 1x the app processes about one row per second; 5x processes about five per second; 60x about sixty per second. A 4,032-row replay takes about 67.2 seconds at 60x, plus processing/transport overhead. Two-hour blocks take about 0.4 seconds at 60x, 4.8 seconds at 5x, and 24 seconds at 1x. These speeds do not change the model's five-minute historical interval. A two-hour assessment does not mean waiting two real-world hours during a sped-up replay.

## What happens after pressing Run

The server validates the file, selects only your chosen replay, and processes its rows in timestamp order. It uses past and current rows, never future answers. Graphs grow while rows arrive; they do not need all 4,032 rows to be processed. At completion, graphs retain the examined history and replay progress stops. Selecting another replay or restarting starts fresh and clears the previous session's history and summary.

The Overview is a summary of the selected replay, not a combined fleet health estimate. Live Twin compares the measured transformer to its mathematical thermal model. Analytics shows measurements and published assessment history. Alerts shows actual recorded operating/data/model alerts. Maintenance shows the last published block's highest-priority recommendation with its evidence. Assets lists replay identifiers and the configured 100-kVA model information.

## Reading each graph

- Actual oil: the CSV's recorded oil temperature. Expected oil: the thermal model's estimate under the recorded load and ambient temperature. A sustained difference is useful evidence.
- Thermal residual: actual minus expected oil temperature, in degrees C. Positive means hotter than expected; it is not an automatic failure diagnosis.
- Loading: estimated electrical utilization as a percentage of the 100-kVA rating. A value near 100% means close to rated utilization.
- R/Y/B voltage and current: measurements for the three electrical phases, in volts and amperes. R00 replay IDs have nothing to do with the R electrical phase.
- Ambient: the recorded surrounding air temperature.
- Thermal score: the supplied ML pipeline's score. It is not a calibrated probability of failure.
- Health/risk: one point per published assessment block; mean of usable prototype row scores only. Gaps are unassessed blocks, not zero health. Date and time are now shown on chart labels to distinguish multiple days.

Horizontal graph axis = historical time. Vertical axis = the selected measurement's units. Charts display at most about 300 representative points for speed; full retained readings remain available for export, up to the 10,000-row retention limit. Short spikes can be absent from the sampled plot, so use recorded alerts/exported readings to examine them.

## Why the old page flickered

Previously the main health and condition cards displayed the latest individual row. A valid row could have no model alarm, the next could have a warning, and another could have missing communications or suspect sensors. These are distinct observations. Unavailable means the model cannot judge reliably; it does not mean failed or healthy. Initial warm-up and recovery after data loss can also withhold the score. The frozen thermal runtime requires more than 288 initial history samples and a clean recent window; merely processing 24 rows cannot bypass that requirement.

## Your new two-hour update rule

The backend publishes a summary after rows 24, 48, 72 and so on. Between these boundaries, the main Health Index, risk, block condition and maintenance guidance remain fixed. Live measurements, communication/data-quality indicators and alerts still update, and are clearly separate from the historical summary.

For a block, average only the numeric health scores that the existing model and interpretation allowed. Report the usable/total count and coverage. Risk is 100 minus that rounded mean health. All-unassessed blocks have no numeric health or risk. A block containing a thermal alarm retains a thermal-alert-observed condition and prompt review recommendation even if its mean score appears moderate. Maintenance retains the highest-priority observed issue; sensor and communication problems cannot be concealed by a healthy mean. A shorter final block in an uploaded file publishes once and is explicitly marked partial. No previous replay's result is reused.

The 24-row duration is nominally two hours only when data maintains five-minute sampling; actual first/end timestamps are shown so gaps cannot imply continuous coverage. This is a block summary, not a new ML model or current health certificate. The frozen per-row predictions, thresholds and calibration are unchanged.

## Downloads

The reporting controls save readings CSV, summary JSON, or a printable HTML report. The report includes measurement trends, published assessment history, alerts, coverage, model/calibration information and limitations. Open the HTML file and choose Print / Save as PDF if desired. Exports contain only processed readings retained by this browser session; they do not include unseen future rows.

For a slow demonstration use 1x or 5x. At 60x, a two-hour block publishes several times per real second, so you will still see the summaries change quickly until the full fourteen-day replay finishes.
