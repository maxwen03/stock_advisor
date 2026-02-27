"""
新闻搜索模块
异动触发时，从 5 个平台同时搜索公司相关新闻：
  - X (Twitter)     — 需要 TWITTER_BEARER_TOKEN
  - Bloomberg        — 通过 Google News RSS 过滤 site:bloomberg.com
  - WSJ              — 通过 Google News RSS 过滤 site:wsj.com
  - FT (ft.com)      — 通过 Google News RSS 过滤 site:ft.com
  - Investing.com    — 通过 Google News RSS 过滤 site:investing.com
"""

import re
import requests
import xml.etree.ElementTree as ET
from datetime import date
from typing import List, Dict
from urllib.parse import quote_plus

from config import TWITTER_BEARER_TOKEN, NEWS_PER_SOURCE

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
_TIMEOUT = 12


# ── 公开入口 ─────────────────────────────────────────────────

def fetch_news(symbol: str, market: str, name: str = "", target_date: date = None) -> List[Dict]:
    """
    并发搜索所有平台，返回合并去重后的新闻列表。
    每条格式: {"title", "source", "url", "time"}
    """
    query_terms = _build_query(symbol, name)

    results: List[Dict] = []

    # 1. X (Twitter)
    results += _search_x(query_terms)

    # 2-5. Google News RSS 过滤各平台
    for site_label, site_domain in [
        ("Bloomberg",     "bloomberg.com"),
        ("WSJ",           "wsj.com"),
        ("Financial Times","ft.com"),
        ("Investing.com", "investing.com"),
    ]:
        results += _search_via_google_news(query_terms, site_domain, site_label)

    # 去重（相同标题只保留第一条）
    seen, deduped = set(), []
    for item in results:
        key = item["title"][:60]
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    return deduped


# ── 各平台实现 ────────────────────────────────────────────────

def _search_x(query_terms: str) -> List[Dict]:
    """通过 Twitter API v2 搜索最近推文"""
    token = TWITTER_BEARER_TOKEN
    if not token:
        return [{"title": "[X搜索未启用：请在 config.py 中填写 TWITTER_BEARER_TOKEN]",
                 "source": "X (Twitter)", "url": "https://developer.twitter.com/en/portal/dashboard", "time": ""}]

    query = f"({query_terms}) lang:en -is:retweet"
    url   = "https://api.twitter.com/2/tweets/search/recent"
    params = {
        "query":        query,
        "max_results":  NEWS_PER_SOURCE,
        "tweet.fields": "created_at,text",
        "expansions":   "author_id",
        "user.fields":  "username",
    }
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=_TIMEOUT)
        r.raise_for_status()
        data  = r.json()
        tweets = data.get("data", [])
        users  = {u["id"]: u["username"] for u in data.get("includes", {}).get("users", [])}
        return [{
            "title":  t["text"][:200],
            "source": "X (Twitter)",
            "url":    f"https://x.com/{users.get(t.get('author_id',''), 'i')}/status/{t['id']}",
            "time":   t.get("created_at", ""),
        } for t in tweets]
    except Exception as e:
        return [{"title": f"[X搜索失败: {e}]", "source": "X (Twitter)", "url": "", "time": ""}]


def _search_via_google_news(query_terms: str, site: str, label: str) -> List[Dict]:
    """
    用 Google News RSS 搜索指定站点的文章
    URL 格式: https://news.google.com/rss/search?q={query}+site:{site}&hl=en-US&gl=US&ceid=US:en
    """
    full_query = f"{query_terms} site:{site}"
    encoded    = quote_plus(full_query)
    url        = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"

    try:
        r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        r.raise_for_status()
        return _parse_rss(r.text, label, max_items=NEWS_PER_SOURCE)
    except Exception as e:
        return [{"title": f"[{label} 搜索失败: {e}]", "source": label, "url": "", "time": ""}]


# ── RSS 解析 ──────────────────────────────────────────────────

def _parse_rss(xml_text: str, default_source: str, max_items: int = 5) -> List[Dict]:
    """解析 RSS/Atom XML，返回新闻列表"""
    results = []
    try:
        root = ET.fromstring(xml_text)
        # 兼容标准 RSS (<channel><item>) 和 Atom (<entry>)
        ns   = {"media": "http://search.yahoo.com/mrss/"}
        items = root.findall(".//item") or root.findall(".//entry")
        for item in items[:max_items]:
            title  = _text(item, "title")
            link   = _text(item, "link") or _text(item, "id")
            pubdate= _text(item, "pubDate") or _text(item, "published") or _text(item, "updated")
            source = _text(item, "source") or default_source
            # Google News 链接是重定向链接，保留原始链接
            if link and "news.google.com" in link:
                # 提取 url= 参数（部分格式有）
                m = re.search(r'url=([^&]+)', link)
                if m:
                    from urllib.parse import unquote
                    link = unquote(m.group(1))
            if title:
                results.append({
                    "title":  _strip_html(title),
                    "source": source,
                    "url":    link or "",
                    "time":   pubdate or "",
                })
    except ET.ParseError:
        pass
    return results


# ── 工具函数 ──────────────────────────────────────────────────

def _build_query(symbol: str, name: str) -> str:
    """构造搜索关键词：股票代码 OR 公司名"""
    parts = []
    if symbol:
        parts.append(f'"{symbol}"')
    if name and name != symbol:
        parts.append(f'"{name}"')
    return " OR ".join(parts) if parts else symbol


def _text(element: ET.Element, tag: str) -> str:
    """安全地获取 XML 元素文本"""
    child = element.find(tag)
    if child is None:
        # 尝试忽略命名空间
        for child in element:
            if child.tag.split("}")[-1] == tag:
                return (child.text or "").strip()
        return ""
    return (child.text or "").strip()


def _strip_html(text: str) -> str:
    """移除 HTML 标签"""
    return re.sub(r"<[^>]+>", "", text).strip()
