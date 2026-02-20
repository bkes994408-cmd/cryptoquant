# cryptoquant

Minimal event-driven scaffold for a future Paper/Backtest engine.

## Configuration layers (Issue #4)

This project supports environment-based configuration for:

- `dev`
- `stg`
- `prd`

Config loading priority (low -> high):

1. `config/config.base.json`
2. `config/config.<env>.json`
3. Environment variables

### Environment variables

- `CRYPTOQUANT_ENV` (`dev`/`stg`/`prd`, default: `dev`)
- `CRYPTOQUANT_API_KEY`
- `CRYPTOQUANT_API_SECRET`
- `CRYPTOQUANT_LOG_LEVEL`

> Secrets should be provided via environment variables, not hardcoded in tracked files.

### Example

```python
from cryptoquant import load_config

cfg = load_config()          # uses CRYPTOQUANT_ENV or dev
prd_cfg = load_config("prd")
```
