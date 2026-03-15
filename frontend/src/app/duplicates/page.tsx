"use client";

import Image from "next/image";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Copy, Loader2, ScanLine } from "lucide-react";
import { Topbar } from "@/components/layout/Topbar";
import {
  backfillPhash,
  listDuplicateGroups,
  resolveDuplicates,
  type DuplicateGroup,
} from "@/lib/api/duplicates";
import { cn, formatBytes } from "@/lib/utils";
import type { MediaItem } from "@/types/api";

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
            {isKept ? "Kept" : "Keep"}
          </button>
        </div>
      </div>
    </div>
  );
}

function DuplicateGroupCard({ group }: { group: DuplicateGroup }) {
  const qc = useQueryClient();

  const resolve = useMutation({
    mutationFn: (keepId: string) => resolveDuplicates(group.group_id, keepId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["duplicates"] }),
  });

  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-[var(--color-border)]">
        <div className="flex items-center gap-2">
          <Copy className="w-3.5 h-3.5 text-amber-400" />
          <span className="text-xs font-medium text-[var(--color-foreground)]">
            {group.count} duplicates
          </span>
        </div>
        {resolve.isPending && (
          <Loader2 className="w-3.5 h-3.5 animate-spin text-[var(--color-muted-foreground)]" />
        )}
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3 p-3">
        {group.items.map((item) => (
          <DuplicateCard
            key={item.id}
            item={item}
            isKept={false}
            onKeep={() => resolve.mutate(item.id)}
          />
        ))}
      </div>
    </div>
  );
}

export default function DuplicatesPage() {
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["duplicates"],
    queryFn: listDuplicateGroups,
    staleTime: 30_000,
  });

  const backfill = useMutation({
    mutationFn: backfillPhash,
    onSuccess: () => {
      // Refetch after a delay to let tasks process
      setTimeout(() => qc.invalidateQueries({ queryKey: ["duplicates"] }), 10_000);
    },
  });

  const groups = data?.groups ?? [];
  const total = data?.total_groups ?? 0;

  return (
    <div className="flex flex-col h-full">
      <Topbar title="Duplicates">
        <div className="flex items-center gap-2">
          <button
            onClick={() => backfill.mutate()}
            disabled={backfill.isPending}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium bg-[hsl(217_91%_60%)] text-white hover:bg-[hsl(217_91%_55%)] disabled:opacity-50 transition-colors"
          >
            {backfill.isPending ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <ScanLine className="w-3.5 h-3.5" />
            )}
            {backfill.isPending ? "Scanning..." : "Scan Existing Files"}
          </button>
          {backfill.isSuccess && (
            <span className="text-[10px] text-emerald-400">Dispatched! Results will appear shortly.</span>
          )}
        </div>
      </Topbar>

      <div className="flex items-center gap-3 px-5 py-2 border-b border-[var(--color-border)] text-xs text-[var(--color-muted-foreground)] shrink-0">
        {isLoading ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
        ) : (
          <span>
            {total} duplicate group{total !== 1 ? "s" : ""} found
          </span>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-3 md:px-5 py-4 space-y-4">
        {isLoading && groups.length === 0 && (
          <div className="flex flex-col items-center justify-center h-64 gap-3 text-[var(--color-muted-foreground)]">
            <Loader2 className="w-8 h-8 animate-spin" />
            <span className="text-sm">Scanning for duplicates...</span>
          </div>
        )}

        {!isLoading && groups.length === 0 && (
          <div className="flex flex-col items-center justify-center h-64 gap-3 text-[var(--color-muted-foreground)]">
            <CheckCircle2 className="w-12 h-12 opacity-30" />
            <p className="text-sm">No duplicates found</p>
            <p className="text-xs opacity-60">
              Duplicates are detected automatically during scans using perceptual hashing.
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
