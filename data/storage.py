"""
数据存储模块
使用 SQLite 保存历史行情数据，支持增量更新
"""

import os
import sqlite3
import pandas as pd
from config import DB_FILE, DATA_DIR


def _get_conn() -> sqlite3.Connection:
    os.makedirs(DATA_DIR, exist_ok=True)
    return sqlite3.connect(DB_FILE)


def save_price_data(symbol: str, market: str, df: pd.DataFrame) -> None:
    """将行情数据写入数据库（自动去重）"""
    if df.empty:
        return

    table = _table_name(symbol, market)
    df = df.copy()
    df["date"] = df["date"].astype(str)

    records = df[["date", "open", "high", "low", "close", "volume"]].values.tolist()

    with _get_conn() as conn:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS "{table}" (
                date    TEXT PRIMARY KEY,
                open    REAL,
                high    REAL,
                low     REAL,
                close   REAL,
                volume  REAL
            )
        """)
        # INSERT OR REPLACE 自动去重/覆盖
        conn.executemany(
            f'INSERT OR REPLACE INTO "{table}" (date, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?)',
            records,
        )
        conn.commit()


def load_price_data(symbol: str, market: str) -> pd.DataFrame:
    """从数据库加载全部历史数据，按日期升序返回"""
    table = _table_name(symbol, market)
    with _get_conn() as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        existing = [t[0] for t in tables]
        if table not in existing:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

        df = pd.read_sql(f'SELECT * FROM "{table}" ORDER BY date ASC', conn)

    df["date"] = pd.to_datetime(df["date"])
    return df


def get_last_date(symbol: str, market: str):
    """返回数据库中该股票最新的日期，如果没有记录则返回 None"""
    table = _table_name(symbol, market)
    with _get_conn() as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        existing = [t[0] for t in tables]
        if table not in existing:
            return None
        row = conn.execute(f'SELECT MAX(date) FROM "{table}"').fetchone()
        return row[0] if row else None


# ── 私有工具 ────────────────────────────────────────────────

def _table_name(symbol: str, market: str) -> str:
    return f"{market}_{symbol}"


