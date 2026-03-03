"use client";

import { Search, Sparkles, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

interface SearchBarProps {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  className?: string;
  inputRef?: React.RefObject<HTMLInputElement | null>;
}

/** Mirror of backend _should_use_semantic: ≥3 words or >30 chars → semantic. */
function isSemantic(q: string) {
  const s = q.trim();
  return s.length > 30 || s.split(/\s+/).length >= 3;
}

export function SearchBar({
  value,
  onChange,
  placeholder = "Search media…",
  className,
  inputRef,
}: SearchBarProps) {
  const [local, setLocal] = useState(value);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const internalRef = useRef<HTMLInputElement | null>(null);
  const ref = inputRef ?? internalRef;

  const showSemantic = local.length > 0 && isSemantic(local);

  // Debounce 300ms
  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => onChange(local), 300);
    return () => { if (timer.current) clearTimeout(timer.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [local]);

  // Sync if parent resets value externally
  useEffect(() => { setLocal(value); }, [value]);

  return (
    <div className={cn("relative flex items-center", className)}>
      <Search className="absolute left-3 w-4 h-4 text-[var(--color-muted-foreground)] pointer-events-none" />
      <input
        ref={ref}
        type="text"
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        placeholder={placeholder}
        className={cn(
          "w-full h-9 pl-9 text-sm rounded-lg",
          showSemantic ? "pr-24" : "pr-8",
          "bg-[var(--color-muted)] border border-[var(--color-border)]",
          "text-[var(--color-foreground)] placeholder:text-[var(--color-muted-foreground)]",
          "focus:outline-none focus:border-[hsl(217_91%_60%)] focus:ring-1 focus:ring-[hsl(217_91%_60%/0.3)]",
          "transition-colors"
        )}
      />
      {/* Semantic mode badge */}
      {showSemantic && (
        <span
          className="absolute right-7 flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-semibold uppercase tracking-wider bg-violet-500/20 text-violet-400 border border-violet-500/30 pointer-events-none"
          title="Semantic search active (CLIP)"
        >
          <Sparkles className="w-2.5 h-2.5" />
          AI
        </span>
      )}
      {local && (
        <button
          onClick={() => { setLocal(""); onChange(""); }}
          className="absolute right-2.5 text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] transition-colors"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}
