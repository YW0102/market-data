# market-data

理財早課市場數據自動抓取系統。GitHub Actions 每天台北時間 05:25 自動執行，產出 `latest.json`，供 Anthropic 雲端 routine 在 05:30 透過 raw.githubusercontent.com 讀取。

## 為什麼需要這個 repo

Anthropic 雲端 routine 的出口受白名單代理限制，無法直接連線 Yahoo Finance / FinMind / Stooq / TWSE 等金融 API（全數回傳 HTTP 403）。但 `raw.githubusercontent.com` 在白名單內，所以利用 GitHub Actions 在外部抓資料、寫入 repo，routine 改讀 raw URL。

## 檔案

- `market_data.py` — 數據抓取主腳本（Yahoo 主 + FinMind/Stooq 備援）
- `.github/workflows/fetch.yml` — 每天 05:25 台北自動跑
- `latest.json` — Actions 產出的數據（每天覆寫）

## 數據來源

| 標的類別 | 主來源 | 備援 |
|---|---|---|
| 台股加權指數 | Yahoo `^TWII` | 無 |
| 台股個股 | Yahoo `*.TW` | FinMind `TaiwanStockPrice` |
| 美股指數（S&P / Nasdaq） | Yahoo | Stooq |
| 費半 SOX | Yahoo `^SOX` | 無 |
| 美股個股 / ETF | Yahoo | FinMind `USStockPrice` |
| 美債10Y | Yahoo `^TNX` | 無 |
| 美元指數 | Yahoo `DX-Y.NYB` | Stooq `dx.f` |
| VIX | Yahoo `^VIX` | 無 |

## latest.json 結構

```json
{
  "generated_at_utc": "2026-05-15T21:25:30Z",
  "generated_at_taipei": "2026-05-16 05:25:30+08:00",
  "taipei_date": "2026-05-16",
  "summary": {"total": 23, "success": 23, "missing": 0},
  "quotes": {
    "NVDA": {
      "name": "NVDA",
      "status": "ok",
      "source": "yahoo",
      "date": "2026-05-15",
      "close": 235.74,
      "prev": 225.83,
      "pct": 4.39
    }
  },
  "missing_names": []
}
```

## Routine 讀取端點

```
https://raw.githubusercontent.com/YW0102/market-data/main/latest.json
```

## 環境變數（選用）

設定 GitHub Secret `FINMIND_TOKEN` 可將 FinMind 限制從 300/hr 升到 600/hr。本系統每日僅呼叫 23 次，未設定也夠用。

## 手動執行

```powershell
# 本機測試
$env:FINMIND_TOKEN = ""  # 選用
python market_data.py
cat latest.json
```

```bash
# GitHub Actions 手動觸發
gh workflow run "Fetch market data"
```
