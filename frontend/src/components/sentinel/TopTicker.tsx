import type { LatestData } from "@/types/sentinel";

/** 顶部滚动快讯条：悬停暂停；左侧 LIVE 脉冲点表达“活性” */
export function TopTicker({ data }: { data: LatestData | null }) {
  const items: string[] = [];
  if (data) {
    for (const s of data.signals) {
      items.push(`${s.time.slice(5)} · ${s.name} ${s.title} · ${s.detail}`);
    }
    if (data.market.hsi.value != null) {
      items.push(
        `恒指 ${data.market.hsi.value.toLocaleString("en-US", { minimumFractionDigits: 2 })} ${(data.market.hsi.changePct ?? 0) >= 0 ? "+" : ""}${data.market.hsi.changePct ?? "—"}%`,
      );
    }
    if (data.market.hstech?.value != null) {
      items.push(
        `恒生科技 ${data.market.hstech.value.toLocaleString("en-US", { minimumFractionDigits: 2 })} ${(data.market.hstech.changePct ?? 0) >= 0 ? "+" : ""}${data.market.hstech.changePct ?? "—"}%`,
      );
    }
    items.push(`下次例行刷新 · 交易时段每 30 分钟`);
  }
  const loop = [...items, ...items];

  return (
    <div className="sticky top-0 z-50 flex h-9 items-center border-b border-[#1a2540] bg-[#0c1220]/95 backdrop-blur">
      <div className="flex h-full shrink-0 items-center gap-2 border-r border-[#1a2540] px-3">
        <span className="live-dot inline-block h-2 w-2 rounded-full bg-[#22d3ee]" />
        <span className="font-data text-[11px] font-semibold tracking-[0.22em] text-[#22d3ee]">
          HK SENTINEL
        </span>
      </div>
      <div className="relative flex-1 overflow-hidden">
        {items.length === 0 ? (
          <div className="px-3 font-data text-[11px] tracking-wider text-slate-500">
            WAITING FOR DATA…
          </div>
        ) : (
          <div className="ticker-track inline-flex whitespace-nowrap py-2">
            {loop.map((t, i) => (
              <span
                key={i}
                className="mx-6 inline-flex items-center gap-2 font-data text-[11px] tracking-wider text-slate-400"
              >
                <span className="inline-block h-1 w-1 rounded-full bg-[#1a2540] ring-1 ring-[#22d3ee]/50" />
                {t}
              </span>
            ))}
          </div>
        )}
      </div>
      {data?.demo && (
        <div className="hidden h-full shrink-0 items-center border-l border-dashed border-[#fbbf24]/50 px-3 sm:flex">
          <span className="font-data text-[10px] tracking-[0.18em] text-[#fbbf24]">
            MOCK 演示数据
          </span>
        </div>
      )}
    </div>
  );
}
