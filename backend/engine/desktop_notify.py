#!/usr/bin/env python3
"""港股哨兵 · Windows 桌面通知

经 PowerShell + WinForms NotifyIcon 气泡实现，零第三方依赖，
无需注册 AppUserModelID（Toast 方案对非打包应用不可靠，已弃用）。
中文文本经 base64 传递，避免 Windows 终端代码页乱码。
失败只告警不阻断主流程。
"""

from __future__ import annotations

import base64
import shutil
import subprocess
from pathlib import Path

_SYSTEM_PS = Path(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe")

# NotifyIcon 气泡：托盘图标挂 6 秒后销毁，进程退出前气泡已弹出
_PS_TEMPLATE = """
$ErrorActionPreference = 'Stop'
$title = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{title_b64}'))
$body  = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{body_b64}'))
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$ni = New-Object System.Windows.Forms.NotifyIcon
$ni.Icon = [System.Drawing.SystemIcons]::Information
$ni.Visible = $true
$ni.ShowBalloonTip(5000, $title, $body, [System.Windows.Forms.ToolTipIcon]::Info)
Start-Sleep -Seconds 6
$ni.Dispose()
"""


def _ps_exe() -> str | None:
    hit = shutil.which("powershell") or shutil.which("powershell.exe") or shutil.which("pwsh")
    if hit:
        return hit
    return str(_SYSTEM_PS) if _SYSTEM_PS.is_file() else None


def notify(title: str, body: str) -> bool:
    """弹一条桌面通知。成功返回 True，失败返回 False（不抛异常）。"""
    ps = _ps_exe()
    if not ps:
        return False
    script = _PS_TEMPLATE.format(
        title_b64=base64.b64encode(title.encode("utf-8")).decode(),
        body_b64=base64.b64encode(body.encode("utf-8")).decode(),
    )
    try:
        proc = subprocess.run(
            [ps, "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, timeout=30,
        )
        return proc.returncode == 0
    except Exception:  # noqa: BLE001 —— 通知失败不影响主流程
        return False


def notify_signals(latest: dict, levels: tuple[str, ...] = ("critical", "high")) -> int:
    """把高等级信号逐条弹桌面通知，返回条数。"""
    count = 0
    for s in latest.get("signals", []):
        if s.get("level") not in levels:
            continue
        ok = notify(
            f"{s.get('title','信号')}｜{s.get('name','')} {s.get('code','')}",
            s.get("detail", "")[:120],
        )
        count += 1 if ok else 0
    return count


if __name__ == "__main__":
    ok = notify("港股哨兵 · 自检", "桌面通知通道正常")
    print("desktop notify:", "ok" if ok else "failed")
