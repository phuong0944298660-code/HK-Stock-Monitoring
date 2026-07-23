#!/usr/bin/env python3
"""港股哨兵 · Automation 任务①入口（行情轮询）

托管 Python runner 约定：模块必须暴露 def run(ctx): ...，返回 JSON 可序列化数据
（AutomationOutput 协议要求包一层 {"artifact": {...}}）。顶层代码不作为入口。

部署说明：本文件是 git 基准副本；线上生效副本位于 Automation 资产目录
（blueprint/automations/automation_81314fce-…/assets/sentinel_job.py），
修改后需同步覆盖资产目录那份。

业务逻辑复用项目 backend.engine.run_poll / feishu_push / desktop_notify：
拉一轮真实行情 → 写 frontend/public/data/latest.json →
critical/high 信号推飞书群 + 桌面通知。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_PROJECT_CANDIDATES = [
    r"E:\MyProject\KimiInvestment\港股监控助手",
]


def _project_root() -> Path:
    candidates = [
        os.environ.get("DAIMON_BLUEPRINT_AUTOMATION_WORKSPACE_PATH", ""),
        *_PROJECT_CANDIDATES,
    ]
    for cand in candidates:
        if cand and (Path(cand) / "backend" / "engine" / "run_poll.py").is_file():
            return Path(cand)
    raise RuntimeError("未找到项目根目录（backend/engine/run_poll.py 不存在）")


def run(ctx: dict) -> dict:
    root = _project_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from backend.engine import run_poll

    latest = run_poll.build_latest(push=True)
    run_poll.write_latest(latest)

    pushed_feishu = 0
    pushed_desktop = 0
    if latest["signals"]:
        try:
            from backend.engine import feishu_push
            pushed_feishu = feishu_push.push_signals(latest)
        except Exception as exc:  # noqa: BLE001
            latest["warnings"].append(f"飞书推送失败: {exc}")
        try:
            from backend.engine import desktop_notify
            pushed_desktop = desktop_notify.notify_signals(latest)
        except Exception as exc:  # noqa: BLE001
            latest["warnings"].append(f"桌面通知失败: {exc}")

    n_sig = len(latest["signals"])
    summary = (
        f"{latest['market']['statusText']}；监控 {len(latest['holdings'])} 只；"
        f"信号 {n_sig} 条（飞书推 {pushed_feishu}，桌面推 {pushed_desktop}）；"
        f"告警 {len(latest['warnings'])} 条"
    )
    return {"artifact": {
        "generatedAt": latest["generatedAt"],
        "marketStatus": latest["market"]["status"],
        "signalsCount": n_sig,
        "signalTitles": [f"{s['name']}·{s['title']}" for s in latest["signals"]],
        "pushedFeishu": pushed_feishu,
        "pushedDesktop": pushed_desktop,
        "warningsCount": len(latest["warnings"]),
        "warnings": latest["warnings"][:5],
        "summary": summary,
    }}


if __name__ == "__main__":
    import json
    print(json.dumps(run({}), ensure_ascii=False))
