#!/usr/bin/env python3
"""港股哨兵 · 规则引擎（纯函数，Decimal 计算，无 IO）

输入：名单配置 + 行情快照 + 20 日均量
输出：持仓信号灯的原始信号列表（verdict/evidence 留空，由 AI 研判官补齐）
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

VOL_ALERT_RATIO = Decimal("1.5")  # 当日成交量 > 1.5 × 20日均量 → 异动
BANDS_PENDING_NOTE = "（价格带为初始估算，未经建仓级分析确认，仅作观察提示）"


def _d(v) -> Decimal | None:
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except ArithmeticError:
        return None


def _q2(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def pnl(cost, shares, price) -> tuple[float | None, float | None]:
    """返回 (浮动盈亏金额, 浮动盈亏%)。无持仓返回 (None, None)。"""
    c, s, p = _d(cost), _d(shares), _d(price)
    if c is None or s is None or p is None:
        return None, None
    amount = (p - c) * s
    pct = (p - c) / c * 100 if c != 0 else None
    return float(_q2(amount)), float(_q2(pct)) if pct is not None else None


def evaluate(stock_cfg: dict, snapshot: dict, vol_avg20, now_hhmm: str) -> tuple[str, list[dict]]:
    """评估单只持仓，返回 (signal_light, signals)。

    signal_light ∈ buy / sell / alert / hold / none（纯观察仓无持仓为 none）
    signals 元素字段与前端 SignalItem 契约对齐（verdict/evidence 由 AI 研判官补）。
    """
    price = _d(snapshot.get("price"))
    if price is None:
        return "none", []

    bands = stock_cfg.get("bands") or {}
    buy_below, sell_above = _d(bands.get("buyBelow")), _d(bands.get("sellAbove"))
    bands_pending = stock_cfg.get("bandsStatus") != "confirmed"
    note = BANDS_PENDING_NOTE if bands_pending else ""

    cost, shares = stock_cfg.get("cost"), stock_cfg.get("shares")
    pnl_amt, pnl_pct = pnl(cost, shares, snapshot.get("price"))
    pnl_txt = ""
    if pnl_amt is not None:
        pnl_txt = f"；持仓浮{'盈' if pnl_amt >= 0 else '亏'} {pnl_amt:+,.0f} HKD（{pnl_pct:+.1f}%）"

    code, name = stock_cfg["code"], stock_cfg["name"]
    signals: list[dict] = []
    light = "hold" if cost is not None else "none"

    def sig(sig_type, level, title, detail):
        signals.append({
            "time": now_hhmm,
            "code": code,
            "name": name,
            "type": sig_type,
            "level": level,
            "title": title,
            "detail": detail,
            "verdict": None,
            "verdictSummary": None,
            "evidence": [],
        })

    if buy_below is not None and price <= buy_below:
        light = "buy"
        sig("BUY_ZONE", "critical", "进入补仓区",
            f"现价 {price} ≤ 补仓线 {_q2(buy_below)}{pnl_txt}{note}")
    elif sell_above is not None and price >= sell_above:
        light = "sell"
        sig("SELL_ZONE", "critical", "涨破卖出区",
            f"现价 {price} ≥ 卖出线 {_q2(sell_above)}{pnl_txt}{note}")

    avg = _d(vol_avg20)
    vol = _d(snapshot.get("volume"))
    if avg and avg > 0 and vol is not None and vol > avg * VOL_ALERT_RATIO:
        ratio = float((vol / avg).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
        if light in ("hold", "none"):
            light = "alert"
        sig("VOL_ALERT", "mid", "成交量异动",
            f"截至当前成交 {vol:,.0f} 股，为 20 日均量 {ratio} 倍（盘中未完结口径）")

    return light, signals
