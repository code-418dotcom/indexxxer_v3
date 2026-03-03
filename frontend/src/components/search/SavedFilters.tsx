"use client";

import { Bookmark, BookmarkCheck, ChevronDown, Trash2 } from "lucide-react";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { createFilter, deleteFilter, listFilters } from "@/lib/api/filters";
import type { SearchParams } from "@/types/api";

interface SavedFiltersProps {
  currentFilters: SearchParams;
  onApply: (filters: SearchParams) => void;
}

export function SavedFilters({ currentFilters, onApply }: SavedFiltersProps) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState("");
  const queryClient = useQueryClient();

  const { data: filters = [] } = useQuery({
    queryKey: ["filters"],
    queryFn: listFilters,
  });

  const saveMutation = useMutation({
    mutationFn: () =>
      createFilter({ name: name.trim(), filters: currentFilters as Record<string, unknown> }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["filters"] });
      setName("");
      setSaving(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteFilter(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["filters"] }),
  });

  const hasFilters =
    !!currentFilters.type ||
    !!currentFilters.date_from ||
    !!currentFilters.favourite ||
    (currentFilters.tag_ids?.length ?? 0) > 0;

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={cn(
          "flex items-center gap-1.5 h-9 px-3 text-sm rounded-lg border transition-colors",
          filters.length > 0
            ? "bg-amber-500/10 border-amber-500/40 text-amber-400"
            : "bg-[var(--color-muted)] border-[var(--color-border)] text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]"
        )}
        title="Saved filters"
      >
        <Bookmark className="w-3.5 h-3.5" />
        {filters.length > 0 && (
          <span className="text-[10px] font-semibold">{filters.length}</span>
        )}
        <ChevronDown className={cn("w-3.5 h-3.5 transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-20" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-11 z-30 w-72 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] shadow-xl shadow-black/30 p-4 space-y-3">
            {/* Save current filter */}
            {hasFilters && (
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-muted-foreground)] mb-2">
                  Save current filters
                </p>
                {saving ? (
                  <div className="flex gap-2">
                    <input
                      autoFocus
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && name.trim()) saveMutation.mutate();
                        if (e.key === "Escape") setSaving(false);
                      }}
                      placeholder="Filter name…"
                      className="flex-1 h-7 px-2 text-xs rounded-lg bg-[var(--color-muted)] border border-[var(--color-border)] text-[var(--color-foreground)] focus:outline-none focus:border-[hsl(217_91%_60%)]"
                    />
                    <button
                      onClick={() => name.trim() && saveMutation.mutate()}
                      disabled={!name.trim() || saveMutation.isPending}
                      className="px-2.5 py-1 text-xs rounded-lg bg-[hsl(217_91%_60%)] text-white disabled:opacity-50"
                    >
                      Save
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setSaving(true)}
                    className="flex items-center gap-1.5 text-xs text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] transition-colors"
                  >
                    <BookmarkCheck className="w-3.5 h-3.5" />
                    Save current filters…
                  </button>
                )}
              </div>
            )}

            {/* Saved filter list */}
            {filters.length > 0 && (
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-muted-foreground)] mb-2">
                  Saved filters
                </p>
                <div className="space-y-1 max-h-48 overflow-y-auto">
                  {filters.map((f) => (
                    <div
                      key={f.id}
                      className="flex items-center gap-2 group/item"
                    >
                      <button
                        onClick={() => {
                          onApply(f.filters as SearchParams);
                          setOpen(false);
                        }}
                        className="flex-1 text-left text-xs px-2 py-1.5 rounded-lg hover:bg-[var(--color-muted)] text-[var(--color-foreground)] transition-colors truncate"
                      >
                        {f.name}
                      </button>
                      <button
                        onClick={() => deleteMutation.mutate(f.id)}
                        className="opacity-0 group-hover/item:opacity-100 p-1 rounded text-[var(--color-muted-foreground)] hover:text-red-400 transition-all"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {filters.length === 0 && !hasFilters && (
              <p className="text-xs text-[var(--color-muted-foreground)]">
                Apply filters first, then save them here.
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
