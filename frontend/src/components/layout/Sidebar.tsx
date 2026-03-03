"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  Archive,
  BarChart2,
  FileText,
  Film,
  FolderOpen,
  Heart,
  ImageIcon,
  LayoutGrid,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
  ScrollText,
  Settings,
  Users,
  Webhook,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/lib/store/uiStore";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { logout } from "@/lib/api/auth";

const NAV = [
  { href: "/library",   label: "Library",   Icon: LayoutGrid },
  { href: "/faces",     label: "Faces",     Icon: Users      },
  { href: "/galleries", label: "Galleries", Icon: Archive    },
  { href: "/pdfs",      label: "PDFs",      Icon: FileText   },
  { href: "/sources",   label: "Sources",   Icon: FolderOpen },
  { href: "/logs",      label: "Logs",      Icon: ScrollText },
  { href: "/settings",  label: "Settings",  Icon: Settings   },
];

const ADMIN_NAV = [
  { href: "/admin/users",     label: "Users",     Icon: Users     },
  { href: "/admin/webhooks",  label: "Webhooks",  Icon: Webhook   },
  { href: "/admin/analytics", label: "Analytics", Icon: BarChart2 },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { sidebarCollapsed, toggleSidebar } = useUIStore();
  const currentType = pathname === "/library" ? searchParams.get("type") : null;
  const { data: user } = useCurrentUser();

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

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
      <nav className="flex-1 py-3 px-2 space-y-0.5 overflow-y-auto">
        {NAV.map(({ href, label, Icon }) => {
          const active = pathname.startsWith(href);
          return (
            <div key={href}>
              <Link
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

              {/* Images / Videos sub-filters under Library */}
              {href === "/library" && (
                <div className={cn("flex gap-1 mt-0.5", sidebarCollapsed ? "flex-col px-1" : "pl-7 pr-1")}>
                  {[
                    { type: "image", label: "Images", Icon: ImageIcon },
                    { type: "video", label: "Videos", Icon: Film },
                  ].map(({ type, label: subLabel, Icon: SubIcon }) => {
                    const subActive = active && currentType === type;
                    return (
                      <Link
                        key={type}
                        href={`/library?type=${type}`}
                        className={cn(
                          "flex items-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-medium transition-colors duration-150",
                          sidebarCollapsed ? "justify-center" : "flex-1",
                          subActive
                            ? "bg-[hsl(217_91%_60%/0.15)] text-[hsl(217_91%_70%)]"
                            : "text-[hsl(215_20%_45%)] hover:bg-[hsl(217_33%_13%)] hover:text-white"
                        )}
                        title={sidebarCollapsed ? subLabel : undefined}
                      >
                        <SubIcon className="w-3 h-3 shrink-0" />
                        {!sidebarCollapsed && <span className="truncate">{subLabel}</span>}
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}

        {/* Favourites shortcut */}
        <Link
          href="/library?favourite=true"
          className={cn(
            "flex items-center gap-3 rounded-lg px-2 py-2.5 text-sm font-medium",
            "transition-colors duration-150",
            "text-[hsl(215_20%_55%)] hover:bg-[hsl(217_33%_13%)] hover:text-rose-400"
          )}
          title={sidebarCollapsed ? "Favourites" : undefined}
        >
          <Heart className="w-4 h-4 shrink-0" />
          {!sidebarCollapsed && <span className="truncate">Favourites</span>}
        </Link>

        {/* Admin section */}
        {user?.role === "admin" && (
          <>
            {!sidebarCollapsed && (
              <p className="text-xs text-neutral-600 uppercase tracking-wider px-2 pt-4 pb-1">
                Admin
              </p>
            )}
            {ADMIN_NAV.map(({ href, label, Icon }) => {
              const active = pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "flex items-center gap-3 rounded-lg px-2 py-2.5 text-sm font-medium",
                    "transition-colors duration-150",
                    active
                      ? "bg-purple-900/30 text-purple-300"
                      : "text-[hsl(215_20%_55%)] hover:bg-[hsl(217_33%_13%)] hover:text-white"
                  )}
                  title={sidebarCollapsed ? label : undefined}
                >
                  <Icon className="w-4 h-4 shrink-0" />
                  {!sidebarCollapsed && <span className="truncate">{label}</span>}
                </Link>
              );
            })}
          </>
        )}
      </nav>

      {/* User info + logout */}
      <div className="px-2 py-3 border-t border-[hsl(217_33%_13%)] space-y-1">
        {user && !sidebarCollapsed && (
          <div className="px-2 py-1">
            <p className="text-xs text-neutral-400 truncate">{user.email}</p>
            <p className="text-xs text-neutral-600">{user.role}</p>
          </div>
        )}
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 w-full rounded-lg px-2 py-2 text-sm text-[hsl(215_20%_45%)] hover:bg-[hsl(217_33%_13%)] hover:text-rose-400 transition-colors"
          title={sidebarCollapsed ? "Logout" : undefined}
        >
          <LogOut className="w-4 h-4 shrink-0" />
          {!sidebarCollapsed && <span>Logout</span>}
        </button>

        {/* Collapse toggle */}
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
