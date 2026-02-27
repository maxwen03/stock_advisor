"""
交易信号生成模块
综合多个指标投票，输出综合信号和置信度
"""

import pandas as pd
from config import SIGNAL_THRESHOLDS as T, INDICATOR_PARAMS as P


def generate_signals(df: pd.DataFrame) -> dict:
    """
    基于最新一行数据，综合所有指标给出交易建议
    返回字典：
        signal    : "强烈买入" / "买入" / "观望" / "卖出" / "强烈卖出"
        score     : 综合评分 [-1.0, 1.0]（正=看多，负=看空）
        details   : 各指标子信号字典
        latest    : 最新行数据字典
    """
    if df.empty or len(df) < 2:
        return {"signal": "数据不足", "score": 0, "details": {}, "latest": {}}

    row  = df.iloc[-1]
    prev = df.iloc[-2]

    details = {}
    votes   = []   # 每个信号 +1(多) / 0(中性) / -1(空)

    # ── 均线系统 ───────────────────────────────────────────
    ma_signals = []
    for p in P["ma_periods"]:
        col = f"MA{p}"
        if pd.notna(row.get(col)):
            if row["close"] > row[col]:
                ma_signals.append(1)
            elif row["close"] < row[col]:
                ma_signals.append(-1)
            else:
                ma_signals.append(0)
    if ma_signals:
        ma_score = sum(ma_signals) / len(ma_signals)
        votes.append(ma_score)
        details["均线"] = _label(ma_score)

    # 黄金交叉 / 死亡交叉 (MA5 vs MA20)
    if all(c in df.columns for c in ["MA5", "MA20"]):
        cross = "无"
        if pd.notna(row["MA5"]) and pd.notna(prev.get("MA5")) and \
           pd.notna(row["MA20"]) and pd.notna(prev.get("MA20")):
            if prev["MA5"] <= prev["MA20"] and row["MA5"] > row["MA20"]:
                cross = "黄金交叉(多头)"
                votes.append(1)
            elif prev["MA5"] >= prev["MA20"] and row["MA5"] < row["MA20"]:
                cross = "死亡交叉(空头)"
                votes.append(-1)
        details["均线交叉"] = cross

    # ── RSI ───────────────────────────────────────────────
    if pd.notna(row.get("RSI")):
        rsi = row["RSI"]
        if rsi >= T["rsi_overbought"]:
            rsi_sig = -1
            rsi_txt = f"超买({rsi:.1f})"
        elif rsi <= T["rsi_oversold"]:
            rsi_sig = 1
            rsi_txt = f"超卖({rsi:.1f})"
        else:
            # 50线多空
            rsi_sig = 0.5 if rsi > 50 else -0.5
            rsi_txt = f"中性({rsi:.1f})"
        votes.append(rsi_sig)
        details["RSI"] = rsi_txt

    # ── MACD ──────────────────────────────────────────────
    if all(c in df.columns for c in ["MACD", "MACD_signal", "MACD_hist"]):
        if pd.notna(row.get("MACD")) and pd.notna(prev.get("MACD_hist")):
            hist_now  = row["MACD_hist"]
            hist_prev = prev["MACD_hist"]
            if hist_prev < 0 and hist_now >= 0:
                macd_sig = 1
                macd_txt = "柱状线由负转正(金叉)"
            elif hist_prev > 0 and hist_now <= 0:
                macd_sig = -1
                macd_txt = "柱状线由正转负(死叉)"
            elif hist_now > 0:
                macd_sig = 0.5
                macd_txt = f"多头区间(hist={hist_now:.3f})"
            else:
                macd_sig = -0.5
                macd_txt = f"空头区间(hist={hist_now:.3f})"
            votes.append(macd_sig)
            details["MACD"] = macd_txt

    # ── ADX ───────────────────────────────────────────────
    if all(c in df.columns for c in ["ADX", "DI_pos", "DI_neg"]):
        if pd.notna(row.get("ADX")):
            adx = row["ADX"]
            if adx >= T["adx_strong"]:
                if row["DI_pos"] > row["DI_neg"]:
                    adx_sig = 0.8
                    adx_txt = f"强趋势上行(ADX={adx:.1f})"
                else:
                    adx_sig = -0.8
                    adx_txt = f"强趋势下行(ADX={adx:.1f})"
            else:
                adx_sig = 0
                adx_txt = f"趋势较弱(ADX={adx:.1f})"
            votes.append(adx_sig)
            details["ADX"] = adx_txt

    # ── 布林带 ────────────────────────────────────────────
    if all(c in df.columns for c in ["BOLL_upper", "BOLL_lower", "BOLL_%B"]):
        if pd.notna(row.get("BOLL_%B")):
            pct_b = row["BOLL_%B"]
            if pct_b > 1.0:
                boll_sig = -1
                boll_txt = "价格突破上轨(超买区域)"
            elif pct_b < 0.0:
                boll_sig = 1
                boll_txt = "价格突破下轨(超卖区域)"
            elif pct_b > 0.8:
                boll_sig = -0.5
                boll_txt = f"接近上轨(%B={pct_b:.2f})"
            elif pct_b < 0.2:
                boll_sig = 0.5
                boll_txt = f"接近下轨(%B={pct_b:.2f})"
            else:
                boll_sig = 0
                boll_txt = f"布林带中部(%B={pct_b:.2f})"
            votes.append(boll_sig)
            details["布林带"] = boll_txt

    # ── ROC & Momentum ────────────────────────────────────
    if pd.notna(row.get("ROC")):
        roc = row["ROC"]
        roc_sig = 0.5 if roc > 0 else (-0.5 if roc < 0 else 0)
        votes.append(roc_sig)
        details["ROC"] = f"{roc:.2f}%({'正向' if roc > 0 else '负向'}动能)"

    if pd.notna(row.get("MOM")):
        mom = row["MOM"]
        mom_sig = 0.5 if mom > 0 else (-0.5 if mom < 0 else 0)
        votes.append(mom_sig)
        details["Momentum"] = f"{mom:.3f}({'正' if mom > 0 else '负'})"

    # ── 成交量动能 ────────────────────────────────────────
    vol_signals = []

    # OBV 趋势
    if "OBV" in df.columns and len(df) >= 5:
        obv_slope = df["OBV"].iloc[-1] - df["OBV"].iloc[-5]
        if obv_slope > 0:
            vol_signals.append(0.5)
            details["OBV"] = "量能上升(多头确认)"
        elif obv_slope < 0:
            vol_signals.append(-0.5)
            details["OBV"] = "量能下降(空头确认)"
        else:
            details["OBV"] = "量能持平"

    # MFI
    if pd.notna(row.get("MFI")):
        mfi = row["MFI"]
        if mfi >= 80:
            vol_signals.append(-0.8)
            details["MFI"] = f"超买资金流出({mfi:.1f})"
        elif mfi <= 20:
            vol_signals.append(0.8)
            details["MFI"] = f"超卖资金流入({mfi:.1f})"
        else:
            mfi_sig = 0.3 if mfi > 50 else -0.3
            vol_signals.append(mfi_sig)
            details["MFI"] = f"资金{'偏多' if mfi > 50 else '偏空'}({mfi:.1f})"

    # VROC — 量价配合
    if pd.notna(row.get("VROC")):
        vroc = row["VROC"]
        details["VROC"] = f"成交量变化率 {vroc:.1f}%"

    # 量均线放量/缩量
    for p in P["vol_ma_periods"]:
        col = f"VOL_MA{p}"
        if pd.notna(row.get(col)):
            if row["volume"] > row[col] * 1.5:
                details[f"量均线MA{p}"] = f"放量({row['volume']/row[col]:.1f}x)"
            elif row["volume"] < row[col] * 0.5:
                details[f"量均线MA{p}"] = f"缩量({row['volume']/row[col]:.1f}x)"
            else:
                details[f"量均线MA{p}"] = "正常量"

    votes.extend(vol_signals)

    # ── 综合评分 ──────────────────────────────────────────
    if not votes:
        score = 0.0
    else:
        score = sum(votes) / len(votes)

    signal = _score_to_signal(score)

    # 最新关键数据
    latest = {
        "收盘价":  round(row["close"], 3),
        "涨跌幅":  f"{(row['close'] / prev['close'] - 1) * 100:.2f}%" if pd.notna(prev.get("close")) else "N/A",
        "成交量":  int(row["volume"]),
        "RSI":    round(row["RSI"], 1)  if pd.notna(row.get("RSI"))  else "N/A",
        "MACD柱": round(row["MACD_hist"], 4) if pd.notna(row.get("MACD_hist")) else "N/A",
        "ADX":    round(row["ADX"], 1)  if pd.notna(row.get("ADX"))  else "N/A",
        "MFI":    round(row["MFI"], 1)  if pd.notna(row.get("MFI"))  else "N/A",
        "OBV":    int(row["OBV"])       if pd.notna(row.get("OBV"))  else "N/A",
    }

    price_levels = {
        "close":      round(row["close"], 3),
        "boll_upper": round(row["BOLL_upper"], 3) if pd.notna(row.get("BOLL_upper")) else None,
        "boll_lower": round(row["BOLL_lower"], 3) if pd.notna(row.get("BOLL_lower")) else None,
        "ma20":       round(row["MA20"], 3)        if pd.notna(row.get("MA20"))        else None,
        "ma60":       round(row["MA60"], 3)        if pd.notna(row.get("MA60"))        else None,
    }

    return {
        "signal":       signal,
        "score":        round(score, 3),
        "details":      details,
        "latest":       latest,
        "price_levels": price_levels,
    }


# ── 工具函数 ──────────────────────────────────────────────────

def _label(score: float) -> str:
    if score >= 0.6:
        return "强烈看多"
    elif score > 0:
        return "看多"
    elif score == 0:
        return "中性"
    elif score > -0.6:
        return "看空"
    else:
        return "强烈看空"


def _score_to_signal(score: float) -> str:
    if score >= 0.6:
        return "强烈买入"
    elif score >= 0.2:
        return "买入"
    elif score > -0.2:
        return "观望"
    elif score > -0.6:
        return "卖出"
    else:
        return "强烈卖出"
