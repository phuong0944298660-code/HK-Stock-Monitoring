#!/usr/bin/env python3
"""港股哨兵 · 行情抓取层

主源：Wind（经 wind_client，agent-gw 网关）。
兜底①：腾讯行情公共接口（qt.gtimg.cn，港股快照，无需凭证）。
兜底②：Yahoo Finance 公共 chart API（无需凭证，偶发 403 限流，排最后）。

返回结构全部显式标注 source 与 asof（数据时点），禁止把兜底数据伪装成主源。
"""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timedelta
from typing import Any

from . import wind_client

# 指标名逐字取自 wind-mcp-skill/references/indicators.md
STOCK_INDEXES = "中文简称,最新成交价,前收盘价,成交量,成交额,涨跌幅"
INDEX_INDEXES = "中文简称,最新成交价,涨跌幅"


def _f(v: Any) -> float | None:
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- Wind 主源

def wind_stock_snapshot(windcode: str) -> dict:
    """个股行情快照。返回 name/price/prev_close/volume/amount/change_pct。"""
    payload = wind_client.call(
        "stock_data", "get_stock_price_indicators",
        {"windcode": windcode, "indexes": STOCK_INDEXES},
    )
    r = wind_client.first_row(payload)
    price = _f(r.get("最新成交价"))
    if price is None:
        raise wind_client.WindError(f"快照缺少最新成交价: {r}")
    return {
        "name": (r.get("中文简称") or "").strip(),
        "price": price,
        "prevClose": _f(r.get("前收盘价")),
        "volume": _f(r.get("成交量")),
        "amount": _f(r.get("成交额")),
        "changePct": _f(r.get("涨跌幅")),
        "source": "wind",
        "asof": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def wind_index_snapshot(windcode: str) -> dict:
    """指数快照（HSI.HI / HSTECH.HI）。"""
    payload = wind_client.call(
        "index_data", "get_index_price_indicators",
        {"windcode": windcode, "indexes": INDEX_INDEXES},
    )
    r = wind_client.first_row(payload)
    value = _f(r.get("最新成交价"))
    if value is None:
        raise wind_client.WindError(f"指数快照缺少数值: {r}")
    return {
        "name": (r.get("中文简称") or "").strip(),
        "value": value,
        "changePct": _f(r.get("涨跌幅")),
        "source": "wind",
    }


def wind_daily_bars(windcode: str, count: int = 25) -> list[dict]:
    """日 K（前复权），最近 count 根，升序。元素: {date, close, volume}。"""
    end = datetime.now()
    begin = end - timedelta(days=max(count * 2, 40))
    payload = wind_client.call(
        "stock_data", "get_stock_kline",
        {
            "windcode": windcode,
            "begin_date": begin.strftime("%Y%m%d"),
            "end_date": end.strftime("%Y%m%d"),
            "period": "10",
            "count": str(-count),
        },
    )
    bars = []
    for r in wind_client.rows(payload):
        close, vol = _f(r.get("close")), _f(r.get("volume"))
        if close is None:
            continue
        bars.append({"date": (r.get("trade_date") or "").strip(), "close": close, "volume": vol or 0.0})
    if not bars:
        raise wind_client.WindError("K线返回空序列")
    return bars


def vol_avg20(windcode: str) -> float | None:
    """20 日均量：取最近 20 根已完成日 K（剔除当日未完结 bar）的成交量均值。"""
    today = datetime.now().strftime("%Y-%m-%d")
    bars = [b for b in wind_daily_bars(windcode, 25) if b["date"] != today]
    vols = [b["volume"] for b in bars[-20:] if b["volume"] > 0]
    if not vols:
        return None
    return sum(vols) / len(vols)


def wind_news(query: str, top_k: int = 5) -> list[dict]:
    """财经新闻（financial_docs RAG）。返回 title/content/date/source；
    注意：该接口不含原文 URL，调用方不得伪造链接。"""
    payload = wind_client.call(
        "financial_docs", "get_financial_news",
        {"query": query.replace(" ", ""), "top_k": top_k},
    )
    out = []
    for r in wind_client.rows(payload):
        title = (r.get("title") or "").strip().strip('"')
        if not title:
            continue
        out.append({
            "title": title,
            "content": (r.get("content") or "").strip().strip('"'),
            "date": (r.get("date") or "").strip(),
            "source": "Wind 财经新闻库",
            "url": None,  # RAG 接口不提供原文链接
        })
    return out


# ------------------------------------------------------------ 腾讯兜底源①

_TENCENT_UA = {"User-Agent": "Mozilla/5.0 (hk-sentinel fallback)"}


def _tencent_symbol(windcode: str) -> str:
    # 09988.HK -> hk09988（腾讯港股保留前导零、小写 hk 前缀）
    code, _, suffix = windcode.partition(".")
    if suffix.upper() == "HK":
        return f"hk{code.zfill(5)}"
    raise RuntimeError(f"腾讯兜底仅支持港股: {windcode}")


def tencent_stock_snapshot(windcode: str) -> dict:
    """腾讯 qt.gtimg.cn 港股快照（GBK 文本，~ 分隔）。

    字段（实测 2026-07-23）：[1]名称 [3]现价 [4]昨收 [6]成交量(股)
    [30]数据时点 [32]涨跌幅(%) [37]成交额(HKD)。
    """
    sym = _tencent_symbol(windcode)
    url = f"https://qt.gtimg.cn/q={sym}"
    req = urllib.request.Request(url, headers=_TENCENT_UA)
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("gbk", "replace")
    if "v_" not in raw or "=" not in raw:
        raise RuntimeError(f"腾讯返回异常: {raw[:120]}")
    body = raw.split("=", 1)[1].strip().strip('";').strip('"')
    f = body.split("~")
    if len(f) < 38:
        raise RuntimeError(f"腾讯字段不足({len(f)}): {sym}")
    price = _f(f[3])
    if price is None or price <= 0:
        raise RuntimeError(f"腾讯缺少有效价格: {sym} -> {f[3]!r}")
    asof_raw = (f[30] or "").strip()
    try:
        asof_dt = datetime.strptime(asof_raw, "%Y/%m/%d %H:%M:%S").astimezone()
        asof = asof_dt.isoformat(timespec="seconds")
    except ValueError:
        asof = datetime.now().astimezone().isoformat(timespec="seconds")
    return {
        "name": (f[1] or "").strip() or sym,
        "price": price,
        "prevClose": _f(f[4]),
        "volume": _f(f[6]),
        "amount": _f(f[37]),
        "changePct": _f(f[32]),
        "source": "tencent-fallback",
        "asof": asof,
    }


# ------------------------------------------------------------- Yahoo 兜底源②

_YAHOO_UA = {"User-Agent": "Mozilla/5.0 (hk-sentinel fallback)"}


def _yahoo_symbol(windcode: str) -> str:
    # 09988.HK -> 9988.HK（Yahoo 港股不带前导零）
    code, _, suffix = windcode.partition(".")
    if suffix.upper() == "HK":
        return f"{code.lstrip('0')}.HK"
    return windcode


def yahoo_stock_snapshot(windcode: str) -> dict:
    sym = _yahoo_symbol(windcode)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=5d"
    req = urllib.request.Request(url, headers=_YAHOO_UA)
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    result = (data.get("chart", {}).get("result") or [None])[0]
    if not result:
        raise RuntimeError(f"Yahoo 无数据: {sym}")
    meta = result["meta"]
    price = meta.get("regularMarketPrice")
    prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    if price is None:
        raise RuntimeError(f"Yahoo 缺少价格: {sym}")
    change_pct = ((price - prev) / prev * 100) if prev else None
    return {
        "name": meta.get("shortName") or sym,
        "price": float(price),
        "prevClose": float(prev) if prev else None,
        "volume": _f(meta.get("regularMarketVolume")),
        "amount": None,
        "changePct": round(change_pct, 3) if change_pct is not None else None,
        "source": "yahoo-fallback",
        "asof": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


# ---------------------------------------------------------------- 统一入口

def stock_snapshot(windcode: str) -> tuple[dict, list[str]]:
    """主源 Wind，失败依次降级腾讯、Yahoo。返回 (snapshot, warnings)。"""
    warnings: list[str] = []
    try:
        return wind_stock_snapshot(windcode), warnings
    except Exception as exc:  # noqa: BLE001 —— 兜底必须兜住一切主源故障
        warnings.append(f"Wind 个股快照失败({windcode}): {exc}")
    try:
        snap = tencent_stock_snapshot(windcode)
        warnings.append(f"{windcode} 已降级腾讯兜底源")
        return snap, warnings
    except Exception as exc1:  # noqa: BLE001
        warnings.append(f"腾讯兜底失败({windcode}): {exc1}")
    try:
        snap = yahoo_stock_snapshot(windcode)
        warnings.append(f"{windcode} 已降级 Yahoo 兜底源（成交量/成交额可能缺失）")
        return snap, warnings
    except Exception as exc2:  # noqa: BLE001
        warnings.append(f"Yahoo 兜底也失败({windcode}): {exc2}")
        raise wind_client.WindError(f"{windcode} 三源均失败") from exc2


def index_snapshot(windcode: str) -> tuple[dict | None, list[str]]:
    """指数仅走 Wind；失败返回 (None, warnings)，由上层决定降级展示。"""
    try:
        return wind_index_snapshot(windcode), []
    except Exception as exc:  # noqa: BLE001
        return None, [f"Wind 指数快照失败({windcode}): {exc}"]
