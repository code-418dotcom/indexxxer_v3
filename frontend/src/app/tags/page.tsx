"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle, CheckCircle2, Film, ImageIcon, Loader2,
  Octagon, Pause, Play, ScanLine, Tag, Trash2, X, XCircle,
} from "lucide-react";
import { Topbar } from "@/components/layout/Topbar";
import {
  listTags, backfillAiTags, pauseTagging, resumeTagging, stopTagging, deleteTag, getTagProgress,
  type TagItem, type TagLogEntry, type BackfillParams,
} from "@/lib/api/tags";
import { cn } from "@/lib/utils";

const CATEGORIES = [
  { value: null, label: "All" },
  { value: "actions", label: "Actions", color: "#e53e3e" },
  { value: "bdsm", label: "BDSM", color: "#9b2c2c" },
  { value: "bodyparts", label: "Body Parts", color: "#3182ce" },
  { value: "positions", label: "Positions", color: "#38a169" },
];

function TagBadge({ tag, onClick, onDelete }: { tag: TagItem; onClick?: () => void; onDelete?: () => void }) {
  return (
    <div
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] hover:border-[hsl(217_33%_30%)] transition-colors group",
        onClick && "cursor-pointer"
      )}
    >
      <span
        className="w-2 h-2 rounded-full shrink-0"
        style={{ backgroundColor: tag.color || "#718096" }}
      />
      <span className="text-xs font-medium text-[var(--color-foreground)]">
        {tag.name}
      </span>
      {tag.category && (
        <span className="text-[10px] text-[var(--color-muted-foreground)]">
          {tag.category}
        </span>
      )}
      {onDelete && (
        <button
          onClick={(e) => { e.stopPropagation(); onDelete(); }}
          className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-red-500/10 text-[var(--color-muted-foreground)] hover:text-red-400 transition-all"
        >
          <X className="w-3 h-3" />
        </button>
      )}
    </div>
  );
}

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "done":
      return <CheckCircle2 className="w-3 h-3 text-emerald-400 shrink-0" />;
    case "error":
      return <XCircle className="w-3 h-3 text-red-400 shrink-0" />;
    case "skipped":
      return <AlertCircle className="w-3 h-3 text-yellow-400 shrink-0" />;
    case "processing":
      return <Loader2 className="w-3 h-3 text-blue-400 animate-spin shrink-0" />;
    default:
      return null;
  }
}

