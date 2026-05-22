"""
理財早課市場數據抓取（GitHub Actions 版）
主來源：Yahoo Finance v8 chart API
備援：FinMind（台股 + 美股個股）、Stooq（美股指數 + DXY）、TWSE 官方 API（台股加權）
輸出：latest.json（給 routine 透過 raw.githubusercontent.com 讀取）
"""
import requests
import json
import os
import sys
from datetime import datetime, timezone, timedelta

HEADERS = {"User-Agent": "Mozilla/5.0"}
TIMEOUT = 15
FINMIND_TOKEN = os.environ.get("FINMIND_TOKEN", "").strip()
TAIPEI_TZ = timezone(timedelta(hours=8))

# 標的清單：(顯示名稱, Yahoo symbol, 備援 symbol, 備援來源)
SYMBOLS = [
    ("台股加權",     "^TWII",     "TWII",     "twse_index"),
    ("台積電(2330)", "2330.TW",   "2330",     "finmind_tw"),
    ("玉山金(2884)", "2884.TW",   "2884",     "finmind_tw"),
    ("兆豐金(2886)", "2886.TW",   "2886",     "finmind_tw"),
    ("元大金(2885)", "2885.TW",   "2885",     "finmind_tw"),
    ("台達電(2308)", "2308.TW",   "2308",     "finmind_tw"),
    ("廣達(2382)",   "2382.TW",   "2382",     "finmind_tw"),
    ("健策(3653)",   "3653.TW",   "3653",     "finmind_tw"),
    ("群聯(8299)",   "8299.TWO",  "8299",     "finmind_tw"),
    ("S&P500",       "^GSPC",     "^spx",     "stooq"),
    ("那指",         "^IXIC",     "^ndq",     "stooq"),
    ("費半",         "^SOX",      None,       None),
    ("NVDA",         "NVDA",      "NVDA",     "finmind_us"),
    ("MU",           "MU",        "MU",       "finmind_us"),
    ("GOOG",         "GOOG",      "GOOG",     "finmind_us"),
    ("PLTR",         "PLTR",      "PLTR",     "finmind_us"),
    ("SPY",          "SPY",       "SPY",      "finmind_us"),
    ("QQQ",          "QQQ",       "QQQ",      "finmind_us"),
    ("VTI",          "VTI",       "VTI",      "finmind_us"),
    ("UUUU",         "UUUU",      "UUUU",     "finmind_us"),
    ("美債10Y",      "^TNX",      None,       None),
    ("美元指數",     "DX-Y.NYB",  "dx.f",     "stooq"),
    ("VIX",          "^VIX",      None,       None),
]


