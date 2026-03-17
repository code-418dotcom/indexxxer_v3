"use client";

import { useQuery } from "@tanstack/react-query";
import { getOverview, getQueryStats, getIndexingStats } from "@/lib/api/analytics";

function bytes(n: number): string {
  if (n >= 1e12) return `${(n / 1e12).toFixed(1)} TB`;
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)} GB`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)} MB`;
  return `${(n / 1e3).toFixed(0)} KB`;
}

export default function AnalyticsPage() {
  const { data: overview } = useQuery({ queryKey: ["analytics", "overview"], queryFn: getOverview });
  const { data: queryStats } = useQuery({ queryKey: ["analytics", "queries"], queryFn: () => getQueryStats(30) });
  const { data: indexingStats } = useQuery({ queryKey: ["analytics", "indexing"], queryFn: () => getIndexingStats(30) });

  return (
    <div className="p-8 space-y-8">
      <h1 className="text-2xl font-bold text-white">Analytics</h1>

      {/* Overview stat cards */}
      {overview && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: "Total Media", value: overview.total_media.toLocaleString() },
            { label: "Sources", value: overview.source_count },
            { label: "Storage", value: bytes(overview.storage_bytes) },
          ].map(({ label, value }) => (
            <div key={label} className="bg-neutral-800 rounded-xl p-4">
              <p className="text-neutral-400 text-xs uppercase tracking-wide mb-1">{label}</p>
              <p className="text-white text-2xl font-bold">{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Search stats */}
      {queryStats && (
        <div className="bg-neutral-800 rounded-xl p-6">
          <h2 className="text-white font-semibold mb-4">
            Search Volume (last 30 days — {queryStats.total_searches.toLocaleString()} total)
          </h2>
          {/* Simple bar chart using CSS */}
          <div className="flex items-end gap-1 h-24">
            {queryStats.daily.map((d) => {
              const max = Math.max(...queryStats.daily.map((x) => x.count), 1);
              const pct = (d.count / max) * 100;
              return (
                <div
                  key={d.date}
                  title={`${d.date}: ${d.count}`}
                  className="flex-1 bg-blue-600 rounded-t opacity-80 hover:opacity-100 min-h-[4px]"
                  style={{ height: `${Math.max(pct, 4)}%` }}
                />
              );
            })}
          </div>

          <div className="mt-6">
            <h3 className="text-neutral-400 text-sm mb-2">Top Queries</h3>
            <div className="space-y-1">
              {queryStats.top_queries.slice(0, 5).map((q) => (
                <div key={q.query} className="flex justify-between text-sm">
                  <span className="text-neutral-300 truncate max-w-[70%]">{q.query}</span>
                  <span className="text-neutral-500">{q.count}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-4 flex gap-4">
            {Object.entries(queryStats.mode_breakdown).map(([mode, count]) => (
              <div key={mode} className="text-sm">
                <span className="text-neutral-400">{mode}: </span>
                <span className="text-white">{count as number}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Indexing stats */}
      {indexingStats && (
        <div className="bg-neutral-800 rounded-xl p-6">
          <h2 className="text-white font-semibold mb-4">Indexing Activity (last 30 days)</h2>
          <div className="flex items-end gap-1 h-24">
            {indexingStats.daily_indexed.map((d) => {
              const max = Math.max(...indexingStats.daily_indexed.map((x) => x.count), 1);
              const pct = (d.count / max) * 100;
              return (
                <div
                  key={d.date}
                  title={`${d.date}: ${d.count}`}
                  className="flex-1 bg-green-600 rounded-t opacity-80 hover:opacity-100 min-h-[4px]"
                  style={{ height: `${Math.max(pct, 4)}%` }}
                />
              );
            })}
          </div>
          <div className="mt-4 flex gap-6 text-sm text-neutral-400">
            <span>Errors: <span className="text-red-400">{indexingStats.error_count}</span></span>
            <span>Avg search latency: <span className="text-white">{indexingStats.avg_search_latency_ms}ms</span></span>
          </div>
        </div>
      )}
    </div>
  );
}
