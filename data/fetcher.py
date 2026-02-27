"""
数据抓取模块
统一使用 yfinance（Yahoo Finance）获取 A股、美股、港股数据
- A股：000001 → 000001.SZ / 600519 → 600519.SS
- 港股：00700  → 0700.HK
- 美股：AAPL   → AAPL
"""

import pandas as pd
from datetime import datetime, timedelta
from config import HISTORY_DAYS


def fetch_stock(symbol: str, market: str, days: int = HISTORY_DAYS) -> pd.DataFrame:
    """
    统一入口：根据市场类型构造 yfinance ticker 并拉取数据
    返回 DataFrame，列：date, open, high, low, close, volume
    """
    import yfinance as yf

    ticker_symbol = _to_yf_symbol(symbol, market)
    end_date   = datetime.today()
    start_date = end_date - timedelta(days=days)

    ticker = yf.Ticker(ticker_symbol)
    df = ticker.history(
        start=start_date.strftime("%Y-%m-%d"),
        end=end_date.strftime("%Y-%m-%d"),
        auto_adjust=True,
    )

    # 日期范围取不到数据时，降级尝试短周期（适用于刚上市的股票）
    if df.empty:
        for fallback in ("5d", "1d"):
            df = ticker.history(period=fallback, auto_adjust=True)
            if not df.empty:
                break

    if df.empty:
        raise ValueError(f"yfinance 未返回任何数据（ticker={ticker_symbol}）")

    df = df.reset_index()
    df = df.rename(columns={
        "Date":   "date",
        "Open":   "open",
        "High":   "high",
        "Low":    "low",
        "Close":  "close",
        "Volume": "volume",
    })
    # 去除时区信息，统一为 naive datetime
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    df = df[["date", "open", "high", "low", "close", "volume"]].sort_values("date").reset_index(drop=True)
    return df


def _to_yf_symbol(symbol: str, market: str) -> str:
    """将本地代码转换为 yfinance 格式"""
    if market == "US":
        return symbol.upper()

    if market == "HK":
        # 00700 → 0700.HK（去掉前导零后保留4位）
        code = symbol.lstrip("0") or "0"
        return f"{int(code):04d}.HK"

    if market == "A":
        # 上海：600xxx 601xxx 603xxx 605xxx 688xxx 689xxx
        # 深圳：000xxx 001xxx 002xxx 003xxx 300xxx 301xxx
        prefix = symbol[:1]
        if symbol.startswith(("6", "9")):
            return f"{symbol}.SS"
        else:
            return f"{symbol}.SZ"

    raise ValueError(f"不支持的市场类型: {market}")
