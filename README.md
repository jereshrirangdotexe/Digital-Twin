# Digital-Twin
VoltMind is an intelligent Digital Twin for distribution transformers (100, 250 &amp; 630 kVA), combining SCADA monitoring, physics-based thermal modeling, ML-powered fault detection, explainable diagnostics, and predictive maintenance insights.
# VoltMind
### Intelligent Digital Twin for Distribution Transformer Condition Monitoring & Predictive Maintenance

**VoltMind** is an open-source Digital Twin platform designed to monitor distribution transformers, identify abnormal operating conditions, investigate potential faults, and support evidence-based maintenance decisions.

Rather than relying only on fixed temperature thresholds, VoltMind combines **physics-based thermal modeling, rating-specific detection systems, SCADA telemetry, and operating history** to compare a transformer's actual behavior with its expected behavior.

The platform supports **100 kVA, 250 kVA, and 630 kVA** distribution transformers, with advanced intelligence features developed for the flagship **100-kVA system**.

## The Problem

Distribution transformers are essential components of electrical distribution networks. Abnormal heating, overloading, voltage irregularities, sensor issues, and recurring faults can affect their operation.

Traditional threshold-based monitoring identifies when measurements cross predefined limits, but it may not fully explain why an abnormality occurs.

VoltMind addresses this problem by continuously comparing measurements with a physics-informed representation of expected transformer behavior and providing understandable evidence for investigation.

## How VoltMind Works

**SCADA Data → Validation → Thermal Physics Model → Fault Detection → Digital Twin Assessment → Maintenance Insights**

1. **Data Collection:** Ingests electrical and thermal measurements from SCADA datasets.
2. **Data Validation:** Checks timestamps, measurement availability, units, and data quality.
3. **Thermal Modeling:** Estimates expected top-oil temperature based on transformer operating conditions.
4. **Fault Detection:** Uses rating-specific detection systems to identify abnormal thermal behavior.
5. **Digital Twin Assessment:** Interprets model outputs, electrical warnings, calibration state, and operating history.
6. **Visualization:** Displays transformer conditions, alerts, trends, and explanations in an interactive dashboard.
7. **Maintenance Intelligence:** Supports investigations, evidence reporting, and operational decision-making.

The current prototype uses chronological synthetic SCADA replay to demonstrate a continuously updating monitoring system.

## Supported Transformer Models

| Transformer | Detection Approach | Synthetic SCADA Dataset |
|---|---|---|
| **100 kVA — Flagship** | Logistic Regression thermal classifier | 241,920 rows across 60 replays |
| **250 kVA** | Histogram Gradient Boosting classifier | 145,152 rows across 24 replays |
| **630 kVA** | Physics-based causal detector | 193,536 rows across 24 replays |

**Total: 580,608 synthetic SCADA records.**

The three detection systems use rating-specific configurations. Advanced investigation modules are currently concentrated on the 100-kVA transformer.

## Core Features

- **Physics-Informed Thermal Monitoring:** Compares actual and expected top-oil temperature.
- **ML-Based Thermal Fault Detection:** Uses temporal thermal-residual features to detect unusual heating behavior.
- **Electrical Condition Monitoring:** Tracks three-phase voltage, current, loading, and operating warnings.
- **Interactive SCADA Replay:** Supports chronological monitoring, playback controls, and compatible dataset uploads.
- **Operational Health Assessment:** Displays transformer condition, risk indicators, and data-confidence information.
- **Explainable Dashboard:** Provides charts, point-specific explanations, alerts, and downloadable summaries.
- **Local Evidence Assistant:** Offers deterministic monitoring summaries and investigation information without relying on a generative AI chatbot.

## Five Advanced VoltMind Innovations

These features are implemented as supporting intelligence modules around the 100-kVA detection system.

### 1. What-If Maintenance Simulator

Compares projected transformer thermal behavior under different operating conditions, such as reduced loading, to help engineers evaluate possible interventions.

### 2. Sensor Fault vs Transformer Fault Investigator

Analyzes suspicious measurements and evaluates whether the available evidence suggests a sensor problem, an equipment abnormality, or an uncertain condition.

### 3. Explainable Fault Evidence Report

Provides detailed information about detected incidents, including measurements, expected behavior, thermal deviations, model evidence, data quality, and recommended verification steps.

### 4. Enhanced VoltMind Falsification Twin

Investigates competing explanations for abnormalities, identifies recurring incidents, and evaluates thermal behavior before and after recorded maintenance activities.

This helps engineers investigate problems that return repeatedly, instead of treating every fault as an isolated event.

