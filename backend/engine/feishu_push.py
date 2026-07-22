#!/usr/bin/env python3
"""港股哨兵 · 飞书推送模块

- tenant_access_token 认证（App ID / Secret 仅存本机 backend/config/feishu.json）
- 所有载荷显式 UTF-8 编码，绕开 Windows 终端 GBK 转码导致的乱码
- 凭证只发往 open.feishu.cn，不进入任何日志与其它对外内容

用法:
  python feishu_push.py --demo            发送演示信号卡片
  python feishu_push.py --text "文本"     发送纯文本
  python feishu_push.py --card card.json  发送自定义卡片（UTF-8 JSON 文件）
"""

import json
import sys
import urllib.request
from pathlib import Path

BASE = "https://open.feishu.cn/open-apis"
CFG_PATH = Path(__file__).resolve().parent.parent / "config" / "feishu.json"


def _post(url: str, payload: dict, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_token(cfg: dict) -> str:
    out = _post(
        f"{BASE}/auth/v3/tenant_access_token/internal",
        {"app_id": cfg["app_id"], "app_secret": cfg["app_secret"]},
    )
    if out.get("code") != 0:
        raise RuntimeError(f"获取 tenant_access_token 失败: {out}")
    return out["tenant_access_token"]


def send(cfg: dict, msg_type: str, content) -> dict:
    """content: 字符串（已是 JSON）或 dict（自动序列化，ensure_ascii=False）"""
    token = get_token(cfg)
    payload = {
        "receive_id": cfg["chat_id"],
        "msg_type": msg_type,
        "content": content if isinstance(content, str) else json.dumps(content, ensure_ascii=False),
    }
    out = _post(f"{BASE}/im/v1/messages?receive_id_type=chat_id", payload, token)
    if out.get("code") != 0:
        raise RuntimeError(f"消息发送失败: {out}")
    return out


def demo_card() -> dict:
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "green",
            "title": {"tag": "plain_text", "content": "🟢 补仓信号（演示）｜阿里巴巴-W 09988"},
        },
        "elements": [
            {
                "tag": "div",
                "fields": [
                    {"is_short": True, "text": {"tag": "lark_md", "content": "**现价**\n108.40 HKD"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": "**日涨跌**\n-2.34%"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": "**持仓浮盈**\n-940 HKD（-4.2%）"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": "**触发规则**\n现价 ≤ 补仓线 110.00"}},
                ],
            },
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "**AI 研判（mock）**\n论点核查：云智能集团增速与回购计划未变化，3 条红线均未触及 → **结论：补仓（分批）**\n建议 105–108 分两批，每批 100 股；若按 108 补入 100 股，新成本约 111.05。",
                },
            },
            {"tag": "hr"},
            {
                "tag": "note",
                "elements": [
                    {"tag": "plain_text", "content": "2026-07-23 15:42 HKT · 研究参考，不构成投资建议 · MOCK 演示"}
                ],
            },
        ],
    }


def main() -> None:
    cfg = json.loads(CFG_PATH.read_text(encoding="utf-8"))
    args = sys.argv[1:]
    if not args or args[0] == "--demo":
        out = send(cfg, "interactive", demo_card())
    elif args[0] == "--text" and len(args) >= 2:
        out = send(cfg, "text", json.dumps({"text": args[1]}, ensure_ascii=False))
    elif args[0] == "--card" and len(args) >= 2:
        out = send(cfg, "interactive", json.loads(Path(args[1]).read_text(encoding="utf-8")))
    else:
        raise SystemExit(__doc__)
    print("push ok, message_id:", out["data"]["message_id"])


if __name__ == "__main__":
    main()
