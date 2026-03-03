"use client";

import Image from "next/image";
import { Film, Heart, ImageIcon, User } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { cn, formatBytes, formatDuration } from "@/lib/utils";
import { thumbnailUrl, patchMedia } from "@/lib/api/media";
import type { MediaItem } from "@/types/api";

interface MediaCardProps {
  item: MediaItem;
  size: "sm" | "md" | "lg";
  selected?: boolean;
  onClick?: () => void;
  onSelect?: () => void;
}

const SIZE_CLASS = {
  sm: "h-32",
  md: "h-44",
  lg: "h-60",
};

export function MediaCard({ item, size, selected, onClick, onSelect }: MediaCardProps) {
  const isVideo = item.media_type === "video";
  const hasThumbnail = !!item.thumbnail_url;
  const queryClient = useQueryClient();

  const toggleFavourite = useMutation({
    mutationFn: () => patchMedia(item.id, { is_favourite: !item.is_favourite }),
    onSuccess: () => {
      // Invalidate all media/search queries so lists refresh
      queryClient.invalidateQueries({ queryKey: ["media"] });
    },
  });

  return (
    <div
      className={cn(
        "group relative rounded-xl overflow-hidden cursor-pointer",
        "bg-[var(--color-card)] border transition-all duration-150",
        selected
          ? "border-[hsl(217_91%_60%)] ring-2 ring-[hsl(217_91%_60%/0.3)]"
          : "border-[var(--color-border)] hover:border-[hsl(217_33%_30%)]",
        "hover:shadow-lg hover:shadow-black/20"
      )}
      onClick={onClick}
    >
      {/* Thumbnail */}
      <div className={cn("relative w-full overflow-hidden bg-[var(--color-muted)]", SIZE_CLASS[size])}>
        {hasThumbnail ? (
          <Image
            src={thumbnailUrl(item.id)}
            alt={item.filename}
            fill
            className="object-cover transition-transform duration-300 group-hover:scale-105"
            sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 20vw"
            unoptimized
          />
        ) : (
          <div className="flex items-center justify-center h-full">
            {isVideo ? (
              <Film className="w-8 h-8 text-[var(--color-muted-foreground)]" />
            ) : (
              <ImageIcon className="w-8 h-8 text-[var(--color-muted-foreground)]" />
            )}
          </div>
        )}

        {/* Video duration badge */}
        {isVideo && item.duration_seconds && (
          <span className="absolute bottom-1.5 right-1.5 text-[10px] font-medium bg-black/70 text-white px-1.5 py-0.5 rounded">
            {formatDuration(item.duration_seconds)}
          </span>
        )}

        {/* Type badge */}
        <span
          className={cn(
            "absolute top-1.5 left-1.5 text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase tracking-wider",
            isVideo
              ? "bg-blue-600/80 text-blue-100"
              : "bg-emerald-600/80 text-emerald-100"
          )}
        >
          {item.media_type}
        </span>

        {/* Face count badge */}
        {item.face_count > 0 && (
          <span className="absolute bottom-1.5 left-7 flex items-center gap-0.5 text-[10px] font-medium bg-black/70 text-white px-1.5 py-0.5 rounded">
            <User className="w-2.5 h-2.5" />
            {item.face_count}
          </span>
        )}

        {/* Favourite heart */}
        <button
          className={cn(
            "absolute bottom-1.5 left-1.5 p-1 rounded-full transition-all",
            item.is_favourite
              ? "opacity-100 text-rose-400"
              : "opacity-0 group-hover:opacity-100 text-white/70 hover:text-rose-400"
          )}
          onClick={(e) => {
            e.stopPropagation();
            toggleFavourite.mutate();
          }}
          title={item.is_favourite ? "Remove from favourites" : "Add to favourites"}
        >
          <Heart
            className="w-3.5 h-3.5"
            fill={item.is_favourite ? "currentColor" : "none"}
          />
        </button>

        {/* Select checkbox overlay */}
        <div
          className="absolute top-1.5 right-1.5 opacity-0 group-hover:opacity-100 transition-opacity"
          onClick={(e) => { e.stopPropagation(); onSelect?.(); }}
        >
          <div
            className={cn(
              "w-5 h-5 rounded border-2 flex items-center justify-center transition-colors",
              selected
                ? "bg-[hsl(217_91%_60%)] border-[hsl(217_91%_60%)]"
                : "bg-black/40 border-white/60 hover:border-white"
            )}
          >
            {selected && (
              <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            )}
          </div>
        </div>
      </div>

      {/* Meta */}
      <div className="px-2.5 py-2">
        <p className="text-xs font-medium text-[var(--color-foreground)] truncate leading-tight">
          {item.filename}
        </p>
        <p className="text-[10px] text-[var(--color-muted-foreground)] mt-0.5">
          {formatBytes(item.file_size)}
          {item.width && item.height && ` · ${item.width}×${item.height}`}
        </p>
      </div>
    </div>
  );
}
