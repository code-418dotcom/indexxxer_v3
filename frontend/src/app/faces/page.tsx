"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pause, Play, RefreshCw, ScanSearch, Trash2, Users, X } from "lucide-react";
import { Topbar } from "@/components/layout/Topbar";
import {
  cancelFaceTask,
  getFaceStats,
  getFaceTaskStatus,
  listClusters,
  triggerBackfill,
  triggerClustering,
  type TaskStatus,
} from "@/lib/api/faces";
import {
  flushQueue,
  getQueueStatus,
  pauseQueue,
  resumeQueue,
} from "@/lib/api/workers";
import { thumbnailUrl } from "@/lib/api/media";
import type { FaceCluster } from "@/types/api";

// ── Task status badge ─────────────────────────────────────────────────────────

function TaskStatusBadge({
  status,
  type,
}: {
  status: TaskStatus | undefined;
  type: "cluster" | "backfill";
}) {
  if (!status) return null;

  if (status.state === "PENDING") {
    return (
      <span className="flex items-center gap-1 text-xs text-[var(--color-muted-foreground)]">
        <RefreshCw className="w-3 h-3 animate-spin" />
        Queued…
      </span>
    );
  }
  if (status.state === "STARTED" || status.state === "RETRY") {
    return (
      <span className="flex items-center gap-1 text-xs text-blue-400">
        <RefreshCw className="w-3 h-3 animate-spin" />
        {type === "cluster" ? "Clustering…" : "Dispatching…"}
      </span>
    );
  }
  if (status.state === "SUCCESS" && status.result != null) {
    if (type === "cluster") {
      const n = status.result.assigned ?? 0;
      return (
        <span className="text-xs text-emerald-400">
          ✓ {n} face{n !== 1 ? "s" : ""} assigned to clusters
        </span>
      );
    }
    const parts = [
      (status.result.faces ?? 0) > 0 && `${status.result.faces} face`,
      (status.result.captions ?? 0) > 0 && `${status.result.captions} caption`,
      (status.result.transcripts ?? 0) > 0 && `${status.result.transcripts} transcript`,
    ].filter(Boolean);
    return (
      <span className="text-xs text-emerald-400">
        ✓ {parts.length > 0 ? `${parts.join(", ")} tasks dispatched` : "Nothing pending"}
      </span>
    );
  }
  if (status.state === "FAILURE") {
    return <span className="text-xs text-red-400">✗ Task failed</span>;
  }
  return null;
}

// ── Queue status bar ──────────────────────────────────────────────────────────

const QUEUE_LABELS: Record<string, string> = {
  ml: "GPU",
  ai: "AI",
  indexing: "Indexing",
  thumbnails: "Thumbs",
  hashing: "Hashing",
};

