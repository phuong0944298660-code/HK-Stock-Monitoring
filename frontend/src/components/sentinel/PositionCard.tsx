import type { Holding, SignalLight } from "@/types/sentinel";
import { PriceBandMeter } from "./PriceBandMeter";

const LIGHT: Record<SignalLight, { text: string; cls: string; dot: string }> = {
  buy: { text: "补仓区", cls: "text-[#34d399] border-[#34d399]/50", dot: "bg-[#34d399]" },
  sell: { text: "卖出区", cls: "text-[#f87171] border-[#f87171]/50", dot: "bg-[#f87171]" },
  hold: { text: "持有", cls: "text-[#fbbf24] border-[#fbbf24]/50", dot: "bg-[#fbbf24]" },
  alert: { text: "红线警报", cls: "text-[#fb4d6d] border-[#fb4d6d]/60", dot: "bg-[#fb4d6d]" },
  none: { text: "观察", cls: "text-slate-400 border-slate-600", dot: "bg-slate-500" },
};

function fmt(n: number, digits = 2) {
  return n.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function Metric({
  label,
  value,
  valueCls = "text-slate-200",
}: {
  label: string;
  value: string;
  valueCls?: string;
}) {
  return (
    <div>
      <div className="font-data text-[10px] tracking-[0.18em] text-slate-500">
        {label}
      </div>
      <div className={`font-data tnum mt-0.5 text-sm ${valueCls}`}>{value}</div>
    </div>
  );
}

/** 持仓卡片：价格 + 盈亏 + 价格带仪表条 + 信号灯 */
export function PositionCard({ h }: { h: Holding }) {
  const light = LIGHT[h.signal];
  const up = h.dayChangePct >= 0;
  const hasPosition = h.cost != null && h.shares != null;
  const pnl = hasPosition ? (h.price - h.cost!) * h.shares! : null;
  const pnlPct = hasPosition ? (h.price / h.cost! - 1) * 100 : null;
  const mktValue = hasPosition ? h.price * h.shares! : null;
  const volRatio = h.volAvg20 > 0 ? h.volume / h.volAvg20 : null;

  return (
    <div className="rounded-lg border border-[#1a2540] bg-[#0c1220] p-4 transition-colors hover:border-[#22d3ee]/30">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-baseline gap-2">
            <span className="text-base font-semibold text-slate-100">{h.name}</span>
            <span className="font-data text-[11px] tracking-wider text-slate-500">
              {h.windcode}
            </span>
          </div>
          {!hasPosition && (
            <span className="mt-1 inline-block rounded border border-dashed border-slate-600 px-1.5 py-0.5 text-[10px] text-slate-400">
              无持仓 · 观察
            </span>
          )}
        </div>
        <span
          className={`flex shrink-0 items-center gap-1.5 rounded border px-2 py-1 text-[11px] ${light.cls}`}
        >
          <span className={`live-dot inline-block h-1.5 w-1.5 rounded-full ${light.dot}`} />
          {light.text}
        </span>
      </div>

      <div className="mt-3 flex items-baseline gap-3">
        <span className="font-data tnum text-3xl font-bold text-slate-50">
          {fmt(h.price)}
        </span>
        <span className={`font-data tnum text-sm font-medium ${up ? "text-up" : "text-down"}`}>
          {up ? "▲" : "▼"} {up ? "+" : ""}
          {fmt(h.dayChangePct)}%
        </span>
        <span className="font-data text-[10px] tracking-wider text-slate-600">
          {h.currency}
        </span>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 border-t border-[#1a2540] pt-3 sm:grid-cols-3">
        {hasPosition ? (
          <>
            <Metric label="成本 / 股数" value={`${fmt(h.cost!)} × ${h.shares}`} />
            <Metric
              label="浮盈浮亏"
              value={`${pnl! >= 0 ? "+" : ""}${fmt(pnl!, 0)} (${pnlPct! >= 0 ? "+" : ""}${fmt(pnlPct!, 1)}%)`}
              valueCls={pnl! >= 0 ? "text-up" : "text-down"}
            />
            <Metric label="持仓市值" value={`${fmt(mktValue!, 0)} HKD`} />
          </>
        ) : (
          <Metric label="前收盘" value={fmt(h.prevClose)} />
        )}
        <Metric
          label="量比（20日）"
          value={volRatio ? `${volRatio.toFixed(1)}×` : "—"}
          valueCls={volRatio && volRatio >= 2 ? "text-[#fbbf24]" : "text-slate-200"}
        />
      </div>

      <PriceBandMeter
        price={h.price}
        buyBelow={h.bands.buyBelow}
        sellAbove={h.bands.sellAbove}
      />
    </div>
  );
}
