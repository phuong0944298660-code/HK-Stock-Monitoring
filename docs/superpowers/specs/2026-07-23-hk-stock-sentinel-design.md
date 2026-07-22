# 港股哨兵（HK Stock Sentinel）设计文档

- 日期：2026-07-23
- 状态：设计已获用户批准；v2 修订（前后端结构与 skill 映射）待用户确认
- 工作区：`E:\MyProject\KimiInvestment\港股监控助手`

---

## 1. 产品定位

「港股哨兵」是一个运行在本机 Kimi Work 环境中的港股持仓监控与决策纪律助手。用户通过对话或监控网站管理监控名单；系统按价值投资纪律（ai-berkshire 方法论）在港股交易时段准实时盯盘，在关键价位、异动与论点变质事件发生时主动推送**有依据的**补仓 / 卖出 / 持有建议。

它不是行情软件，不提供逐笔 tick；所有建议为研究参考，不构成投资建议，下单永远由用户手动执行。

## 2. 已确认决策（需求基线）

| 决策点 | 结论 |
|---|---|
| 产品形态 | 方案 A 变体：React 监控网站 + 定时任务混合体 |
| 前端 | React + Vite + TypeScript，代码在 `frontend/` |
| 后端 | Python 引擎（无常驻进程，自动化驱动），代码在 `backend/` |
| 持仓模式 | A：真实持仓，录入成本价与股数，信号结合浮盈浮亏个性化 |
| 初始标的 | 阿里巴巴-W（09988.HK），成本 113.1 港元，200 股 |
| 推送渠道 | 桌面通知 + 飞书群机器人（链路已验证连通） |
| 信号风格 | B：价值区间带 + 红线为核心，异动（涨跌 / 量能 / 公告新闻）为核查触发器 |
| 名单管理 | 对话修改与网站操作双通道，写同一份配置，即时生效 |

### 插件 / skill 使用映射

| 插件 | 定位 | 用途 |
|---|---|---|
| wind-allskill | 核心 | 任务①港股取价主源（`stock_data`）；新闻公告兜底（`financial_docs`） |
| gildata-aifinmarket | 核心 | 任务②公告 / 新闻 / 研报证据；建仓档案财务估值取数 |
| yahoo_finance | 核心 | Wind 失败时的行情兜底 |
| superpowers | 核心 | brainstorming → writing-plans → TDD / 验证 / 执行 全流程 |
| xtt-public-markets-investing | 可选增强 | 建仓档案估值锚加深（valuation / technical 工作流） |
| interactive-research-report-en | 可选增强 | 建仓档案渲染为交互式研究页 |
| xtt-investment-banking-private-equity | 不使用 | 面向并购 / PE 尽调 / 基金结构，与本产品场景不符 |

### 飞书接入（已验证）

- 应用：AIInvestment（飞书个人版，自建应用）
- App ID：`cli_aac5261b6239dcfa`
- 群聊 ID：`oc_a26bd52919d41df6b9315ca50325158e`
- 认证方式：`tenant_access_token`（App ID + App Secret 换取）
- App Secret 仅存本机 `backend/config/feishu.json`，只用于飞书 API 调用，不进入任何对外内容
- **已知坑**：Windows 终端会把命令行内联中文转成 GBK 导致乱码；所有含中文的飞书推送必须走 UTF-8 文件载荷或 Python 直接发送（已验证修复）

## 3. 架构总览

```
                 ┌────────────────────────────────────────┐
                 │     用户：React 网站操作 / 对话          │
                 └──────┬───────────────┬─────────────────┘
                        │ POST /api/*    │ 助手改配置
                        │ (Vite 中间件)  ▼
                        ▼        backend/config/watchlist.json（唯一事实源）
   ┌────────────────────────────────────────────────────┐
   │  股票 / 成本 / 股数 / 三档价格带 / 论点 / 红线        │
   └──────┬───────────────────────────┬────────────────┘
          │ 交易时段每30分钟            │ 交易时段每小时+收盘
          ▼                           ▼
 ┌──────────────────────┐   ┌──────────────────────┐
 │ 任务① 行情哨兵         │   │ 任务② AI 研判官        │
 │ Python（backend/）     │   │ 定时任务 agent        │
 │ 取价→对规则→写数据契约  │   │ 信号→查新闻公告→研判   │
 │ →记信号→推事实快讯     │   │ 收盘简报→推"为什么+怎么办"│
 └───────┬──────────────┘   └──────────┬───────────┘
         │ 写 frontend/public/data/*.json       │
         ▼                           ▼
   React 前端轮询读取          桌面通知 + 飞书群
```

