#!/usr/bin/env python3
"""一次性手动状态播报：用 latest.json 真实数据推飞书状态卡 + 桌面通知。

卡片构造与推送逻辑复用 backend.engine.feishu_push.status_card / push_status，
与每日 09:42 自动开盘状态卡同一实现。

用法（项目根）:  python -m backend.push_status_now
"""
import json
from pathlib import Path

from backend.engine import feishu_push

ROOT = Path(__file__).resolve().parents[1]
latest = json.loads((ROOT / "frontend" / "public" / "data" / "latest.json").read_text(encoding="utf-8"))

pushed = feishu_push.push_status(latest, desktop=True)
print("status card pushed:", pushed)
