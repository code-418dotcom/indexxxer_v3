"use client";

import Image from "next/image";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, Loader2, RefreshCw } from "lucide-react";
import { Topbar } from "@/components/layout/Topbar";
import { galleryCoverUrl, listGalleries, triggerGalleryScan } from "@/lib/api/galleries";
import type { Gallery } from "@/types/api";
import { formatBytes } from "@/lib/utils";

function GalleryCard({ gallery }: { gallery: Gallery }) {
  const cover = gallery.cover_url ? galleryCoverUrl(gallery.id) : null;

  return (
    <Link
      href={`/galleries/${gallery.id}`}
      className="group relative rounded-xl overflow-hidden border border-[var(--color-border)] bg-[var(--color-card)] hover:border-[hsl(217_33%_30%)] hover:shadow-lg hover:shadow-black/20 transition-all duration-150 cursor-pointer"
    >
      <div className="relative w-full aspect-square bg-[var(--color-muted)]">
        {cover ? (
          <Image
            src={cover}
            alt={gallery.filename}
            fill
            className="object-cover transition-transform duration-300 group-hover:scale-105"
            unoptimized
          />
        ) : (
          <div className="flex items-center justify-center h-full">
            <Archive className="w-10 h-10 text-[var(--color-muted-foreground)]" />
          </div>
        )}
        <span className="absolute bottom-1.5 right-1.5 text-[10px] font-semibold bg-black/70 text-white px-1.5 py-0.5 rounded">
          {gallery.image_count} images
        </span>
      </div>
      <div className="px-2.5 py-2">
        <p className="text-xs font-medium text-[var(--color-foreground)] truncate" title={gallery.filename}>
          {gallery.filename}
        </p>
        <p className="text-[10px] text-[var(--color-muted-foreground)] mt-0.5">
          {gallery.file_size ? formatBytes(gallery.file_size) : "—"}
        </p>
      </div>
    </Link>
  );
}

export default function GalleriesPage() {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["galleries"],
    queryFn: () => listGalleries(1, 200),
    staleTime: 60_000,
  });

  const scan = useMutation({
    mutationFn: triggerGalleryScan,
    onSuccess: () => {
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ["galleries"] }), 3000);
    },
  });

  const galleries = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="flex flex-col h-full">
      <Topbar title="Galleries">
        <div className="flex items-center gap-2">
          <button
            onClick={() => scan.mutate()}
            disabled={scan.isPending}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium border border-[var(--color-border)] hover:border-[hsl(217_33%_30%)] hover:bg-[var(--color-muted)] disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            title="Scan all local sources for ZIP galleries"
          >
            <RefreshCw className={`w-3 h-3 ${scan.isPending ? "animate-spin" : ""}`} />
            {scan.isPending ? "Scanning…" : "Scan for Galleries"}
          </button>
          {scan.isSuccess && (
            <span className="text-xs text-emerald-400">Scan queued</span>
          )}
        </div>
      </Topbar>

      {/* Stats bar */}
      <div className="flex items-center gap-3 px-5 py-2 border-b border-[var(--color-border)] text-xs text-[var(--color-muted-foreground)]">
        {isLoading ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
        ) : (
          <span>{total.toLocaleString()} galleries</span>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4">
        {isLoading && (
          <div className="flex flex-col items-center justify-center h-64 gap-3 text-[var(--color-muted-foreground)]">
            <Loader2 className="w-8 h-8 animate-spin" />
            <span className="text-sm">Loading…</span>
          </div>
        )}

        {!isLoading && galleries.length === 0 && (
          <div className="flex flex-col items-center justify-center h-64 gap-3 text-[var(--color-muted-foreground)]">
            <Archive className="w-12 h-12 opacity-30" />
            <p className="text-sm">No galleries indexed yet.</p>
            <p className="text-xs opacity-70 text-center max-w-xs">
              Click "Scan for Galleries" to index ZIP files from your media sources.
            </p>
          </div>
        )}

        {galleries.length > 0 && (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
            {galleries.map((g) => (
              <GalleryCard key={g.id} gallery={g} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