两个 Blueprint Automation：

| # | 名称 | 类别 | 触发 | 职责 |
|---|---|---|---|---|
| ① | 行情哨兵 | widget 任务（Python code） | schedule `12,42 9-16 * * 1-5`（Asia/Hong_Kong） | 取价 → 规则比对 → 写数据契约 → 记信号 → 推事实快讯 |
| ② | AI 研判官 | 定时任务（agent local_conversation） | schedule `47 10-16 * * 1-5`（Asia/Hong_Kong） | 处理未研判信号；16:47 兼任收盘简报 |

配额占用：widget 任务 1/6，定时任务 1/6。

**无常驻后端进程**：backend 由任务①②定时驱动；前端读 JSON 数据契约；网站写操作由 Vite 开发服务器中间件承接（预览运行期内有效），对话改配置始终可用。

## 4. 数据层

| 用途 | 主用 | 兜底 |
|---|---|---|
| 港股实时/延时行情 | Wind（`stock_data`，经 agent-gw CLI：`node skills/wind-mcp-skill/scripts/cli.mjs call ...`，Python subprocess 调用） | Yahoo Finance 公共行情接口 |
| 公告 / 新闻 / 研报 | Gildata（任务② agent 直接用插件工具） | Wind `financial_docs` |
| 财务 / 估值数据 | Wind + Gildata | 建仓档案人工补充 |

数据纪律：

- 取价失败 → 标记「数据不可用」，前端标灰，**绝不编造价格**
- 单次工具调用单标的；日期 `yyyyMMdd`；参数以 tool-contracts.md 为准
- 精度纪律（移植 ai-berkshire financial_rigor）：金额计算用 `decimal.Decimal`；市值 = 价 × 股本手工校验；港币 / 人民币单位显式标注
- 港股假日：取价无更新即自动静默，不产生信号

## 5. 信号规则（任务①）

每只股票在 watchlist.json 中持有一份规则卡：

| 信号 | 触发条件 | 级别 |
|---|---|---|
| 🟢 补仓信号 | 现价进入补仓区（估值锚 × 安全边际，建仓档案确定） | 高 |
| 🔴 卖出信号 | 现价涨破卖出区（高估区，估值锚定） | 高 |
| ⚡ 异动核查 | 单日涨跌 > ±5%，或成交量 > 20 日均量 2 倍 | 中 |
| ⚫ 红线警报 | 触碰用户设定的硬性止损价，或论点红线事件（管理层诚信、主业变质等，由任务②判定） | 最高 |

通用规则：

- **冷却期**：同股票同类型信号，1 个交易日内只发一次，防止 30 分钟轮询刷屏
- 浮盈浮亏、持仓市值随价实时重算（成本 × 股数 vs 现价 × 股数，港币）
- 补仓建议输出「按现价补 X 股后的新成本价」演算
- 红线默认**不含**硬止损价，除非用户主动设定

## 6. AI 研判流（任务②）

1. 读取 `backend/data/signals.jsonl` 中未研判的信号
2. 用 Gildata / Wind 查该股当日公告、新闻、研报观点
3. 按 ai-berkshire 纪律输出结构化研判：
   - **论点还活着吗**（thesis 核查）
   - **结论**：补仓 / 卖出 / 持有 / 噪音（强制给结论，不打太极）
   - **依据**：数据 + 新闻 + 价格带位置
   - **建议操作**：具体价位与股数演算
4. 推送飞书富文本卡片（标题 = 结论）+ 桌面通知；研判写回 signals.jsonl 并同步进数据契约
5. 16:47 运行兼任收盘简报：持仓概览、今日信号、要闻、价格带位置，存档 `backend/reports/YYYY-MM-DD-close.md` 并拷贝到 `frontend/public/reports/`
6. 无信号的日子：仅 16:47 出简短持仓日报

## 7. 前端（React 监控网站）

- **技术栈**：React + Vite + TypeScript，`npm run dev` 可预览
- **数据契约**（backend 写入 `frontend/public/data/`，前端每 30–60 秒轮询）：
  - `latest.json`：行情快照、持仓盈亏、价格带位置、信号灯、最近信号、市场开闭状态、数据时间戳
  - `reports-index.json` + `reports/*.md`：收盘简报与建仓档案索引
- **页面内容**：
  - 持仓卡片墙：现价、日涨跌、成本对比浮盈浮亏、**价格带仪表条**（现价在补仓区—卖出区之间的位置）、信号灯
  - 顶栏：恒指快照 + 市场状态 + 数据更新时间（过期数据显式标灰提示）
  - 信号流水与研判摘要，链接到报告存档
  - 名单管理表单：添加（名称/代码+成本+股数）、编辑、删除
