"""
Trading Agent — 主程序入口
每天自动运行：拉取数据 → 计算指标 → 生成信号 → 检测异动 → 输出报告
"""

import sys
import schedule
import time
import traceback
from datetime import datetime, timedelta

from config import WATCHLIST, SCHEDULE_TIME, HISTORY_DAYS
from data.fetcher import fetch_stock
from data.storage import save_price_data, load_price_data, get_last_date
from analysis.indicators import compute_all
from analysis.signals import generate_signals
from analysis.anomaly import check_anomaly
from report.generator import build_report, save_report, print_report


def run_once():
    """执行一次完整的分析流程"""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始分析...")

    results = []
    for stock in WATCHLIST:
        symbol = stock["symbol"]
        market = stock["market"]
        name   = stock.get("name", symbol)

        print(f"  处理: {name} ({symbol}) [{market}]", end=" ... ", flush=True)
        try:
            result = _process_stock(symbol, market, name)
        except Exception as e:
            traceback.print_exc()
            result = {
                "symbol": symbol, "name": name, "market": market,
                "error": str(e),
            }

        results.append(result)
        print("完成" if "error" not in result else f"失败: {result['error']}")

    report_text = build_report(results)
    print_report(report_text)

    path = save_report(report_text)
    print(f"\n报告已保存至: {path}")


def _process_stock(symbol: str, market: str, name: str) -> dict:
    """处理单只股票：增量更新数据 → 计算指标 → 生成信号 → 检测异动"""

    # 1. 增量更新数据
    last_date_str = get_last_date(symbol, market)
    if last_date_str is None:
        # 首次运行，拉取全量历史
        new_df = fetch_stock(symbol, market, days=HISTORY_DAYS)
    else:
        last_dt = datetime.strptime(last_date_str[:10], "%Y-%m-%d")
        days_missing = (datetime.today() - last_dt).days + 1
        if days_missing <= 0:
            new_df = None
        else:
            new_df = fetch_stock(symbol, market, days=min(days_missing + 5, HISTORY_DAYS))

    if new_df is not None and not new_df.empty:
        save_price_data(symbol, market, new_df)

    # 2. 加载全量历史
    df = load_price_data(symbol, market)
    if df.empty or len(df) < 2:
        return {"symbol": symbol, "name": name, "market": market,
                "error": f"历史数据不足（仅 {len(df)} 条，至少需要 2 条）"}

    # 3. 计算技术指标
    df_with_ind = compute_all(df)

    # 4. 生成交易信号
    sig = generate_signals(df_with_ind)

    # 5. 检测异动（单日涨跌 > 5%）
    anomaly = check_anomaly(df, symbol, market, name)

    return {
        "symbol":       symbol,
        "name":         name,
        "market":       market,
        "signal":       sig["signal"],
        "score":        sig["score"],
        "details":      sig["details"],
        "latest":       sig["latest"],
        "price_levels": sig["price_levels"],
        "anomaly":      anomaly,
    }


def main():
    # 支持命令行参数：python main.py --now  立即运行一次
    if "--now" in sys.argv or "-n" in sys.argv:
        run_once()
        return

    # 定时模式：每天在指定时间运行
    print(f"Trading Agent 已启动，每天 {SCHEDULE_TIME} 自动运行。")
    print("按 Ctrl+C 退出。如需立即运行，请使用: python main.py --now\n")

    schedule.every().day.at(SCHEDULE_TIME).do(run_once)

    # 启动时先运行一次
    run_once()

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
