import { useCallback, useEffect, useState } from "react";
import type { LatestData } from "@/types/sentinel";

const STALE_MS = 45 * 60 * 1000; // 45 分钟不更新视为过期

export function useSentinelData(pollMs = 30_000) {
  const [data, setData] = useState<LatestData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`./data/latest.json?ts=${Date.now()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData((await res.json()) as LatestData);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const timer = window.setInterval(load, pollMs);
    return () => window.clearInterval(timer);
  }, [load, pollMs]);

  const stale = data
    ? Date.now() - new Date(data.generatedAt).getTime() > STALE_MS
    : false;

  return { data, error, loading, stale, reload: load };
}
