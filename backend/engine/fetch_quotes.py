#!/usr/bin/env python3
"""港股哨兵 · 行情抓取层

主源：Wind（经 wind_client，agent-gw 网关）。
兜底①：腾讯行情公共接口（qt.gtimg.cn，港股个股+指数快照，无需凭证）。
兜底②：Yahoo Finance 公共 chart API（无需凭证，偶发 403 限流，排最后）。
日 K 兜底：东方财富 push2his 接口（无需凭证；20 日均量在 Wind 失败时改走此源）。

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


def vol_avg20(windcode: str) -> tuple[float | None, list[str]]:
    """20 日均量：取最近 20 根已完成日 K（剔除当日未完结 bar）的成交量均值。

    主源 Wind 日 K，失败降级东财日 K。返回 (avg20, warnings)；两源均失败返回 (None, warnings)。
    """
    warnings: list[str] = []
    today = datetime.now().strftime("%Y-%m-%d")
    bars = None
    try:
        bars = wind_daily_bars(windcode, 25)
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"{windcode} Wind 日K获取失败: {exc}")
        try:
            bars = em_daily_bars(windcode, 25)
            warnings.append(f"{windcode} 20日均量已降级东财日K源")
        except Exception as exc2:  # noqa: BLE001
            warnings.append(f"{windcode} 东财日K也失败: {exc2}")
            return None, warnings
    done = [b for b in bars if b["date"] != today]
    vols = [b["volume"] for b in done[-20:] if b["volume"] > 0]
    if not vols:
        warnings.append(f"{windcode} 日K无有效成交量")
        return None, warnings
    return sum(vols) / len(vols), warnings


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


def _parse_tencent_body(raw: str, sym: str) -> list[str]:
    if "v_" not in raw or "=" not in raw:
        raise RuntimeError(f"腾讯返回异常: {raw[:120]}")
    body = raw.split("=", 1)[1].strip().strip('";').strip('"')
    f = body.split("~")
    if len(f) < 38:
        raise RuntimeError(f"腾讯字段不足({len(f)}): {sym}")
    return f


def _tencent_asof(f: list[str]) -> str:
    asof_raw = (f[30] or "").strip()
    try:
        return datetime.strptime(asof_raw, "%Y/%m/%d %H:%M:%S").astimezone().isoformat(timespec="seconds")
    except ValueError:
        return datetime.now().astimezone().isoformat(timespec="seconds")


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
    f = _parse_tencent_body(raw, sym)
    price = _f(f[3])
    if price is None or price <= 0:
        raise RuntimeError(f"腾讯缺少有效价格: {sym} -> {f[3]!r}")
    return {
        "name": (f[1] or "").strip() or sym,
        "price": price,
        "prevClose": _f(f[4]),
        "volume": _f(f[6]),
        "amount": _f(f[37]),
        "changePct": _f(f[32]),
        "source": "tencent-fallback",
        "asof": _tencent_asof(f),
    }


TENCENT_INDEX_MAP = {"HSI.HI": "hkHSI", "HSTECH.HI": "hkHSTECH"}


def tencent_index_snapshot(windcode: str) -> dict:
    """腾讯港股指数快照（恒指 hkHSI / 恒生科技 hkHSTECH）。

    字段（实测 2026-07-23）：[1]名称 [3]最新点位 [32]涨跌幅(%) [30]数据时点。
    与东方财富指数快照交叉验证一致（恒指 25210.81 / +1.28%）。
    """
    sym = TENCENT_INDEX_MAP.get(windcode)
    if not sym:
        raise RuntimeError(f"腾讯指数兜底未覆盖: {windcode}")
    url = f"https://qt.gtimg.cn/q={sym}"
    req = urllib.request.Request(url, headers=_TENCENT_UA)
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("gbk", "replace")
    f = _parse_tencent_body(raw, sym)
    value = _f(f[3])
    if value is None or value <= 0:
        raise RuntimeError(f"腾讯指数缺少有效点位: {sym} -> {f[3]!r}")
    return {
        "name": (f[1] or "").strip() or sym,
        "value": value,
        "changePct": _f(f[32]),
        "source": "tencent-fallback",
    }


# ------------------------------------------------------- 东方财富日 K 兜底源

_EM_HEADERS = {"User-Agent": "Mozilla/5.0 (hk-sentinel fallback)", "Referer": "https://quote.eastmoney.com/"}
_EM_UT = "fa5fd1943c7b386f172d6893dbfba10b"  # 公开行情接口通用 token（前端固定值）


def _em_secid(windcode: str) -> str:
    # 09988.HK -> 116.09988（东财港股市场号 116）
    code, _, suffix = windcode.partition(".")
    if suffix.upper() == "HK":
        return f"116.{code.zfill(5)}"
    raise RuntimeError(f"东财兜底仅支持港股: {windcode}")


def em_daily_bars(windcode: str, count: int = 25) -> list[dict]:
    """东财 push2his 日 K（前复权），最近 count 根，升序。元素: {date, close, volume}。

    实测 2026-07-23：kline 每行 "date,open,close,high,low,volume,amount"，
    09988 当日 bar 成交量与腾讯快照成交量逐字一致。
    """
    secid = _em_secid(windcode)
    url = (
        "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        f"?secid={secid}&fields1=f1,f2,f3,f4,f5&fields2=f51,f52,f53,f54,f55,f56,f57"
        f"&klt=101&fqt=1&end=20500101&lmt={count}&ut={_EM_UT}"
    )
    req = urllib.request.Request(url, headers=_EM_HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    klines = ((data or {}).get("data") or {}).get("klines") or []
    bars = []
    for line in klines:
        p = str(line).split(",")
        if len(p) < 6:
            continue
        close, vol = _f(p[2]), _f(p[5])
        if close is None:
            continue
        bars.append({"date": p[0].strip(), "close": close, "volume": vol or 0.0})
    if not bars:
        raise RuntimeError(f"东财日K返回空序列: {secid}")
    return bars


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
    """指数快照：主源 Wind，失败降级腾讯。均失败返回 (None, warnings)。"""
    try:
        return wind_index_snapshot(windcode), []
    except Exception as exc:  # noqa: BLE001
        warnings = [f"Wind 指数快照失败({windcode}): {exc}"]
    try:
        snap = tencent_index_snapshot(windcode)
        warnings.append(f"{windcode} 指数已降级腾讯兜底源")
        return snap, warnings
    except Exception as exc2:  # noqa: BLE001
        warnings.append(f"腾讯指数兜底也失败({windcode}): {exc2}")
        return None, warnings
