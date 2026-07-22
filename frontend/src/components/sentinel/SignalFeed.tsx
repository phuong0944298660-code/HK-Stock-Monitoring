import type { SignalItem, SignalType } from "@/types/sentinel";

const TYPE_STYLE: Record<
  SignalType,
  { icon: string; label: string; color: string }
> = {
  BUY_ZONE: { icon: "🟢", label: "补仓信号", color: "#34d399" },
  SELL_ZONE: { icon: "🔴", label: "卖出信号", color: "#f87171" },
  VOL_ALERT: { icon: "⚡", label: "异动核查", color: "#fbbf24" },
  RED_LINE: { icon: "⚫", label: "红线警报", color: "#fb4d6d" },
  EVENT: { icon: "📅", label: "事件", color: "#22d3ee" },
};

function SignalCard({ s }: { s: SignalItem }) {
  const st = TYPE_STYLE[s.type];
  return (
    <div
      className="rounded-r-md border border-[#1a2540] bg-[#0c1220] p-3"
      style={{ borderLeft: `3px solid ${st.color}` }}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm">{st.icon}</span>
        <span
          className="font-data text-[10px] font-semibold tracking-[0.18em]"
          style={{ color: st.color }}
        >
          {st.label}
        </span>
        <span className="text-sm font-medium text-slate-200">
          {s.name} · {s.title}
        </span>
        <span className="font-data tnum ml-auto text-[11px] text-slate-500">
          {s.time}
        </span>
      </div>
      <p className="mt-1.5 text-xs leading-relaxed text-slate-400">{s.detail}</p>
      {s.verdict && (
        <div className="mt-2 rounded border border-[#1a2540] bg-[#111a2b] p-2.5">
          <div className="flex items-center gap-2">
            <span className="font-data text-[10px] tracking-[0.18em] text-[#22d3ee]">
              AI 研判
            </span>
            <span
              className="rounded px-1.5 py-0.5 text-[11px] font-semibold"
              style={{ color: st.color, background: `${st.color}1a` }}
            >
              {s.verdict}
            </span>
          </div>
          <p className="mt-1 text-xs leading-relaxed text-slate-400">
            {s.verdictSummary}
          </p>
        </div>
      )}
    </div>
  );
}

/** 信号流水：左侧 3px 色条按信号语义分级 */
export function SignalFeed({ signals }: { signals: SignalItem[] }) {
  return (
    <section>
      <div className="mb-3 flex items-center gap-3">
        <h2 className="font-data text-xs font-semibold tracking-[0.22em] text-slate-400">
          信号流水 SIGNALS
        </h2>
        <div className="h-px flex-1 bg-[#1a2540]" />
      </div>
      {signals.length === 0 ? (
        <div className="rounded-md border border-dashed border-[#1a2540] p-8 text-center">
          <p className="font-data text-xs tracking-wider text-slate-500">
            暂无信号 · 系统在交易时段每 30 分钟巡检一次
          </p>
        </div>
      ) : (
        <div className="space-y-2.5">
          {signals.map((s) => (
            <SignalCard key={s.id} s={s} />
          ))}
        </div>
      )}
    </section>
  );
}
