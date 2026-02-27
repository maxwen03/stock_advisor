# ============================================================
# 股票配置文件
# ============================================================

# 股票列表，格式：{"symbol": "代码", "name": "名称", "market": "市场"}
# market 可选值: "A" (A股), "US" (美股), "HK" (港股)
# 若同目录存在 watchlist.json，则优先从该文件加载（由交互菜单维护）
WATCHLIST = [
    # 美股
    {"symbol": "ASTS",  "name": "AST SpaceMobile", "market": "US"},
    {"symbol": "SATS",  "name": "EchoStar",         "market": "US"},
    {"symbol": "ABVX",  "name": "Abivax",            "market": "US"},
    {"symbol": "NKTR",  "name": "Nektar Therapeutics","market": "US"},
    # 港股
    {"symbol": "00100", "name": "Minimax",           "market": "HK"},
]

import json as _json, os as _os
_wl_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "watchlist.json")
if _os.path.exists(_wl_path):
    with open(_wl_path, encoding="utf-8") as _f:
        WATCHLIST = _json.load(_f)
del _json, _os, _wl_path

# ============================================================
# 技术指标参数
# ============================================================
INDICATOR_PARAMS = {
    "ma_periods":   [5, 10, 20, 60],  # 均线周期
    "rsi_period":   14,                # RSI 周期
    "macd_fast":    12,                # MACD 快线
    "macd_slow":    26,                # MACD 慢线
    "macd_signal":  9,                 # MACD 信号线
    "boll_period":  20,                # 布林带周期
    "boll_std":     2,                 # 布林带标准差倍数
    "adx_period":   14,                # ADX 周期
    "roc_period":   12,                # ROC 周期
    "mom_period":   10,                # Momentum 周期
    # 成交量动能指标
    "vol_ma_periods": [5, 10, 20],    # 成交量均线周期
    "vroc_period":  12,                # 成交量变化率周期
    "mfi_period":   14,                # 资金流量指数周期（MFI）
}

# ============================================================
# 信号阈值
# ============================================================
SIGNAL_THRESHOLDS = {
    "rsi_overbought":  70,   # RSI 超买
    "rsi_oversold":    30,   # RSI 超卖
    "adx_strong":      25,   # ADX 强趋势阈值
}

# ============================================================
# 数据设置
# ============================================================
DATA_DIR = "data_store"           # 本地数据库目录
DB_FILE  = "data_store/stocks.db" # SQLite 数据库路径
HISTORY_DAYS = 365                 # 拉取历史天数

# ============================================================
# 调度设置（每天自动运行的时间，24小时制）
# ============================================================
SCHEDULE_TIME = "09:00"            # 每天09:00自动运行（A股/港股开盘前）

# ============================================================
# 新闻搜索设置
# ============================================================

# X (Twitter) Bearer Token — 填入后启用 X 搜索，留空则跳过
# 申请地址: https://developer.twitter.com/en/portal/dashboard
TWITTER_BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAAOZp7wEAAAAA3Solr%2BKFcSmA2f3iByInmPrIW6A%3Dh1NkJGgFvP6XDHMWAvtEzKPzrRKQgQtdMbQcSQ3pEYfL5dMCnJ"

# 每个平台最多抓取的新闻条数
NEWS_PER_SOURCE = 5

# ============================================================
# 报告输出
# ============================================================
REPORT_DIR = "reports"             # 报告保存目录
