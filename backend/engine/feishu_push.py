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
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "**依据来源**\n1. [阿里巴巴集团 2026 财年业绩（官网）：云外部收入 +40%，AI 相关收入占比 30%](https://www.alibabagroup.com/document-1991237455038119936)\n2. [华尔街见闻：阿里云收入同比 +38%，AI 相关收入 89.71 亿元](https://wallstreetcn.com/articles/3772187)\n3. [智通财经：6 月 25 日斥资 1249.78 万美元回购 104.64 万股](https://finance.jrj.com.cn/2026/06/26183257598615.shtml)",
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


_HEADER_STYLE = {
    "BUY_ZONE": ("green", "🟢 补仓信号"),
    "SELL_ZONE": ("red", "🔴 卖出信号"),
    "RED_LINE": ("red", "⛔ 红线警报"),
    "VOL_ALERT": ("orange", "🟠 量价异动"),
    "EVENT": ("blue", "🔵 事件提示"),
}
_PUSH_LEVELS = {"critical", "high"}


def signal_card(signal: dict, holding: dict | None, generated_at: str) -> dict:
    """真实信号卡片。verdict/evidence 为空时不渲染对应区块，绝不编造。"""
    template, label = _HEADER_STYLE.get(signal["type"], ("grey", "信号"))
    holding = holding or {}
    price = holding.get("price")
    chg = holding.get("dayChangePct")
    pnl, pnl_pct = holding.get("pnl"), holding.get("pnlPct")

    def field(title, value):
        return {"is_short": True, "text": {"tag": "lark_md", "content": f"**{title}**\n{value}"}}

    fields = [field("现价", f"{price} HKD" if price is not None else "—"),
              field("日涨跌", f"{chg:+.2f}%" if isinstance(chg, (int, float)) else "—")]
    if pnl is not None:
        fields.append(field("持仓浮盈", f"{pnl:+,.0f} HKD（{pnl_pct:+.1f}%）"))
    fields.append(field("触发规则", signal.get("detail", "")[:80]))

    elements: list[dict] = [{"tag": "div", "fields": fields}]

    if signal.get("verdict"):
        summary = signal.get("verdictSummary") or ""
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md",
                     "content": f"**AI 研判**\n**结论：{signal['verdict']}**\n{summary}".strip()},
        })
        evidence = signal.get("evidence") or []
        links = [e for e in evidence if e.get("url")]
        if links:
            lines = "\n".join(
                f"{i}. [{e['title']}（{e.get('source','')}·{e.get('date','')}）]({e['url']})".replace("（·", "（").replace("·）", "）")
                for i, e in enumerate(links, 1)
            )
            elements.append({"tag": "div",
                             "text": {"tag": "lark_md", "content": f"**依据来源**\n{lines}"}})
        else:
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md",
                         "content": "**依据来源**\n暂无可靠公开来源支撑该结论，按灰色地带处理"},
            })
    else:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md",
                     "content": "**AI 研判**\n待 AI 研判官核查论点后给出结论与依据来源"},
        })

    src = holding.get("source") or "wind"
    elements.append({"tag": "hr"})
    elements.append({
        "tag": "note",
        "elements": [{"tag": "plain_text",
                      "content": f"{generated_at} · 数据源 {src} · 研究参考，不构成投资建议"}],
    })
    return {
        "config": {"wide_screen_mode": True},
        "header": {"template": template,
                   "title": {"tag": "plain_text",
                             "content": f"{label}｜{signal.get('name','')} {signal.get('code','')}"}},
        "elements": elements,
    }


def push_signals(latest: dict, cfg: dict | None = None) -> int:
    """把 critical/high 等级信号逐条推送到飞书群。返回推送条数。"""
    cfg = cfg or json.loads(CFG_PATH.read_text(encoding="utf-8"))
    holdings = {h["code"]: h for h in latest.get("holdings", [])}
    generated_at = latest.get("generatedAt", "")
    count = 0
    for s in latest.get("signals", []):
        if s.get("level") not in _PUSH_LEVELS:
            continue
        card = signal_card(s, holdings.get(s.get("code")), generated_at)
        send(cfg, "interactive", card)
        count += 1
    return count


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
