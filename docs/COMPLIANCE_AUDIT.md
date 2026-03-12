# Compliance & Audit Support

本文件說明 CryptoQuant 在 MVP-8 新增的「合規性與審計支持」。

## 合規檢查（Pre-trade）

`RuleBasedComplianceChecker` 提供最小可用的規則檢查：

- `blocked_symbols`：禁止交易的標的
- `allowed_accounts`：允許下單帳戶白名單
- `max_abs_qty`：單筆下單最大絕對數量

若檢查不通過，會回傳 `ComplianceDecision(allowed=False, reasons=...)`。

## 稽核日誌（Audit Trail）

`AuditTrail` 為 in-memory 的防竄改稽核記錄：

- 每筆事件都有 `prev_hash` 與 `event_hash`
- 使用 hash-chain（SHA-256）串接事件
- `verify_chain()` 可驗證事件序列是否遭修改
- 寫入前會使用 `redact_secrets` 處理敏感資訊

## 與 live executor 整合

`MultiAccountLiveExecutor` 新增兩個可選依賴：

- `compliance_checker`
- `audit_trail`

流程：

1. 檢查 idempotency cache
2. 執行 compliance check（失敗會拒單並記錄 `compliance.order_blocked`）
3. 送單前記錄 `execution.order_submitted`
4. 收到 ACK 記錄 `execution.order_acknowledged`
5. 重複請求命中 cache 記錄 `execution.idempotent_return`

## 測試覆蓋

- `tests/test_compliance_audit.py`
  - 規則允許/拒絕案例
  - hash-chain 完整性驗證
  - tamper 檢測
  - secrets redaction
- `tests/test_multi_account_execution.py`
  - 合規拒單整合測試
  - 成功/冪等返回 audit 事件測試
