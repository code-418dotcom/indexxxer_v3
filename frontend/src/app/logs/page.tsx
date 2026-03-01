"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listJobs, cancelJob } from "@/lib/api/jobs";
import { listSources } from "@/lib/api/sources";
import { useJobStream } from "@/lib/hooks/useJobStream";
import { Topbar } from "@/components/layout/Topbar";
import { cn, formatDate, formatRelative, jobProgress } from "@/lib/utils";
import type { IndexJob, JobEvent } from "@/types/api";
import {
  AlertCircle,
  CheckCircle2,
  ChevronRight,
  Clock,
  Loader2,
  Radio,
  ScrollText,
  XCircle,
} from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

const STATUS_ICON = {
  pending:   <Clock className="w-3.5 h-3.5 text-yellow-400" />,
  running:   <Loader2 className="w-3.5 h-3.5 text-blue-400 animate-spin" />,
  completed: <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />,
  failed:    <AlertCircle className="w-3.5 h-3.5 text-red-400" />,
  cancelled: <XCircle className="w-3.5 h-3.5 text-[var(--color-muted-foreground)]" />,
};

const EVENT_COLOR: Record<string, string> = {
  "scan.start":      "text-blue-400",
  "scan.discovered": "text-blue-400",
  "scan.dispatched": "text-blue-300",
  "scan.complete":   "text-emerald-400",
  "file.extracted":  "text-[var(--color-foreground)]",
  "file.error":      "text-red-400",
  "stream.connected":"text-[var(--color-muted-foreground)]",
  "stream.end":      "text-[var(--color-muted-foreground)]",
};

function eventMessage(ev: JobEvent): string {
  switch (ev.type) {
    case "scan.start":
      return `Scan started — ${String(ev.source ?? "")} (${String(ev.path ?? "")})`;
    case "scan.discovered":
      return `Discovered ${String(ev.total ?? 0)} files`;
    case "scan.dispatched":
      return `Dispatched ${String(ev.dispatched ?? 0)} tasks · ${String(ev.skipped ?? 0)} skipped`;
    case "scan.complete":
      return `Scan complete — ${String(ev.processed ?? 0)} processed · ${String(ev.skipped ?? 0)} skipped`;
    case "file.extracted":
      return `Indexed ${String(ev.filename ?? "")} [${String(ev.media_type ?? "")}]`;
    case "file.error":
      return `Error: ${String(ev.filename ?? ev.file_path ?? "")} — ${String(ev.error ?? "")}`;
    case "stream.connected":
      return "Stream connected";
    case "stream.end":
      return "Stream ended";
    default:
      return ev.type;
  }
}

