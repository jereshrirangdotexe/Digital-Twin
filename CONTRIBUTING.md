# Contributing

Start with README.md, then install dependencies and run the checks below. Keep changes focused and explain their purpose and validation in the pull request.

```powershell
.venv\Scripts\python.exe -m pytest tests -q
cd frontend
node --test tests/*.test.mjs
npm run build
cd ../backend
.\mvnw.cmd -B test
```

HTTP workflow scripts create monitoring sessions. Run them against a separate test instance, not an active presentation session.

Preserve the frozen model artifacts, calibration files and original datasets unless a change explicitly proposes a versioned research release. Do not describe synthetic evaluation as field accuracy. Do not fabricate missing sensors, use future observations in inference, or fit calibration from an unverified monitoring prefix. Add regression checks when changing these boundaries.

Use Git LFS before staging datasets. Never commit uploads, local databases, credentials, virtual environments, dependencies or build products. Run `python scripts/prepare_github.py --check` before publishing. Supplied code or data must be yours to distribute under the documented license; retain third-party notices.
