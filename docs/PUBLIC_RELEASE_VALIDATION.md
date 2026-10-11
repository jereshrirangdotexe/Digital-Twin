# Public source release validation — 11 October 2026

The public packaging work preserves runtime behavior and original frozen inputs. It changes release documentation, licensing, ignore/storage rules, CI configuration and export tooling. The HTTP acceptance script recognizes the separate labelled demo while still checking the 60 original 100-kVA replays.

Executed locally on Windows:

- Full project Python suite: **80 passed**.
- Spring Boot tests: **5 passed**, Maven BUILD SUCCESS.
- Fresh Git checkout frontend: **21 passed** and production build checked.
- Public-source common credential/size scan: PASS, no matches in its documented scan scope.
- Original protected artifact checks: **209 of 209 SHA-256 matches**, including after Git staging, LFS filtering and a fresh checkout.
- README relative links: all resolve in the public checkout.
- Ignore checks: runtime database, `.env`, installed frontend dependencies and backend build products excluded.

The checkout test used the local Git index, not a remote GitHub clone. GitHub Actions has been configured but has not yet run remotely; no public repository was created or pushed during preparation. Fresh Python dependency installation on another machine and non-Windows end-to-end execution were not performed in this packaging round. Existing pinned dependencies were preserved.

The prepared full source ZIP includes original dataset bytes. Git stores larger CSVs through LFS. Model artifacts and original datasets have not been retrained, rewritten or removed. Excluded local state is retained in the working installation.

These software checks do not establish field model accuracy or third-party redistribution rights. License scope and retained rights are described in `THIRD_PARTY_NOTICES.md`.
