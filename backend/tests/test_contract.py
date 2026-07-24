#!/usr/bin/env python3
"""latest.json 数据契约校验：字段、类型、来源纪律。

用法:
  python -m backend.tests.test_contract [path/to/latest.json]
  默认校验 frontend/public/data/latest.json（真实跑完一轮后执行）
"""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = ROOT / "frontend" / "public" / "data" / "latest.json"

REQUIRED_HOLDING = ["code", "windcode", "name", "price", "bands", "signal"]
REQUIRED_SIGNAL = ["id", "time", "code", "name", "type", "level", "title", "detail",
                   "verdict", "verdictSummary", "evidence"]
SIGNAL_TYPES = {"BUY_ZONE", "SELL_ZONE", "VOL_ALERT", "RED_LINE", "EVENT"}
LEVELS = {"critical", "high", "mid", "info"}
LIGHTS = {"buy", "hold", "sell", "alert", "none"}


def validate(latest: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(latest.get("demo"), bool):
        errors.append("demo 必须是 bool")
    if not latest.get("generatedAt"):
        errors.append("缺少 generatedAt")
    market = latest.get("market") or {}
    if market.get("status") not in {"open", "closed", "pre"}:
        errors.append(f"market.status 非法: {market.get('status')}")

    for h in latest.get("holdings", []):
        for k in REQUIRED_HOLDING:
            if k not in h:
                errors.append(f"holding {h.get('code','?')} 缺字段 {k}")
        if h.get("signal") not in LIGHTS:
            errors.append(f"holding {h.get('code')} signal 非法: {h.get('signal')}")
        if not isinstance(h.get("price"), (int, float)):
            errors.append(f"holding {h.get('code')} price 非数值")

    for s in latest.get("signals", []):
        for k in REQUIRED_SIGNAL:
            if k not in s:
                errors.append(f"signal {s.get('id','?')} 缺字段 {k}")
        if s.get("type") not in SIGNAL_TYPES:
            errors.append(f"signal {s.get('id')} type 非法: {s.get('type')}")
        if s.get("level") not in LEVELS:
            errors.append(f"signal {s.get('id')} level 非法: {s.get('level')}")
        # 来源纪律：有 verdict 时 evidence 非空且 url 必须 https；无 verdict 时不得编造证据
        ev = s.get("evidence") or []
        if s.get("verdict") and not ev:
            errors.append(f"signal {s.get('id')} 有结论但无依据来源")
        for e in ev:
            if e.get("url") and not str(e["url"]).startswith("https://"):
                errors.append(f"signal {s.get('id')} evidence 链接非 https: {e['url']}")
            for ek in ("title", "source", "date"):
                if e.get("url") and not e.get(ek):
                    errors.append(f"signal {s.get('id')} evidence 缺 {ek}")
    return errors


class TestContract(unittest.TestCase):
    def test_latest_json(self):
        custom = [a for a in sys.argv[1:] if a.endswith(".json")]
        path = Path(custom[0]) if custom else DEFAULT
        if not path.is_file():
            self.skipTest(f"{path} 不存在，先跑一轮 run_poll")
        latest = json.loads(path.read_text(encoding="utf-8"))
        errors = validate(latest)
        self.assertEqual(errors, [], "\n".join(errors))

    def test_synthetic_minimal(self):
        latest = {
            "demo": False,
            "generatedAt": "2026-07-23T10:00:00+08:00",
            "market": {"status": "open", "statusText": "港股交易中",
                       "hsi": {"value": 25056.27, "changePct": 0.66},
                       "hstech": {"value": 4678.03, "changePct": 0.21}},
            "holdings": [{"code": "09988", "windcode": "09988.HK", "name": "阿里巴巴-W",
                          "price": 113.2, "bands": {"buyBelow": 110, "sellAbove": 152,
                                                    "stopLoss": None},
                          "signal": "hold"}],
            "signals": [],
        }
        self.assertEqual(validate(latest), [])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
