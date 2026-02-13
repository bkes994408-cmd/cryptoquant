# CryptoQuant (MVP-0)

This repository is **documentation-first** for the CryptoQuant project.
MVP-0 focuses on repo hygiene (structure + CI + config templates), so that code can be added later without rework.

## Repository structure

- `src/` – application code (to be added). Currently contains a placeholder.
- `tests/` – automated tests (to be added). Currently contains a placeholder.
- `docs/` – all documentation
  - `docs/ROADMAP.md` – MVP checklist / roadmap
  - `docs/legacy/` – imported original documents and binaries (docx/png/zip/csv)
- `config/` – environment-layered configuration templates (`dev/stg/prd`)

## Config layering (dev / stg / prd)

Config is split into a shared base plus per-environment overrides:

- `config/base.yaml` – defaults shared by all environments
- `config/dev.yaml` – development overrides
- `config/stg.yaml` – staging overrides
- `config/prd.yaml` – production overrides

> Notes
> - Do **not** commit real API keys. The templates reference environment variable names instead.
> - Actual config merge/loading will be implemented once application code lands.

## CI (GitHub Actions)

The CI workflow runs on pushes to `main` and on pull requests:

- **Markdown lint** (for `README.md` and `docs/**/*.md`)
- (Optional) **Link check** for markdown links
- **Secrets pattern scan** (simple grep-based guardrail)

See: `.github/workflows/ci.yml`.
