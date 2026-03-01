"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  FolderOpen,
  LayoutGrid,
  PanelLeftClose,
  PanelLeftOpen,
  ScrollText,
  Settings,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/lib/store/uiStore";

const NAV = [
  { href: "/library",  label: "Library",  Icon: LayoutGrid },
  { href: "/sources",  label: "Sources",  Icon: FolderOpen  },
  { href: "/logs",     label: "Logs",     Icon: ScrollText  },
  { href: "/settings", label: "Settings", Icon: Settings    },
];

export function Sidebar() {
  const pathname = usePathname();
  const { sidebarCollapsed, toggleSidebar } = useUIStore();

  return (
    <aside
      className={cn(
        "flex flex-col h-full bg-[hsl(222_47%_5%)] border-r border-[hsl(217_33%_13%)]",
        "transition-all duration-200 shrink-0",
        sidebarCollapsed ? "w-14" : "w-52"
      )}
    >
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-3 py-4 border-b border-[hsl(217_33%_13%)]">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-[hsl(217_91%_60%)] shrink-0">
          <Zap className="w-4 h-4 text-white" strokeWidth={2.5} />
        </div>
        {!sidebarCollapsed && (
          <span className="font-semibold text-sm tracking-wide text-white truncate">
            indexxxer
          </span>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 py-3 px-2 space-y-0.5">
        {NAV.map(({ href, label, Icon }) => {
          const active = pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-2 py-2.5 text-sm font-medium",
                "transition-colors duration-150 group",
                active
                  ? "bg-[hsl(217_91%_60%/0.15)] text-[hsl(217_91%_70%)]"
                  : "text-[hsl(215_20%_55%)] hover:bg-[hsl(217_33%_13%)] hover:text-white"
              )}
              title={sidebarCollapsed ? label : undefined}
            >
              <Icon
                className={cn(
                  "w-4 h-4 shrink-0",
                  active ? "text-[hsl(217_91%_65%)]" : "text-current"
                )}
              />
              {!sidebarCollapsed && <span className="truncate">{label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <div className="px-2 py-3 border-t border-[hsl(217_33%_13%)]">
        <button
          onClick={toggleSidebar}
          className="flex items-center justify-center w-full h-8 rounded-lg text-[hsl(215_20%_45%)] hover:bg-[hsl(217_33%_13%)] hover:text-white transition-colors"
          title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {sidebarCollapsed ? (
            <PanelLeftOpen className="w-4 h-4" />
          ) : (
            <PanelLeftClose className="w-4 h-4" />
          )}
        </button>
      </div>
    </aside>
  );
}
