"use client";

import Image from "next/image";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Copy,
  HardDrive,
  Loader2,
  ScanLine,
  Trash2,
} from "lucide-react";
import { Topbar } from "@/components/layout/Topbar";
import {
  backfillPhash,
  destroyDuplicates,
  getDedupStats,
  listDuplicateGroups,
  resolveDuplicates,
  type DedupStats,
  type DuplicateGroup,
} from "@/lib/api/duplicates";
import { cn, formatBytes } from "@/lib/utils";
import type { MediaItem } from "@/types/api";

// ── Stats panel ─────────────────────────────────────────────────────────────

function StatsPanel({ stats }: { stats: DedupStats }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 px-3 md:px-5 py-3 border-b border-[var(--color-border)] bg-[var(--color-card)]">
      <div>
        <p className="text-[10px] uppercase tracking-wider text-[var(--color-muted-foreground)]">Scanned</p>
        <p className="text-sm font-semibold text-[var(--color-foreground)]">
          {stats.hashed_items.toLocaleString()} / {stats.total_items.toLocaleString()}
        </p>
      </div>
      <div>
        <p className="text-[10px] uppercase tracking-wider text-[var(--color-muted-foreground)]">Duplicates</p>
        <p className="text-sm font-semibold text-amber-400">
          {stats.duplicate_items} in {stats.duplicate_groups} groups
        </p>
      </div>
      <div>
        <p className="text-[10px] uppercase tracking-wider text-[var(--color-muted-foreground)]">Wasted Space</p>
        <p className="text-sm font-semibold text-red-400">
          {formatBytes(stats.wasted_bytes)}
        </p>
      </div>
      <div>
        <p className="text-[10px] uppercase tracking-wider text-[var(--color-muted-foreground)]">Pending</p>
        <p className="text-sm font-semibold text-[var(--color-foreground)]">
          {stats.pending_items.toLocaleString()} files
        </p>
      </div>
    </div>
  );
}

// ── Progress bar ────────────────────────────────────────────────────────────

function ProgressBar({ stats, scanning }: { stats: DedupStats; scanning: boolean }) {
  if (stats.progress_pct >= 100 && !scanning) return null;

  return (
    <div className="px-3 md:px-5 py-2 border-b border-[var(--color-border)]">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] text-[var(--color-muted-foreground)]">
          {scanning ? "Scanning..." : "Scan progress"}
        </span>
        <span className="text-[10px] font-mono text-[var(--color-muted-foreground)]">
          {stats.progress_pct}%
        </span>
      </div>
      <div className="w-full h-1.5 rounded-full bg-[var(--color-muted)] overflow-hidden">
        <div
          className={cn(
            "h-full rounded-full transition-all duration-500",
            scanning ? "bg-blue-500 animate-pulse" : "bg-emerald-500"
          )}
          style={{ width: `${stats.progress_pct}%` }}
        />
      </div>
    </div>
  );
}

// ── Duplicate card ──────────────────────────────────────────────────────────

