"use client";

import Image from "next/image";
import { ExternalLink, Film, Heart, ImageIcon, Tag, X } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { cn, formatBytes, formatDate, formatDuration } from "@/lib/utils";
import { patchMedia, thumbnailUrl, streamUrl } from "@/lib/api/media";
import type { MediaItem } from "@/types/api";

interface MediaDetailProps {
  item: MediaItem;
  onClose?: () => void;
  onSelectItem?: (item: MediaItem) => void;
}

function MetaRow({ label, value }: { label: string; value?: string | number | null }) {
  if (value == null || value === "") return null;
  return (
    <div className="flex gap-2 py-1.5 border-b border-[var(--color-border)] last:border-0">
      <span className="text-xs text-[var(--color-muted-foreground)] w-28 shrink-0">{label}</span>
      <span className="text-xs text-[var(--color-foreground)] break-all">{String(value)}</span>
    </div>
  );
}

export function MediaDetail({ item, onClose }: MediaDetailProps) {
  const isVideo = item.media_type === "video";
  const queryClient = useQueryClient();

  const toggleFavourite = useMutation({
    mutationFn: () => patchMedia(item.id, { is_favourite: !item.is_favourite }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["media"] }),
  });

  return (
    <div className="flex flex-col h-full bg-[var(--color-card)] border-l border-[var(--color-border)]">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
        <h3 className="text-sm font-semibold text-[var(--color-foreground)] truncate pr-2">
          {item.filename}
        </h3>
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={() => toggleFavourite.mutate()}
            className={cn(
              "p-1.5 rounded transition-colors",
              item.is_favourite
                ? "text-rose-400 hover:text-rose-300"
                : "text-[var(--color-muted-foreground)] hover:text-rose-400"
            )}
            title={item.is_favourite ? "Remove from favourites" : "Add to favourites"}
          >
            <Heart
              className="w-4 h-4"
              fill={item.is_favourite ? "currentColor" : "none"}
            />
          </button>
          <a
            href={streamUrl(item.id)}
            target="_blank"
            rel="noopener noreferrer"
            className="p-1.5 rounded hover:bg-[var(--color-muted)] text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] transition-colors"
            title="Open original"
          >
            <ExternalLink className="w-4 h-4" />
          </a>
          {onClose && (
            <button
              onClick={onClose}
              className="p-1.5 rounded hover:bg-[var(--color-muted)] text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Preview */}
        <div className="relative w-full aspect-video bg-black flex items-center justify-center">
          {item.thumbnail_url ? (
            isVideo ? (
              <video
                src={streamUrl(item.id)}
                poster={thumbnailUrl(item.id)}
                controls
                className="w-full h-full object-contain"
              />
            ) : (
              <Image
                src={thumbnailUrl(item.id)}
                alt={item.filename}
                fill
                className="object-contain"
                unoptimized
              />
            )
          ) : (
            <div className="flex flex-col items-center gap-2 text-[var(--color-muted-foreground)]">
              {isVideo ? <Film className="w-10 h-10" /> : <ImageIcon className="w-10 h-10" />}
              <span className="text-xs">No thumbnail</span>
            </div>
          )}
        </div>

        {/* Tags */}
        {item.tags.length > 0 && (
          <div className="px-4 py-3 border-b border-[var(--color-border)]">
            <div className="flex items-center gap-1.5 mb-2">
              <Tag className="w-3.5 h-3.5 text-[var(--color-muted-foreground)]" />
              <span className="text-xs font-semibold text-[var(--color-muted-foreground)] uppercase tracking-wider">
                Tags
              </span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {item.tags.map((tag) => (
                <span
                  key={tag.id}
                  className="px-2 py-0.5 rounded-full text-xs font-medium bg-[var(--color-muted)] text-[var(--color-foreground)]"
                  style={tag.color ? { backgroundColor: `${tag.color}22`, color: tag.color } : undefined}
                >
                  {tag.name}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Metadata */}
        <div className="px-4 py-3 border-b border-[var(--color-border)]">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-muted-foreground)] mb-2">
            File info
          </p>
          <MetaRow label="Path" value={item.file_path} />
          <MetaRow label="Size" value={formatBytes(item.file_size)} />
          <MetaRow label="Type" value={item.mime_type} />
          <MetaRow label="Status" value={item.index_status} />
          {item.width && item.height && (
            <MetaRow label="Dimensions" value={`${item.width} × ${item.height}`} />
          )}
          {item.duration_seconds && (
            <MetaRow label="Duration" value={formatDuration(item.duration_seconds)} />
          )}
          {item.frame_rate && (
            <MetaRow label="Frame rate" value={`${item.frame_rate} fps`} />
          )}
          {item.bitrate && (
            <MetaRow label="Bitrate" value={`${Math.round(item.bitrate / 1000)} kbps`} />
          )}
          {item.codec && <MetaRow label="Codec" value={item.codec} />}
          <MetaRow label="Indexed" value={formatDate(item.indexed_at)} />
          {item.file_hash && (
            <MetaRow label="Hash (SHA-256)" value={item.file_hash.slice(0, 16) + "…"} />
          )}
          {item.index_error && (
            <div className="mt-2 p-2 rounded-lg bg-red-500/10 border border-red-500/20">
              <p className="text-[11px] text-red-400">{item.index_error}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
