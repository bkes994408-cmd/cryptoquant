# Sprint Result（MVP-0 工程化門檻）

日期：2026-02-27

## 本輪完成項目

1. CI 建置完成（GitHub Actions）
   - `lint`：`ruff check src tests` + markdown lint
   - `unit-tests`：`pytest -q`
   - `security-scan`：`bandit -r src` + 基本 secret pattern grep + `gitleaks`

2. 組態分層完成（dev/stg/prd）
   - 新增 `config/base.yaml`
   - 新增 `config/dev.yaml`
   - 新增 `config/stg.yaml`
   - 新增 `config/prd.yaml`
   - 新增 `config/.env.example`
   - 新增 `docs/CONFIG.md` 使用說明

3. 依賴與程式小修
   - `pyproject.toml` 的 dev dependencies 新增 `ruff`、`bandit`
   - 移除 `src/cryptoquant/events/bus.py` 未使用 import（讓 lint 可通過）

## 驗證結果（本機）

- `./venv_ci_cryptoquant/bin/pytest -q`：**5 passed**
- `./venv_ci_cryptoquant/bin/python -m pip install -e .[dev]` 後：
  - `./venv_ci_cryptoquant/bin/ruff check src tests`：**passed**
  - `./venv_ci_cryptoquant/bin/bandit -q -r src`：**passed**

## 未完成與風險

- 目前僅建立組態分層檔案與規範，**尚未**在 runtime 實作統一 config loader（MVP-1 建議補齊）。
- `gitleaks` 掃描採 `--no-git`，只掃工作樹內容；若要掃歷史提交，需改用含 git history 的模式。
- 目前 security scan 為 baseline（bandit + pattern + gitleaks），未含依賴漏洞掃描（如 pip-audit）。

## 下一步建議

1. 在 `src/cryptoquant/config` 增加 loader（base + overlay merge + env override）。
2. 加入 config schema 驗證（至少檢查 risk 與 strategy 欄位）。
3. 視需求在 CI 增加 `pip-audit`。
