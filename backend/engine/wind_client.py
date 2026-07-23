#!/usr/bin/env python3
"""港股哨兵 · Wind 取数客户端

封装 wind-allskill 插件的 CLI（node skills/wind-mcp-skill/scripts/cli.mjs），
经 Moonshot agent-gw 网关取 Wind 数据。凭证在网关侧，本机只用 ~/.kimi/agent-gw.json。

CLI 输出为三层嵌套：
  stdout JSON -> content[0].text (Python repr 风格字符串)
  -> ast.literal_eval -> {"text": 内层 JSON 字符串}
  -> json.loads -> {"is_success": ..., "data_preview": CSV 文本, "notice": ...}

纪律（沿用 wind skill 门禁）：单标的单次调用、日期 yyyyMMdd、
指标名逐字取自 indicators.md、失败不跨域修补。
"""

from __future__ import annotations

import ast
import csv
import io
import json
import shutil
import subprocess
from pathlib import Path

WIND_PLUGIN_ROOT = Path(
    r"C:\Users\PC\AppData\Roaming\kimi-desktop\daimon-share\daimon\runtime"
    r"\kimi-code\home\plugins\managed\wind-allskill"
)
CLI_PATH = WIND_PLUGIN_ROOT / "skills" / "wind-mcp-skill" / "scripts" / "cli.mjs"

DEFAULT_TIMEOUT = 90


class WindError(RuntimeError):
    """Wind 取数失败（网络/凭证/参数/网关），携带原始信息。"""


def _node_exe() -> str:
    for name in ("node", "node.exe"):
        hit = shutil.which(name)
        if hit:
            return hit
    raise WindError("未找到 node 可执行文件，无法调用 Wind CLI")


def call(server_type: str, tool: str, params: dict, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """调用 Wind CLI，返回解析后的内层 payload（含 is_success / data_preview / notice）。"""
    if not CLI_PATH.is_file():
        raise WindError(f"Wind CLI 不存在: {CLI_PATH}")
    cmd = [_node_exe(), str(CLI_PATH), "call", server_type, tool, json.dumps(params, ensure_ascii=False)]
    try:
        proc = subprocess.run(cmd, cwd=str(WIND_PLUGIN_ROOT), capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise WindError(f"Wind CLI 超时({timeout}s): {server_type}/{tool}") from exc
    stdout = proc.stdout.decode("utf-8", "replace").strip()
    stderr = proc.stderr.decode("utf-8", "replace").strip()
    if proc.returncode != 0:
        raise WindError(f"Wind CLI 退出码 {proc.returncode}: {stderr or stdout[:300]}")
    if not stdout:
        raise WindError(f"Wind CLI 无输出: {stderr[:300]}")
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise WindError(f"Wind CLI 输出非 JSON: {stdout[:300]}") from exc
    if envelope.get("isError"):
        raise WindError(f"Wind 网关返回错误: {stdout[:400]}")
    try:
        text = envelope["content"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise WindError(f"Wind CLI 输出结构异常: {stdout[:300]}") from exc
    try:
        inner = ast.literal_eval(text)
        payload = json.loads(inner["text"])
    except (ValueError, SyntaxError, KeyError, TypeError) as exc:
        raise WindError(f"Wind 内层载荷解析失败: {text[:300]}") from exc
    if not str(payload.get("is_success", "")).strip():
        raise WindError(f"Wind 取数未成功: {json.dumps(payload, ensure_ascii=False)[:400]}")
    return payload


def rows(payload: dict) -> list[dict]:
    """把 payload 的 data_preview（CSV 文本）解析为 dict 列表。"""
    preview = str(payload.get("data_preview", "")).strip()
    if not preview:
        return []
    return [dict(r) for r in csv.DictReader(io.StringIO(preview))]


def first_row(payload: dict) -> dict:
    rs = rows(payload)
    if not rs:
        raise WindError("Wind 返回空数据行")
    return rs[0]
