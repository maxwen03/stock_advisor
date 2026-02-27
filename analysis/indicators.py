"""
技术指标计算模块
包含：均线(MA)、ROC、Momentum、RSI、MACD、ADX、布林带(BOLL)
成交量动能：OBV、VROC、MFI、量均线
"""

import pandas as pd
import numpy as np
from config import INDICATOR_PARAMS as P


def compute_all(df: pd.DataFrame) -> pd.DataFrame:
    """
    对传入的行情 DataFrame 计算全部技术指标
    输入列：date, open, high, low, close, volume
    输出：在原 df 上追加所有指标列
    """
    df = df.copy()

    df = _ma(df)
    df = _roc(df)
    df = _momentum(df)
    df = _rsi(df)
    df = _macd(df)
    df = _adx(df)
    df = _bollinger(df)

    # 成交量动能
    df = _vol_ma(df)
    df = _vroc(df)
    df = _obv(df)
    df = _mfi(df)

    return df


# ── 价格类指标 ────────────────────────────────────────────────

def _ma(df: pd.DataFrame) -> pd.DataFrame:
    for p in P["ma_periods"]:
        df[f"MA{p}"] = df["close"].rolling(p).mean()
    return df


def _roc(df: pd.DataFrame) -> pd.DataFrame:
    n = P["roc_period"]
    df["ROC"] = df["close"].pct_change(n) * 100
    return df


def _momentum(df: pd.DataFrame) -> pd.DataFrame:
    n = P["mom_period"]
    df["MOM"] = df["close"] - df["close"].shift(n)
    return df


def _rsi(df: pd.DataFrame) -> pd.DataFrame:
    n = P["rsi_period"]
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=n - 1, min_periods=n).mean()
    avg_loss = loss.ewm(com=n - 1, min_periods=n).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))
    return df


def _macd(df: pd.DataFrame) -> pd.DataFrame:
    fast   = P["macd_fast"]
    slow   = P["macd_slow"]
    signal = P["macd_signal"]
    ema_fast   = df["close"].ewm(span=fast,   adjust=False).mean()
    ema_slow   = df["close"].ewm(span=slow,   adjust=False).mean()
    df["MACD"]        = ema_fast - ema_slow
    df["MACD_signal"] = df["MACD"].ewm(span=signal, adjust=False).mean()
    df["MACD_hist"]   = df["MACD"] - df["MACD_signal"]
    return df


def _adx(df: pd.DataFrame) -> pd.DataFrame:
    n = P["adx_period"]
    high  = df["high"]
    low   = df["low"]
    close = df["close"]

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)

    dm_plus  = (high - high.shift()).clip(lower=0)
    dm_minus = (low.shift() - low).clip(lower=0)
    # 当 +DM < -DM 时 +DM 归零，反之亦然
    dm_plus  = dm_plus.where(dm_plus > dm_minus, 0)
    dm_minus = dm_minus.where(dm_minus > dm_plus.shift().fillna(0), 0)

    atr    = tr.ewm(span=n, adjust=False).mean()
    di_pos = 100 * dm_plus.ewm(span=n, adjust=False).mean() / atr
    di_neg = 100 * dm_minus.ewm(span=n, adjust=False).mean() / atr
    dx     = 100 * (di_pos - di_neg).abs() / (di_pos + di_neg).replace(0, np.nan)

    df["ADX"]    = dx.ewm(span=n, adjust=False).mean()
    df["DI_pos"] = di_pos
    df["DI_neg"] = di_neg
    return df


def _bollinger(df: pd.DataFrame) -> pd.DataFrame:
    n   = P["boll_period"]
    std = P["boll_std"]
    mid         = df["close"].rolling(n).mean()
    band        = df["close"].rolling(n).std()
    df["BOLL_mid"]   = mid
    df["BOLL_upper"] = mid + std * band
    df["BOLL_lower"] = mid - std * band
    df["BOLL_width"] = (df["BOLL_upper"] - df["BOLL_lower"]) / mid  # 带宽
    df["BOLL_%B"]    = (df["close"] - df["BOLL_lower"]) / (df["BOLL_upper"] - df["BOLL_lower"])  # %B 位置
    return df


# ── 成交量动能指标 ────────────────────────────────────────────

def _vol_ma(df: pd.DataFrame) -> pd.DataFrame:
    for p in P["vol_ma_periods"]:
        df[f"VOL_MA{p}"] = df["volume"].rolling(p).mean()
    return df


def _vroc(df: pd.DataFrame) -> pd.DataFrame:
    n = P["vroc_period"]
    df["VROC"] = df["volume"].pct_change(n) * 100
    return df


def _obv(df: pd.DataFrame) -> pd.DataFrame:
    direction = np.sign(df["close"].diff()).fillna(0)
    df["OBV"] = (direction * df["volume"]).cumsum()
    return df


def _mfi(df: pd.DataFrame) -> pd.DataFrame:
    n = P["mfi_period"]
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    raw_mf        = typical_price * df["volume"]
    pos_mf = raw_mf.where(typical_price > typical_price.shift(), 0)
    neg_mf = raw_mf.where(typical_price < typical_price.shift(), 0)
    pos_sum = pos_mf.rolling(n).sum()
    neg_sum = neg_mf.rolling(n).sum()
    mfr = pos_sum / neg_sum.replace(0, np.nan)
    df["MFI"] = 100 - (100 / (1 + mfr))
    return df
