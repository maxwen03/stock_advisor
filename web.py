"""
Trading Agent — Flask Web 界面（普通 HTTP，无需 WebSocket）
运行方式: python web.py
"""

import os, sys, json, traceback
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, session

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
app.secret_key = "trading-agent-secret-2025"

WATCHLIST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "watchlist.json")
MARKET_LABELS  = {"US": "美股", "HK": "港股", "A": "A股"}

# ── 自选股管理 ─────────────────────────────────────────────────

def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, encoding="utf-8") as f:
            return json.load(f)
    from config import WATCHLIST
    return list(WATCHLIST)

def save_watchlist(wl):
    with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(wl, f, ensure_ascii=False, indent=2)

# ── 股票分析 ───────────────────────────────────────────────────

def process_stock(symbol, market, name):
    from config import HISTORY_DAYS
    from data.fetcher import fetch_stock
    from data.storage import save_price_data, load_price_data, get_last_date
    from analysis.indicators import compute_all
    from analysis.signals import generate_signals
    from analysis.anomaly import check_anomaly

    last_date_str = get_last_date(symbol, market)
    if last_date_str is None:
        new_df = fetch_stock(symbol, market, days=HISTORY_DAYS)
    else:
        last_dt = datetime.strptime(last_date_str[:10], "%Y-%m-%d")
        days_missing = (datetime.today() - last_dt).days + 1
        new_df = fetch_stock(symbol, market, days=min(days_missing + 5, HISTORY_DAYS)) if days_missing > 0 else None

    if new_df is not None and not new_df.empty:
        save_price_data(symbol, market, new_df)

    df = load_price_data(symbol, market)
    if df.empty or len(df) < 2:
        return {"symbol": symbol, "name": name, "market": market,
                "error": f"历史数据不足（仅 {len(df)} 条）"}

    df_ind  = compute_all(df)
    sig     = generate_signals(df_ind)
    anomaly = check_anomaly(df, symbol, market, name)

    # 最近90天收盘价（用于图表）
    chart = df[["date", "close"]].tail(90).copy()
    chart["date"] = chart["date"].astype(str).str[:10]

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
        "chart_dates":  chart["date"].tolist(),
        "chart_prices": chart["close"].round(3).tolist(),
    }

# ── HTML 模板 ──────────────────────────────────────────────────

BASE_HTML = """
<!doctype html>
<html lang="zh">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Trading Agent</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
  <style>
    body { background: #0f1117; color: #e0e0e0; }
    .navbar { background: #1a1d27 !important; border-bottom: 1px solid #2d3042; }
    .card  { background: #1a1d27; border: 1px solid #2d3042; }
    .card-header { background: #22263a; border-bottom: 1px solid #2d3042; }
    .table { color: #e0e0e0; }
    .table thead th { border-color: #2d3042; }
    .table td, .table th { border-color: #2d3042; }
    .badge-强烈买入 { background:#00c853; color:#000; }
    .badge-买入     { background:#69f0ae; color:#000; }
    .badge-观望     { background:#ffd740; color:#000; }
    .badge-卖出     { background:#ff6d00; color:#fff; }
    .badge-强烈卖出 { background:#d50000; color:#fff; }
    .metric-box { background:#22263a; border-radius:8px; padding:12px 16px; text-align:center; }
    .metric-label { font-size:.75rem; color:#888; margin-bottom:4px; }
    .metric-value { font-size:1.3rem; font-weight:700; }
    pre { background:#0d1117; border:1px solid #2d3042; border-radius:6px;
          padding:16px; color:#c9d1d9; white-space:pre-wrap; word-break:break-all; }
    .btn-primary { background:#5c6bc0; border-color:#5c6bc0; }
    .btn-primary:hover { background:#7986cb; border-color:#7986cb; }
    .loading-overlay { display:none; position:fixed; inset:0; background:rgba(0,0,0,.6);
                       z-index:9999; align-items:center; justify-content:center; flex-direction:column; }
    .loading-overlay.show { display:flex; }
    .spinner-border { width:3rem; height:3rem; }
  </style>
</head>
<body>
<div class="loading-overlay" id="loadingOverlay">
  <div class="spinner-border text-light mb-3"></div>
  <div class="text-light fs-5">正在分析，请稍候...</div>
</div>

<nav class="navbar navbar-expand-lg navbar-dark">
  <div class="container-fluid">
    <a class="navbar-brand fw-bold" href="/">📈 Trading Agent</a>
    <div class="d-flex">
      <a class="nav-link text-light me-3" href="/">仪表盘</a>
      <a class="nav-link text-light me-3" href="/single">分析单只</a>
      <a class="nav-link text-light me-3" href="/reports">历史报告</a>
      <a class="nav-link text-light" href="/watchlist">管理自选股</a>
    </div>
  </div>
</nav>

<div class="container-fluid py-4">
  {% with msgs = get_flashed_messages(with_categories=true) %}
    {% for cat, msg in msgs %}
      <div class="alert alert-{{ 'danger' if cat=='error' else 'success' }} alert-dismissible">
        {{ msg }}<button type="button" class="btn-close" data-bs-dismiss="alert"></button>
      </div>
    {% endfor %}
  {% endwith %}

  {{ content | safe }}
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
<script>
function showLoading() {
  document.getElementById('loadingOverlay').classList.add('show');
  return true;
}
</script>
{{ extra_js | safe }}
</body>
</html>
"""

