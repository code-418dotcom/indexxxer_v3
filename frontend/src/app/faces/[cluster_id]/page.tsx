"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Users } from "lucide-react";
import { Topbar } from "@/components/layout/Topbar";
import { MediaCard } from "@/components/media/MediaCard";
import { ImageOverlay } from "@/components/media/ImageOverlay";
import { VideoOverlay } from "@/components/media/VideoOverlay";
import { getCluster } from "@/lib/api/faces";
import { getMedia } from "@/lib/api/media";
import type { MediaItem } from "@/types/api";

export default function ClusterDetailPage({
  params,
}: {
  params: Promise<{ cluster_id: string }>;
}) {
  const { cluster_id } = use(params);
  const clusterId = parseInt(cluster_id, 10);

  const [selected, setSelected] = useState<MediaItem | null>(null);

  // Fetch the cluster's media_ids (page 1, up to 200)
  const { data: cluster, isLoading: clusterLoading } = useQuery({
    queryKey: ["face-cluster", clusterId],
    queryFn: () => getCluster(clusterId, 1, 200),
    staleTime: 60_000,
  });

  // Fetch full MediaItem for each id in parallel
  const { data: items = [], isLoading: itemsLoading } = useQuery({
    queryKey: ["face-cluster-items", clusterId, cluster?.media_ids],
    queryFn: async () => {
      if (!cluster?.media_ids?.length) return [];
      return Promise.all(cluster.media_ids.map((id) => getMedia(id)));
    },
    enabled: !!cluster?.media_ids?.length,
    staleTime: 60_000,
  });

  // Keyboard navigation
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") { setSelected(null); return; }
      if (!selected) return;
      if (e.key === "ArrowRight") {
        const idx = items.findIndex((i) => i.id === selected.id);
        const next = items[idx + 1];
        if (next) setSelected(next);
      }
      if (e.key === "ArrowLeft") {
        const idx = items.findIndex((i) => i.id === selected.id);
        const prev = items[idx - 1];
        if (prev) setSelected(prev);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [items, selected]);

  const isLoading = clusterLoading || itemsLoading;

  return (
    <div className="flex flex-col h-full">
      <Topbar
        title={
          <span className="flex items-center gap-2">
            <Link
              href="/faces"
              className="flex items-center gap-1 text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              Faces
            </Link>
            <span className="text-[var(--color-muted-foreground)] opacity-40">/</span>
            <span>Cluster {clusterId}</span>
          </span>
        }
      />

      <div className="flex flex-1 min-h-0">
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          {/* Stats bar */}
          <div className="flex items-center gap-3 px-5 py-2 border-b border-[var(--color-border)] text-xs text-[var(--color-muted-foreground)]">
            {isLoading ? (
              <span>Loading…</span>
            ) : (
              <span>{cluster?.total ?? 0} appearances</span>
            )}
          </div>

          {/* Grid */}
          <div className="flex-1 overflow-y-auto px-5 py-4">
            {isLoading && (
              <div className="flex items-center justify-center h-64 text-[var(--color-muted-foreground)]">
                <span className="text-sm">Loading…</span>
              </div>
            )}

            {!isLoading && items.length === 0 && (
              <div className="flex flex-col items-center justify-center h-64 gap-3 text-[var(--color-muted-foreground)]">
                <Users className="w-12 h-12 opacity-30" />
                <p className="text-sm">No media in this cluster.</p>
              </div>
            )}

            {items.length > 0 && (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-2.5">
                {items.map((item) => (
                  <MediaCard
                    key={item.id}
                    item={item}
                    size="md"
                    selected={selected?.id === item.id}
                    onClick={() => setSelected(selected?.id === item.id ? null : item)}
                  />
                ))}
              </div>
            )}
          </div>
        </div>

      </div>

      {selected && selected.media_type === "image" && (
        <ImageOverlay
          item={selected}
          onClose={() => setSelected(null)}
          onSelectItem={setSelected}
        />
      )}

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
