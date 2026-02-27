"""
异动检测模块
当单日价格涨跌幅超过阈值（默认 5%）时触发新闻搜索
"""

import pandas as pd
from typing import Optional, Dict, List
from data.news import fetch_news


ANOMALY_THRESHOLD = 0.05  # 5% 触发阈值


def check_anomaly(
    df: pd.DataFrame,
    symbol: str,
    market: str,
    name: str = "",
    threshold: float = ANOMALY_THRESHOLD,
) -> Optional[Dict]:
    """
    检查最新一日是否出现异动（涨跌幅超过 threshold）
    如果异动，自动搜索新闻并返回异动报告字典
    没有异动返回 None
    """
    if df is None or len(df) < 2:
        return None

    latest = df.iloc[-1]
    prev   = df.iloc[-2]

    if pd.isna(prev["close"]) or prev["close"] == 0:
        return None

    change_pct = (latest["close"] - prev["close"]) / prev["close"]

    if abs(change_pct) < threshold:
        return None

    # 异动确认，搜索新闻
    direction = "暴涨" if change_pct > 0 else "暴跌"
    news      = fetch_news(symbol, market, name, target_date=latest["date"].date() if hasattr(latest["date"], "date") else None)

    return {
        "symbol":      symbol,
        "name":        name,
        "market":      market,
        "date":        str(latest["date"])[:10],
        "close":       round(latest["close"], 3),
        "prev_close":  round(prev["close"], 3),
        "change_pct":  round(change_pct * 100, 2),
        "direction":   direction,
        "news":        news,
    }


def format_anomaly_report(anomaly: Dict) -> str:
    """将异动字典格式化为可读字符串"""
    lines = [
        f"  *** 异动提醒 [{anomaly['date']}] ***",
        f"  方向：{anomaly['direction']}  涨跌幅：{anomaly['change_pct']:+.2f}%",
        f"  收盘：{anomaly['close']}  前收：{anomaly['prev_close']}",
        "",
        "  相关新闻（自动搜索）：",
    ]

    news_list: List[Dict] = anomaly.get("news", [])
    if not news_list:
        lines.append("  （未找到相关新闻）")
    else:
        for i, item in enumerate(news_list[:8], 1):
            time_str = f"[{item['time']}] " if item.get("time") else ""
            src_str  = f"({item['source']}) " if item.get("source") else ""
            url_str  = f"\n    链接: {item['url']}" if item.get("url") else ""
            lines.append(f"  {i}. {time_str}{src_str}{item['title']}{url_str}")

    return "\n".join(lines)