def fetch_yahoo(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    result = r.json()["chart"]["result"][0]
    timestamps = result["timestamp"]
    closes = result["indicators"]["quote"][0]["close"]
    valid = [(t, c) for t, c in zip(timestamps, closes) if c is not None]
    if not valid:
        return None
    last_ts, last_close = valid[-1]
    prev_close = valid[-2][1] if len(valid) >= 2 else None
    tz_offset = result["meta"].get("gmtoffset", 0)
    dt = datetime.fromtimestamp(last_ts + tz_offset, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d"), last_close, prev_close


def fetch_stooq(symbol):
    url = f"https://stooq.com/q/l/?s={symbol}&f=sd2t2ohlcv&h&e=csv"
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    lines = r.text.strip().split("\n")
    if len(lines) < 2:
        return None
    parts = lines[1].split(",")
    if "N/D" in parts:
        return None
    return parts[1], float(parts[6]), None


def _fetch_finmind(dataset, data_id):
    start = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
    url = f"https://api.finmindtrade.com/api/v4/data?dataset={dataset}&data_id={data_id}&start_date={start}"
    if FINMIND_TOKEN:
        url += f"&token={FINMIND_TOKEN}"
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json().get("data", [])
    if not data:
        return None
    last = data[-1]
    prev = data[-2] if len(data) >= 2 else None
    close_key = "close" if "close" in last else "Close"
    return last["date"], float(last[close_key]), float(prev[close_key]) if prev else None


def fetch_finmind_tw(stock_id):
    return _fetch_finmind("TaiwanStockPrice", stock_id)


def fetch_finmind_us(symbol):
    return _fetch_finmind("USStockPrice", symbol)


def fetch_twse_index(_=None):
    """TWSE 官方加權指數，從當月（不夠則往前一個月）取最新兩個交易日"""
    today = datetime.now(TAIPEI_TZ)
    first_this = today.replace(day=1)
    first_prev = (first_this - timedelta(days=1)).replace(day=1)
    months = [first_this.strftime("%Y%m%d"), first_prev.strftime("%Y%m%d")]
    rows = []
    for ym in months:
        url = f"https://www.twse.com.tw/indicesReport/MI_5MINS_HIST?response=json&date={ym}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            r.raise_for_status()
            month_rows = r.json().get("data", []) or []
            rows = month_rows + rows
        except Exception:
            continue
        if len(rows) >= 2:
            break
    if not rows:
        return None

    def roc_to_ad(s):
        y, m, d = s.split("/")
        return f"{int(y) + 1911}-{m.zfill(2)}-{d.zfill(2)}"

    def to_float(s):
        return float(str(s).replace(",", ""))

    last = rows[-1]
    prev = rows[-2] if len(rows) >= 2 else None
    return (
        roc_to_ad(last[0]),
        to_float(last[4]),
        to_float(prev[4]) if prev else None,
    )


BACKUP_FUNCS = {
    "finmind_tw": fetch_finmind_tw,
    "finmind_us": fetch_finmind_us,
    "stooq": fetch_stooq,
    "twse_index": fetch_twse_index,
}


def get_quote(name, yahoo_sym, backup_sym, backup_src):
    yahoo_err = None
    try:
        result = fetch_yahoo(yahoo_sym)
        if result:
            return _make_quote(name, "yahoo", result)
        yahoo_err = "no data"
    except Exception as e:
        yahoo_err = f"{type(e).__name__}: {str(e)[:80]}"

    if backup_sym and backup_src in BACKUP_FUNCS:
        try:
            result = BACKUP_FUNCS[backup_src](backup_sym)
            if result:
                return _make_quote(name, backup_src, result)
            return {"name": name, "status": "missing", "error": f"yahoo: {yahoo_err}; {backup_src}: no data"}
        except Exception as e:
            return {"name": name, "status": "missing", "error": f"yahoo: {yahoo_err}; {backup_src}: {type(e).__name__}: {str(e)[:80]}"}

    return {"name": name, "status": "missing", "error": f"yahoo: {yahoo_err}; no backup"}


def _make_quote(name, source, result):
    date_str, close, prev = result
    quote = {
        "name": name,
        "status": "ok",
        "source": source,
        "date": date_str,
        "close": round(close, 4),
    }
    if prev:
        quote["prev"] = round(prev, 4)
        quote["pct"] = round((close - prev) / prev * 100, 2)
    return quote


def main():
    now_utc = datetime.now(timezone.utc)
    now_taipei = now_utc.astimezone(TAIPEI_TZ)

    quotes = []
    for name, ysym, bsym, bsrc in SYMBOLS:
        print(f"Fetching {name}...", flush=True)
        q = get_quote(name, ysym, bsym, bsrc)
        quotes.append(q)

    ok = [q for q in quotes if q["status"] == "ok"]
    missing = [q for q in quotes if q["status"] == "missing"]

    output = {
        "generated_at_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_at_taipei": now_taipei.strftime("%Y-%m-%d %H:%M:%S+08:00"),
        "taipei_date": now_taipei.strftime("%Y-%m-%d"),
        "summary": {
            "total": len(quotes),
            "success": len(ok),
            "missing": len(missing),
        },
        "quotes": {q["name"]: q for q in quotes},
        "missing_names": [q["name"] for q in missing],
    }

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "latest.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n=== Done: {len(ok)}/{len(quotes)} success | Missing: {output['missing_names']} ===")
    print(f"Output: {out_path}")

    # 若全部失敗則非零退出，讓 Actions 失敗
    if len(ok) == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
