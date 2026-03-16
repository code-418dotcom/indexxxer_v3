"use client";

import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronDown,
  ChevronUp,
  Download,
  Plus,
  RefreshCw,
  Search,
  Star,
  UserCircle,
  X,
} from "lucide-react";
import { Topbar } from "@/components/layout/Topbar";
import {
  createPerformer,
  listPerformers,
  matchAllPerformers,
  performerImageUrl,
  scrapeAllPerformers,
  scrapeNewPerformer,
} from "@/lib/api/performers";
import { getAccessToken, getLegacyToken } from "@/lib/api/client";
import type { Performer } from "@/types/api";

// ── Types for SSE events ─────────────────────────────────────────────────────

interface ScrapeEvent {
  type: string;
  task_id?: string;
  total?: number;
  current?: number;
  performer_id?: string;
  performer_name?: string;
  status?: string;
  error?: string;
  fields_updated?: number;
  has_image?: boolean;
  succeeded?: number;
  failed?: number;
}

// ── Performer card ───────────────────────────────────────────────────────────

function PerformerCard({ performer }: { performer: Performer }) {
  return (
    <Link
      href={`/performers/${performer.id}`}
      className="group relative rounded-xl overflow-hidden border border-[var(--color-border)] bg-[var(--color-card)] hover:border-[hsl(217_33%_30%)] hover:shadow-lg hover:shadow-black/20 transition-all duration-150 cursor-pointer"
    >
      <div className="relative w-full aspect-[3/4] bg-[var(--color-muted)]">
        {performer.profile_image_url ? (
          <Image
            src={`${performerImageUrl(performer.id)}?v=${performer.updated_at}`}
            alt={performer.name}
            fill
            className="object-cover transition-transform duration-300 group-hover:scale-105"
            unoptimized
          />
        ) : (
          <div className="flex items-center justify-center h-full">
            <UserCircle className="w-16 h-16 text-[var(--color-muted-foreground)] opacity-30" />
          </div>
        )}
        {(performer.video_count > 0 || performer.gallery_count > 0) && (
          <div className="absolute bottom-1.5 right-1.5 flex items-center gap-1">
            {performer.video_count > 0 && (
              <span className="text-[10px] font-semibold bg-black/70 text-white px-1.5 py-0.5 rounded">
                {performer.video_count} {performer.video_count === 1 ? "video" : "videos"}
              </span>
            )}
            {performer.gallery_count > 0 && (
              <span className="text-[10px] font-semibold bg-black/70 text-emerald-300 px-1.5 py-0.5 rounded">
                {performer.gallery_count} {performer.gallery_count === 1 ? "gallery" : "galleries"}
              </span>
            )}
          </div>
        )}
      </div>
      <div className="px-2.5 py-2">
        <p className="text-xs font-medium text-[var(--color-foreground)] truncate">
          {performer.name}
        </p>
        {performer.nationality && (
          <p className="text-[10px] text-[var(--color-muted-foreground)] mt-0.5 truncate">
            {performer.nationality}
          </p>
        )}
      </div>
    </Link>
  );
}

// ── Add performer dialog ─────────────────────────────────────────────────────

function AddPerformerDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [freeonesUrl, setFreeonesUrl] = useState("");
  const [mode, setMode] = useState<"name" | "url">("name");

  const addByName = useMutation({
    mutationFn: () => createPerformer({ name, freeones_url: freeonesUrl || undefined }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["performers"] });
      setName("");
      setFreeonesUrl("");
      onClose();
    },
  });

  const addByUrl = useMutation({
    mutationFn: () => scrapeNewPerformer({ freeones_url: freeonesUrl }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["performers"] });
      setFreeonesUrl("");
      onClose();
    },
  });

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl p-5 w-full max-w-md space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-sm font-semibold text-[var(--color-foreground)]">Add Performer</h2>

        <div className="flex gap-2">
          <button
            onClick={() => setMode("name")}
            className={`px-3 py-1 rounded text-xs font-medium border transition-colors ${
              mode === "name"
                ? "border-[hsl(217_91%_60%)] text-[hsl(217_91%_70%)] bg-[hsl(217_91%_60%/0.1)]"
                : "border-[var(--color-border)] text-[var(--color-muted-foreground)] hover:border-[hsl(217_33%_30%)]"
            }`}
          >
            By Name
          </button>
          <button
            onClick={() => setMode("url")}
            className={`px-3 py-1 rounded text-xs font-medium border transition-colors ${
              mode === "url"
                ? "border-[hsl(217_91%_60%)] text-[hsl(217_91%_70%)] bg-[hsl(217_91%_60%/0.1)]"
                : "border-[var(--color-border)] text-[var(--color-muted-foreground)] hover:border-[hsl(217_33%_30%)]"
            }`}
          >
            By Freeones URL
          </button>
        </div>

        {mode === "name" ? (
          <div className="space-y-3">
            <input
              type="text"
              placeholder="Performer name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 rounded-lg text-sm bg-[var(--color-muted)] border border-[var(--color-border)] text-[var(--color-foreground)] placeholder:text-[var(--color-muted-foreground)] focus:outline-none focus:border-[hsl(217_91%_60%)]"
            />
            <input
              type="text"
              placeholder="Freeones URL (optional, for scraping)"
              value={freeonesUrl}
              onChange={(e) => setFreeonesUrl(e.target.value)}
              className="w-full px-3 py-2 rounded-lg text-sm bg-[var(--color-muted)] border border-[var(--color-border)] text-[var(--color-foreground)] placeholder:text-[var(--color-muted-foreground)] focus:outline-none focus:border-[hsl(217_91%_60%)]"
            />
            <button
              onClick={() => addByName.mutate()}
              disabled={!name.trim() || addByName.isPending}
              className="w-full px-3 py-2 rounded-lg text-sm font-medium bg-[hsl(217_91%_60%)] text-white hover:bg-[hsl(217_91%_55%)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {addByName.isPending ? "Adding..." : "Add Performer"}
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <input
              type="text"
              placeholder="https://www.freeones.com/performer-name"
              value={freeonesUrl}
              onChange={(e) => setFreeonesUrl(e.target.value)}
              className="w-full px-3 py-2 rounded-lg text-sm bg-[var(--color-muted)] border border-[var(--color-border)] text-[var(--color-foreground)] placeholder:text-[var(--color-muted-foreground)] focus:outline-none focus:border-[hsl(217_91%_60%)]"
            />
            <button
              onClick={() => addByUrl.mutate()}
              disabled={!freeonesUrl.trim() || addByUrl.isPending}
              className="w-full px-3 py-2 rounded-lg text-sm font-medium bg-[hsl(217_91%_60%)] text-white hover:bg-[hsl(217_91%_55%)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {addByUrl.isPending ? "Scraping..." : "Scrape & Add"}
            </button>
          </div>
        )}

        {(addByName.isError || addByUrl.isError) && (
          <p className="text-xs text-red-400">
            {(addByName.error as Error)?.message || (addByUrl.error as Error)?.message || "Failed to add performer"}
          </p>
        )}
      </div>
    </div>
  );
}

// ── Scrape-all progress panel ────────────────────────────────────────────────

