"""
Trading Agent — 交互式菜单
运行方式: python menu.py
"""

import os
import sys
import json
import traceback
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

WATCHLIST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "watchlist.json")

MARKET_LABELS = {"US": "美股", "HK": "港股", "A": "A股"}


# ── 自选股 JSON 管理 ───────────────────────────────────────────

def _load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, encoding="utf-8") as f:
            return json.load(f)
    from config import WATCHLIST
    return list(WATCHLIST)


def _save_watchlist(wl):
    with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(wl, f, ensure_ascii=False, indent=2)


# ── 终端工具 ───────────────────────────────────────────────────

def _clear():
    os.system("cls" if os.name == "nt" else "clear")


def _banner(subtitle="主菜单"):
    print("=" * 52)
    print(f"  Trading Agent — {subtitle}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 52)


def _pause():
    input("\n  按 Enter 返回菜单...")


# ── 功能：分析全部 ─────────────────────────────────────────────

def run_all():
    _clear()
    _banner("分析全部自选股")
    print()
    from main import run_once
    run_once()
    _pause()


# ── 功能：分析单只 ─────────────────────────────────────────────

def run_single():
    from config import HISTORY_DAYS
    from data.fetcher import fetch_stock
    from data.storage import save_price_data, load_price_data, get_last_date
    from analysis.indicators import compute_all
    from analysis.signals import generate_signals
    from analysis.anomaly import check_anomaly
    from report.generator import build_report, print_report, save_report

    wl = _load_watchlist()
    _clear()
    _banner("分析单只股票")
    print()
    for i, s in enumerate(wl, 1):
        market_label = MARKET_LABELS.get(s["market"], s["market"])
        print(f"  [{i:2d}] {s['name']:<22} {s['symbol']:<8} {market_label}")
    print()
    print("  [ c] 输入自定义股票代码")
    print("  [ 0] 返回")
    print()
    choice = input("  请选择 → ").strip()

    if choice == "0":
        return
    elif choice.lower() == "c":
        symbol = input("  股票代码（如 AAPL / 00700 / 600519）: ").strip().upper()
        if not symbol:
            return
        name = input("  股票名称（可留空）: ").strip() or symbol
        market = ""
        while market not in ("US", "HK", "A"):
            market = input("  市场 (US / HK / A): ").strip().upper()
        stock = {"symbol": symbol, "name": name, "market": market}
    else:
        try:
            stock = wl[int(choice) - 1]
        except (ValueError, IndexError):
            input("  无效选项，按 Enter 继续...")
            return

    _clear()
    _banner(f"分析 {stock['name']} ({stock['symbol']})")
    print()
    print(f"  正在拉取数据并分析，请稍候...\n")

    try:
        symbol = stock["symbol"]
        market = stock["market"]
        name   = stock.get("name", symbol)

        last_date_str = get_last_date(symbol, market)
        if last_date_str is None:
            new_df = fetch_stock(symbol, market, days=HISTORY_DAYS)
        else:
            from datetime import datetime as dt
            last_d = dt.strptime(last_date_str[:10], "%Y-%m-%d")
            days_missing = (dt.today() - last_d).days + 1
            new_df = fetch_stock(symbol, market, days=min(days_missing + 5, HISTORY_DAYS)) if days_missing > 0 else None

        if new_df is not None and not new_df.empty:
            save_price_data(symbol, market, new_df)

        df = load_price_data(symbol, market)
        if df.empty or len(df) < 2:
            print(f"  ⚠ 数据不足，无法分析。")
            _pause()
            return

        df_ind  = compute_all(df)
        sig     = generate_signals(df_ind)
        anomaly = check_anomaly(df, symbol, market, name)

        result = {
            "symbol": symbol, "name": name, "market": market,
            "signal": sig["signal"], "score": sig["score"],
            "details": sig["details"], "latest": sig["latest"],
            "price_levels": sig["price_levels"], "anomaly": anomaly,
        }

        report_text = build_report([result])
        print_report(report_text)
        path = save_report(report_text)
        print(f"\n  报告已保存至: {path}")

    except Exception as e:
        print(f"  ⚠ 分析失败: {e}")
        traceback.print_exc()

    _pause()


# ── 功能：查看历史报告 ─────────────────────────────────────────

def view_reports():
    from config import REPORT_DIR
    _clear()
    _banner("历史报告")
    print()

    if not os.path.exists(REPORT_DIR):
        print("  尚无历史报告。")
        _pause()
        return

    files = sorted(
        [f for f in os.listdir(REPORT_DIR) if f.endswith(".txt")],
        reverse=True
    )
    if not files:
        print("  尚无历史报告。")
        _pause()
        return

    show = files[:20]
    for i, fname in enumerate(show, 1):
        ts = fname.replace("report_", "").replace(".txt", "")
        try:
            label = datetime.strptime(ts, "%Y%m%d_%H%M").strftime("%Y-%m-%d %H:%M")
        except ValueError:
            label = ts
        size_kb = os.path.getsize(os.path.join(REPORT_DIR, fname)) // 1024
        print(f"  [{i:2d}] {label}  ({size_kb} KB)")

    print()
    print("  [ 0] 返回")
    print()
    choice = input("  请选择 → ").strip()

    if choice == "0":
        return

    try:
        path = os.path.join(REPORT_DIR, show[int(choice) - 1])
        _clear()
        with open(path, encoding="utf-8") as f:
            content = f.read()
        # 分页显示（每屏 40 行）
        lines = content.splitlines()
        page_size = 40
        for start in range(0, len(lines), page_size):
            print("\n".join(lines[start:start + page_size]))
            if start + page_size < len(lines):
                more = input("\n  -- 按 Enter 继续，输入 q 退出 -- ").strip().lower()
                if more == "q":
                    break
    except (ValueError, IndexError):
        print("  无效选项。")

    _pause()


# ── 功能：管理自选股 ───────────────────────────────────────────

def manage_watchlist():
    while True:
        wl = _load_watchlist()
        _clear()
        _banner("管理自选股列表")
        print()
        print(f"  {'编号':<4} {'名称':<22} {'代码':<10} 市场")
        print("  " + "-" * 42)
        for i, s in enumerate(wl, 1):
            market_label = MARKET_LABELS.get(s["market"], s["market"])
            print(f"  [{i:2d}] {s['name']:<22} {s['symbol']:<10} {market_label}")
        print()
        print("  [a] 添加股票")
        print("  [d] 删除股票")
        print("  [0] 返回")
        print()
        choice = input("  请选择 → ").strip().lower()

        if choice == "0":
            break

        elif choice == "a":
            print()
            symbol = input("  股票代码（如 AAPL / 00700 / 600519）: ").strip().upper()
            if not symbol:
                continue
            name = input("  股票名称: ").strip() or symbol
            market = ""
            while market not in ("US", "HK", "A"):
                market = input("  市场 (US / HK / A): ").strip().upper()
            if any(s["symbol"] == symbol and s["market"] == market for s in wl):
                print(f"\n  ⚠ {symbol} 已在列表中。")
            else:
                wl.append({"symbol": symbol, "name": name, "market": market})
                _save_watchlist(wl)
                print(f"\n  ✓ 已添加 {name} ({symbol}) [{market}]")
            input("  按 Enter 继续...")

        elif choice == "d":
            print()
            idx_str = input("  输入要删除的编号: ").strip()
            try:
                removed = wl.pop(int(idx_str) - 1)
                _save_watchlist(wl)
                print(f"\n  ✓ 已删除 {removed['name']} ({removed['symbol']})")
            except (ValueError, IndexError):
                print("  无效编号。")
            input("  按 Enter 继续...")

        else:
            input("  无效选项，按 Enter 继续...")


# ── 主菜单 ─────────────────────────────────────────────────────

def main():
    while True:
        wl = _load_watchlist()
        _clear()
        _banner("主菜单")
        print()

        # 自选股概览
        print(f"  自选股（{len(wl)} 只）：", end="")
        labels = [f"{s['name']}({s['symbol']})" for s in wl[:4]]
        if len(wl) > 4:
            labels.append(f"...共{len(wl)}只")
        print("  ".join(labels))
        print()

        print("  [1] 分析全部自选股（完整报告）")
        print("  [2] 分析单只股票")
        print("  [3] 查看历史报告")
        print("  [4] 管理自选股列表")
        print("  [0] 退出")
        print()
        choice = input("  请选择 → ").strip()

        if   choice == "1": run_all()
        elif choice == "2": run_single()
        elif choice == "3": view_reports()
        elif choice == "4": manage_watchlist()
        elif choice == "0":
            print("\n  再见！\n")
            break
        else:
            input("  无效选项，按 Enter 继续...")


if __name__ == "__main__":
    main()
