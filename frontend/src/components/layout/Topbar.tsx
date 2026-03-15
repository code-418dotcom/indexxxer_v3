"use client";

import { Menu, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/lib/store/uiStore";

interface TopbarProps {
  title: React.ReactNode;
  children?: React.ReactNode;
}

export function Topbar({ title, children }: TopbarProps) {
  const { resolvedTheme, setTheme } = useTheme();
  const { setMobileMenuOpen } = useUIStore();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  return (
    <header className="flex items-center gap-3 md:gap-4 px-3 md:px-5 h-14 border-b border-[var(--color-border)] bg-[var(--color-background)] shrink-0">
      {/* Mobile hamburger */}
      <button
        onClick={() => setMobileMenuOpen(true)}
        className="md:hidden flex items-center justify-center w-8 h-8 rounded-lg text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] hover:bg-[var(--color-muted)] transition-colors shrink-0"
        title="Open menu"
      >
        <Menu className="w-5 h-5" />
      </button>

      <h1 className="text-sm font-semibold text-[var(--color-foreground)] shrink-0">
        {title}
      </h1>

      {/* Slot for page-specific controls (e.g. search bar) */}
      <div className="flex-1 min-w-0">{children}</div>

      {/* Theme toggle — rendered only after mount to avoid SSR/client mismatch */}
      <button
        onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
        className={cn(
          "flex items-center justify-center w-8 h-8 rounded-lg",
          "text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)]",
          "hover:bg-[var(--color-muted)] transition-colors shrink-0"
        )}
        title="Toggle theme"
      >
        {mounted && (resolvedTheme === "dark" ? (
          <Sun className="w-4 h-4" />
        ) : (
          <Moon className="w-4 h-4" />
        ))}
      </button>
    </header>
  );
}
