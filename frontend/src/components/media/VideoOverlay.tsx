"use client";

import Image from "next/image";
import { ExternalLink, Film, Heart, ImageIcon, Mic, Sparkles, Tag, X } from "lucide-react";
import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { cn, formatBytes, formatDate, formatDuration } from "@/lib/utils";
import { getSimilar, patchMedia, thumbnailUrl, streamUrl } from "@/lib/api/media";
import type { MediaItem } from "@/types/api";

interface VideoOverlayProps {
  item: MediaItem;
  onClose: () => void;
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

export function VideoOverlay({ item, onClose, onSelectItem }: VideoOverlayProps) {
  const queryClient = useQueryClient();

  // Esc to close
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  // Lock body scroll while open
  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = ""; };
  }, []);

  const toggleFavourite = useMutation({
    mutationFn: () => patchMedia(item.id, { is_favourite: !item.is_favourite }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["media"] }),
  });

  const { data: similar } = useQuery({
    queryKey: ["similar", item.id],
    queryFn: () => getSimilar(item.id, 12),
    enabled: item.clip_status === "done",
    staleTime: 5 * 60 * 1000,
  });

  return (
    // Backdrop — click outside to close
    <div
      className="fixed inset-0 z-50 bg-black/90 overflow-y-auto"
      onClick={onClose}
    >
      {/* Content — stop propagation so clicks inside don't dismiss */}
      <div
        className="relative w-full max-w-5xl mx-auto px-4 pt-6 pb-12 flex flex-col gap-4"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header row */}
        <div className="flex items-center gap-3">
          <h2 className="flex-1 text-sm font-semibold text-white truncate min-w-0">
            {item.filename}
          </h2>
          <div className="flex items-center gap-1 shrink-0">
            <button
              onClick={() => toggleFavourite.mutate()}
              className={cn(
                "p-2 rounded-lg transition-colors",
                item.is_favourite
                  ? "text-rose-400 hover:text-rose-300"
                  : "text-white/50 hover:text-rose-400"
              )}
              title={item.is_favourite ? "Remove from favourites" : "Add to favourites"}
            >
              <Heart className="w-4 h-4" fill={item.is_favourite ? "currentColor" : "none"} />
            </button>
            <a
              href={streamUrl(item.id)}
              target="_blank"
              rel="noopener noreferrer"
              className="p-2 rounded-lg text-white/50 hover:text-white transition-colors"
              title="Open original file"
            >
              <ExternalLink className="w-4 h-4" />
            </a>
            <button
              onClick={onClose}
              className="p-2 rounded-lg text-white/50 hover:text-white transition-colors"
              title="Close (Esc)"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Video player */}
        <div className="w-full bg-black rounded-xl overflow-hidden ring-1 ring-white/10">
          {item.thumbnail_url ? (
            <video
              key={item.id}
              src={streamUrl(item.id)}
              poster={thumbnailUrl(item.id)}
              controls
              autoPlay
              className="w-full max-h-[70vh] object-contain"
            />
          ) : (
            <div className="flex items-center justify-center h-64 text-white/30">
              <Film className="w-12 h-12" />
            </div>
          )}
        </div>

        {/* Info panel */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Left: File info + AI */}
          <div className="flex flex-col gap-4">
            {/* File info */}
            <div className="bg-[var(--color-card)] rounded-xl border border-[var(--color-border)] px-4 py-3">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-muted-foreground)] mb-2">
                File info
              </p>
              <MetaRow label="Path" value={item.file_path} />
              <MetaRow label="Size" value={formatBytes(item.file_size)} />
              <MetaRow label="Type" value={item.mime_type} />
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
                <MetaRow label="Hash" value={item.file_hash.slice(0, 16) + "…"} />
              )}
              {item.index_error && (
                <div className="mt-2 p-2 rounded-lg bg-red-500/10 border border-red-500/20">
                  <p className="text-[11px] text-red-400">{item.index_error}</p>
                </div>
              )}
            </div>

            {/* Tags */}
            {item.tags.length > 0 && (
              <div className="bg-[var(--color-card)] rounded-xl border border-[var(--color-border)] px-4 py-3">
                <div className="flex items-center gap-1.5 mb-2">
                  <Tag className="w-3.5 h-3.5 text-[var(--color-muted-foreground)]" />
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-muted-foreground)]">
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

            {/* AI: Caption */}
            {item.caption_status === "done" && item.caption && (
              <div className="bg-[var(--color-card)] rounded-xl border border-[var(--color-border)] px-4 py-3">
                <div className="flex items-center gap-1.5 mb-2">
                  <Sparkles className="w-3.5 h-3.5 text-[var(--color-muted-foreground)]" />
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-muted-foreground)]">
                    Caption
                  </span>
                  <span className="ml-auto text-[10px] text-[var(--color-muted-foreground)] bg-[var(--color-muted)] px-1.5 py-0.5 rounded">
                    BLIP-2
                  </span>
                </div>
                <p className="text-xs text-[var(--color-foreground)] italic leading-relaxed">
                  {item.caption}
                </p>
              </div>
            )}

            {/* AI: Transcript */}
            {item.transcript_status === "done" && item.transcript && (
              <div className="bg-[var(--color-card)] rounded-xl border border-[var(--color-border)] px-4 py-3">
                <div className="flex items-center gap-1.5 mb-2">
                  <Mic className="w-3.5 h-3.5 text-[var(--color-muted-foreground)]" />
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-muted-foreground)]">
                    Transcript
                  </span>
                  <span className="ml-auto text-[10px] text-[var(--color-muted-foreground)] bg-[var(--color-muted)] px-1.5 py-0.5 rounded">
                    Whisper
                  </span>
                </div>
                <pre className="text-xs text-[var(--color-foreground)] whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto font-sans">
                  {item.transcript}
                </pre>
              </div>
            )}

            {/* AI: Summary */}
            {item.summary_status === "done" && item.summary && (
              <div className="bg-[var(--color-card)] rounded-xl border border-[var(--color-border)] px-4 py-3">
                <div className="flex items-center gap-1.5 mb-2">
                  <Sparkles className="w-3.5 h-3.5 text-[var(--color-muted-foreground)]" />
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-muted-foreground)]">
                    Summary
                  </span>
                  <span className="ml-auto text-[10px] text-[var(--color-muted-foreground)] bg-[var(--color-muted)] px-1.5 py-0.5 rounded">
                    Ollama
                  </span>
                </div>
                <p className="text-xs text-[var(--color-foreground)] leading-relaxed">
                  {item.summary}
                </p>
              </div>
            )}
          </div>

          {/* Right: Similar items */}
          {similar && similar.length > 0 && (
            <div className="bg-[var(--color-card)] rounded-xl border border-[var(--color-border)] px-4 py-3 self-start">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-muted-foreground)] mb-3">
                Similar
              </p>
              <div className="grid grid-cols-3 gap-2">
                {similar.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => onSelectItem?.(s)}
                    className="relative aspect-video rounded-lg overflow-hidden bg-[var(--color-muted)] hover:ring-2 hover:ring-[hsl(217_91%_60%)] transition-all group"
                    title={s.filename}
                  >
                    {s.thumbnail_url ? (
                      <Image
                        src={thumbnailUrl(s.id)}
                        alt={s.filename}
                        fill
                        className="object-cover transition-transform duration-200 group-hover:scale-105"
                        unoptimized
                      />
                    ) : (
                      <div className="flex items-center justify-center h-full text-[var(--color-muted-foreground)]">
                        {s.media_type === "video" ? (
                          <Film className="w-5 h-5" />
                        ) : (
                          <ImageIcon className="w-5 h-5" />
                        )}
                      </div>
                    )}
                    <span className="absolute inset-x-0 bottom-0 px-1.5 py-1 bg-gradient-to-t from-black/80 text-[9px] text-white truncate opacity-0 group-hover:opacity-100 transition-opacity">
                      {s.filename}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