function QueueStatusBar() {
  const queryClient = useQueryClient();
  // Track per-queue paused state (client-side; reflects last action)
  const [paused, setPaused] = useState<Record<string, boolean>>({});
  // Flush confirm: stores queue name that's pending confirmation
  const [flushConfirm, setFlushConfirm] = useState<string | null>(null);

  const { data: queueData } = useQuery({
    queryKey: ["worker-queues"],
    queryFn: getQueueStatus,
    refetchInterval: 5000,
    staleTime: 3000,
  });

  // Derive paused state from active_queues info returned by inspect
  useEffect(() => {
    if (!queueData) return;
    const consuming = new Set(queueData.workers.flatMap((w) => w.queues));
    const next: Record<string, boolean> = {};
    for (const q of Object.keys(queueData.depths)) {
      // A queue is paused if NO online worker is consuming it
      // (but only meaningful if there's at least one worker online)
      if (queueData.workers.length > 0) {
        next[q] = !consuming.has(q);
      }
    }
    setPaused((prev) => ({ ...prev, ...next }));
  }, [queueData]);

  const togglePause = useMutation({
    mutationFn: async (queue: string) => {
      if (paused[queue]) {
        await resumeQueue(queue);
        setPaused((p) => ({ ...p, [queue]: false }));
      } else {
        await pauseQueue(queue);
        setPaused((p) => ({ ...p, [queue]: true }));
      }
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["worker-queues"] }),
  });

  const doFlush = useMutation({
    mutationFn: (queue: string) => flushQueue(queue),
    onSuccess: () => {
      setFlushConfirm(null);
      queryClient.invalidateQueries({ queryKey: ["worker-queues"] });
    },
  });

  // Clear flush confirm if user clicks away (after 4 s)
  useEffect(() => {
    if (!flushConfirm) return;
    const t = setTimeout(() => setFlushConfirm(null), 4000);
    return () => clearTimeout(t);
  }, [flushConfirm]);

  const depths = queueData?.depths ?? {};
  const workers = queueData?.workers ?? [];
  const activeQueues = Object.entries(depths).filter(
    ([q, n]) => n > 0 || q === "ml" || q === "ai"
  );

  return (
    <div className="flex items-center justify-between px-4 py-1.5 border-b border-[var(--color-border)] bg-[var(--color-card)]/60 shrink-0 gap-4">
      {/* Left: queue depths */}
      <div className="flex items-center gap-3 text-xs min-w-0">
        <span className="text-[var(--color-muted-foreground)] opacity-60 shrink-0">Queues</span>
        {activeQueues.map(([q, n]) => (
          <span key={q} className="flex items-center gap-1 shrink-0">
            <span className="text-[var(--color-muted-foreground)]">{QUEUE_LABELS[q] ?? q}</span>
            <span
              className={
                n > 0
                  ? "font-mono font-semibold text-amber-400"
                  : "font-mono text-[var(--color-muted-foreground)] opacity-40"
              }
            >
              {n.toLocaleString()}
            </span>
          </span>
        ))}
        {workers.length > 0 && (
          <>
            <span className="opacity-20">|</span>
            <span className="text-[var(--color-muted-foreground)] opacity-60">
              {workers.length} worker{workers.length !== 1 ? "s" : ""} online
            </span>
          </>
        )}
        {workers.length === 0 && queueData && (
          <>
            <span className="opacity-20">|</span>
            <span className="text-[var(--color-muted-foreground)] opacity-50">no workers</span>
          </>
        )}
      </div>

      {/* Right: controls for ml queue */}
      <div className="flex items-center gap-2 shrink-0">
        {/* Pause / Resume ML */}
        <button
          onClick={() => togglePause.mutate("ml")}
          disabled={togglePause.isPending}
          className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium border border-[var(--color-border)] hover:border-[hsl(217_33%_30%)] hover:bg-[var(--color-muted)] disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          title={paused["ml"] ? "Resume GPU queue" : "Pause GPU queue"}
        >
          {paused["ml"] ? (
            <><Play className="w-2.5 h-2.5" /> Resume GPU</>
          ) : (
            <><Pause className="w-2.5 h-2.5" /> Pause GPU</>
          )}
        </button>

        {/* Flush ML — two-click confirm */}
        {flushConfirm === "ml" ? (
          <button
            onClick={() => doFlush.mutate("ml")}
            disabled={doFlush.isPending}
            className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium border border-red-500/60 text-red-400 hover:bg-red-500/10 disabled:opacity-50 transition-all"
            title="Confirm: remove all pending GPU tasks"
          >
            <Trash2 className="w-2.5 h-2.5" />
            Confirm flush
          </button>
        ) : (
          <button
            onClick={() => setFlushConfirm("ml")}
            disabled={(depths["ml"] ?? 0) === 0}
            className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium border border-[var(--color-border)] hover:border-red-500/50 hover:text-red-400 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
            title="Flush all pending GPU tasks"
          >
            <Trash2 className="w-2.5 h-2.5" />
            Flush GPU ({(depths["ml"] ?? 0).toLocaleString()})
          </button>
        )}
      </div>
    </div>
  );
}

// ── Cluster card ──────────────────────────────────────────────────────────────