### 5. VoltMind Thermal DNA

Studies how a transformer heats and cools in response to changes in electrical loading.

When sufficient evidence and a valid reference fingerprint are available, it can identify changes in thermal-response behavior over time.

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React, Vite, JavaScript |
| Backend | Java, Spring Boot |
| ML & Engineering Intelligence | Python, Scikit-learn |
| Thermal Modeling | Physics-based transformer thermal model |
| Database | SQLite |
| Data Sources | Synthetic SCADA datasets and compatible uploaded files |
| Communication | Backend APIs and replay updates |

## 100-kVA Thermal Detection Model

The flagship thermal classifier uses **Logistic Regression** with four physics-informed features:

1. Current actual-minus-expected oil-temperature residual.
2. 30-minute mean thermal residual.
3. 60-minute mean thermal residual.
4. 30-minute thermal-residual change.

Separate experimental investigation components also assess oil-depletion indications and R-phase terminal heating when appropriate measurements are available.

These are not equivalent to validated internal-fault or component-failure diagnosis.

## Testing and Validation

VoltMind follows a **Kill-First** development methodology:

**Understand → Establish Baseline → Challenge → Identify Failures → Improve → Revalidate → Lock**

### Reported 100-kVA Internal Synthetic Benchmark

| Metric | Reported Result |
|---|---|
| Thermal events detected | 22 of 23 |
| Assessment coverage | 93.1% |
| False episodes per negative-truth day | 0.127 |
| Python tests passed | 80 |
| Frontend tests passed | 18 |
| Protected model/data files preserved | 209 |

These results are from the reported internal synthetic benchmark and software validation. They are **not field-validated accuracy results** and must not be interpreted as guaranteed performance on real transformers.

## Getting Started

### Prerequisites

- Java and the JDK version required by the backend
- Node.js and npm
- Python and the dependencies required by the ML service
- Git

### Installation

1. Clone the VoltMind repository.
2. Install the frontend dependencies using the frontend package configuration.
3. Install the backend dependencies using its existing build configuration.
4. Install the Python ML dependencies using the supplied requirements.
5. Configure the required local environment settings.
6. Start the services using the project's supplied startup instructions or scripts.
7. Open the local React application in your browser.

Use the startup and installation scripts supplied with the repository. Document their exact filenames and commands once verified.

### Using VoltMind

After opening the application:

1. Select **Run on Local Data** or **Add a Dataset**.
2. Choose the supported transformer rating and data source.
3. Start chronological SCADA replay.
4. Monitor actual versus expected oil temperature and electrical telemetry.
5. Investigate warnings and abnormal conditions.
6. Explore available intelligence modules and evidence reports.
7. Download monitoring summaries where supported.

The monitoring interface starts without automatically generating or inventing readings.

## Data and Model Transparency

VoltMind's bundled SCADA datasets are synthetic and intended for research, prototyping, testing, and demonstration.

The system distinguishes:

- Measured or source-provided values
- Derived engineering quantities
- ML inferences
- Simulation outputs
- Maintenance records
- Offline evaluation labels

Not every column in a dataset is an input to the trained model.

Missing essential inputs may prevent reliable assessment. Additional data columns do not automatically enable new fault-diagnosis capabilities.

## Future Roadmap

- Live SCADA and physical sensor integration
- Independent field-data validation
- Asset-specific thermal calibration
- Improved transformer fault diagnosis
- Extended sensor-integrity assessment
- Maintenance-management integration
- Insulation aging and remaining useful life estimation
- Advanced intelligence features for 250-kVA and 630-kVA transformers
- Multi-transformer fleet monitoring

## Project Status

**Working research prototype — synthetically validated.**

VoltMind is designed for engineering research, condition-monitoring demonstrations, and decision-support development.

It is not a certified electrical protection system and should not be used as the sole basis for safety-critical transformer operation or maintenance decisions.

## Contributing

Contributions, suggestions, bug reports, and improvements are welcome.

You can contribute by opening an issue, suggesting an enhancement, or submitting a pull request.

Please provide reproducible steps for bugs and describe the validation evidence for changes to engineering or ML logic.

## License

This project is open-source under the **MIT License**, subject to the contents of the repository's LICENSE file.

Third-party datasets, publications, and external assets retain their respective licenses.

## Acknowledgments

Developed as an engineering and machine-learning project focused on intelligent distribution-transformer monitoring, digital-twin technology, and explainable predictive maintenance.

---

**VoltMind — From Transformer Measurements to Intelligent Maintenance Decisions.**