def render_page(content, extra_js=""):
    from flask import get_flashed_messages
    return render_template_string(BASE_HTML, content=content, extra_js=extra_js)

# ── 信号徽章 ───────────────────────────────────────────────────

def signal_badge(signal):
    return f'<span class="badge badge-{signal} px-3 py-2 fs-6">{signal}</span>'

def score_bar(score):
    pct  = int((score + 1) / 2 * 100)
    color = "#00c853" if score >= 0.2 else ("#d50000" if score <= -0.2 else "#ffd740")
    return (f'<div class="progress" style="height:8px;background:#2d3042;">'
            f'<div class="progress-bar" style="width:{pct}%;background:{color};"></div></div>'
            f'<small class="text-muted">{score:+.3f}</small>')

def stock_card(r, idx=0):
    market_label = MARKET_LABELS.get(r["market"], r["market"])
    if "error" in r:
        return (f'<div class="card mb-3"><div class="card-body">'
                f'<h6 class="text-danger">⚠ {r["name"]} ({r["symbol"]}) [{market_label}]</h6>'
                f'<p class="mb-0">{r["error"]}</p></div></div>')

    signal  = r.get("signal", "N/A")
    score   = r.get("score", 0)
    latest  = r.get("latest", {})
    details = r.get("details", {})
    price_levels = r.get("price_levels", {})
    anomaly = r.get("anomaly")
    chart_dates  = r.get("chart_dates", [])
    chart_prices = r.get("chart_prices", [])

    # 指标表格行
    det_rows = "".join(
        f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in details.items()
    )

    # 价格
    def fmt(v): return str(v) if v is not None else "N/A"

    # 图表 JS
    chart_js = ""
    if chart_dates and chart_prices:
        cid = f"chart_{idx}"
        chart_js = f"""
<script>
(function(){{
  var ctx = document.getElementById('{cid}');
  if(!ctx) return;
  new Chart(ctx, {{
    type:'line',
    data:{{
      labels:{json.dumps(chart_dates)},
      datasets:[{{
        data:{json.dumps(chart_prices)},
        borderColor:'#5c6bc0', borderWidth:2,
        pointRadius:0, tension:0.3, fill:false
      }}]
    }},
    options:{{
      responsive:true, maintainAspectRatio:false,
      plugins:{{legend:{{display:false}}}},
      scales:{{
        x:{{ticks:{{color:'#888',maxTicksLimit:6}},grid:{{color:'#2d3042'}}}},
        y:{{ticks:{{color:'#888'}},grid:{{color:'#2d3042'}}}}
      }}
    }}
  }});
}})();
</script>"""

    # 异动提醒
    anomaly_html = ""
    if anomaly:
        direction  = anomaly.get("direction", "")
        change_pct = anomaly.get("change_pct", 0)
        news_list  = anomaly.get("news", [])
        icon = "🚀" if direction == "暴涨" else "📉"
        news_html = ""
        for i, item in enumerate(news_list[:8], 1):
            time_str  = f"[{item['time']}] " if item.get("time") else ""
            src_str   = f"({item['source']}) " if item.get("source") else ""
            url, title = item.get("url",""), item.get("title","")
            link = f'<a href="{url}" target="_blank">{title}</a>' if url else title
            news_html += f"<li>{time_str}{src_str}{link}</li>"
        anomaly_html = f"""
<div class="alert alert-warning mt-3">
  {icon} <strong>异动提醒</strong> [{anomaly['date']}]
  {direction} {change_pct:+.2f}%
  收盘: {anomaly['close']} &nbsp;前收: {anomaly['prev_close']}
  {'<ul class="mt-2 mb-0">' + news_html + '</ul>' if news_html else ''}
</div>"""

    canvas_html = f'<canvas id="chart_{idx}" style="height:200px;"></canvas>' if chart_dates else ""

    return f"""
<div class="card mb-4">
  <div class="card-header d-flex justify-content-between align-items-center">
    <div>
      <span class="badge bg-secondary me-2">{market_label}</span>
      <strong>{r['name']}</strong>
      <span class="text-muted ms-2">({r['symbol']})</span>
    </div>
    <div class="text-end">
      {signal_badge(signal)}
      <div class="mt-1">{score_bar(score)}</div>
    </div>
  </div>
  <div class="card-body">
    <div class="row g-2 mb-3">
      <div class="col-6 col-md-3"><div class="metric-box">
        <div class="metric-label">收盘价</div>
        <div class="metric-value">{fmt(latest.get('收盘价'))}</div>
      </div></div>
      <div class="col-6 col-md-3"><div class="metric-box">
        <div class="metric-label">涨跌幅</div>
        <div class="metric-value">{fmt(latest.get('涨跌幅'))}</div>
      </div></div>
      <div class="col-6 col-md-3"><div class="metric-box">
        <div class="metric-label">RSI</div>
        <div class="metric-value">{fmt(latest.get('RSI'))}</div>
      </div></div>
      <div class="col-6 col-md-3"><div class="metric-box">
        <div class="metric-label">ADX</div>
        <div class="metric-value">{fmt(latest.get('ADX'))}</div>
      </div></div>
      <div class="col-6 col-md-3"><div class="metric-box">
        <div class="metric-label">MACD柱</div>
        <div class="metric-value">{fmt(latest.get('MACD柱'))}</div>
      </div></div>
      <div class="col-6 col-md-3"><div class="metric-box">
        <div class="metric-label">MFI</div>
        <div class="metric-value">{fmt(latest.get('MFI'))}</div>
      </div></div>
      <div class="col-6 col-md-3"><div class="metric-box">
        <div class="metric-label">布林上轨</div>
        <div class="metric-value">{fmt(price_levels.get('boll_upper'))}</div>
      </div></div>
      <div class="col-6 col-md-3"><div class="metric-box">
        <div class="metric-label">布林下轨</div>
        <div class="metric-value">{fmt(price_levels.get('boll_lower'))}</div>
      </div></div>
    </div>

    {canvas_html}

    {anomaly_html}

    <details class="mt-3">
      <summary class="text-muted" style="cursor:pointer;">📊 指标详情</summary>
      <table class="table table-sm mt-2">
        <thead><tr><th>指标</th><th>状态</th></tr></thead>
        <tbody>{det_rows}</tbody>
      </table>
    </details>
  </div>
</div>
{chart_js}"""

