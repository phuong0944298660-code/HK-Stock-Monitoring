import { useCallback, useEffect, useState } from "react";
import type { WatchStock, WatchlistConfig } from "@/types/sentinel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const EMPTY: WatchStock = {
  code: "",
  windcode: "",
  name: "",
  cost: null,
  shares: null,
  bands: { buyBelow: 0, sellAbove: 0, stopLoss: null },
};

/** 监控名单管理：读写 backend/config/watchlist.json（经 Vite 中间件） */
export function WatchlistManager({ onChanged }: { onChanged?: () => void }) {
  const [stocks, setStocks] = useState<WatchStock[]>([]);
  const [form, setForm] = useState<WatchStock>(EMPTY);
  const [editing, setEditing] = useState<string | null>(null);
  const [msg, setMsg] = useState<string>("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/config");
      const cfg = (await res.json()) as WatchlistConfig;
      setStocks(cfg.stocks ?? []);
    } catch {
      setMsg("配置读取失败（预览中间件未运行？）");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const submit = async (action: "upsert" | "remove", stock: WatchStock) => {
    setBusy(true);
    setMsg("");
    try {
      const res = await fetch("/api/watchlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, stock }),
      });
      const out = await res.json();
      if (!res.ok) throw new Error(out.error || `HTTP ${res.status}`);
      setMsg(action === "remove" ? "已删除" : "已保存（价格带为默认占位，建仓级分析后生效）");
      setForm(EMPTY);
      setEditing(null);
      await load();
      onChanged?.();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-lg border border-[#1a2540] bg-[#0c1220] p-4">
      <div className="mb-3 flex items-center gap-3">
        <h2 className="font-data text-xs font-semibold tracking-[0.22em] text-slate-400">
          监控名单 WATCHLIST
        </h2>
        <div className="h-px flex-1 bg-[#1a2540]" />
      </div>

      <div className="space-y-2">
        {stocks.map((s) => (
          <div
            key={s.code}
            className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-md border border-[#1a2540] bg-[#111a2b] px-3 py-2"
          >
            <span className="font-data text-sm font-semibold text-slate-100">
              {s.code}
            </span>
            <span className="text-sm text-slate-300">{s.name}</span>
            <span className="font-data tnum text-xs text-slate-500">
              {s.cost != null ? `成本 ${s.cost} × ${s.shares} 股` : "观察"}
            </span>
            <span className="font-data tnum text-xs text-slate-500">
              带 ≤{s.bands.buyBelow} / ≥{s.bands.sellAbove}
            </span>
            <span className="ml-auto flex gap-1.5">
              <Button
                size="sm"
                variant="outline"
                className="h-7 border-[#1a2540] bg-transparent text-xs text-slate-300 hover:bg-[#1a2540]"
                onClick={() => {
                  setEditing(s.code);
                  setForm(s);
                }}
              >
                编辑
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="h-7 border-[#f87171]/40 bg-transparent text-xs text-[#f87171] hover:bg-[#f87171]/10"
                disabled={busy}
                onClick={() => submit("remove", s)}
              >
                删除
              </Button>
            </span>
          </div>
        ))}
      </div>

      <div className="mt-4 border-t border-[#1a2540] pt-3">
        <div className="mb-2 font-data text-[10px] tracking-[0.18em] text-slate-500">
          {editing ? `编辑 ${editing}` : "添加股票（代码如 09988，成本/股数可留空表示观察）"}
        </div>
        <div className="flex flex-wrap gap-2">
          <Input
            className="h-8 w-24 border-[#1a2540] bg-[#111a2b] font-data text-xs"
            placeholder="代码"
            value={form.code}
            onChange={(e) => setForm({ ...form, code: e.target.value.trim() })}
          />
          <Input
            className="h-8 w-32 border-[#1a2540] bg-[#111a2b] text-xs"
            placeholder="名称"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <Input
            className="h-8 w-24 border-[#1a2540] bg-[#111a2b] font-data text-xs"
            placeholder="成本价"
            value={form.cost ?? ""}
            onChange={(e) =>
              setForm({ ...form, cost: e.target.value ? Number(e.target.value) : null })
            }
          />
          <Input
            className="h-8 w-24 border-[#1a2540] bg-[#111a2b] font-data text-xs"
            placeholder="股数"
            value={form.shares ?? ""}
            onChange={(e) =>
              setForm({ ...form, shares: e.target.value ? Number(e.target.value) : null })
            }
          />
          <Button
            size="sm"
            className="h-8 bg-[#22d3ee] text-xs font-semibold text-[#050810] hover:bg-[#22d3ee]/85"
            disabled={busy || !form.code}
            onClick={() => submit("upsert", form)}
          >
            {editing ? "保存修改" : "添加"}
          </Button>
          {editing && (
            <Button
              size="sm"
              variant="outline"
              className="h-8 border-[#1a2540] bg-transparent text-xs text-slate-400"
              onClick={() => {
                setEditing(null);
                setForm(EMPTY);
              }}
            >
              取消
            </Button>
          )}
        </div>
        {msg && <p className="mt-2 font-data text-[11px] text-[#fbbf24]">{msg}</p>}
        <p className="mt-2 text-[11px] leading-relaxed text-slate-600">
          新股票保存后，会在对话中触发建仓级分析：生成三档价格带与论点红线，经你确认后正式生效。
        </p>
      </div>
    </section>
  );
}