function LogPanel({ entries }: { entries: TagLogEntry[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const prevCountRef = useRef(entries.length);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || entries.length <= prevCountRef.current) {
      prevCountRef.current = entries.length;
      return;
    }
    prevCountRef.current = entries.length;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
    if (atBottom) {
      el.scrollTop = el.scrollHeight;
    }
  }, [entries.length]);

  if (entries.length === 0) return null;

  return (
    <div
      ref={containerRef}
      className="border border-[var(--color-border)] rounded-lg bg-black/30 max-h-52 overflow-y-auto font-mono text-[11px]"
    >
      <div className="p-2 space-y-0.5">
        {entries.map((entry, i) => {
          const time = new Date(parseInt(entry.ts)).toLocaleTimeString();
          return (
            <div key={`${entry.ts}-${i}`} className="flex items-start gap-2">
              <span className="text-[var(--color-muted-foreground)] shrink-0 w-16">{time}</span>
              <StatusIcon status={entry.status} />
              <span className="text-[var(--color-foreground)] truncate">{entry.filename}</span>
              {entry.status === "done" && entry.tags_applied > 0 && (
                <span className="text-emerald-400 shrink-0">+{entry.tags_applied}</span>
              )}
              {entry.detail && (
                <span className="text-[var(--color-muted-foreground)] truncate">{entry.detail}</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function TagButton({
  onClick,
  disabled,
  active,
  children,
  variant = "default",
}: {
  onClick: () => void;
  disabled?: boolean;
  active?: boolean;
  children: React.ReactNode;
  variant?: "default" | "danger";
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors disabled:opacity-50",
        variant === "danger"
          ? "bg-red-600/80 text-white hover:bg-red-600"
          : active
            ? "bg-[hsl(217_91%_60%)] text-white"
            : "bg-[var(--color-muted)] text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] hover:bg-[var(--color-muted)]/80"
      )}
    >
      {children}
    </button>
  );
}

export default function TagsPage() {
  const qc = useQueryClient();
  const router = useRouter();
  const [filterCategory, setFilterCategory] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [showLog, setShowLog] = useState(false);
  const [pollFast, setPollFast] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["tags", { page, category: filterCategory, }],
    queryFn: () => listTags({ page, limit: 100, category: filterCategory || undefined }),
    staleTime: 15_000,
  });

  const { data: progress } = useQuery({
    queryKey: ["tag-progress"],
    queryFn: getTagProgress,
    refetchInterval: pollFast ? 2_000 : 10_000,
    staleTime: 1_000,
  });

  const isActive = (progress?.queue_depth ?? 0) > 0;
  const isPaused = progress?.paused ?? false;

  useEffect(() => {
    setPollFast(showLog || isActive);
  }, [showLog, isActive]);

  useEffect(() => {
    if (isActive) setShowLog(true);
  }, [isActive]);

  const startTag = useMutation({
    mutationFn: (params?: BackfillParams) => backfillAiTags(params),
    onSuccess: () => {
      setShowLog(true);
      qc.invalidateQueries({ queryKey: ["tag-progress"] });
      setTimeout(() => qc.invalidateQueries({ queryKey: ["tags"] }), 10_000);
    },
  });

  const pause = useMutation({
    mutationFn: pauseTagging,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tag-progress"] }),
  });

  const resume = useMutation({
    mutationFn: resumeTagging,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tag-progress"] }),
  });

  const stop = useMutation({
    mutationFn: stopTagging,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tag-progress"] });
    },
  });

  const removeMutation = useMutation({
    mutationFn: deleteTag,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tags"] }),
  });

  const tags = data?.items ?? [];
  const total = data?.total ?? 0;
  const pages = data?.pages ?? 1;
  const anyMutating = startTag.isPending || stop.isPending || pause.isPending || resume.isPending;

  return (
    <div className="flex flex-col h-full">
      <Topbar title="Tags" />

      {/* Controls bar */}
      <div className="flex flex-wrap items-center gap-2 px-3 md:px-5 py-2.5 border-b border-[var(--color-border)] shrink-0">
        {/* Tag all */}
        <TagButton
          onClick={() => startTag.mutate({})}
          disabled={anyMutating || isActive}
          active={isActive}
        >
          {isActive ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <ScanLine className="w-3.5 h-3.5" />
          )}
          Tag All
        </TagButton>

        {/* By media type */}
        <TagButton
          onClick={() => startTag.mutate({ media_type: "image" })}
          disabled={anyMutating || isActive}
        >
          <ImageIcon className="w-3.5 h-3.5" />
          Images
        </TagButton>

        <TagButton
          onClick={() => startTag.mutate({ media_type: "video" })}
          disabled={anyMutating || isActive}
        >
          <Film className="w-3.5 h-3.5" />
          Videos
        </TagButton>

        {/* Separator */}
        <div className="w-px h-5 bg-[var(--color-border)]" />

        {/* By category */}
        {CATEGORIES.filter((c) => c.value).map((cat) => (
          <TagButton
            key={cat.value}
            onClick={() => startTag.mutate({ category: cat.value! })}
            disabled={anyMutating || isActive}
          >
            <span
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: cat.color }}
            />
            {cat.label}
          </TagButton>
        ))}

        {/* Separator */}
        <div className="w-px h-5 bg-[var(--color-border)]" />

        {/* Pause / Resume */}
        {isPaused ? (
          <TagButton
            onClick={() => resume.mutate()}
            disabled={!isActive || anyMutating}
          >
            <Play className="w-3.5 h-3.5" />
            Resume
          </TagButton>
        ) : (
          <TagButton
            onClick={() => pause.mutate()}
            disabled={!isActive || anyMutating}
          >
            <Pause className="w-3.5 h-3.5" />
            Pause
          </TagButton>
        )}

        {/* Stop */}
        <TagButton
          onClick={() => stop.mutate()}
          disabled={!isActive || stop.isPending}
          variant="danger"
        >
          <Octagon className="w-3.5 h-3.5" />
          Stop
        </TagButton>
      </div>

      {/* Progress section */}
      {progress && progress.total > 0 && (
        <div className="px-3 md:px-5 py-3 border-b border-[var(--color-border)] space-y-2">
          {/* Progress bar */}
          <div className="flex items-center gap-3">
            <div className="flex-1 h-2 rounded-full bg-[var(--color-muted)] overflow-hidden">
              <div
                className={cn(
                  "h-full rounded-full transition-all duration-500",
                  isPaused ? "bg-amber-500" : isActive ? "bg-blue-500" : "bg-emerald-500"
                )}
                style={{ width: `${progress.progress_pct}%` }}
              />
            </div>
            <span className="text-xs text-[var(--color-muted-foreground)] shrink-0 w-24 text-right">
              {progress.tagged.toLocaleString()} / {progress.total.toLocaleString()}
            </span>
            <span className="text-xs font-medium text-[var(--color-foreground)] shrink-0 w-12 text-right">
              {progress.progress_pct}%
            </span>
          </div>

          {/* Stats row */}
          <div className="flex items-center gap-4 text-[11px] text-[var(--color-muted-foreground)]">
            <span>
              <span className="text-emerald-400">{progress.tagged.toLocaleString()}</span> tagged
            </span>
            <span>
              <span className="text-[var(--color-foreground)]">{progress.pending.toLocaleString()}</span> pending
            </span>
            {isActive && !isPaused && (
              <span>
                <span className="text-blue-400">{progress.queue_depth}</span> in queue
              </span>
            )}
            {isPaused && (
              <span className="text-amber-400 font-medium">Paused</span>
            )}
            <button
              onClick={() => setShowLog(!showLog)}
              className="ml-auto text-[10px] text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] transition-colors"
            >
              {showLog ? "Hide log" : "Show log"}
            </button>
          </div>

          {showLog && <LogPanel entries={progress.log} />}
        </div>
      )}

      {/* Category filter tabs */}
      <div className="flex flex-wrap items-center gap-2 px-3 md:px-5 py-2.5 border-b border-[var(--color-border)] shrink-0">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.label}
            onClick={() => { setFilterCategory(cat.value); setPage(1); }}
            className={cn(
              "px-2.5 py-1 rounded-md text-xs font-medium transition-colors",
              filterCategory === cat.value
                ? "bg-[var(--color-foreground)] text-[var(--color-background)]"
                : "bg-[var(--color-muted)] text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]"
            )}
          >
            {cat.color && (
              <span
                className="inline-block w-1.5 h-1.5 rounded-full mr-1.5"
                style={{ backgroundColor: cat.color }}
              />
            )}
            {cat.label}
          </button>
        ))}
        <div className="ml-auto text-xs text-[var(--color-muted-foreground)]">
          {total} tag{total !== 1 ? "s" : ""}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-3 md:px-5 py-4">
        {isLoading && tags.length === 0 && (
          <div className="flex flex-col items-center justify-center h-64 gap-3 text-[var(--color-muted-foreground)]">
            <Loader2 className="w-8 h-8 animate-spin" />
            <span className="text-sm">Loading tags...</span>
          </div>
        )}

        {!isLoading && tags.length === 0 && (
          <div className="flex flex-col items-center justify-center h-64 gap-3 text-[var(--color-muted-foreground)]">
            <Tag className="w-12 h-12 opacity-30" />
            <p className="text-sm">No tags found</p>
            <p className="text-xs opacity-60">
              Tags are created automatically when the AI tagger processes your media.
            </p>
          </div>
        )}

        {tags.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {tags.map((tag) => (
              <TagBadge
                key={tag.id}
                tag={tag}
                onClick={() => router.push(`/library?tag_ids=${tag.id}`)}
                onDelete={() => {
                  if (confirm(`Delete tag "${tag.name}"?`)) {
                    removeMutation.mutate(tag.id);
                  }
                }}
              />
            ))}
          </div>
        )}

        {pages > 1 && (
          <div className="flex items-center justify-center gap-2 mt-6">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-3 py-1 rounded text-xs border border-[var(--color-border)] hover:bg-[var(--color-muted)] disabled:opacity-30 transition-colors"
            >
              Prev
            </button>
            <span className="text-xs text-[var(--color-muted-foreground)]">
              Page {page} of {pages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(pages, p + 1))}
              disabled={page >= pages}
              className="px-3 py-1 rounded text-xs border border-[var(--color-border)] hover:bg-[var(--color-muted)] disabled:opacity-30 transition-colors"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
