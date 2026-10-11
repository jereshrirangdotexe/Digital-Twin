# Future sensor/utility connection contract

The challenge requires design for later extension. No real IoT sensor, SCADA utility feed or MQTT broker is currently connected. Do not describe historical playback as a live physical sensor feed.

The CSV input adapter already resolves explicit channel mappings, units, timestamps, quality, and asset identity. A future collector can normalize the physical feed into that input contract, then call the same persistent frozen runtime. Keep the Spring Boot/Python API boundary and dashboard SSE payload. The two-hour assessment publisher consumes the same genuine per-row outputs and needs no retraining.

Required measured channels are timestamp, R/Y/B phase-neutral RMS voltage (V), R/Y/B current (A), ambient temperature (C), top-oil temperature (C), and an explicit communication indicator where available. Asset identifier must bind to 100-kVA engineering configuration and independently verified commissioning. The bundled replay_id becomes asset_id through the adapter; replay IDs are not real asset inventory evidence.

The locked model assumes five-minute causal samples. A collector must define aggregation and timestamps for faster physical sampling, validate that such aggregation is compatible with the model, and mark incomplete intervals honestly. Do not fill missing sensor values, silently interpolate outages, combine assets' histories, or infer electrical conventions from numbers. Communications and sensor validity must remain distinct from physical condition.

Suggested implementation sequence:

1. Obtain the actual hardware/utility protocol, credentials, voltage convention, nameplate and data-quality flags. Choose its supported client (for example, an actual utility HTTP endpoint, MQTT topic or OPC-UA server).
2. Build a collector that produces normalized five-minute asset rows. First save them as a compatible CSV and validate with ADD A DATASET. Reject incompatible rating/schema/cadence.
3. Introduce a separately selected LIVE session using the existing per-asset runtime and an append-only queue instead of finite replay rows. Keep replay controls separate from live collector controls; do not silently restart monitoring on page visit.
4. Verify ordering, duplicate/backward timestamps, outage handling, reconnects and independently verified commissioning on recorded physical data. Retain raw evidence alongside results.
5. Add authentication, transport security, persistent storage and approved utility deployment only when leaving loopback. Confirm alert responsibilities with qualified operators.

This contract makes the architecture extensible. It is not a claim that those protocol connectors, production security or physical validation have been implemented.
