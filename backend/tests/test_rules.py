#!/usr/bin/env python3
"""rules 引擎单元测试：纯函数，不触网。"""

import unittest

from backend.engine import rules

STOCK = {
    "code": "09988",
    "windcode": "09988.HK",
    "name": "阿里巴巴-W",
    "cost": 113.1,
    "shares": 200,
    "bands": {"buyBelow": 110, "sellAbove": 152, "stopLoss": None},
    "bandsStatus": "mock-pending-dossier",
}


def snap(price, volume=10_000_000):
    return {"price": price, "volume": volume, "prevClose": price, "changePct": 0.0}


class TestPnl(unittest.TestCase):
    def test_profit(self):
        amt, pct = rules.pnl(113.1, 200, 120.0)
        self.assertEqual(amt, 1380.0)
        self.assertAlmostEqual(pct, 6.10, places=2)

    def test_loss(self):
        amt, pct = rules.pnl(113.1, 200, 108.4)
        self.assertEqual(amt, -940.0)
        self.assertAlmostEqual(pct, -4.16, places=2)

    def test_no_position(self):
        self.assertEqual(rules.pnl(None, None, 100), (None, None))


class TestEvaluate(unittest.TestCase):
    def test_buy_zone(self):
        light, sigs = rules.evaluate(STOCK, snap(108.4), 10_000_000, "10:15")
        self.assertEqual(light, "buy")
        self.assertEqual(sigs[0]["type"], "BUY_ZONE")
        self.assertEqual(sigs[0]["level"], "critical")
        self.assertIn("108.4", sigs[0]["detail"])
        self.assertIn("未经", sigs[0]["detail"])  # 价格带未确认提示
        self.assertIsNone(sigs[0]["verdict"])
        self.assertEqual(sigs[0]["evidence"], [])

    def test_sell_zone(self):
        light, sigs = rules.evaluate(STOCK, snap(153.0), 10_000_000, "10:15")
        self.assertEqual(light, "sell")
        self.assertEqual(sigs[0]["type"], "SELL_ZONE")

    def test_hold_no_signal(self):
        light, sigs = rules.evaluate(STOCK, snap(113.2), 10_000_000, "10:15")
        self.assertEqual(light, "hold")
        self.assertEqual(sigs, [])

    def test_vol_alert(self):
        light, sigs = rules.evaluate(STOCK, snap(113.2, volume=25_000_000), 10_000_000, "10:15")
        self.assertEqual(light, "alert")
        self.assertEqual(sigs[0]["type"], "VOL_ALERT")
        self.assertEqual(sigs[0]["level"], "mid")

    def test_buy_zone_beats_vol_alert_light(self):
        light, sigs = rules.evaluate(STOCK, snap(108.0, volume=30_000_000), 10_000_000, "10:15")
        self.assertEqual(light, "buy")
        self.assertEqual({s["type"] for s in sigs}, {"BUY_ZONE", "VOL_ALERT"})

    def test_confirmed_bands_no_note(self):
        cfg = {**STOCK, "bandsStatus": "confirmed"}
        _, sigs = rules.evaluate(cfg, snap(108.4), 10_000_000, "10:15")
        self.assertNotIn("未经", sigs[0]["detail"])

    def test_watch_only_no_position(self):
        cfg = {**STOCK, "cost": None, "shares": None}
        light, sigs = rules.evaluate(cfg, snap(120.0), 10_000_000, "10:15")
        self.assertEqual(light, "none")
        self.assertEqual(sigs, [])


if __name__ == "__main__":
    unittest.main()
