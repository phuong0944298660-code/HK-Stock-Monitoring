#!/usr/bin/env python3
"""港股哨兵 · 行情快照 git 同步

任务①每轮轮询把 frontend/public/data/latest.json 提交并推送到 GitHub UAT 分支，
触发 GitHub Actions 重新构建 Pages，让线上网站看到接近实时的真实行情。

设计约束：
- 仅在当前检出于 UAT 分支时同步；其他分支直接跳过（避免污染 master）。
- 推送前 pull --rebase 防冲突；所有 git 调用带超时，失败抛异常由调用方降级为告警。
- 凭证依赖本机 Windows 凭据管理器（credential.helper=manager），不持有任何 token。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = "frontend/public/data/latest.json"
BRANCH = "UAT"


def _git(*args: str, timeout: int = 30) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败: {proc.stderr.strip()[:300]}")
    return proc.stdout.strip()


def sync_latest_to_remote(generated_at: str) -> str:
    """若 latest.json 相对 HEAD 有变化则提交并推送 UAT；返回状态描述。"""
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    if branch != BRANCH:
        return f"当前分支为 {branch}，跳过同步（仅 {BRANCH} 分支同步）"

    if not _git("status", "--porcelain", "--", TARGET):
        return "快照无变化，跳过提交"

    _git("add", "--", TARGET)
    _git(
        "-c", "user.name=hk-sentinel-bot",
        "-c", "user.email=hk-sentinel@local",
        "commit", "-m", f"data: 行情快照 {generated_at}",
    )
    _git("pull", "--rebase", "origin", BRANCH, timeout=120)
    _git("push", "origin", BRANCH, timeout=120)
    return f"已推送 {BRANCH}（{generated_at}）"


if __name__ == "__main__":
    import json

    latest = json.loads((ROOT / TARGET).read_text(encoding="utf-8"))
    print(sync_latest_to_remote(latest.get("generatedAt", "unknown")))
