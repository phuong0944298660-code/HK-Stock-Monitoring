#!/usr/bin/env python3
"""港股哨兵 · 轮询主流程

读取 backend/config/watchlist.json → 抓真实行情（Wind 主源，腾讯 → Yahoo 依次兜底）
→ 规则引擎评估 → 写 frontend/public/data/latest.json（前端唯一数据契约）
→ 可选 --push 把 critical/high 信号推飞书 + 桌面。

用法（工作区根目录）:
  python -m backend.engine.run_poll            拉一轮并写契约
  python -m backend.engine.run_poll --push     拉一轮并把高等级信号推送出去
  python -m backend.engine.run_poll --dry-run  只打印结果不写文件
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import fetch_quotes, rules

ROOT = Path(__file__).resolve().parents[2]
WATCHLIST = ROOT / "backend" / "config" / "watchlist.json"
LATEST = ROOT / "frontend" / "public" / "data" / "latest.json"
ARCHIVE_DIR = ROOT / "backend" / "data"

HK_TZ = timezone(timedelta(hours=8), "HKT")  # 香港无夏令时，固定 UTC+8
INDICES = {"hsi": "HSI.HI", "hstech": "HSTECH.HI"}


def market_status(now: datetime) -> tuple[str, str]:
    """港股交易时段：周一至五 09:30-16:00（简化处理，午间休市仍计 open）。"""
    if now.weekday() >= 5:
        return "closed", "港股已闭市（周末）"
    hm = now.strftime("%H:%M")
    if "09:30" <= hm < "16:00":
        return "open", "港股交易中"
    if hm < "09:30":
        return "pre", "盘前"
    return "closed", "港股已收市"


def load_watchlist() -> dict:
    with open(WATCHLIST, encoding="utf-8") as f:
        return json.load(f)


def build_latest(push: bool = False) -> dict:
    now = datetime.now(HK_TZ)
    now_hhmm = now.strftime("%H:%M")
    status, status_text = market_status(now)
    warnings: list[str] = []
    cfg = load_watchlist()

    market: dict = {"status": status, "statusText": status_text}
    for key, windcode in INDICES.items():
        snap, w = fetch_quotes.index_snapshot(windcode)
        warnings.extend(w)
        market[key] = (
            {"value": snap["value"], "changePct": snap["changePct"]}
            if snap else {"value": None, "changePct": None}
        )

    holdings: list[dict] = []
    signals: list[dict] = []
    for stock in cfg.get("stocks", []):
        windcode = stock["windcode"]
        try:
            snap, w = fetch_quotes.stock_snapshot(windcode)
            warnings.extend(w)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{windcode} 行情获取失败，本轮跳过: {exc}")
            continue

        try:
            avg20 = fetch_quotes.vol_avg20(windcode)
        except Exception as exc:  # noqa: BLE001
            avg20 = None
            warnings.append(f"{windcode} 20日均量获取失败: {exc}")

        pnl_amt, pnl_pct = rules.pnl(stock.get("cost"), stock.get("shares"), snap["price"])
        light, stock_signals = rules.evaluate(stock, snap, avg20, now_hhmm)

        holdings.append({
            "code": stock["code"],
            "windcode": windcode,
            "name": snap.get("name") or stock["name"],
            "currency": "HKD",
            "price": snap["price"],
            "prevClose": snap.get("prevClose"),
            "dayChangePct": snap.get("changePct"),
            "volume": snap.get("volume"),
            "volAvg20": round(avg20, 0) if avg20 else None,
            "cost": stock.get("cost"),
            "shares": stock.get("shares"),
            "pnl": pnl_amt,
            "pnlPct": pnl_pct,
            "bands": stock.get("bands"),
            "bandsStatus": stock.get("bandsStatus"),
            "signal": light,
            "source": snap.get("source"),
            "asof": snap.get("asof"),
        })
        for s in stock_signals:
            s["id"] = f"sig-{uuid.uuid4().hex[:8]}"
            signals.append(s)

    latest = {
        "demo": False,
        "generatedAt": now.isoformat(timespec="seconds"),
        "market": market,
        "holdings": holdings,
        "signals": signals,
        "warnings": warnings,
        "sources": ["Wind（经 agent-gw 网关）", "腾讯行情（兜底①）", "Yahoo Finance（兜底②，仅前两源失败时）"],
    }
    return latest


def write_latest(latest: dict) -> None:
    LATEST.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(LATEST.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(latest, f, ensure_ascii=False, indent=2)
        os.replace(tmp, LATEST)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(HK_TZ).strftime("%Y%m%d-%H%M")
    with open(ARCHIVE_DIR / f"latest-{stamp}.json", "w", encoding="utf-8") as f:
        json.dump(latest, f, ensure_ascii=False, indent=2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--push", action="store_true", help="推送 critical/high 信号")
    ap.add_argument("--dry-run", action="store_true", help="只打印不写文件")
    args = ap.parse_args()

    latest = build_latest(push=args.push)
    text = json.dumps(latest, ensure_ascii=False, indent=2)
    if args.dry_run:
        print(text)
        return 0
    write_latest(latest)
    n_sig = len(latest["signals"])
    print(f"[run_poll] 已写 {LATEST}（信号 {n_sig} 条，告警 {len(latest['warnings'])} 条）")

    if args.push and n_sig:
        from . import desktop_notify, feishu_push
        pushed = feishu_push.push_signals(latest)
        toasted = desktop_notify.notify_signals(latest)
        print(f"[run_poll] 飞书推送 {pushed} 条，桌面通知 {toasted} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
