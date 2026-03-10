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

## MVP-8：多帳戶交易所配置建議

可用清單方式管理多個交易帳戶，再由執行層依 `account_id` 路由：

```yaml
execution:
  accounts:
    - account_id: acct-a
      exchange: binance
      base_url: https://testnet.binancefuture.com
      api_key: ${BINANCE_API_KEY_ACCT_A}
      api_secret: ${BINANCE_API_SECRET_ACCT_A}
    - account_id: acct-b
      exchange: binance
      base_url: https://testnet.binancefuture.com
      api_key: ${BINANCE_API_KEY_ACCT_B}
      api_secret: ${BINANCE_API_SECRET_ACCT_B}
```

目前程式已提供 `MultiAccountBinanceGateway` 與 `MultiAccountLiveExecutor`，可直接套用上述配置模式。