function ScrapeAllPanel({
  taskId,
  onDone,
}: {
  taskId: string;
  onDone: () => void;
}) {
  const [events, setEvents] = useState<ScrapeEvent[]>([]);
  const [logExpanded, setLogExpanded] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);
  const esRef = useRef<EventSource | null>(null);

  // Derived state
  const lastProgress = [...events].reverse().find(
    (e) => e.type === "scrape_all.progress" || e.type === "scrape_all.item"
  );
  const completeEvent = events.find((e) => e.type === "scrape_all.complete");
  const total = completeEvent?.total ?? lastProgress?.total ?? 0;
  const current = completeEvent
    ? total
    : lastProgress?.current ?? 0;
  const pct = total > 0 ? Math.round((current / total) * 100) : 0;
  const isComplete = !!completeEvent;

  // Connect to SSE
  useEffect(() => {
    const token = getAccessToken() || getLegacyToken();
    if (!token || !taskId) return;

    const url = `/api/v1/performers/scrape-all/stream?task_id=${encodeURIComponent(taskId)}&token=${encodeURIComponent(token)}`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onmessage = (e) => {
      try {
        const data: ScrapeEvent = JSON.parse(e.data);
        setEvents((prev) => [...prev, data]);
      } catch {
        // ignore parse errors
      }
    };

    es.onerror = () => {
      es.close();
    };

    return () => {
      es.close();
    };
  }, [taskId]);

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current && logExpanded) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [events, logExpanded]);

  const succeeded = completeEvent?.succeeded ?? events.filter((e) => e.type === "scrape_all.item" && e.status === "done").length;
  const failed = completeEvent?.failed ?? events.filter((e) => e.type === "scrape_all.item" && (e.status === "failed" || e.status === "error")).length;

  return (
    <div className="border-b border-[var(--color-border)] bg-[var(--color-card)]">
      {/* Progress bar row */}
      <div className="px-4 py-2 space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs">
            <Download className={`w-3.5 h-3.5 ${isComplete ? "text-emerald-400" : "text-blue-400 animate-pulse"}`} />
            <span className="font-medium text-[var(--color-foreground)]">
              {isComplete ? "Scrape Complete" : "Scraping All Performers..."}
            </span>
            <span className="text-[var(--color-muted-foreground)]">
              {current}/{total}
            </span>
            {lastProgress?.performer_name && !isComplete && (
              <span className="text-[var(--color-muted-foreground)] truncate max-w-48">
                — {lastProgress.performer_name}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {isComplete && (
              <span className="text-[10px] text-[var(--color-muted-foreground)]">
                <span className="text-emerald-400">{succeeded} ok</span>
                {failed > 0 && <span className="text-red-400 ml-1.5">{failed} failed</span>}
              </span>
            )}
            <button
              onClick={() => setLogExpanded((v) => !v)}
              className="p-1 rounded hover:bg-[var(--color-muted)] text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] transition-colors"
              title={logExpanded ? "Collapse log" : "Expand log"}
            >
              {logExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
            {isComplete && (
              <button
                onClick={onDone}
                className="p-1 rounded hover:bg-[var(--color-muted)] text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] transition-colors"
                title="Dismiss"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>

        {/* Progress bar */}
        <div className="w-full h-1.5 rounded-full bg-[var(--color-muted)] overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-300 ${
              isComplete ? "bg-emerald-500" : "bg-blue-500"
            }`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* Expandable debug log */}
      {logExpanded && (
        <div
          ref={logRef}
          className="max-h-64 overflow-y-auto border-t border-[var(--color-border)] bg-[hsl(222_47%_3%)] px-4 py-2 font-mono text-[11px] leading-relaxed space-y-0.5"
        >
          {events.map((evt, i) => (
            <LogLine key={i} event={evt} />
          ))}
          {events.length === 0 && (
            <span className="text-[var(--color-muted-foreground)] opacity-50">Waiting for events...</span>
          )}
        </div>
      )}
    </div>
  );
}

function LogLine({ event }: { event: ScrapeEvent }) {
  const ts = new Date().toLocaleTimeString("en-GB", { hour12: false });

  if (event.type === "stream.connected") {
    return <div className="text-[var(--color-muted-foreground)] opacity-50">[{ts}] Connected to scrape stream</div>;
  }
  if (event.type === "scrape_all.start") {
    return <div className="text-blue-400">[{ts}] Starting scrape for {event.total} performers</div>;
  }
  if (event.type === "scrape_all.progress") {
    return (
      <div className="text-[var(--color-muted-foreground)]">
        [{ts}] [{event.current}/{event.total}] Scraping <span className="text-[var(--color-foreground)]">{event.performer_name}</span>...
      </div>
    );
  }
  if (event.type === "scrape_all.item") {
    if (event.status === "done") {
      return (
        <div className="text-emerald-400">
          [{ts}] [{event.current}/{event.total}] {event.performer_name} — {event.fields_updated} fields{event.has_image ? " + image" : ""}
        </div>
      );
    }
    return (
      <div className="text-red-400">
        [{ts}] [{event.current}/{event.total}] {event.performer_name} — {event.status}: {event.error || "unknown error"}
      </div>
    );
  }
  if (event.type === "scrape_all.complete") {
    return (
      <div className="text-emerald-400 font-semibold">
        [{ts}] Complete: {event.succeeded} succeeded, {event.failed} failed out of {event.total}
      </div>
    );
  }
  if (event.type === "stream.end") {
    return <div className="text-[var(--color-muted-foreground)] opacity-50">[{ts}] Stream ended</div>;
  }
  return <div className="text-[var(--color-muted-foreground)] opacity-30">[{ts}] {event.type}</div>;
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function PerformersPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [page, setPage] = useState(1);
  const [scrapeTaskId, setScrapeTaskId] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["performers", { page, q: search || undefined }],
    queryFn: () => listPerformers({ page, limit: 60, q: search || undefined, sort: "name", order: "asc" }),
    staleTime: 30_000,
  });

  const matchAll = useMutation({
    mutationFn: matchAllPerformers,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["performers"] });
    },
  });

  const scrapeAll = useMutation({
    mutationFn: scrapeAllPerformers,
    onSuccess: (data) => {
      setScrapeTaskId(data.task_id);
    },
  });

  const handleScrapeAllDone = useCallback(() => {
    setScrapeTaskId(null);
    queryClient.invalidateQueries({ queryKey: ["performers"] });
  }, [queryClient]);

  const performers = data?.items ?? [];
  const total = data?.total ?? 0;
  const pages = data?.pages ?? 1;

  return (
    <div className="flex flex-col h-full">
      <Topbar title="Performers">
        <div className="flex items-center gap-3 max-w-lg">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--color-muted-foreground)]" />
            <input
              type="text"
              placeholder="Search performers..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              className="w-full pl-8 pr-3 py-1.5 rounded-lg text-xs bg-[var(--color-muted)] border border-[var(--color-border)] text-[var(--color-foreground)] placeholder:text-[var(--color-muted-foreground)] focus:outline-none focus:border-[hsl(217_91%_60%)]"
            />
          </div>
        </div>
      </Topbar>

      {/* Actions bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-3 md:px-4 py-2 border-b border-[var(--color-border)] bg-[var(--color-card)] shrink-0">
        <div className="text-xs text-[var(--color-muted-foreground)]">
          {total} performer{total !== 1 ? "s" : ""}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => scrapeAll.mutate()}
            disabled={scrapeAll.isPending || !!scrapeTaskId}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium border border-[var(--color-border)] hover:border-[hsl(217_33%_30%)] hover:bg-[var(--color-muted)] disabled:opacity-50 transition-all"
            title="Scrape bio data + images for all performers from Freeones"
          >
            <Download className={`w-3 h-3 ${scrapeAll.isPending ? "animate-pulse" : ""}`} />
            Scrape All
          </button>
          <button
            onClick={() => matchAll.mutate()}
            disabled={matchAll.isPending}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium border border-[var(--color-border)] hover:border-[hsl(217_33%_30%)] hover:bg-[var(--color-muted)] disabled:opacity-50 transition-all"
            title="Re-match all performers against filenames/directories"
          >
            <RefreshCw className={`w-3 h-3 ${matchAll.isPending ? "animate-spin" : ""}`} />
            Match All
          </button>
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium bg-[hsl(217_91%_60%)] text-white hover:bg-[hsl(217_91%_55%)] transition-colors"
          >
            <Plus className="w-3 h-3" />
            Add Performer
          </button>
        </div>
      </div>

      {/* Scrape-all progress panel */}
      {scrapeTaskId && (
        <ScrapeAllPanel taskId={scrapeTaskId} onDone={handleScrapeAllDone} />
      )}

      <div className="flex-1 overflow-y-auto p-3 md:p-4">
        {isLoading && (
          <div className="flex items-center justify-center h-64 text-[var(--color-muted-foreground)]">
            <span className="text-sm">Loading...</span>
          </div>
        )}

        {!isLoading && performers.length === 0 && (
          <div className="flex flex-col items-center justify-center h-64 gap-3 text-[var(--color-muted-foreground)]">
            <Star className="w-12 h-12 opacity-30" />
            <p className="text-sm">No performers yet.</p>
            <p className="text-xs opacity-70 text-center max-w-xs">
              Add performers by name or Freeones URL. They&apos;ll be automatically matched against your video filenames and directories.
            </p>
          </div>
        )}

        {performers.length > 0 && (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-8 gap-3">
            {performers.map((p) => (
              <PerformerCard key={p.id} performer={p} />
            ))}
          </div>
        )}

        {/* Pagination */}
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

      <AddPerformerDialog open={showAdd} onClose={() => setShowAdd(false)} />
    </div>
  );
}
