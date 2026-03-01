"use client";

import { ChevronDown, X } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";
import type { MediaType, SearchParams } from "@/types/api";

interface FilterPanelProps {
  filters: SearchParams;
  onChange: (f: Partial<SearchParams>) => void;
}

const SORT_OPTIONS = [
  { value: "relevance", label: "Relevance" },
  { value: "date",      label: "Date indexed" },
  { value: "name",      label: "Filename" },
  { value: "size",      label: "File size" },
] as const;

const TYPE_OPTIONS: { value: MediaType | ""; label: string }[] = [
  { value: "",       label: "All types" },
  { value: "image",  label: "Images" },
  { value: "video",  label: "Videos" },
];

export function FilterPanel({ filters, onChange }: FilterPanelProps) {
  const [open, setOpen] = useState(false);

  const active =
    !!filters.type || !!filters.date_from || !!filters.date_to || !!filters.sort;

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={cn(
          "flex items-center gap-1.5 h-9 px-3 text-sm rounded-lg border transition-colors",
          active
            ? "bg-[hsl(217_91%_60%/0.1)] border-[hsl(217_91%_60%)] text-[hsl(217_91%_65%)]"
            : "bg-[var(--color-muted)] border-[var(--color-border)] text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]"
        )}
      >
        Filters
        {active && (
          <span className="w-4 h-4 rounded-full bg-[hsl(217_91%_60%)] text-white text-[9px] font-bold flex items-center justify-center">
            !
          </span>
        )}
        <ChevronDown className={cn("w-3.5 h-3.5 transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-20" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-11 z-30 w-64 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] shadow-xl shadow-black/30 p-4 space-y-4">
            {/* Media type */}
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-muted-foreground)] mb-1.5 block">
                Type
              </label>
              <div className="flex gap-1.5 flex-wrap">
                {TYPE_OPTIONS.map(({ value, label }) => (
                  <button
                    key={value}
                    onClick={() => onChange({ type: value as MediaType | undefined })}
                    className={cn(
                      "px-2.5 py-1 rounded-lg text-xs font-medium transition-colors",
                      filters.type === value || (!filters.type && value === "")
                        ? "bg-[hsl(217_91%_60%/0.15)] text-[hsl(217_91%_65%)] border border-[hsl(217_91%_60%/0.4)]"
                        : "bg-[var(--color-muted)] text-[var(--color-muted-foreground)] border border-transparent hover:border-[var(--color-border)]"
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {/* Sort */}
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-muted-foreground)] mb-1.5 block">
                Sort
              </label>
              <div className="flex gap-1.5 flex-wrap">
                {SORT_OPTIONS.map(({ value, label }) => (
                  <button
                    key={value}
                    onClick={() => onChange({ sort: value })}
                    className={cn(
                      "px-2.5 py-1 rounded-lg text-xs font-medium transition-colors",
                      filters.sort === value
                        ? "bg-[hsl(217_91%_60%/0.15)] text-[hsl(217_91%_65%)] border border-[hsl(217_91%_60%/0.4)]"
                        : "bg-[var(--color-muted)] text-[var(--color-muted-foreground)] border border-transparent hover:border-[var(--color-border)]"
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {/* Date range */}
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-muted-foreground)] mb-1.5 block">
                Indexed after
              </label>
              <input
                type="date"
                value={filters.date_from ?? ""}
                onChange={(e) => onChange({ date_from: e.target.value || undefined })}
                className="w-full h-8 px-2.5 text-xs rounded-lg bg-[var(--color-muted)] border border-[var(--color-border)] text-[var(--color-foreground)] focus:outline-none focus:border-[hsl(217_91%_60%)]"
              />
            </div>

            {/* Clear */}
            {active && (
              <button
                onClick={() => { onChange({ type: undefined, sort: undefined, date_from: undefined, date_to: undefined }); setOpen(false); }}
                className="flex items-center gap-1.5 text-xs text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] transition-colors"
              >
                <X className="w-3 h-3" /> Clear filters
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
