"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";

interface TopbarProps {
  title: string;
  children?: React.ReactNode;
}

export function Topbar({ title, children }: TopbarProps) {
  const { theme, setTheme } = useTheme();

  return (
    <header className="flex items-center gap-4 px-5 h-14 border-b border-[var(--color-border)] bg-[var(--color-background)] shrink-0">
      <h1 className="text-sm font-semibold text-[var(--color-foreground)] shrink-0">
        {title}
      </h1>

      {/* Slot for page-specific controls (e.g. search bar) */}
      <div className="flex-1 min-w-0">{children}</div>

      {/* Theme toggle */}
      <button
        onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        className={cn(
          "flex items-center justify-center w-8 h-8 rounded-lg",
          "text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]",
          "hover:bg-[var(--color-muted)] transition-colors shrink-0"
        )}
        title="Toggle theme"
      >
        {theme === "dark" ? (
          <Sun className="w-4 h-4" />
        ) : (
          <Moon className="w-4 h-4" />
        )}
      </button>
    </header>
  );
}
