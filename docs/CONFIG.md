# 組態分層（MVP-0）

本專案採 **base + environment overlay** 模式：

- `config/base.yaml`：共用預設值
- `config/dev.yaml`：開發環境（低風險、可觀測）
- `config/stg.yaml`：staging（接近正式）
- `config/prd.yaml`：正式環境
- `config/.env.example`：環境變數範例

## 使用規範

1. 先載入 `base.yaml`
2. 再以 `CONFIG_ENV` 對應的檔案覆蓋（`dev/stg/prd`）
3. 如有 `CONFIG_FILE`，可直接指定完整檔案路徑覆蓋第 2 步

> 目前 MVP-0 先建立檔案與約定，後續在 MVP-1 將實作程式端的載入器。

## 安全要求

- 不得把真實 API key / secret 寫入 repo。
- 敏感資訊只放在本機或 secrets manager；log 必須遮罩。
