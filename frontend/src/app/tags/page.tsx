"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, ScanLine, Tag, Trash2, X } from "lucide-react";
import { Topbar } from "@/components/layout/Topbar";
import { listTags, backfillAiTags, deleteTag, type TagItem } from "@/lib/api/tags";
import { cn } from "@/lib/utils";

const CATEGORIES = [
  { value: null, label: "All" },
  { value: "actions", label: "Actions", color: "#e53e3e" },
  { value: "bdsm", label: "BDSM", color: "#9b2c2c" },
  { value: "bodyparts", label: "Body Parts", color: "#3182ce" },
  { value: "positions", label: "Positions", color: "#38a169" },
];

function TagBadge({ tag, onDelete }: { tag: TagItem; onDelete?: () => void }) {
  return (
    <div
      className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] hover:border-[hsl(217_33%_30%)] transition-colors group"
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

export default function TagsPage() {
  const qc = useQueryClient();
  const [category, setCategory] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["tags", { page, category, q: search || undefined }],
    queryFn: () => listTags({ page, limit: 100, category: category || undefined, q: search || undefined }),
    staleTime: 15_000,
  });

  const backfill = useMutation({
    mutationFn: backfillAiTags,
    onSuccess: () => {
      setTimeout(() => qc.invalidateQueries({ queryKey: ["tags"] }), 10_000);
    },
  });

  const removeMutation = useMutation({
    mutationFn: deleteTag,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tags"] }),
  });

  const tags = data?.items ?? [];
  const total = data?.total ?? 0;
  const pages = data?.pages ?? 1;

  return (
    <div className="flex flex-col h-full">
      <Topbar title="Tags">
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
            {backfill.isPending ? "Tagging..." : "Auto-Tag All"}
          </button>
          {backfill.isSuccess && (
            <span className="text-[10px] text-emerald-400">Dispatched! Tags will appear as files are processed.</span>
          )}
        </div>
      </Topbar>

      {/* Filters bar */}
      <div className="flex flex-wrap items-center gap-2 px-3 md:px-5 py-2.5 border-b border-[var(--color-border)] shrink-0">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.label}
            onClick={() => { setCategory(cat.value); setPage(1); }}
            className={cn(
              "px-2.5 py-1 rounded-md text-xs font-medium transition-colors",
              category === cat.value
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
              Click &quot;Auto-Tag All&quot; to start.
            </p>
          </div>
        )}

        {tags.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {tags.map((tag) => (
              <TagBadge
                key={tag.id}
                tag={tag}
                onDelete={() => {
                  if (confirm(`Delete tag "${tag.name}"?`)) {
                    removeMutation.mutate(tag.id);
                  }
                }}
              />
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
    </div>
  );
}