function DuplicateCard({
  item,
  isKept,
  onKeep,
}: {
  item: MediaItem;
  isKept: boolean;
  onKeep: () => void;
}) {
  return (
    <div
      className={cn(
        "relative rounded-lg overflow-hidden border transition-all",
        isKept
          ? "border-emerald-500/60 ring-2 ring-emerald-500/20"
          : "border-[var(--color-border)] hover:border-[hsl(217_33%_30%)]"
      )}
    >
      <div className="relative w-full aspect-video bg-[var(--color-muted)]">
        {item.thumbnail_url ? (
          <Image
            src={item.thumbnail_url}
            alt={item.filename}
            fill
            className="object-cover"
            unoptimized
          />
        ) : (
          <div className="flex items-center justify-center h-full text-[var(--color-muted-foreground)] text-xs">
            No thumb
          </div>
        )}
        {isKept && (
          <div className="absolute top-1.5 left-1.5">
            <CheckCircle2 className="w-5 h-5 text-emerald-400 drop-shadow" />
          </div>
        )}
        {item.duration_seconds != null && item.duration_seconds > 0 && (
          <span className="absolute bottom-1 right-1 text-[10px] font-mono bg-black/70 text-white px-1 py-0.5 rounded">
            {Math.floor(item.duration_seconds / 60)}:
            {String(Math.floor(item.duration_seconds % 60)).padStart(2, "0")}
          </span>
        )}
      </div>
      <div className="px-2.5 py-2 space-y-1">
        <p className="text-[11px] text-[var(--color-foreground)] truncate" title={item.filename}>
          {item.filename}
        </p>
        <p className="text-[10px] text-[var(--color-muted-foreground)] truncate" title={item.file_path}>
          {item.file_path}
        </p>
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-[var(--color-muted-foreground)]">
            {item.file_size ? formatBytes(item.file_size) : "—"}
            {item.width && item.height ? ` · ${item.width}×${item.height}` : ""}
          </span>
          <button
            onClick={onKeep}
            className={cn(
              "text-[10px] font-medium px-2 py-0.5 rounded transition-colors",
              isKept
                ? "bg-emerald-500/15 text-emerald-400"
                : "bg-[var(--color-muted)] text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]"
            )}
          >
            {isKept ? "Keeping" : "Keep this"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Duplicate group card ────────────────────────────────────────────────────

function DuplicateGroupCard({ group }: { group: DuplicateGroup }) {
  const qc = useQueryClient();
  const [kept, setKept] = useState<string | null>(null);
  const [confirmDestroy, setConfirmDestroy] = useState(false);

  const dismiss = useMutation({
    mutationFn: (keepId: string) => resolveDuplicates(group.group_id, keepId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["duplicates"] });
      qc.invalidateQueries({ queryKey: ["dedup-stats"] });
    },
  });

  const destroy = useMutation({
    mutationFn: (keepId: string) => destroyDuplicates(group.group_id, keepId),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["duplicates"] });
      qc.invalidateQueries({ queryKey: ["dedup-stats"] });
    },
  });

  const savingsBytes = group.items.reduce((sum, i) => sum + (i.file_size || 0), 0) -
    Math.max(...group.items.map((i) => i.file_size || 0));

  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 border-b border-[var(--color-border)]">
        <div className="flex items-center gap-2">
          <Copy className="w-3.5 h-3.5 text-amber-400" />
          <span className="text-xs font-medium text-[var(--color-foreground)]">
            {group.count} duplicates
          </span>
          <span className="text-[10px] text-[var(--color-muted-foreground)]">
            · {formatBytes(group.total_size)} total
            · ~{formatBytes(savingsBytes)} reclaimable
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          {(dismiss.isPending || destroy.isPending) && (
            <Loader2 className="w-3.5 h-3.5 animate-spin text-[var(--color-muted-foreground)]" />
          )}
          {kept && !confirmDestroy && (
            <>
              <button
                onClick={() => dismiss.mutate(kept)}
                disabled={dismiss.isPending}
                className="text-[10px] font-medium px-2 py-1 rounded bg-[var(--color-muted)] text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] transition-colors"
              >
                Dismiss
              </button>
              <button
                onClick={() => setConfirmDestroy(true)}
                disabled={destroy.isPending}
                className="flex items-center gap-1 text-[10px] font-medium px-2 py-1 rounded bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors"
              >
                <Trash2 className="w-3 h-3" />
                Delete others
              </button>
            </>
          )}
          {kept && confirmDestroy && (
            <div className="flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
              <span className="text-[10px] text-red-400">Delete {group.count - 1} files from disk?</span>
              <button
                onClick={() => { destroy.mutate(kept); setConfirmDestroy(false); }}
                disabled={destroy.isPending}
                className="text-[10px] font-medium px-2 py-1 rounded bg-red-500 text-white hover:bg-red-600 transition-colors"
              >
                Confirm
              </button>
              <button
                onClick={() => setConfirmDestroy(false)}
                className="text-[10px] font-medium px-2 py-1 rounded bg-[var(--color-muted)] text-[var(--color-muted-foreground)] transition-colors"
              >
                Cancel
              </button>
            </div>
          )}
          {destroy.isSuccess && (
            <span className="text-[10px] text-emerald-400">
              Deleted {destroy.data.deleted_files} files ({formatBytes(destroy.data.deleted_bytes)})
            </span>
          )}
        </div>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3 p-3">
        {group.items.map((item) => (
          <DuplicateCard
            key={item.id}
            item={item}
            isKept={kept === item.id}
            onKeep={() => setKept(item.id)}
          />
        ))}
      </div>
    </div>
  );
}

// ── Page ────────────────────────────────────────────────────────────────────

export default function DuplicatesPage() {
  const qc = useQueryClient();

  const { data: stats } = useQuery({
    queryKey: ["dedup-stats"],
    queryFn: getDedupStats,
    refetchInterval: 5_000,
  });

  const { data, isLoading } = useQuery({
    queryKey: ["duplicates"],
    queryFn: listDuplicateGroups,
    refetchInterval: 15_000,
  });

  const backfill = useMutation({
    mutationFn: backfillPhash,
    onSuccess: (data) => {
      // Auto-refresh stats to show progress
      qc.invalidateQueries({ queryKey: ["dedup-stats"] });
    },
  });

  const groups = data?.groups ?? [];
  const total = data?.total_groups ?? 0;
  const scanning = backfill.isPending || (stats != null && stats.pending_items > 0 && stats.progress_pct < 100);

  return (
    <div className="flex flex-col h-full">
      <Topbar title="Duplicates">
        <div className="flex items-center gap-2">
          <button
            onClick={() => backfill.mutate()}
            disabled={backfill.isPending || scanning}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium bg-[hsl(217_91%_60%)] text-white hover:bg-[hsl(217_91%_55%)] disabled:opacity-50 transition-colors"
          >
            {scanning ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <ScanLine className="w-3.5 h-3.5" />
            )}
            {scanning ? "Scanning..." : "Scan for Duplicates"}
          </button>
          {backfill.isSuccess && !scanning && (
            <span className="text-[10px] text-emerald-400">
              Dispatched {backfill.data.pending} items
            </span>
          )}
        </div>
      </Topbar>

      {/* Stats */}
      {stats && <StatsPanel stats={stats} />}

      {/* Progress bar */}
      {stats && <ProgressBar stats={stats} scanning={scanning} />}

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-3 md:px-5 py-4 space-y-4">
        {isLoading && groups.length === 0 && (
          <div className="flex flex-col items-center justify-center h-64 gap-3 text-[var(--color-muted-foreground)]">
            <Loader2 className="w-8 h-8 animate-spin" />
            <span className="text-sm">Loading duplicate groups...</span>
          </div>
        )}

        {!isLoading && groups.length === 0 && (
          <div className="flex flex-col items-center justify-center h-64 gap-3 text-[var(--color-muted-foreground)]">
            <CheckCircle2 className="w-12 h-12 opacity-30" />
            <p className="text-sm">No duplicates found</p>
            <p className="text-xs opacity-60">
              {stats && stats.progress_pct < 100
                ? `Scan in progress (${stats.progress_pct}%). Duplicates will appear as files are processed.`
                : 'Click "Scan for Duplicates" to analyze your library.'}
            </p>
          </div>
        )}

        {groups.map((group) => (
          <DuplicateGroupCard key={group.group_id} group={group} />
        ))}
      </div>
    </div>
  );
}
