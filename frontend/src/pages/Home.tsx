import { TopTicker } from "@/components/sentinel/TopTicker";
import { MarketHeader } from "@/components/sentinel/MarketHeader";
import { PositionCard } from "@/components/sentinel/PositionCard";
import { SignalFeed } from "@/components/sentinel/SignalFeed";
import { WatchlistManager } from "@/components/sentinel/WatchlistManager";
import { useSentinelData } from "@/hooks/useSentinelData";

export default function Home() {
  const { data, error, loading, stale, reload } = useSentinelData();

  const refreshNow = async () => {
    await fetch("/api/refresh", { method: "POST" });
    await reload();
  };

  return (
    <div className="min-h-screen bg-[#050810]">
      <TopTicker data={data} />
      <main className="mx-auto max-w-6xl space-y-5 px-4 py-5">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold text-slate-100">持仓监控</h1>
          <button
            onClick={refreshNow}
            className="rounded border border-[#1a2540] px-2.5 py-1 font-data text-[11px] tracking-wider text-[#22d3ee] transition-colors hover:border-[#22d3ee]/50"
          >
            ⟳ 立即刷新
          </button>
        </div>

        {loading && (
          <div className="space-y-3">
            {[0, 1].map((i) => (
              <div
                key={i}
                className="skeleton-pulse h-44 rounded-lg border border-[#1a2540] bg-[#0c1220]"
              />
            ))}
          </div>
        )}

        {error && (
          <div className="rounded-md border border-[#f87171]/50 bg-[#0c1220] p-4 text-sm text-[#f87171]">
            数据加载失败：{error}
          </div>
        )}

        {data && (
          <>
            <MarketHeader data={data} stale={stale} />
            <div className="grid gap-4 lg:grid-cols-2">
              {data.holdings.map((h) => (
                <PositionCard key={h.code} h={h} />
              ))}
            </div>
            <SignalFeed signals={data.signals} />
            <WatchlistManager onChanged={reload} />
            <footer className="border-t border-[#1a2540] pb-8 pt-4 text-center">
              <p className="font-data text-[10px] tracking-wider text-slate-600">
                研究参考，不构成投资建议 · 当前为 MOCK 演示数据 · 港股哨兵 v0.1
              </p>
            </footer>
          </>
        )}
      </main>
    </div>
  );
}
