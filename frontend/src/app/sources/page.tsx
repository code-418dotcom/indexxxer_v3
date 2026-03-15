"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createSource,
  deleteSource,
  listSources,
  triggerScan,
  updateSource,
} from "@/lib/api/sources";
import { Topbar } from "@/components/layout/Topbar";
import { cn, formatDate, formatRelative } from "@/lib/utils";
import type { MediaSource, SourceCreate } from "@/types/api";
import {
  CheckCircle2,
  Copy,
  FolderOpen,
  Loader2,
  Play,
  Plus,
  RefreshCw,
  Trash2,
  X,
} from "lucide-react";
import Link from "next/link";

export default function SourcesPage() {
  const [showAdd, setShowAdd] = useState(false);
  const qc = useQueryClient();

  const { data: sources, isLoading } = useQuery({
    queryKey: ["sources"],
    queryFn: listSources,
    refetchInterval: 5000,
  });

  const scanMutation = useMutation({
    mutationFn: ({ id, type }: { id: string; type: "full" | "incremental" }) =>
      triggerScan(id, { job_type: type }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteSource,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sources"] }),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      updateSource(id, { enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sources"] }),
  });

  return (
    <div className="flex flex-col h-full">
      <Topbar title="Sources">
        <div />
      </Topbar>

      <div className="flex-1 overflow-y-auto px-6 py-6 max-w-4xl">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="text-base font-semibold text-[var(--color-foreground)]">
              Media directories
            </h2>
            <p className="text-xs text-[var(--color-muted-foreground)] mt-0.5">
              Add the paths you want indexxxer to scan and index.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href="/duplicates"
              className="flex items-center gap-2 px-3 py-2 rounded-lg border border-[var(--color-border)] hover:border-[hsl(217_33%_30%)] hover:bg-[var(--color-muted)] text-sm font-medium text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] transition-all"
            >
              <Copy className="w-4 h-4" />
              Duplicates
            </Link>
            <button
              onClick={() => setShowAdd(true)}
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[hsl(217_91%_60%)] hover:bg-[hsl(217_91%_55%)] text-white text-sm font-medium transition-colors"
            >
              <Plus className="w-4 h-4" />
              Add source
            </button>
          </div>
        </div>

        {showAdd && (
          <AddSourceForm
            onClose={() => setShowAdd(false)}
            onCreated={() => {
              setShowAdd(false);
              qc.invalidateQueries({ queryKey: ["sources"] });
            }}
          />
        )}

        {isLoading ? (
          <div className="flex items-center gap-2 text-[var(--color-muted-foreground)] py-8">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="text-sm">Loading sources…</span>
          </div>
        ) : sources?.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3 text-[var(--color-muted-foreground)]">
            <FolderOpen className="w-12 h-12 opacity-30" />
            <p className="text-sm">No sources configured</p>
            <p className="text-xs opacity-60">Add a directory path to get started</p>
          </div>
        ) : (
          <div className="space-y-3">
            {sources?.map((source) => (
              <SourceCard
                key={source.id}
                source={source}
                onScan={(type) => scanMutation.mutate({ id: source.id, type })}
                onDelete={() => deleteMutation.mutate(source.id)}
                onToggle={(enabled) => toggleMutation.mutate({ id: source.id, enabled })}
                scanning={scanMutation.isPending}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Add source form ──────────────────────────────────────────────────────

function AddSourceForm({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [form, setForm] = useState<SourceCreate>({
    name: "",
    path: "",
    source_type: "local",
  });
  const [error, setError] = useState("");

  const mutation = useMutation({
    mutationFn: createSource,
    onSuccess: onCreated,
    onError: (e: unknown) => {
      setError(e instanceof Error ? e.message : "Failed to create source");
    },
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim() || !form.path.trim()) {
      setError("Name and path are required");
      return;
    }
    setError("");
    mutation.mutate(form);
  };

  return (
    <div className="mb-5 rounded-xl border border-[hsl(217_91%_60%/0.3)] bg-[hsl(217_91%_60%/0.05)] p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-[var(--color-foreground)]">
          New source
        </h3>
        <button
          onClick={onClose}
          className="text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
      <form onSubmit={submit} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-muted-foreground)] mb-1 block">
              Name
            </label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="My media library"
              className="w-full h-9 px-3 text-sm rounded-lg bg-[var(--color-muted)] border border-[var(--color-border)] text-[var(--color-foreground)] placeholder:text-[var(--color-muted-foreground)] focus:outline-none focus:border-[hsl(217_91%_60%)]"
            />
          </div>
          <div>
            <label className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-muted-foreground)] mb-1 block">
              Path
            </label>
            <input
              type="text"
              value={form.path}
              onChange={(e) => setForm({ ...form, path: e.target.value })}
              placeholder="/mnt/e/media/xxx"
              className="w-full h-9 px-3 text-sm rounded-lg bg-[var(--color-muted)] border border-[var(--color-border)] text-[var(--color-foreground)] placeholder:text-[var(--color-muted-foreground)] focus:outline-none focus:border-[hsl(217_91%_60%)] font-mono"
            />
          </div>
        </div>
        {error && <p className="text-xs text-red-400">{error}</p>}
        <div className="flex gap-2 justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 text-sm rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-muted)] transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={mutation.isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg bg-[hsl(217_91%_60%)] hover:bg-[hsl(217_91%_55%)] text-white font-medium disabled:opacity-60 transition-colors"
          >
            {mutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            Add source
          </button>
        </div>
      </form>
    </div>
  );
}

// ─── Source card ──────────────────────────────────────────────────────────

function SourceCard({
  source,
  onScan,
  onDelete,
  onToggle,
  scanning,
}: {
  source: MediaSource;
  onScan: (type: "full" | "incremental") => void;
  onDelete: () => void;
  onToggle: (enabled: boolean) => void;
  scanning: boolean;
}) {
  const [confirmDelete, setConfirmDelete] = useState(false);

  return (
    <div
      className={cn(
        "rounded-xl border p-4 transition-colors",
        source.enabled
          ? "bg-[var(--color-card)] border-[var(--color-border)]"
          : "bg-[var(--color-card)] border-[var(--color-border)] opacity-60"
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          <div className="mt-0.5 flex items-center justify-center w-8 h-8 rounded-lg bg-[var(--color-muted)] shrink-0">
            <FolderOpen className="w-4 h-4 text-[var(--color-muted-foreground)]" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-[var(--color-foreground)] truncate">
                {source.name}
              </h3>
              <span
                className={cn(
                  "text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase tracking-wider",
                  source.enabled
                    ? "bg-emerald-500/15 text-emerald-400"
                    : "bg-[var(--color-muted)] text-[var(--color-muted-foreground)]"
                )}
              >
                {source.enabled ? "active" : "disabled"}
              </span>
            </div>
            <p className="text-xs font-mono text-[var(--color-muted-foreground)] mt-0.5 truncate">
              {source.path}
            </p>
            {source.last_scan_at && (
              <p className="text-[11px] text-[var(--color-muted-foreground)] mt-1 flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                Last scanned {formatRelative(source.last_scan_at)}
              </p>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1.5 shrink-0">
          <button
            onClick={() => onScan("incremental")}
            disabled={scanning || !source.enabled}
            title="Incremental scan"
            className="flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-lg bg-[hsl(217_91%_60%/0.1)] text-[hsl(217_91%_65%)] hover:bg-[hsl(217_91%_60%/0.2)] disabled:opacity-40 transition-colors border border-[hsl(217_91%_60%/0.2)]"
          >
            {scanning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
            Scan
          </button>
          <button
            onClick={() => onScan("full")}
            disabled={scanning || !source.enabled}
            title="Full re-scan"
            className="p-1.5 rounded-lg hover:bg-[var(--color-muted)] text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] disabled:opacity-40 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => onToggle(!source.enabled)}
            title={source.enabled ? "Disable" : "Enable"}
            className="p-1.5 rounded-lg hover:bg-[var(--color-muted)] text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] transition-colors"
          >
            <span className="text-xs">{source.enabled ? "Off" : "On"}</span>
          </button>
          {confirmDelete ? (
            <div className="flex items-center gap-1">
              <button
                onClick={onDelete}
                className="px-2 py-1 text-xs rounded bg-red-500/90 text-white hover:bg-red-500 transition-colors"
              >
                Confirm
              </button>
              <button
                onClick={() => setConfirmDelete(false)}
                className="p-1.5 rounded hover:bg-[var(--color-muted)] text-[var(--color-muted-foreground)] transition-colors"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          ) : (
            <button
              onClick={() => setConfirmDelete(true)}
              className="p-1.5 rounded-lg hover:bg-red-500/10 text-[var(--color-muted-foreground)] hover:text-red-400 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
