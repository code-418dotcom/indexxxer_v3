"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";
import {
  Archive,
  BarChart2,
  Download,
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
  Star,
  Tag,
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
  { href: "/performers",label: "Performers", Icon: Star       },
  { href: "/tags",      label: "Tags",      Icon: Tag        },
  { href: "/galleries", label: "Galleries", Icon: Archive    },
  { href: "/pdfs",      label: "PDFs",      Icon: FileText   },
  { href: "/downloader",label: "Downloader", Icon: Download   },
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
  const { sidebarCollapsed, toggleSidebar, mobileMenuOpen, setMobileMenuOpen } = useUIStore();
  const currentType = pathname === "/library" ? searchParams.get("type") : null;
  const { data: user } = useCurrentUser();

  // Close mobile menu on route change
  useEffect(() => {
    setMobileMenuOpen(false);
  }, [pathname, setMobileMenuOpen]);

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  const sidebarContent = (
    <aside
      className={cn(
        "flex flex-col h-full bg-[hsl(222_47%_5%)] border-r border-[hsl(217_33%_13%)]",
        "transition-all duration-200 shrink-0",
        // Desktop: normal sidebar behavior
        "max-md:w-52",
        !mobileMenuOpen && "max-md:hidden",
        // Desktop widths
        "md:block",
        sidebarCollapsed ? "md:w-14" : "md:w-52"
      )}
    >
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-3 py-4 border-b border-[hsl(217_33%_13%)]">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-[hsl(217_91%_60%)] shrink-0">
          <Zap className="w-4 h-4 text-white" strokeWidth={2.5} />
        </div>
        {(!sidebarCollapsed || mobileMenuOpen) && (
          <span className="font-semibold text-sm tracking-wide text-white truncate md:hidden">
            indexxxer
          </span>
        )}
        {!sidebarCollapsed && (
          <span className="font-semibold text-sm tracking-wide text-white truncate hidden md:block">
            indexxxer
          </span>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 py-3 px-2 space-y-0.5 overflow-y-auto">
        {NAV.map(({ href, label, Icon }) => {
          const active = pathname.startsWith(href);
          const showLabel = mobileMenuOpen || !sidebarCollapsed;
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
                title={!showLabel ? label : undefined}
              >
                <Icon
                  className={cn(
                    "w-4 h-4 shrink-0",
                    active ? "text-[hsl(217_91%_65%)]" : "text-current"
                  )}
                />
                {/* Mobile: always show label. Desktop: respect collapsed state */}
                <span className={cn("truncate", !sidebarCollapsed ? "md:block" : "md:hidden")}>
                  {label}
                </span>
              </Link>

              {/* Images / Videos sub-filters under Library */}
              {href === "/library" && (
                <div className={cn(
                  "flex gap-1 mt-0.5",
                  // Mobile: always expanded
                  "max-md:pl-7 max-md:pr-1",
                  // Desktop: respect collapsed
                  sidebarCollapsed ? "md:flex-col md:px-1" : "md:pl-7 md:pr-1"
                )}>
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
                          "max-md:flex-1",
                          sidebarCollapsed ? "md:justify-center" : "md:flex-1",
                          subActive
                            ? "bg-[hsl(217_91%_60%/0.15)] text-[hsl(217_91%_70%)]"
                            : "text-[hsl(215_20%_45%)] hover:bg-[hsl(217_33%_13%)] hover:text-white"
                        )}
                        title={!showLabel ? subLabel : undefined}
                      >
                        <SubIcon className="w-3 h-3 shrink-0" />
                        <span className={cn("truncate", !sidebarCollapsed ? "md:block" : "md:hidden")}>
                          {subLabel}
                        </span>
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
          title={sidebarCollapsed && !mobileMenuOpen ? "Favourites" : undefined}
        >
          <Heart className="w-4 h-4 shrink-0" />
          <span className={cn("truncate", !sidebarCollapsed ? "md:block" : "md:hidden")}>
            Favourites
          </span>
        </Link>

        {/* Admin section */}
        {user?.role === "admin" && (
          <>
            {(!sidebarCollapsed || mobileMenuOpen) && (
              <p className={cn(
                "text-xs text-neutral-600 uppercase tracking-wider px-2 pt-4 pb-1",
                sidebarCollapsed ? "md:hidden" : ""
              )}>
                Admin
              </p>
            )}
            {ADMIN_NAV.map(({ href, label, Icon }) => {
              const active = pathname.startsWith(href);
              const showLabel = mobileMenuOpen || !sidebarCollapsed;
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
                  title={!showLabel ? label : undefined}
                >
                  <Icon className="w-4 h-4 shrink-0" />
                  <span className={cn("truncate", !sidebarCollapsed ? "md:block" : "md:hidden")}>
                    {label}
                  </span>
                </Link>
              );
            })}
          </>
        )}
      </nav>

      {/* User info + logout */}
      <div className="px-2 py-3 border-t border-[hsl(217_33%_13%)] space-y-1">
        {user && (!sidebarCollapsed || mobileMenuOpen) && (
          <div className={cn("px-2 py-1", sidebarCollapsed ? "md:hidden" : "")}>
            <p className="text-xs text-neutral-400 truncate">{user.email}</p>
            <p className="text-xs text-neutral-600">{user.role}</p>
          </div>
        )}
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 w-full rounded-lg px-2 py-2 text-sm text-[hsl(215_20%_45%)] hover:bg-[hsl(217_33%_13%)] hover:text-rose-400 transition-colors"
          title={sidebarCollapsed && !mobileMenuOpen ? "Logout" : undefined}
        >
          <LogOut className="w-4 h-4 shrink-0" />
          <span className={cn("truncate", !sidebarCollapsed ? "md:block" : "md:hidden")}>
            Logout
          </span>
        </button>

        {/* Collapse toggle — desktop only */}
        <button
          onClick={toggleSidebar}
          className="hidden md:flex items-center justify-center w-full h-8 rounded-lg text-[hsl(215_20%_45%)] hover:bg-[hsl(217_33%_13%)] hover:text-white transition-colors"
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

  return (
    <>
      {/* Mobile: overlay backdrop */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 md:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Mobile: slide-over sidebar */}
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-50 md:hidden transition-transform duration-200",
          mobileMenuOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {sidebarContent}
      </div>

      {/* Desktop: static sidebar */}
      <div className="hidden md:block">
        {sidebarContent}
      </div>
    </>
  );
}
