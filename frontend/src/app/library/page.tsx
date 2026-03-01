"use client";

import { useCallback, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listMedia } from "@/lib/api/media";
import { search } from "@/lib/api/search";
import { useUIStore } from "@/lib/store/uiStore";
import { MediaCard } from "@/components/media/MediaCard";
import { MediaDetail } from "@/components/media/MediaDetail";
import { SearchBar } from "@/components/search/SearchBar";
import { FilterPanel } from "@/components/search/FilterPanel";
import { ViewToggle } from "@/components/media/ViewToggle";
import { Topbar } from "@/components/layout/Topbar";
import { cn, formatBytes } from "@/lib/utils";
import type { MediaItem, SearchParams } from "@/types/api";
import { Film, ImageIcon, Loader2 } from "lucide-react";

export default function LibraryPage() {
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<SearchParams>({});
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<MediaItem | null>(null);
  const { viewMode, thumbnailSize } = useUIStore();

  const LIMIT = 48;

  const params: SearchParams & { page: number; limit: number } = {
    ...filters,
    q: query || undefined,
    page,
    limit: LIMIT,
  };

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["media", params],
    queryFn: () => (query ? search(params) : listMedia(params)),
    placeholderData: (prev) => prev,
  });

  const updateFilters = useCallback((patch: Partial<SearchParams>) => {
    setFilters((f) => ({ ...f, ...patch }));
    setPage(1);
  }, []);

  const gridCols = {
    sm: "grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-7 xl:grid-cols-9",
    md: "grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6",
    lg: "grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4",
  };

  const items = data?.items ?? [];

  return (
    <div className="flex flex-col h-full">
      <Topbar title="Library">
        <div className="flex items-center gap-2 max-w-2xl">
          <SearchBar
            value={query}
            onChange={(v) => { setQuery(v); setPage(1); }}
            className="flex-1"
          />
          <FilterPanel filters={filters} onChange={updateFilters} />
          <ViewToggle />
        </div>
      </Topbar>

      <div className="flex flex-1 min-h-0">
        {/* Media area */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          {/* Stats bar */}
          <div className="flex items-center gap-3 px-5 py-2 border-b border-[var(--color-border)] text-xs text-[var(--color-muted-foreground)]">
            {isLoading ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <>
                <span>{data?.total?.toLocaleString() ?? 0} items</span>
                {isFetching && <Loader2 className="w-3 h-3 animate-spin" />}
              </>
            )}
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto px-5 py-4">
            {isLoading && items.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-64 gap-3 text-[var(--color-muted-foreground)]">
                <Loader2 className="w-8 h-8 animate-spin" />
                <span className="text-sm">Loading…</span>
              </div>
            ) : items.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-64 gap-3 text-[var(--color-muted-foreground)]">
                <ImageIcon className="w-12 h-12 opacity-30" />
                <p className="text-sm">No media found</p>
                {query && (
                  <p className="text-xs opacity-60">Try a different search term</p>
                )}
              </div>
            ) : viewMode === "grid" ? (
              <div className={cn("grid gap-2.5", gridCols[thumbnailSize])}>
                {items.map((item) => (
                  <MediaCard
                    key={item.id}
                    item={item}
                    size={thumbnailSize}
                    selected={selected?.id === item.id}
                    onClick={() => setSelected(selected?.id === item.id ? null : item)}
                  />
                ))}
              </div>
            ) : (
              <div className="space-y-1">
                {items.map((item) => (
                  <MediaListRow
                    key={item.id}
                    item={item}
                    selected={selected?.id === item.id}
                    onClick={() => setSelected(selected?.id === item.id ? null : item)}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Pagination */}
          {data && data.pages > 1 && (
            <div className="flex items-center justify-center gap-2 px-5 py-3 border-t border-[var(--color-border)]">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1.5 text-xs rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-muted)] disabled:opacity-40 transition-colors"
              >
                Previous
              </button>
              <span className="text-xs text-[var(--color-muted-foreground)]">
                {page} / {data.pages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
                disabled={page === data.pages}
                className="px-3 py-1.5 text-xs rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-muted)] disabled:opacity-40 transition-colors"
              >
                Next
              </button>
            </div>
          )}
        </div>

        {/* Detail panel */}
        {selected && (
          <div className="w-80 shrink-0 overflow-hidden">
            <MediaDetail item={selected} onClose={() => setSelected(null)} />
          </div>
        )}
      </div>
    </div>
  );
}

function MediaListRow({
  item,
  selected,
  onClick,
}: {
  item: MediaItem;
  selected: boolean;
  onClick: () => void;
}) {
  const isVideo = item.media_type === "video";
  return (
    <div
      onClick={onClick}
      className={cn(
        "flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer transition-colors",
        selected
          ? "bg-[hsl(217_91%_60%/0.1)] border border-[hsl(217_91%_60%/0.3)]"
          : "hover:bg-[var(--color-muted)] border border-transparent"
      )}
    >
      <div className="w-8 h-8 rounded shrink-0 flex items-center justify-center bg-[var(--color-muted)] text-[var(--color-muted-foreground)]">
        {isVideo ? <Film className="w-4 h-4" /> : <ImageIcon className="w-4 h-4" />}
      </div>
      <span className="flex-1 text-sm text-[var(--color-foreground)] truncate">{item.filename}</span>
      <span className="text-xs text-[var(--color-muted-foreground)] shrink-0">{formatBytes(item.file_size)}</span>
      <span
        className={cn(
          "text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded shrink-0",
          isVideo ? "bg-blue-500/15 text-blue-400" : "bg-emerald-500/15 text-emerald-400"
        )}
      >
        {item.media_type}
      </span>
    </div>
  );
}
