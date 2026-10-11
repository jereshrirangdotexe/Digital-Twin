# VoltMind — Distribution Transformer Digital Twin

An open-source local prototype for replaying SCADA, comparing measured and expected transformer temperature, and investigating condition warnings.

**React + Vite → Spring Boot → Python model worker.** All three services run locally. No cloud account, API key or paid chatbot service is required.

## Features

- Full-size historical graphs with date selection, actual versus expected oil temperature, load and phase measurements.
- Locked **100-kVA V4 Logistic Regression**, with separate experimental oil-depletion and terminal-heating detectors.
- Independent **250-kVA histogram boosting** and **630-kVA physics** runtimes, with their original datasets and calibration.
- Two-hour health/risk summaries, immediate incidents and explicit unavailable-data states.
- Thermal DNA, fault investigation, local incident memory, maintenance evidence and what-if projections.
- Floating local assistant, processed-data insights and exportable reports.
- A labelled **4,032-row thermal demonstration**: normal response → injected excess heat → recovery.

Local datasets and commissioning are synthetic. This is a research/hackathon prototype, not field-certified protection. Synthetic demonstrations do not prove real-world accuracy. Unmeasured short circuits, internal bushing damage, pressure faults and remaining useful life have no trained diagnosis. Missing inputs remain unavailable.

## Get the complete project

Install [Git LFS](https://git-lfs.com/) before cloning. Larger original CSVs use LFS; models and the small demo remain directly included. Replace the URL with this repository's URL:

```sh
git lfs install
git clone <repository-url> VoltMind
cd VoltMind
git lfs pull
```

If a downloaded GitHub source ZIP contains LFS pointer text instead of CSV readings, use a clone with LFS. The prepared full source release ZIP contains actual CSV bytes.

## Install and run on Windows

Install Python **3.13 64-bit**, Java **JDK 17+**, Node.js **22+**, and Git LFS. Python, Java and Node must be on PATH. Use a short writable folder such as `C:\Projects\VoltMind`.

```bat
install_voltmind.bat
start_voltmind.bat
```

Wait for **Installation complete**, then start. Open **http://localhost:5173/**, choose a rating/replay and click **RUN ON LOCAL DATA**. Starting the services alone does not start a replay.

The launcher starts and checks all three services. `stop_voltmind.bat` stops launcher-owned processes. Avoid duplicate servers on occupied ports.

### Run manually

After installation, use three separate terminals:

```powershell
# Terminal 1 — project root
.venv\Scripts\python.exe ml\main.py --serve --port 8765

# Terminal 2 — backend
cd backend
.\mvnw.cmd spring-boot:run

# Terminal 3 — frontend
cd frontend
npm run dev
```

IntelliJ can replace terminal 2. Python is still required. Defaults: frontend **5173**, backend **8080**, worker **8765**. Optional variables are in [.env.example](.env.example); backend/worker do not automatically load that file.

### Linux/macOS manual setup

The batch launcher is Windows-only. With Python 3.13 and the same Java/Node prerequisites:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
cd frontend
npm ci
npm run build
cd ../backend
bash mvnw -B test package
cd ..
```

Then run `.venv/bin/python ml/main.py --serve --port 8765`, `bash mvnw spring-boot:run` from `backend`, and `npm run dev` from `frontend` in separate terminals. The reviewed desktop installation is Windows; these manual instructions support other platforms without the Windows launcher.

## Present the thermal twin

Select **100 kVA → JUDGE DEMO · thermal twin · synthetic → 60x → RUN ON LOCAL DATA**. In **Monitor → Live Twin**, choose **1 February 2026** (normal), **10 February** (excess heat), then **14 February** (recovery). Read [the demo guide](data/demo100/README.md).

The 4,032 five-minute sample slots cover fourteen days. Speed changes playback time, not historical time. Warm-up is explained separately from warnings. The detector records the injected thermal episode and later recovers; recorded incidents stay visible.

## Upload another dataset

100 kVA supports CSV/TSV/TXT/XLSX/JSON/JSONL/NDJSON with explicit timestamps and asset identity. Supply clear column names/units or mappings and matching calibration, or separate independently verified healthy commissioning. Thermal inference abstains without valid calibration. Extra columns do not become trained features; missing sensors are not filled automatically. The final 100-kVA runtime requires native five-minute samples.

See [input/calibration](docs/INPUT_AND_CALIBRATION.md), [100-kVA compatibility](docs/DATASET_COMPATIBILITY_100KVA.md) and [rating behavior](docs/THREE_RATING_INTEGRATION.md). An organizer sensor checklist is not timestamped SCADA.

## Repository layout

| Folder | Contents |
| --- | --- |
| `frontend/` | React interface, charts, assistant and tests |
| `backend/` | Spring Boot proxy and Maven wrapper |
| `ml/` | Worker, integration, frozen models and calibration |
| `data/` | Original synthetic SCADA, commissioning, metadata and demo |
| `examples/` | Example inputs, mappings and synthetic outputs |
| `tests/` | Model, integration and HTTP checks |
| `scripts/` | Launcher, demo generator, validation and public packaging |
| `docs/` | Architecture, contracts, model behavior and release guide |

Model cards and training READMEs inside frozen bundles describe their respective releases. Current application behavior is described here and in [final intelligence](docs/FINAL_INTELLIGENCE.md); older reports are historical evidence.

## Validate

```powershell
.venv\Scripts\python.exe scripts\prepare_github.py --check
.venv\Scripts\python.exe -m pytest tests -q
cd frontend
node --test tests/*.test.mjs
npm run build
cd ../backend
.\mvnw.cmd -B test
```

GitHub Actions runs source checks. HTTP workflows create sessions: use a separate test instance. [Artifact checksums](docs/ARTIFACT_CHECKSUMS.json) identify original protected model/data bytes. LFS changes storage, not checked-out dataset bytes.

## License and data handling

Original project work is released under [MIT](LICENSE), subject to retained third-party rights and [notices](THIRD_PARTY_NOTICES.md). Local `.state/` evidence, uploads, logs, dependencies and builds are excluded from public source. External organizer documents and research publications are not redistributed.

Read [security](SECURITY.md), [contributing](CONTRIBUTING.md), [publishing instructions](docs/GITHUB_RELEASE.md) and [current installation scope](START_HERE.md).
