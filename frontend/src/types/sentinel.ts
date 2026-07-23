// 数据契约：backend/engine 每轮刷新写入 frontend/public/data/latest.json
// 前端只消费这份契约，不直接依赖任何取价实现。

export type MarketStatus = "open" | "closed" | "pre";

export type SignalType =
  | "BUY_ZONE" // 进入补仓区
  | "SELL_ZONE" // 涨破卖出区
  | "VOL_ALERT" // 量价异动
  | "RED_LINE" // 红线警报
  | "EVENT"; // 公告/财报等事件

export type SignalLevel = "critical" | "high" | "mid" | "info";

export type SignalLight = "buy" | "hold" | "sell" | "alert" | "none";

export interface IndexSnapshot {
  value: number | null; // 指数抓取失败时为 null
  changePct: number | null;
}

export interface Bands {
  buyBelow: number; // 补仓线：价格 ≤ 此值进入补仓区
  sellAbove: number; // 卖出线：价格 ≥ 此值进入卖出区
  stopLoss: number | null; // 可选硬止损价（默认不设）
}

export interface Holding {
  code: string; // 09988
  windcode: string; // 09988.HK
  name: string;
  currency: "HKD";
  price: number;
  prevClose: number;
  dayChangePct: number;
  volume: number;
  volAvg20: number;
  cost: number | null; // null = 纯观察，无持仓
  shares: number | null;
  pnl?: number | null; // 浮动盈亏金额（HKD），后端计算
  pnlPct?: number | null; // 浮动盈亏 %
  bands: Bands;
  bandsStatus?: string; // confirmed = 价格带已经建仓级分析确认
  signal: SignalLight;
  source?: string; // 数据源：wind / tencent-fallback / yahoo-fallback
  asof?: string; // 行情快照时点
}

export interface Evidence {
  title: string; // 标题（含关键数据点）
  url: string; // 准确链接，禁止编造
  source: string; // 来源机构
  date: string; // 发布日期
}

export interface SignalItem {
  id: string;
  time: string;
  code: string;
  name: string;
  type: SignalType;
  level: SignalLevel;
  title: string;
  detail: string;
  verdict: string | null; // AI 研判结论（补仓/卖出/持有/噪音）
  verdictSummary: string | null; // AI 研判依据摘要
  evidence: Evidence[]; // 建议动作的来源依据，可多条；无可靠来源时为空并标注“灰色地带”
}

export interface LatestData {
  demo: boolean;
  generatedAt: string; // ISO 时间戳；>45min 未更新前端提示“数据过期”
  market: {
    status: MarketStatus;
    statusText: string;
    hsi: IndexSnapshot;
    hstech: IndexSnapshot;
  };
  holdings: Holding[];
  signals: SignalItem[];
  warnings?: string[]; // 本轮取数降级/失败告警（前端可提示）
  sources?: string[]; // 数据源说明
}

// watchlist.json（backend/config）结构
export interface WatchStock {
  code: string;
  windcode: string;
  name: string;
  cost: number | null;
  shares: number | null;
  bands: Bands;
  thesis?: string;
  redLines?: string[];
  bandsStatus?: string;
}

export interface WatchlistConfig {
  version: number;
  updatedAt: string;
  stocks: WatchStock[];
}
