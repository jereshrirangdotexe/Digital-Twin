"""Publish evidence summaries every 24 historical rows; never changes ML output."""
import copy

ROWS = 24
PRIORITY = {'DATA_REQUIRED': 0, 'ROUTINE_OBSERVATION': 1, 'TREND_REVIEW': 2,
            'REVIEW_OPERATING_WARNING': 3, 'RESTORE_TELEMETRY': 4,
            'VERIFY_SENSORS': 5, 'PROMPT_INSPECTION': 6}


class AssessmentWindow:
    def __init__(self):
        self.pending = []
        self.latest = None
        self.published = 0

    def update(self, payload, final=False):
        # Store only this block; returned snapshots never share mutable state.
        self.pending.append(copy.deepcopy(payload))
        if len(self.pending) == ROWS or final:
            rows = self.pending
            twins = [r['digitalTwin'] for r in rows]
            valid = [t for t in twins if t['healthIndex'] is not None]
            representative = max(twins, key=lambda t: PRIORITY[t['maintenancePriority']])
            twin = copy.deepcopy(representative)
            health = round(sum(t['healthIndex'] for t in valid) / len(valid), 1) if valid else None
            risk = round(100 - health, 1) if health is not None else None
            twin.update(healthIndex=health, riskScore=risk,
                healthBand=('OBSERVED_STABLE' if health >= 75 else 'WATCH' if health >= 55 else 'ELEVATED_STRESS' if health >= 35 else 'HIGH_STRESS') if health is not None else 'UNASSESSED',
                riskLevel=('LOW' if risk < 30 else 'MODERATE' if risk < 50 else 'HIGH' if risk < 75 else 'CRITICAL') if risk is not None else 'UNASSESSED',
                formulaComponents=None,
                scoreScope='Mean of assessable per-row prototype health scores within the published block; not a current reading or certified asset health.')
            thermal = sum(r['ml']['thermalAlert'] is True for r in rows)
            electrical = sum(any(r['ml'][k] is True for k in ('phaseLoadingWarning', 'undervoltageWarning', 'imbalanceWarning')) for r in rows)
            offline = sum(r['telemetry']['communicationAvailable'] is not True for r in rows)
            sensor = sum(r['ml']['assetCondition'] == 'SENSOR_SUSPECT' for r in rows)
            optional = sum(r['ml'].get('oilAlert') is True or r['ml'].get('terminalAlert') is True for r in rows)
            condition = 'THERMAL_ALERT_OBSERVED' if thermal else 'SENSOR_REVIEW_REQUIRED' if sensor else 'OPTIONAL_SENSOR_ALERT_OBSERVED' if optional else 'OPERATING_WARNING_OBSERVED' if electrical else 'DATA_INTERRUPTED' if offline else 'UNASSESSED' if not valid else 'NO_ALERT_OBSERVED'
            twin['explanation'] = (f"Published block: {len(valid)}/{len(rows)} rows assessable; "
                f"{thermal} thermal-alert, {electrical} electrical-warning, {offline} offline and {sensor} sensor-suspect rows. "
                'Health is the mean of assessable scores only; excluded readings are not assumed healthy. '
                'Maintenance reflects the highest-priority evidence observed in this block. '
                'Synthetic reference calibration and prototype score limitations still apply.')
            twin['suggestedReviewTiming'] = {
                'PROMPT_INSPECTION': 'Review promptly when the alert is observed; do not wait for the next summary.',
                'VERIFY_SENSORS': 'Verify sensors before relying on another health assessment.',
                'RESTORE_TELEMETRY': 'Restore telemetry before interpreting current condition.',
                'REVIEW_OPERATING_WARNING': 'Review the operating warning before continuing unchanged operation.',
                'TREND_REVIEW': 'Review the trend before the next two-hour assessment block.',
                'ROUTINE_OBSERVATION': 'Continue monitoring; review the next two-hour assessment.',
                'DATA_REQUIRED': 'Collect clean model history before scheduling maintenance from this score.',
            }[twin['maintenancePriority']]
            self.published += 1
            self.latest = dict(number=self.published, firstTimestamp=rows[0]['timestamp'], lastTimestamp=rows[-1]['timestamp'],
                firstRow=rows[0]['replay']['processedRows'], lastRow=rows[-1]['replay']['processedRows'],
                rows=len(rows), partial=len(rows) < ROWS, assessableRows=len(valid),
                coveragePct=round(len(valid)/len(rows)*100, 1), thermalAlertRows=thermal,
                electricalWarningRows=electrical, offlineRows=offline, sensorSuspectRows=sensor,optionalAlertRows=optional,
                condition=condition, digitalTwin=twin)
            self.pending = []
        return dict(policy='24_ROWS_2_HOURS', targetRows=ROWS, historicalMinutes=120,
            pendingRows=len(self.pending), publishedCount=self.published,
            latest=copy.deepcopy(self.latest), publishedOnThisRow=not self.pending,
            nextUpdateAfterRows=ROWS-len(self.pending) if not final else 0)
