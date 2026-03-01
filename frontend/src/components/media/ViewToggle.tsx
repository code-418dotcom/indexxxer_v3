"use client";

import { LayoutGrid, LayoutList, Minus, Plus } from "lucide-react";
import { cn } from "@/lib/utils";
import { useUIStore, type ThumbnailSize, type ViewMode } from "@/lib/store/uiStore";

const SIZES: ThumbnailSize[] = ["sm", "md", "lg"];

export function ViewToggle() {
  const { viewMode, setViewMode, thumbnailSize, setThumbnailSize } = useUIStore();

  const cycleSize = (dir: 1 | -1) => {
    const idx = SIZES.indexOf(thumbnailSize);
    const next = SIZES[Math.max(0, Math.min(SIZES.length - 1, idx + dir))];
    setThumbnailSize(next);
  };

  return (
    <div className="flex items-center gap-2">
      {/* Size controls (grid only) */}
      {viewMode === "grid" && (
        <div className="flex items-center gap-1 rounded-lg border border-[var(--color-border)] p-0.5">
          <button
            onClick={() => cycleSize(-1)}
            disabled={thumbnailSize === "sm"}
            className="p-1 rounded hover:bg-[var(--color-muted)] disabled:opacity-30 transition-colors"
            title="Smaller thumbnails"
          >
            <Minus className="w-3.5 h-3.5" />
          </button>
          <span className="text-[11px] font-medium w-6 text-center text-[var(--color-muted-foreground)] uppercase">
            {thumbnailSize}
          </span>
          <button
            onClick={() => cycleSize(1)}
            disabled={thumbnailSize === "lg"}
            className="p-1 rounded hover:bg-[var(--color-muted)] disabled:opacity-30 transition-colors"
            title="Larger thumbnails"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Grid / List toggle */}
      <div className="flex rounded-lg border border-[var(--color-border)] p-0.5">
        {(["grid", "list"] as ViewMode[]).map((m) => (
          <button
            key={m}
            onClick={() => setViewMode(m)}
            className={cn(
              "p-1.5 rounded transition-colors",
              viewMode === m
                ? "bg-[hsl(217_91%_60%/0.15)] text-[hsl(217_91%_65%)]"
                : "text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]"
            )}
            title={m === "grid" ? "Grid view" : "List view"}
          >
            {m === "grid" ? (
              <LayoutGrid className="w-4 h-4" />
            ) : (
              <LayoutList className="w-4 h-4" />
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
