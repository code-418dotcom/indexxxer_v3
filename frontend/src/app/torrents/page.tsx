"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDownToLine,
  ArrowUpDown,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Loader2,
  Search,
  Trash2,
  X,
} from "lucide-react";
import { Topbar } from "@/components/layout/Topbar";
import { listPerformers } from "@/lib/api/performers";
import {
  cancelDownload,
  getActiveDownloads,
  getDownloadHistory,
  searchProwlarr,
  sendToTransmission,
  type ProwlarrResult,
} from "@/lib/api/torrents";
import { formatBytes } from "@/lib/utils";

type SortKey = "title" | "size" | "seeders" | "leechers" | "age";
type SortDir = "asc" | "desc";

export default function TorrentsPage() {
  const qc = useQueryClient();
  const [query, setQuery] = useState("");
  const [performerId, setPerformerId] = useState("");
  const [sentTitles, setSentTitles] = useState<Set<string>>(new Set());
  const [sortKey, setSortKey] = useState<SortKey>("seeders");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  // Performer list for dropdown
  const { data: performers } = useQuery({
    queryKey: ["performers-list"],
    queryFn: () => listPerformers({ limit: 200, sort: "name", order: "asc" }),
  });

  // Search
  const search = useMutation({
    mutationFn: (q: string) => searchProwlarr(q),
    onSuccess: () => setSentTitles(new Set()),
  });

  // Active downloads — poll every 5s
  const { data: active } = useQuery({
    queryKey: ["torrent-active"],
    queryFn: getActiveDownloads,
    refetchInterval: 5_000,
  });

  // History
  const { data: history } = useQuery({
    queryKey: ["torrent-history"],
    queryFn: getDownloadHistory,
    refetchInterval: 30_000,
  });

  const [sendingTitle, setSendingTitle] = useState<string | null>(null);

  const download = useMutation({
    mutationFn: (result: ProwlarrResult) => {
      setSendingTitle(result.title);
      return sendToTransmission({
        title: result.title,
        magnet_url: result.magnet_url,
        download_url: result.download_url,
        performer_id: performerId,
        size: result.size,
        indexer: result.indexer,
      });
    },
    onSuccess: (_data, result) => {
      setSentTitles((prev) => new Set(prev).add(result.title));
      setSendingTitle(null);
      qc.invalidateQueries({ queryKey: ["torrent-active"] });
    },
    onError: () => setSendingTitle(null),
  });

  const cancel = useMutation({
    mutationFn: cancelDownload,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["torrent-active"] });
      qc.invalidateQueries({ queryKey: ["torrent-history"] });
    },
  });

  function handleSearch() {
    if (!query.trim()) return;
    search.mutate(query.trim());
  }

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "title" ? "asc" : "desc");
    }
  }

  const sortedResults = useMemo(() => {
    if (!search.data?.results) return [];
    const results = [...search.data.results];
    results.sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "title":
          cmp = a.title.localeCompare(b.title);
          break;
        case "size":
          cmp = a.size - b.size;
          break;
        case "seeders":
          cmp = a.seeders - b.seeders;
          break;
        case "leechers":
          cmp = a.leechers - b.leechers;
          break;
        case "age": {
          const parseAge = (s: string) => {
            const m = s.match(/^(\d+)/);
            return m ? parseInt(m[1]) : 0;
          };
          cmp = parseAge(a.age) - parseAge(b.age);
          break;
        }
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return results;
  }, [search.data?.results, sortKey, sortDir]);

  function SortHeader({ label, field, className }: { label: string; field: SortKey; className?: string }) {
    const active = sortKey === field;
    return (
      <th
        className={`px-3 py-2 font-medium cursor-pointer select-none hover:text-[var(--color-foreground)] transition-colors ${className ?? ""}`}
        onClick={() => toggleSort(field)}
      >
        <span className="inline-flex items-center gap-0.5">
          {label}
          {active ? (
            sortDir === "asc" ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />
          ) : (
            <ArrowUpDown className="w-2.5 h-2.5 opacity-30" />
          )}
        </span>
      </th>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <Topbar title="Torrents">
        <div />
      </Topbar>

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-5xl mx-auto px-3 md:px-5 py-6 space-y-6">
          {/* Search section */}
          <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-4 space-y-3">
            <h2 className="text-sm font-semibold text-[var(--color-foreground)]">
              Search Prowlarr
            </h2>

            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Search indexers..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleSearch();
                }}
                className="flex-1 px-3 py-2 rounded-lg text-sm bg-[var(--color-muted)] border border-[var(--color-border)] text-[var(--color-foreground)] placeholder:text-[var(--color-muted-foreground)] focus:outline-none focus:border-[hsl(217_91%_60%)]"
              />
              <select
                value={performerId}
                onChange={(e) => setPerformerId(e.target.value)}
                className="px-3 py-2 rounded-lg text-sm bg-[var(--color-muted)] border border-[var(--color-border)] text-[var(--color-foreground)] focus:outline-none focus:border-[hsl(217_91%_60%)] max-w-[200px]"
              >
                <option value="">Select performer...</option>
                {performers?.items.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <button
                onClick={handleSearch}
                disabled={!query.trim() || search.isPending}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium border border-[var(--color-border)] hover:border-[hsl(217_33%_30%)] hover:bg-[var(--color-muted)] disabled:opacity-50 transition-all shrink-0"
              >
                {search.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Search className="w-4 h-4" />
                )}
                Search
              </button>
            </div>

            {search.isError && (
              <p className="text-xs text-red-400">
                Search failed. Check Prowlarr connection.
              </p>
            )}
            {download.isError && (
              <p className="text-xs text-red-400">
                Failed to send to Transmission: {(download.error as Error)?.message}
              </p>
            )}
          </div>

          {/* Search results */}
          {search.data && sortedResults.length > 0 && (
            <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] overflow-hidden">
              <div className="px-4 py-2.5 border-b border-[var(--color-border)]">
                <span className="text-xs font-medium text-[var(--color-foreground)]">
                  {search.data.count} results for &ldquo;{search.data.query}&rdquo;
                </span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-[var(--color-border)] text-[var(--color-muted-foreground)]">
                      <SortHeader label="Title" field="title" className="text-left px-4 w-auto" />
                      <SortHeader label="Size" field="size" className="text-right w-20" />
                      <SortHeader label="S" field="seeders" className="text-right w-14" />
                      <SortHeader label="L" field="leechers" className="text-right w-14" />
                      <SortHeader label="Age" field="age" className="text-right w-14" />
                      <th className="text-left px-3 py-2 font-medium w-28">Indexer</th>
                      <th className="px-3 py-2 w-20" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--color-border)]">
                    {sortedResults.map((r, i) => {
                      const sent = sentTitles.has(r.title);
                      const sending = sendingTitle === r.title;
                      return (
                        <tr
                          key={i}
                          className="hover:bg-[var(--color-muted)] transition-colors"
                        >
                          <td className="px-4 py-2 text-[var(--color-foreground)] max-w-[400px]">
                            <div className="flex items-center gap-1.5">
                              <span className="truncate" title={r.title}>
                                {r.title}
                              </span>
                              {r.info_url && (
                                <a
                                  href={r.info_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="shrink-0 text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]"
                                >
                                  <ExternalLink className="w-3 h-3" />
                                </a>
                              )}
                            </div>
                          </td>
                          <td className="text-right px-3 py-2 text-[var(--color-muted-foreground)] whitespace-nowrap">
                            {formatBytes(r.size)}
                          </td>
                          <td className="text-right px-3 py-2 text-emerald-400">
                            {r.seeders}
                          </td>
                          <td className="text-right px-3 py-2 text-[var(--color-muted-foreground)]">
                            {r.leechers}
                          </td>
                          <td className="text-right px-3 py-2 text-[var(--color-muted-foreground)] whitespace-nowrap">
                            {r.age}
                          </td>
                          <td className="px-3 py-2 text-[var(--color-muted-foreground)] truncate">
                            {r.indexer}
                          </td>
                          <td className="px-3 py-2">
                            {sent ? (
                              <span className="flex items-center gap-1 px-2 py-1 rounded text-[10px] font-medium text-emerald-400">
                                <CheckCircle2 className="w-3 h-3" />
                                Sent
                              </span>
                            ) : (
                              <button
                                onClick={() => download.mutate(r)}
                                disabled={
                                  !performerId ||
                                  (!r.magnet_url && !r.download_url) ||
                                  sending
                                }
                                className="flex items-center gap-1 px-2 py-1 rounded text-[10px] font-medium bg-[hsl(217_91%_60%)] text-white hover:bg-[hsl(217_91%_55%)] disabled:opacity-40 transition-colors"
                                title={
                                  !performerId
                                    ? "Select a performer first"
                                    : !r.magnet_url && !r.download_url
                                      ? "No download link"
                                      : "Send to Transmission"
                                }
                              >
                                {sending ? (
                                  <Loader2 className="w-3 h-3 animate-spin" />
                                ) : (
                                  <ArrowDownToLine className="w-3 h-3" />
                                )}
                                DL
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {search.data && search.data.results.length === 0 && (
            <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-6 text-center">
              <p className="text-sm text-[var(--color-muted-foreground)]">
                No results found for &ldquo;{search.data.query}&rdquo;
              </p>
            </div>
          )}

          {/* Active downloads */}
          {active && active.length > 0 && (
            <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] overflow-hidden">
              <div className="px-4 py-2.5 border-b border-[var(--color-border)]">
                <span className="text-xs font-medium text-[var(--color-foreground)]">
                  Active Downloads ({active.length})
                </span>
              </div>
              <div className="divide-y divide-[var(--color-border)]">
                {active.map((dl) => (
                  <div
                    key={dl.id}
                    className="flex items-center gap-3 px-4 py-3"
                  >
                    <div className="flex-1 min-w-0 space-y-1.5">
                      <div className="flex items-center gap-2">
                        <p className="text-xs font-medium text-[var(--color-foreground)] truncate">
                          {dl.title}
                        </p>
                        {dl.performer_name && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-muted)] text-[var(--color-muted-foreground)] shrink-0">
                            {dl.performer_name}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-1.5 rounded-full bg-[var(--color-muted)] overflow-hidden">
                          <div
                            className="h-full rounded-full bg-[hsl(217_91%_60%)] transition-all duration-500"
                            style={{ width: `${dl.progress}%` }}
                          />
                        </div>
                        <span className="text-[10px] text-[var(--color-muted-foreground)] shrink-0 w-12 text-right">
                          {dl.progress.toFixed(1)}%
                        </span>
                      </div>
                    </div>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-muted)] text-[var(--color-muted-foreground)] shrink-0">
                      {dl.status}
                    </span>
                    <button
                      onClick={() => cancel.mutate(dl.id)}
                      className="text-[var(--color-muted-foreground)] hover:text-red-400 transition-colors shrink-0"
                      title="Cancel"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* History */}
          {history && history.length > 0 && (
            <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] overflow-hidden">
              <div className="px-4 py-2.5 border-b border-[var(--color-border)]">
                <span className="text-xs font-medium text-[var(--color-foreground)]">
                  Download History
                </span>
              </div>
              <div className="divide-y divide-[var(--color-border)]">
                {history.map((dl) => (
                  <div
                    key={dl.id}
                    className="flex items-center gap-3 px-4 py-2.5"
                  >
                    {dl.status === "completed" ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    ) : (
                      <Trash2 className="w-4 h-4 text-red-400 shrink-0" />
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-[var(--color-foreground)] truncate">
                        {dl.title}
                      </p>
                      {dl.status === "error" && dl.destination_path === null && (
                        <p className="text-[10px] text-red-400 truncate">
                          Error
                        </p>
                      )}
                    </div>
                    {dl.performer_name && (
                      <span className="text-[10px] text-[var(--color-muted-foreground)] shrink-0">
                        {dl.performer_name}
                      </span>
                    )}
                    {dl.size && (
                      <span className="text-[10px] text-[var(--color-muted-foreground)] shrink-0">
                        {formatBytes(dl.size)}
                      </span>
                    )}
                    {dl.completed_at && (
                      <span className="text-[10px] text-[var(--color-muted-foreground)] shrink-0">
                        {new Date(dl.completed_at).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