- **写接口**（Vite 中间件，仅预览服务器运行期有效）：
  - `POST /api/watchlist`：`{action: add|update|remove, ...}` → 校验 → 写 `backend/config/watchlist.json`
  - `GET /api/config`：返回脱敏配置（不含任何凭证）
  - `POST /api/refresh`：立即执行一次取价刷新
- 新增股票（无论网站还是对话录入）都会触发建仓级分析（第 8 节）

## 8. 建仓级分析（新股票入会仪式）

每只新股票（含首只 09988）执行一次 ai-berkshire 精简流程：

1. Wind + Gildata 取财务、估值、股本、近一年价格区间（可选：xtt-public-markets-investing 估值工作流加深）
2. investment-checklist 改编版打分（能力圈 / 好生意 / 护城河 / 管理层 / 安全边际）
3. 输出：**通过 / 灰色 / 否决** + 内在价值区间 + **三档价格带**（补仓区 / 持有区 / 卖出区）+ 3–5 条论点红线
4. **人工确认门**：价格带与红线经用户确认后才写入 watchlist.json（防止 AI 单方面定锚）
5. 档案存 `backend/reports/dossier-09988.md`（可选：interactive-research-report-en 渲染交互版）

## 9. 文件布局

```
frontend/                     React + Vite + TS 监控网站
  public/data/latest.json     行情数据契约（backend 写入）
  public/reports/             报告存档（backend 同步）
  vite.config.ts              含写接口中间件
backend/
  config/watchlist.json       监控名单 + 规则卡（唯一事实源）
  config/feishu.json          App ID / Secret / 群 ID（仅本机，仅用于飞书 API）
  engine/fetch_quotes.py      Wind + Yahoo 取价
  engine/rules.py             信号规则引擎（Decimal）
  engine/feishu_push.py       飞书推送（UTF-8 载荷）
  engine/run_poll.py          任务①入口
  data/signals.jsonl          信号流水（含研判状态，可复盘准确率）
  data/quotes_cache.json      最近一次行情缓存
  reports/                    收盘简报、建仓档案（Markdown 母本）
skills/vendor/                ai-berkshire 方法论改编版（附原 LICENSE）
docs/superpowers/specs/       本设计文档
```

## 10. 错误处理与降级

| 故障 | 处理 |
|---|---|
| Wind 取价失败 | Yahoo 兜底；都失败 → 数据契约标记不可用，前端标灰 + 推「数据不可用」 |
| 飞书推送失败 | 桌面通知兜底，失败消息记入待重发队列，下轮重试一次 |
| 前端数据过期 | 时间戳超过 45 分钟未更新 → 顶栏显式提示「数据过期」 |
| 写接口参数非法 | 中间件校验后拒绝并返回错误说明，不写盘 |
| 信号判定数据缺失 | 该条信号跳过并标注原因，不用推测伪装确定性（留白原则） |

## 11. 边界与免责

- 准实时：行情源对港股可能有延迟，叠加 30 分钟轮询，为分钟级监控；不适合日内高频
- 所有推送与报告固定附「研究参考，不构成投资建议」
- AI 不执行任何交易；补仓/卖出仅为建议与演算
- App Secret 不出本机；前端写接口只暴露脱敏配置，不含任何凭证

## 12. ai-berkshire 复用清单

| 资产 | 用法 |
|---|---|
| skills/investment-checklist.md | 改编为建仓档案打分模板 |
| skills/thesis-tracker.md / thesis-drift.md | 改编为任务②的论点核查与漂移检测流程 |
| skills/news-pulse.md | 改编为任务②的新闻脉搏扫描 |
| tools/financial_rigor.py | Decimal 精度与市值校验思路移植进 backend/engine |
| 分层建议风格（激进/稳健/保守 + 价格区间） | 研判输出格式 |

原仓库 LICENSE 随 vendor 目录保留并注明出处。

## 13. 实现顺序（高层）

1. 阿里巴巴（09988）建仓级分析 → 用户确认三档价格带与红线 → 初始化 watchlist.json
2. backend/engine：取价（Wind+Yahoo 兜底）、规则引擎、飞书推送（UTF-8 载荷）
3. frontend：React 监控网站（数据契约消费 + 名单管理 + Vite 写接口中间件）
4. 任务①②注册为 Blueprint Automation 并联调
5. 端到端演练：手动触发 → 信号 → 研判 → 双渠道推送 → 网站刷新

详细实现计划由 writing-plans 阶段产出。