export default function LogsPage() {
  const [selectedJob, setSelectedJob] = useState<IndexJob | null>(null);
  const qc = useQueryClient();

  const { data: jobsData, isLoading } = useQuery({
    queryKey: ["jobs"],
    queryFn: () => listJobs({ limit: 50 }),
    refetchInterval: 3000,
  });

  const { data: sources } = useQuery({
    queryKey: ["sources"],
    queryFn: listSources,
  });

  const cancelMutation = useMutation({
    mutationFn: cancelJob,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  });

  const sourceMap = Object.fromEntries(sources?.map((s) => [s.id, s.name]) ?? []);
  const jobs = jobsData?.items ?? [];

  return (
    <div className="flex flex-col h-full">
      <Topbar title="Logs" />

      <div className="flex flex-1 min-h-0">
        {/* Job feed */}
        <div className="w-80 shrink-0 border-r border-[var(--color-border)] flex flex-col">
          <div className="px-4 py-3 border-b border-[var(--color-border)]">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-muted-foreground)]">
              Job history
            </h2>
          </div>
          <div className="flex-1 overflow-y-auto">
            {isLoading ? (
              <div className="flex items-center gap-2 p-4 text-[var(--color-muted-foreground)]">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span className="text-sm">Loading…</span>
              </div>
            ) : jobs.length === 0 ? (
              <div className="flex flex-col items-center gap-2 py-12 text-[var(--color-muted-foreground)]">
                <ScrollText className="w-8 h-8 opacity-30" />
                <p className="text-sm">No jobs yet</p>
              </div>
            ) : (
              jobs.map((job) => (
                <button
                  key={job.id}
                  onClick={() => setSelectedJob(job)}
                  className={cn(
                    "w-full text-left px-4 py-3 border-b border-[var(--color-border)] hover:bg-[var(--color-muted)] transition-colors",
                    selectedJob?.id === job.id && "bg-[hsl(217_91%_60%/0.08)]"
                  )}
                >
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      {STATUS_ICON[job.status]}
                      <span className="text-xs font-semibold text-[var(--color-foreground)] capitalize">
                        {job.job_type}
                      </span>
                    </div>
                    <ChevronRight className="w-3.5 h-3.5 text-[var(--color-muted-foreground)]" />
                  </div>
                  <p className="text-xs text-[var(--color-muted-foreground)] truncate">
                    {sourceMap[job.source_id] ?? job.source_id.slice(0, 8)}
                  </p>
                  <div className="flex items-center justify-between mt-1">
                    <p className="text-[10px] text-[var(--color-muted-foreground)]">
                      {job.created_at ? formatRelative(job.created_at) : "—"}
                    </p>
                    {job.total_files != null && (
                      <p className="text-[10px] text-[var(--color-muted-foreground)]">
                        {job.processed_files}/{job.total_files}
                      </p>
                    )}
                  </div>
                  {job.status === "running" && job.total_files && (
                    <div className="mt-1.5 h-1 rounded-full bg-[var(--color-muted)] overflow-hidden">
                      <div
                        className="h-full rounded-full bg-[hsl(217_91%_60%)] transition-all duration-500"
                        style={{ width: `${jobProgress(job)}%` }}
                      />
                    </div>
                  )}
                  {job.status === "running" && (
                    <button
                      onClick={(e) => { e.stopPropagation(); cancelMutation.mutate(job.id); }}
                      className="mt-1 text-[10px] text-red-400 hover:text-red-300 transition-colors"
                    >
                      Cancel
                    </button>
                  )}
                </button>
              ))
            )}
          </div>
        </div>

        {/* Live tail / detail */}
        <div className="flex-1 flex flex-col min-w-0">
          {selectedJob ? (
            <LivePanel job={selectedJob} sourceMap={sourceMap} />
          ) : (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-[var(--color-muted-foreground)]">
              <Radio className="w-10 h-10 opacity-30" />
              <p className="text-sm">Select a job to see its live log</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Live tail panel ──────────────────────────────────────────────────────

function LivePanel({ job, sourceMap }: { job: IndexJob; sourceMap: Record<string, string> }) {
  const [logLines, setLogLines] = useState<{ ev: JobEvent; ts: Date }[]>([]);

  const { connected, done } = useJobStream({
    jobId: job.id,
    enabled: job.status === "running" || job.status === "pending",
    onEvent: (ev) => setLogLines((prev) => [...prev.slice(-499), { ev, ts: new Date() }]),
  });

  const isLive = job.status === "running" || job.status === "pending";

  return (
    <div className="flex flex-col h-full">
      {/* Panel header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-[var(--color-border)]">
        <div className="flex items-center gap-3">
          {STATUS_ICON[job.status]}
          <div>
            <p className="text-sm font-semibold text-[var(--color-foreground)] capitalize">
              {job.job_type} scan — {sourceMap[job.source_id] ?? job.source_id.slice(0, 8)}
            </p>
            <p className="text-xs text-[var(--color-muted-foreground)]">
              {job.started_at ? formatDate(job.started_at) : "Not started"}
              {job.completed_at && ` → ${formatDate(job.completed_at)}`}
            </p>
          </div>
        </div>

        {isLive && (
          <div className="flex items-center gap-1.5 text-xs">
            <span
              className={cn(
                "w-1.5 h-1.5 rounded-full",
                connected ? "bg-emerald-400 animate-pulse" : "bg-yellow-400"
              )}
            />
            <span className="text-[var(--color-muted-foreground)]">
              {connected ? "Live" : "Connecting…"}
            </span>
          </div>
        )}
      </div>

      {/* Progress bar */}
      {job.total_files != null && (
        <div className="px-5 py-2 border-b border-[var(--color-border)]">
          <div className="flex items-center justify-between text-[11px] text-[var(--color-muted-foreground)] mb-1">
            <span>
              {job.processed_files} processed · {job.failed_files} failed · {job.skipped_files} skipped
            </span>
            <span>{jobProgress(job)}%</span>
          </div>
          <div className="h-1.5 rounded-full bg-[var(--color-muted)] overflow-hidden">
            <div
              className="h-full rounded-full bg-[hsl(217_91%_60%)] transition-all duration-500"
              style={{ width: `${jobProgress(job)}%` }}
            />
          </div>
        </div>
      )}

      {/* Log output */}
      <div className="flex-1 overflow-y-auto p-5 font-mono text-xs space-y-0.5">
        {logLines.length === 0 && !isLive && (
          <p className="text-[var(--color-muted-foreground)] italic">
            {done ? "Stream ended." : "No live events — job is not running."}
          </p>
        )}
        {logLines.length === 0 && isLive && !connected && (
          <p className="text-[var(--color-muted-foreground)] italic">Connecting to stream…</p>
        )}
        {logLines.map(({ ev, ts }, i) => (
          <div key={i} className="flex items-start gap-3">
            <span className="text-[var(--color-muted-foreground)] shrink-0 tabular-nums">
              {ts.toLocaleTimeString()}
            </span>
            <span className={cn(EVENT_COLOR[ev.type] ?? "text-[var(--color-foreground)]")}>
              {eventMessage(ev)}
            </span>
          </div>
        ))}
      </div>

      {/* Error message */}
      {job.error_message && (
        <div className="px-5 py-3 border-t border-red-500/20 bg-red-500/5">
          <p className="text-xs text-red-400">{job.error_message}</p>
        </div>
      )}
    </div>
  );
}
