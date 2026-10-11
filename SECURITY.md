# Security

VoltMind is a local research prototype. The worker, backend and development frontend bind to loopback by default. It has no production authentication or authorization layer. Keep it local; production hosting requires a separate deployment and security review.

Uploaded monitoring and evidence memory may contain private operational data. They are stored locally and excluded from version control. Do not attach real operational data to public issues.

Python serialized models can execute code during loading. Use only the bundled artifacts or replacements from a trusted source. Do not load arbitrary pickle/joblib files from users.

Report non-sensitive bugs through repository issues. For a vulnerability, use the repository's private security reporting feature when enabled; otherwise contact a maintainer privately before disclosing exploit details. Never include credentials in a report.