# ── 路由：仪表盘 ───────────────────────────────────────────────

@app.route("/")
def dashboard():
    wl = load_watchlist()
    results = session.get("dashboard_results", [])
    timestamp = session.get("dashboard_time", "")

    summary_rows = ""
    for r in results:
        if "error" not in r:
            sig = r.get("signal","N/A")
            summary_rows += (
                f"<tr><td>{r['name']}</td><td>{r['symbol']}</td>"
                f"<td>{MARKET_LABELS.get(r['market'],r['market'])}</td>"
                f"<td>{r['latest'].get('收盘价','N/A')}</td>"
                f"<td>{r['latest'].get('涨跌幅','N/A')}</td>"
                f"<td>{r['latest'].get('RSI','N/A')}</td>"
                f"<td>{signal_badge(sig)}</td>"
                f"<td>{r['score']:+.3f}</td></tr>"
            )

    cards_html  = "".join(stock_card(r, i) for i, r in enumerate(results))
    extra_js    = "".join(
        r.get("_chart_js","") for r in results
    )

    summary_html = f"""
<div class="card mb-4">
  <div class="card-header">汇总总览
    {'<small class="text-muted ms-2">更新于 ' + timestamp + '</small>' if timestamp else ''}
  </div>
  <div class="card-body p-0">
    <div class="table-responsive">
    <table class="table table-hover mb-0">
      <thead><tr>
        <th>名称</th><th>代码</th><th>市场</th>
        <th>收盘价</th><th>涨跌幅</th><th>RSI</th>
        <th>信号</th><th>评分</th>
      </tr></thead>
      <tbody>{summary_rows if summary_rows else '<tr><td colspan="8" class="text-center text-muted py-3">点击下方按钮开始分析</td></tr>'}</tbody>
    </table>
    </div>
  </div>
</div>""" if results else ""

    content = f"""
<div class="d-flex justify-content-between align-items-center mb-4">
  <h4 class="mb-0">📊 自选股仪表盘 <small class="text-muted fs-6">共 {len(wl)} 只</small></h4>
  <form method="post" action="/analyze-all" onsubmit="return showLoading()">
    <button class="btn btn-primary" type="submit">🔄 分析全部自选股</button>
  </form>
</div>
{summary_html}
{cards_html if cards_html else
  '<div class="text-center text-muted py-5"><h5>点击「分析全部自选股」开始</h5></div>'}
"""
    return render_page(content)