function ClusterCard({ cluster }: { cluster: FaceCluster }) {
  const imgSrc = cluster.face_crop_url
    ?? (cluster.representative_media_id ? thumbnailUrl(cluster.representative_media_id) : null);

  return (
    <Link
      href={`/faces/${cluster.cluster_id}`}
      className="group relative rounded-xl overflow-hidden border border-[var(--color-border)] bg-[var(--color-card)] hover:border-[hsl(217_33%_30%)] hover:shadow-lg hover:shadow-black/20 transition-all duration-150 cursor-pointer"
    >
      <div className="relative w-full aspect-square bg-[var(--color-muted)]">
        {imgSrc ? (
          <Image
            src={imgSrc}
            alt={`Cluster ${cluster.cluster_id}`}
            fill
            className="object-cover transition-transform duration-300 group-hover:scale-105"
            unoptimized
          />
        ) : (
          <div className="flex items-center justify-center h-full">
            <Users className="w-10 h-10 text-[var(--color-muted-foreground)]" />
          </div>
        )}
        <span className="absolute bottom-1.5 right-1.5 text-[10px] font-semibold bg-black/70 text-white px-1.5 py-0.5 rounded">
          {cluster.member_count} {cluster.member_count === 1 ? "item" : "items"}
        </span>
      </div>
      <div className="px-2.5 py-2">
        <p className="text-xs font-medium text-[var(--color-foreground)] truncate">
          Cluster {cluster.cluster_id}
        </p>
        <p className="text-[10px] text-[var(--color-muted-foreground)] mt-0.5">
          {cluster.member_count} {cluster.member_count === 1 ? "appearance" : "appearances"}
        </p>
      </div>
    </Link>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function FacesPage() {
  const queryClient = useQueryClient();

  const [activeTaskId, setActiveTaskId] = useState<string | null>(() => {
    try {
      return JSON.parse(localStorage.getItem("faces_active_task") ?? "null")?.taskId ?? null;
    } catch {
      return null;
    }
  });
  const [activeTaskType, setActiveTaskType] = useState<"cluster" | "backfill" | null>(() => {
    try {
      return JSON.parse(localStorage.getItem("faces_active_task") ?? "null")?.taskType ?? null;
    } catch {
      return null;
    }
  });

  useEffect(() => {
    if (activeTaskId && activeTaskType) {
      localStorage.setItem("faces_active_task", JSON.stringify({ taskId: activeTaskId, taskType: activeTaskType }));
    } else {
      localStorage.removeItem("faces_active_task");
    }
  }, [activeTaskId, activeTaskType]);

  const { data: clusters, isLoading: clustersLoading } = useQuery({
    queryKey: ["face-clusters"],
    queryFn: listClusters,
    staleTime: 60 * 1000,
    refetchInterval: 60 * 1000,
  });

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["face-stats"],
    queryFn: getFaceStats,
    staleTime: 15 * 1000,
    refetchInterval: 30 * 1000,
  });

  const { data: taskStatus } = useQuery({
    queryKey: ["face-task", activeTaskId],
    queryFn: () => getFaceTaskStatus(activeTaskId!),
    enabled: !!activeTaskId,
    refetchInterval: (query) => {
      const state = query.state.data?.state;
      if (state === "SUCCESS" || state === "FAILURE") return false;
      return 1500;
    },
  });

  useEffect(() => {
    if (!taskStatus) return;
    if (taskStatus.state === "SUCCESS" || taskStatus.state === "FAILURE") {
      queryClient.invalidateQueries({ queryKey: ["face-stats"] });
      queryClient.invalidateQueries({ queryKey: ["face-clusters"] });
      const t = setTimeout(() => {
        setActiveTaskId(null);
        setActiveTaskType(null);
      }, 7000);
      return () => clearTimeout(t);
    }
  }, [taskStatus?.state, queryClient]);

  const cancel = useMutation({
    mutationFn: () => cancelFaceTask(activeTaskId!),
    onSettled: () => {
      setActiveTaskId(null);
      setActiveTaskType(null);
    },
  });

  const cluster = useMutation({
    mutationFn: triggerClustering,
    onSuccess: (data) => {
      setActiveTaskId(data.task_id);
      setActiveTaskType("cluster");
    },
  });

  const backfill = useMutation({
    mutationFn: triggerBackfill,
    onSuccess: (data) => {
      setActiveTaskId(data.task_id);
      setActiveTaskType("backfill");
    },
  });

  const isLoading = clustersLoading || statsLoading;
  const isRunning = taskStatus && taskStatus.state !== "SUCCESS" && taskStatus.state !== "FAILURE";

  return (
    <div className="flex flex-col h-full">
      <Topbar title="Faces" />

      {/* Row 1: face stats + cluster controls */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--color-border)] bg-[var(--color-card)] shrink-0">
        <div className="flex items-center gap-3 text-xs text-[var(--color-muted-foreground)]">
          {stats ? (
            <>
              <span>{stats.total_faces.toLocaleString()} faces detected</span>
              <span className="opacity-30">·</span>
              <span>{stats.cluster_count} clusters</span>
              {stats.unclustered > 0 && (
                <>
                  <span className="opacity-30">·</span>
                  <span className="text-amber-400 font-medium">
                    {stats.unclustered.toLocaleString()} unclustered
                  </span>
                </>
              )}
              {stats.unclustered === 0 && stats.total_faces > 0 && (
                <>
                  <span className="opacity-30">·</span>
                  <span className="text-emerald-400">all clustered</span>
                </>
              )}
            </>
          ) : (
            <span>Loading…</span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {activeTaskId && activeTaskType && (
            <div className="flex items-center gap-1.5">
              <TaskStatusBadge status={taskStatus} type={activeTaskType} />
              <button
                onClick={() => cancel.mutate()}
                disabled={cancel.isPending}
                className="p-0.5 rounded hover:bg-[var(--color-muted)] text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] transition-colors"
                title="Cancel / dismiss"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          )}

          <button
            onClick={() => backfill.mutate()}
            disabled={backfill.isPending || !!isRunning}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium border border-[var(--color-border)] hover:border-[hsl(217_33%_30%)] hover:bg-[var(--color-muted)] disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-150"
            title="Dispatch caption, transcript & face detection for all pending items"
          >
            <ScanSearch className={`w-3 h-3 ${backfill.isPending ? "animate-pulse" : ""}`} />
            Run Backfill
          </button>

          <button
            onClick={() => cluster.mutate()}
            disabled={cluster.isPending || !!isRunning}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium border border-[var(--color-border)] hover:border-[hsl(217_33%_30%)] hover:bg-[var(--color-muted)] disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-150"
            title="Run face clustering now (auto-runs every 30 min)"
          >
            <RefreshCw className={`w-3 h-3 ${cluster.isPending ? "animate-spin" : ""}`} />
            Cluster Now
          </button>
        </div>
      </div>

      {/* Row 2: live queue depths + pause/flush controls */}
      <QueueStatusBar />

      <div className="flex-1 overflow-y-auto p-4">
        {isLoading && (
          <div className="flex items-center justify-center h-64 text-[var(--color-muted-foreground)]">
            <span className="text-sm">Loading…</span>
          </div>
        )}

        {!isLoading && (!clusters || clusters.length === 0) && (
          <div className="flex flex-col items-center justify-center h-64 gap-3 text-[var(--color-muted-foreground)]">
            <Users className="w-12 h-12 opacity-30" />
            <p className="text-sm">No face clusters yet.</p>
            <p className="text-xs opacity-70 text-center max-w-xs">
              {stats && stats.unclustered > 0
                ? `${stats.unclustered} faces detected but not yet clustered — click "Cluster Now" above.`
                : stats && stats.total_faces === 0
                ? `No faces detected yet. Click "Run Backfill" to start face detection on indexed media (requires GPU worker).`
                : "Clustering runs automatically every 30 minutes."}
            </p>
          </div>
        )}

        {clusters && clusters.length > 0 && (
          <>
            <p className="text-xs text-[var(--color-muted-foreground)] mb-4">
              {clusters.length} cluster{clusters.length !== 1 ? "s" : ""} detected
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
              {clusters.map((c) => (
                <ClusterCard key={c.cluster_id} cluster={c} />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
