interface Props {
  price: number;
  buyBelow: number;
  sellAbove: number;
}

/** 价格带仪表条：一眼看出现价在 补仓区—持有区—卖出区 中的位置 */
export function PriceBandMeter({ price, buyBelow, sellAbove }: Props) {
  const min = buyBelow * 0.9;
  const max = sellAbove * 1.1;
  const pct = (v: number) =>
    Math.min(100, Math.max(0, ((v - min) / (max - min)) * 100));

  const buyEdge = pct(buyBelow);
  const sellEdge = pct(sellAbove);
  const pricePct = pct(price);

  const inBuy = price <= buyBelow;
  const inSell = price >= sellAbove;
  const marker = inBuy ? "#34d399" : inSell ? "#f87171" : "#fbbf24";
  const stateText = inBuy
    ? "处于补仓区"
    : inSell
      ? "处于卖出区"
      : "持有区 · 距补仓线 " +
        ((price / buyBelow - 1) * 100).toFixed(1) +
        "% · 距卖出线 +" +
        ((sellAbove / price - 1) * 100).toFixed(1) +
        "%";

  return (
    <div className="pt-7">
      <div className="relative h-2 rounded-full bg-[#1a2540]">
        <div
          className="absolute inset-y-0 left-0 rounded-l-full bg-[#34d399]/20"
          style={{ width: `${buyEdge}%` }}
        />
        <div
          className="absolute inset-y-0 right-0 rounded-r-full bg-[#f87171]/20"
          style={{ left: `${sellEdge}%` }}
        />
        <div
          className="absolute -inset-y-0.5 w-px bg-[#34d399]/70"
          style={{ left: `${buyEdge}%` }}
        />
        <div
          className="absolute -inset-y-0.5 w-px bg-[#f87171]/70"
          style={{ left: `${sellEdge}%` }}
        />
        <div
          className="absolute -top-7 -translate-x-1/2 font-data tnum text-[11px] font-semibold"
          style={{ left: `${pricePct}%`, color: marker }}
        >
          {price.toFixed(2)}
        </div>
        <div
          className="absolute -top-1.5 h-5 w-[3px] -translate-x-1/2 rounded-full"
          style={{
            left: `${pricePct}%`,
            background: marker,
            boxShadow: `0 0 8px 1px ${marker}`,
          }}
        />
      </div>
      <div className="mt-1.5 flex items-baseline justify-between">
        <span className="font-data text-[10px] tracking-wider text-[#34d399]">
          ≤{buyBelow.toFixed(2)} 补仓区
        </span>
        <span className="font-data tnum text-[10px] tracking-wider text-slate-500">
          {stateText}
        </span>
        <span className="font-data text-[10px] tracking-wider text-[#f87171]">
          ≥{sellAbove.toFixed(2)} 卖出区
        </span>
      </div>
    </div>
  );
}