@app.route("/analyze-all", methods=["POST"])
def analyze_all():
    wl = load_watchlist()
    results = []
    for stock in wl:
        sym  = stock["symbol"]
        mkt  = stock["market"]
        name = stock.get("name", sym)
        try:
            r = process_stock(sym, mkt, name)
        except Exception as e:
            r = {"symbol": sym, "name": name, "market": mkt, "error": str(e)}
        results.append(r)

    # 保存报告
    try:
        from report.generator import build_report, save_report
        clean = [{k: v for k, v in r.items()
                  if k not in ("chart_dates","chart_prices")} for r in results]
        save_report(build_report(clean))
    except Exception:
        pass

    session["dashboard_results"] = results
    session["dashboard_time"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    return redirect(url_for("dashboard"))


# ── 路由：分析单只 ─────────────────────────────────────────────

@app.route("/single", methods=["GET","POST"])
def single():
    wl = load_watchlist()
    result_html = ""
    selected_symbol = request.form.get("symbol","")
    selected_market = request.form.get("market","US")

    if request.method == "POST":
        name   = request.form.get("name","").strip()
        symbol = selected_symbol.strip().upper()
        market = selected_market
        if symbol:
            try:
                r = process_stock(symbol, market, name or symbol)
                result_html = stock_card(r, 99)
            except Exception as e:
                result_html = f'<div class="alert alert-danger">{e}<pre>{traceback.format_exc()}</pre></div>'

    options_html = ""
    for s in wl:
        sel = 'selected' if s["symbol"]==selected_symbol and s["market"]==selected_market else ""
        options_html += (f'<option value="{s["symbol"]}" data-market="{s["market"]}" {sel}>'
                        f'{s["name"]} ({s["symbol"]}) [{s["market"]}]</option>')

    content = f"""
<h4 class="mb-4">🔍 分析单只股票</h4>
<div class="card mb-4">
  <div class="card-body">
    <form method="post" onsubmit="return showLoading()">
      <div class="row g-3">
        <div class="col-md-4">
          <label class="form-label">从自选股选择</label>
          <select class="form-select bg-dark text-light border-secondary" id="wl_select">
            <option value="">— 手动输入 —</option>
            {options_html}
          </select>
        </div>
        <div class="col-md-3">
          <label class="form-label">股票代码</label>
          <input class="form-control bg-dark text-light border-secondary" name="symbol"
                 id="sym_input" placeholder="如 AAPL / 00700 / 600519"
                 value="{selected_symbol}" required>
        </div>
        <div class="col-md-2">
          <label class="form-label">名称（可选）</label>
          <input class="form-control bg-dark text-light border-secondary" name="name">
        </div>
        <div class="col-md-2">
          <label class="form-label">市场</label>
          <select class="form-select bg-dark text-light border-secondary" name="market" id="mkt_select">
            <option value="US" {'selected' if selected_market=='US' else ''}>美股 US</option>
            <option value="HK" {'selected' if selected_market=='HK' else ''}>港股 HK</option>
            <option value="A"  {'selected' if selected_market=='A'  else ''}>A股</option>
          </select>
        </div>
        <div class="col-md-1 d-flex align-items-end">
          <button class="btn btn-primary w-100" type="submit">分析</button>
        </div>
      </div>
    </form>
  </div>
</div>
{result_html}
<script>
document.getElementById('wl_select').addEventListener('change', function(){{
  var opt = this.options[this.selectedIndex];
  if(opt.value){{
    document.getElementById('sym_input').value = opt.value;
    var mkt = opt.getAttribute('data-market');
    document.getElementById('mkt_select').value = mkt;
  }}
}});
</script>"""
    return render_page(content)


# ── 路由：历史报告 ─────────────────────────────────────────────

@app.route("/reports")
def reports():
    from config import REPORT_DIR
    files = []
    if os.path.exists(REPORT_DIR):
        files = sorted([f for f in os.listdir(REPORT_DIR) if f.endswith(".txt")], reverse=True)

    rows = ""
    for f in files[:30]:
        ts = f.replace("report_","").replace(".txt","")
        try:    label = datetime.strptime(ts,"%Y%m%d_%H%M").strftime("%Y-%m-%d %H:%M")
        except: label = ts
        size_kb = os.path.getsize(os.path.join(REPORT_DIR, f)) // 1024
        rows += (f'<tr><td>{label}</td><td>{size_kb} KB</td>'
                 f'<td><a href="/reports/{f}" class="btn btn-sm btn-outline-light">查看</a> '
                 f'<a href="/reports/{f}/download" class="btn btn-sm btn-outline-secondary">下载</a>'
                 f'</td></tr>')

    content = f"""
<h4 class="mb-4">📋 历史报告</h4>
<div class="card">
  <div class="card-body p-0">
    <table class="table table-hover mb-0">
      <thead><tr><th>时间</th><th>大小</th><th>操作</th></tr></thead>
      <tbody>{rows if rows else '<tr><td colspan="3" class="text-center text-muted py-4">暂无历史报告</td></tr>'}</tbody>
    </table>
  </div>
</div>"""
    return render_page(content)


@app.route("/reports/<filename>")
def view_report(filename):
    from config import REPORT_DIR
    path = os.path.join(REPORT_DIR, os.path.basename(filename))
    if not os.path.exists(path):
        return redirect(url_for("reports"))
    with open(path, encoding="utf-8") as f:
        content_text = f.read()
    content = f"""
<div class="d-flex justify-content-between align-items-center mb-3">
  <h4 class="mb-0">📄 {filename}</h4>
  <div>
    <a href="/reports/{filename}/download" class="btn btn-outline-light btn-sm me-2">⬇ 下载</a>
    <a href="/reports" class="btn btn-outline-secondary btn-sm">← 返回</a>
  </div>
</div>
<pre>{content_text}</pre>"""
    return render_page(content)


@app.route("/reports/<filename>/download")
def download_report(filename):
    from flask import send_from_directory
    from config import REPORT_DIR
    return send_from_directory(
        os.path.abspath(REPORT_DIR),
        os.path.basename(filename),
        as_attachment=True,
    )


# ── 路由：管理自选股 ───────────────────────────────────────────

@app.route("/watchlist", methods=["GET","POST"])
def watchlist():
    from flask import flash
    wl = load_watchlist()

    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            sym  = request.form.get("symbol","").strip().upper()
            name = request.form.get("name","").strip()
            mkt  = request.form.get("market","US")
            if sym:
                if any(s["symbol"]==sym and s["market"]==mkt for s in wl):
                    flash(f"{sym} 已在列表中", "error")
                else:
                    wl.append({"symbol": sym, "name": name or sym, "market": mkt})
                    save_watchlist(wl)
                    flash(f"已添加 {name or sym} ({sym}) [{mkt}]", "success")
        elif action == "delete":
            idx = int(request.form.get("idx", -1))
            if 0 <= idx < len(wl):
                removed = wl.pop(idx)
                save_watchlist(wl)
                flash(f"已删除 {removed['name']} ({removed['symbol']})", "success")
        return redirect(url_for("watchlist"))

    rows = ""
    for i, s in enumerate(wl):
        sname  = s["name"]
        smkt   = MARKET_LABELS.get(s["market"], s["market"])
        confirm_msg = "确认删除 " + sname + " ?"
        rows += (f'<tr><td>{i+1}</td><td>{sname}</td><td>{s["symbol"]}</td>'
                 f'<td>{smkt}</td>'
                 f'<td><form method="post" style="display:inline">'
                 f'<input type="hidden" name="action" value="delete">'
                 f'<input type="hidden" name="idx" value="{i}">'
                 f'<button class="btn btn-sm btn-outline-danger" '
                 f'onclick="return confirm({json.dumps(confirm_msg)})">删除</button>'
                 f'</form></td></tr>')

    content = f"""
<h4 class="mb-4">⚙ 管理自选股列表</h4>
<div class="card mb-4">
  <div class="card-header">当前自选股（{len(wl)} 只）</div>
  <div class="card-body p-0">
    <table class="table mb-0">
      <thead><tr><th>#</th><th>名称</th><th>代码</th><th>市场</th><th>操作</th></tr></thead>
      <tbody>{rows if rows else '<tr><td colspan="5" class="text-center text-muted py-3">列表为空</td></tr>'}</tbody>
    </table>
  </div>
</div>

<div class="card">
  <div class="card-header">添加股票</div>
  <div class="card-body">
    <form method="post">
      <input type="hidden" name="action" value="add">
      <div class="row g-3">
        <div class="col-md-3">
          <label class="form-label">股票代码</label>
          <input class="form-control bg-dark text-light border-secondary" name="symbol"
                 placeholder="如 AAPL / 00700 / 600519" required>
        </div>
        <div class="col-md-4">
          <label class="form-label">名称</label>
          <input class="form-control bg-dark text-light border-secondary" name="name" placeholder="可留空">
        </div>
        <div class="col-md-3">
          <label class="form-label">市场</label>
          <select class="form-select bg-dark text-light border-secondary" name="market">
            <option value="US">美股 US</option>
            <option value="HK">港股 HK</option>
            <option value="A">A股</option>
          </select>
        </div>
        <div class="col-md-2 d-flex align-items-end">
          <button class="btn btn-primary w-100" type="submit">➕ 添加</button>
        </div>
      </div>
    </form>
  </div>
</div>"""
    return render_page(content)


# ── 启动 ───────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8501, debug=False)
