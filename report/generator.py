"""
报告生成模块
将分析结果输出为纯文本报告，并保存到文件
"""

import os
from datetime import datetime
from typing import List, Dict, Optional

from config import REPORT_DIR


SIGNAL_EMOJI = {
    "强烈买入": "★★★ 强烈买入",
    "买入":     "★★  买入",
    "观望":     "★   观望",
    "卖出":     "▼▼  卖出",
    "强烈卖出": "▼▼▼ 强烈卖出",
}


def build_report(results: List[Dict]) -> str:
    """
    根据所有股票的分析结果列表，生成完整报告文本
    results 中每个元素格式：
        {
            "symbol": ..., "name": ..., "market": ...,
            "signal": ..., "score": ..., "details": ..., "latest": ...,
            "anomaly": ... (可能为 None),
            "error": ... (可能存在，表示该股票处理失败),
        }
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "=" * 64,
        f"  Trading Agent — 每日报告",
        f"  生成时间：{now}",
        "=" * 64,
        "",
    ]

    for r in results:
        lines += _stock_section(r)
        lines.append("")

    lines += [
        "=" * 64,
        "  免责声明：本报告仅供参考，不构成投资建议。",
        "  股市有风险，投资需谨慎。",
        "=" * 64,
    ]

    return "\n".join(lines)


def save_report(text: str) -> str:
    """将报告写入文件，返回文件路径"""
    os.makedirs(REPORT_DIR, exist_ok=True)
    filename = datetime.now().strftime("report_%Y%m%d_%H%M.txt")
    path = os.path.join(REPORT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def print_report(text: str) -> None:
    print(text)


# ── 私有工具 ──────────────────────────────────────────────────

def _stock_section(r: Dict) -> List[str]:
    symbol = r["symbol"]
    name   = r.get("name", symbol)
    market = r.get("market", "")
    lines  = [
        f"┌{'─' * 62}┐",
        f"│  [{market}] {name} ({symbol})",
        f"└{'─' * 62}┘",
    ]

    if "error" in r:
        lines.append(f"  ⚠ 数据获取失败：{r['error']}")
        return lines

    # 最新行情
    latest = r.get("latest", {})
    if latest:
        lines.append("  【最新行情】")
        for k, v in latest.items():
            lines.append(f"    {k:<10}: {v}")
        lines.append("")

    # 交易信号
    signal = r.get("signal", "N/A")
    score  = r.get("score", 0)
    signal_label = SIGNAL_EMOJI.get(signal, signal)
    lines.append(f"  【综合信号】  {signal_label}  (评分: {score:+.3f})")
    lines.append("")

    # 各指标详情
    details = r.get("details", {})
    if details:
        lines.append("  【指标详情】")
        for k, v in details.items():
            lines.append(f"    {k:<12}: {v}")
        lines.append("")

    # 交易建议
    price_levels = r.get("price_levels", {})
    lines += _trading_suggestion(signal, score, latest, details, price_levels, r.get("anomaly"))
    lines.append("")

    # 异动提醒
    anomaly = r.get("anomaly")
    if anomaly:
        from analysis.anomaly import format_anomaly_report
        lines.append("  【异动提醒】")
        lines.append(format_anomaly_report(anomaly))

    return lines


def _trading_suggestion(
    signal: str,
    score: float,
    latest: Dict,
    details: Dict = None,
    price_levels: Dict = None,
    anomaly: Dict = None,
) -> List[str]:
    details      = details or {}
    price_levels = price_levels or {}
    lines = ["  【交易建议】"]

    close      = price_levels.get("close") or latest.get("收盘价", 0)
    boll_upper = price_levels.get("boll_upper")
    boll_lower = price_levels.get("boll_lower")
    ma20       = price_levels.get("ma20")
    rsi_val    = latest.get("RSI", "N/A")

    # ── 操作指令 ──────────────────────────────────────────────
    action_map = {
        "强烈买入": "买入 / 加仓      建议新增仓位 20–30%",
        "买入":    "轻仓买入 / 小幅加仓  建议新增仓位 10–15%",
        "观望":    "持仓不动 / 空仓观望  本期不操作",
        "卖出":    "减仓            建议减少仓位 20–30%",
        "强烈卖出": "大幅减仓 / 清仓    建议减少仓位 50% 以上",
    }
    lines.append(f"    ▶ 操作指令：{action_map.get(signal, '—')}")
    lines.append("")

    # ── 理由 ──────────────────────────────────────────────────
    reasons = _build_reasons(details, rsi_val)
    if reasons:
        lines.append("    ▶ 理由：")
        for reason in reasons:
            lines.append(f"      · {reason}")
        lines.append("")

    # ── 关键价位 ──────────────────────────────────────────────
    if signal in ("强烈买入", "买入") and close:
        lines.append("    ▶ 关键价位：")
        if boll_lower:
            pct = (boll_lower / close - 1) * 100
            lines.append(f"      · 止损参考：布林下轨 {boll_lower}（现价 {pct:+.1f}%），跌破后减仓止损")
        if ma20:
            pct = (ma20 / close - 1) * 100
            lines.append(f"      · 支撑参考：MA20 = {ma20}（现价 {pct:+.1f}%）")
        if boll_upper:
            pct = (boll_upper / close - 1) * 100
            lines.append(f"      · 目标参考：布林上轨 {boll_upper}（现价 {pct:+.1f}%），可在此附近减仓锁利")
        lines.append("")
    elif signal in ("卖出", "强烈卖出") and close:
        lines.append("    ▶ 关键价位：")
        if ma20:
            pct = (ma20 / close - 1) * 100
            lines.append(f"      · 压力参考：MA20 = {ma20}（现价 {pct:+.1f}%），反弹至此可逢高减仓")
        if boll_upper:
            pct = (boll_upper / close - 1) * 100
            lines.append(f"      · 强压力：布林上轨 {boll_upper}（现价 {pct:+.1f}%）")
        if boll_lower:
            pct = (boll_lower / close - 1) * 100
            lines.append(f"      · 下方目标：布林下轨 {boll_lower}（现价 {pct:+.1f}%）")
        lines.append("")

    # ── 未来操作计划 ──────────────────────────────────────────
    lines.append("    ▶ 未来操作计划：")
    lines += _future_plan(signal, close, boll_upper, boll_lower, ma20)
    lines.append("")

    # ── 异动应对 ──────────────────────────────────────────────
    if anomaly:
        lines += _anomaly_plan(anomaly)
        lines.append("")

    return lines


def _build_reasons(details: Dict, rsi_val) -> List[str]:
    reasons = []

    # 均线交叉（高信号强度，优先列出）
    cross = details.get("均线交叉", "无")
    if "黄金交叉" in cross:
        reasons.append("MA5 上穿 MA20（黄金交叉），短期动能由空转多")
    elif "死亡交叉" in cross:
        reasons.append("MA5 下穿 MA20（死亡交叉），短期动能由多转空")

    # 均线趋势
    ma = details.get("均线", "")
    if "强烈看多" in ma:
        reasons.append("均线多头排列，收盘价站上全部关键均线（MA5/10/20/60）")
    elif "看多" in ma:
        reasons.append("均线偏多头，收盘价站上多数均线")
    elif "强烈看空" in ma:
        reasons.append("均线空头排列，收盘价跌破全部关键均线")
    elif "看空" in ma:
        reasons.append("均线偏空头，收盘价低于多数均线")

    # RSI
    rsi_txt = details.get("RSI", "")
    if "超买" in rsi_txt:
        reasons.append(f"RSI 超买（{rsi_txt}），短期面临回调压力")
    elif "超卖" in rsi_txt:
        reasons.append(f"RSI 超卖（{rsi_txt}），存在超跌反弹机会")
    elif isinstance(rsi_val, (int, float)):
        if rsi_val > 55:
            reasons.append(f"RSI={rsi_val} 站上 50 中线，动能偏多")
        elif rsi_val < 45:
            reasons.append(f"RSI={rsi_val} 低于 50 中线，动能偏空")

    # MACD
    macd = details.get("MACD", "")
    if "金叉" in macd:
        reasons.append("MACD 柱状线由负转正（金叉），动能反转确认")
    elif "死叉" in macd:
        reasons.append("MACD 柱状线由正转负（死叉），动能走弱")
    elif "多头区间" in macd:
        reasons.append(f"MACD 处于多头区间（{macd}），上行趋势延续")
    elif "空头区间" in macd:
        reasons.append(f"MACD 处于空头区间（{macd}），下行趋势延续")

    # ADX
    adx = details.get("ADX", "")
    if "强趋势上行" in adx:
        reasons.append(f"ADX 确认强势上行趋势（{adx}）")
    elif "强趋势下行" in adx:
        reasons.append(f"ADX 确认强势下行趋势（{adx}）")
    elif "趋势较弱" in adx:
        reasons.append(f"ADX 显示趋势动能不足（{adx}），方向不明")

    # 布林带
    boll = details.get("布林带", "")
    if "突破上轨" in boll:
        reasons.append("价格突破布林上轨，短期超买，回调风险较高")
    elif "突破下轨" in boll:
        reasons.append("价格跌破布林下轨，短期超卖，关注反弹机会")
    elif "接近上轨" in boll:
        reasons.append("价格接近布林上轨，上方压力较大")
    elif "接近下轨" in boll:
        reasons.append("价格接近布林下轨，下方支撑较强")

    # 量能
    obv = details.get("OBV", "")
    mfi = details.get("MFI", "")
    if "多头确认" in obv:
        reasons.append("OBV 量能上升，成交量配合多头，上涨可信度高")
    elif "空头确认" in obv:
        reasons.append("OBV 量能下降，成交量配合空头，下跌趋势确认")
    if "超买资金流出" in mfi:
        reasons.append(f"MFI 超买区域资金流出（{mfi}），大资金出逃迹象")
    elif "超卖资金流入" in mfi:
        reasons.append(f"MFI 超卖区域资金流入（{mfi}），大资金开始介入")

    return reasons


def _future_plan(signal: str, close, boll_upper, boll_lower, ma20) -> List[str]:
    lines = []

    if signal in ("强烈买入", "买入"):
        if boll_upper and close:
            up_pct = (boll_upper / close - 1) * 100
            lines.append(f"      · 若上涨 {up_pct:.1f}% 触及布林上轨（{boll_upper}）→ 减仓 20–30% 锁定利润")
        else:
            lines.append(f"      · 若上涨 5–8% → 可减仓 20–30% 锁定利润")
        lines.append(f"      · 若突破布林上轨且成交量同步放大 → 持仓不动，上调止损至成本价附近")
        if ma20 and close:
            dn_pct = abs((ma20 / close - 1) * 100)
            lines.append(f"      · 若下跌 {dn_pct:.1f}% 跌破 MA20（{ma20}）→ 减仓 50%，警惕趋势反转")
        if boll_lower and close:
            dn_pct = abs((boll_lower / close - 1) * 100)
            lines.append(f"      · 若跌破布林下轨（{boll_lower}，-{dn_pct:.1f}%）→ 止损清仓出场")

    elif signal == "观望":
        if boll_upper and close:
            up_pct = (boll_upper / close - 1) * 100
            lines.append(f"      · 若放量突破布林上轨（{boll_upper}，+{up_pct:.1f}%）→ 可考虑买入 10–15%")
        elif ma20 and close:
            up_pct = (ma20 / close - 1) * 100
            if up_pct > 0:
                lines.append(f"      · 若放量站上 MA20（{ma20}，+{up_pct:.1f}%）→ 可轻仓买入 10%")
            else:
                lines.append(f"      · 若收盘价重新站稳 MA20（{ma20}）并放量确认 → 可轻仓买入 10%")
        else:
            lines.append(f"      · 若出现放量突破关键均线信号 → 可考虑轻仓试多")
        if boll_lower and close:
            dn_pct = abs((boll_lower / close - 1) * 100)
            lines.append(f"      · 若下跌 {dn_pct:.1f}% 跌破布林下轨（{boll_lower}）→ 持仓者减仓，空仓者继续观望")
        else:
            lines.append(f"      · 若下跌 3–5% 且无基本面支撑 → 持仓者考虑减仓止损")

    elif signal in ("卖出", "强烈卖出"):
        if ma20 and close:
            up_pct = (ma20 / close - 1) * 100
            if up_pct > 0:
                lines.append(f"      · 若反弹至 MA20（{ma20}，+{up_pct:.1f}%）→ 逢高继续减仓 20–30%")
            else:
                lines.append(f"      · 若反弹至 MA20（{ma20}）→ 逢高继续减仓 20–30%")
        if boll_upper and close:
            up_pct = (boll_upper / close - 1) * 100
            lines.append(f"      · 若反弹至布林上轨（{boll_upper}，+{up_pct:.1f}%）→ 强压力位，可考虑清仓")
        if boll_lower and close:
            dn_pct = abs((boll_lower / close - 1) * 100)
            lines.append(f"      · 若继续下跌至布林下轨（{boll_lower}，-{dn_pct:.1f}%）→ 关注超卖反弹，暂不追空")
        lines.append(f"      · 若出现 RSI<30 + 量能萎缩 + MACD 柱缩短三重底部信号 → 可考虑轻仓试多（10%）")

    return lines


def _anomaly_plan(anomaly: Dict) -> List[str]:
    direction  = anomaly.get("direction", "")
    change_pct = anomaly.get("change_pct", 0)
    lines = [f"    ▶ 异动应对 【今日{direction} {change_pct:+.2f}%，需结合基本面判断】："]

    if direction == "暴涨":
        lines += [
            "      · 首先查阅上方新闻，判断涨因（业绩超预期 / 合同中标 / 政策利好 / 纯情绪炒作）",
            "      · 若为实质利好驱动（业绩/合同/政策）→ 可持仓，等回调 3–5% 后再视信号择机加仓",
            "      · 若消息面不明朗或短期情绪炒作 → 警惕高位回落，建议锁定部分利润（减仓 20–30%）",
            "      · 若次日出现高开低走 + 量能萎缩 → 视为反转信号，进一步减仓 30–50%",
        ]
    elif direction == "暴跌":
        lines += [
            "      · 首先查阅上方新闻，判断跌因（业绩下修 / 政策打压 / 行业利空 / 市场恐慌）",
            "      · 若为突发非系统性利空、基本面未变 → 可持仓观察，避免在恐慌底部割肉",
            "      · 若基本面已发生负面变化（盈利预警 / 监管处罚）→ 不抄底，考虑减仓或清仓",
            "      · 若仅为市场情绪恐慌且 RSI<30 + 量能萎缩 → 可小仓位试探性买入（5–10%）",
        ]

    return lines
