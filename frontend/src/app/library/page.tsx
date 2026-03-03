"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useInfiniteQuery } from "@tanstack/react-query";
import { listMedia } from "@/lib/api/media";
import { search } from "@/lib/api/search";
import { useUIStore } from "@/lib/store/uiStore";
import { MediaCard } from "@/components/media/MediaCard";
import { ImageOverlay } from "@/components/media/ImageOverlay";
import { VideoOverlay } from "@/components/media/VideoOverlay";
import { SearchBar } from "@/components/search/SearchBar";
import { FilterPanel } from "@/components/search/FilterPanel";
import { SavedFilters } from "@/components/search/SavedFilters";
import { ViewToggle } from "@/components/media/ViewToggle";
import { Topbar } from "@/components/layout/Topbar";
import { useInfiniteScroll } from "@/hooks/useInfiniteScroll";
import { cn, formatBytes } from "@/lib/utils";
import type { MediaItem, SearchParams } from "@/types/api";
import { Film, ImageIcon, Loader2 } from "lucide-react";

export default function LibraryPage() {
  const searchParamsHook = useSearchParams();
  const router = useRouter();

  // Read params from URL
  const urlFavourite = searchParamsHook.get("favourite") === "true" ? true : undefined;
  const urlType = (searchParamsHook.get("type") ?? undefined) as "image" | "video" | undefined;

  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<SearchParams>({
    favourite: urlFavourite,
    type: urlType,
  });
  const [selected, setSelected] = useState<MediaItem | null>(null);
  const { viewMode, thumbnailSize } = useUIStore();
  const searchInputRef = useRef<HTMLInputElement | null>(null);

  const LIMIT = 48;

  // Sync URL params → filter state when navigating via sidebar links
  useEffect(() => {
    setFilters((f) => ({ ...f, favourite: urlFavourite, type: urlType }));
    setSelected(null);
  }, [urlFavourite, urlType]);

  const queryParams: SearchParams = {
    ...filters,
    q: query || undefined,
    limit: LIMIT,
  };

  const { data, isLoading, isFetchingNextPage, fetchNextPage, hasNextPage } =
    useInfiniteQuery({
      queryKey: ["media", queryParams],
      queryFn: ({ pageParam = 1 }) =>
        query
          ? search({ ...queryParams, page: pageParam })
          : listMedia({ ...queryParams, page: pageParam }),
      getNextPageParam: (last) =>
        last.page < last.pages ? last.page + 1 : undefined,
      initialPageParam: 1,
      placeholderData: (prev) => prev,
    });

  const items = Array.from(
    new Map(data?.pages.flatMap((p) => p.items).map((i) => [i.id, i]) ?? []).values()
  );
  const total = data?.pages[0]?.total ?? 0;
  const isFetching = isFetchingNextPage;

  const updateFilters = useCallback((patch: Partial<SearchParams>) => {
    setFilters((f) => ({ ...f, ...patch }));
  }, []);

  // Infinite scroll sentinel
  const sentinelRef = useInfiniteScroll({
    onLoadMore: fetchNextPage,
    disabled: !hasNextPage || isFetchingNextPage,
  });

  // ── Keyboard shortcuts ─────────────────────────────────────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      const inInput = tag === "INPUT" || tag === "TEXTAREA";

      if (e.key === "/" && !inInput) {
        e.preventDefault();
        searchInputRef.current?.focus();
        return;
      }
      if (inInput) return;

      if (e.key === "Escape") {
        setSelected(null);
        return;
      }
      if (e.key === "v") {
        useUIStore.getState().toggleView();
        return;
      }
      if (e.key === "g") {
        useUIStore.getState().setViewMode("grid");
        return;
      }
      if (e.key === "l") {
        useUIStore.getState().setViewMode("list");
        return;
      }
      if (e.key === "f" && selected) {
        // Toggle favourite on selected item — handled by MediaCard/Detail mutation
        return;
      }
      if (e.key === "ArrowRight" && selected) {
        const idx = items.findIndex((i) => i.id === selected.id);
        const next = items[idx + 1];
        if (next) setSelected(next);
        return;
      }
      if (e.key === "ArrowLeft" && selected) {
        const idx = items.findIndex((i) => i.id === selected.id);
        const prev = items[idx - 1];
        if (prev) setSelected(prev);
        return;
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [items, selected]);

  const gridCols = {
    sm: "grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-7 xl:grid-cols-9",
    md: "grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6",
    lg: "grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4",
  };

  return (
    <div className="flex flex-col h-full">
      <Topbar title={filters.favourite ? "Favourites" : filters.type === "image" ? "Images" : filters.type === "video" ? "Videos" : "Library"}>
        <div className="flex items-center gap-2 max-w-2xl">
          <SearchBar
            value={query}
            onChange={(v) => setQuery(v)}
            className="flex-1"
            inputRef={searchInputRef}
          />
          <FilterPanel filters={filters} onChange={updateFilters} />
          <SavedFilters currentFilters={filters} onApply={(f) => setFilters(f)} />
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
                <span>{total.toLocaleString()} items</span>
                {isFetching && <Loader2 className="w-3 h-3 animate-spin" />}
                {query && (
                  <span className="text-violet-400 text-[10px]">
                    {items.length >= 3 && query.split(" ").length >= 3 ? "· semantic" : "· text"}
                  </span>
                )}
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

            {/* Infinite scroll sentinel */}
            <div ref={sentinelRef} className="h-4" />
            {isFetchingNextPage && (
              <div className="flex justify-center py-4">
                <Loader2 className="w-5 h-5 animate-spin text-[var(--color-muted-foreground)]" />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Image overlay — fixed position, covers full viewport */}
      {selected && selected.media_type === "image" && (
        <ImageOverlay
          item={selected}
          onClose={() => setSelected(null)}
          onSelectItem={setSelected}
        />
      )}

      {/* Video overlay — fixed position, covers full viewport */}
      {selected && selected.media_type === "video" && (
        <VideoOverlay
          item={selected}
          onClose={() => setSelected(null)}
          onSelectItem={setSelected}
        />
      )}
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
      {item.is_favourite && (
        <span className="text-rose-400 shrink-0">♥</span>
      )}
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
