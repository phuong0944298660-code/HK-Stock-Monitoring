import type { IndexSnapshot, LatestData } from "@/types/sentinel";

function IndexChip({ label, idx }: { label: string; idx: IndexSnapshot }) {
  const missing = idx.value == null;
  const up = (idx.changePct ?? 0) >= 0;
  return (
    <div className="flex items-baseline gap-2 rounded-md border border-[#1a2540] bg-[#111a2b] px-3 py-1.5">
      <span className="font-data text-[10px] tracking-[0.18em] text-slate-500">
        {label}
      </span>
      <span className="font-data tnum text-sm font-semibold text-slate-100">
        {missing ? "—" : idx.value!.toLocaleString("en-US", { minimumFractionDigits: 2 })}
      </span>
      {!missing && idx.changePct != null && (
        <span
          className={`font-data tnum text-xs font-medium ${up ? "text-up" : "text-down"}`}
        >
          {up ? "▲" : "▼"} {up ? "+" : ""}
          {idx.changePct}%
        </span>
      )}
    </div>
  );
}

/** 市场状态 + 指数快照 + 数据新鲜度 */
export function MarketHeader({
  data,
  stale,
}: {
  data: LatestData;
  stale: boolean;
}) {
  const open = data.market.status === "open";
  return (
    <div className="flex flex-wrap items-center gap-2 sm:gap-3">
      <div className="flex items-center gap-2 rounded-md border border-[#1a2540] bg-[#111a2b] px-3 py-1.5">
        <span
          className={`inline-block h-2 w-2 rounded-full ${open ? "live-dot bg-[#22d3ee]" : "bg-slate-600"}`}
        />
        <span className="text-xs text-slate-300">{data.market.statusText}</span>
      </div>
      <IndexChip label="HSI 恒指" idx={data.market.hsi} />
      <IndexChip label="HSTECH 恒生科技" idx={data.market.hstech} />
      <div className="ml-auto flex items-center gap-2">
        {stale && (
          <span className="rounded border border-[#fbbf24]/60 px-2 py-0.5 font-data text-[10px] tracking-wider text-[#fbbf24]">
            数据过期
          </span>
        )}
        <span className="font-data tnum text-[11px] text-slate-500">
          更新于 {new Date(data.generatedAt).toLocaleString("zh-CN", { hour12: false })}
        </span>
      </div>
    </div>
  );
}
