"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Topbar } from "@/components/layout/Topbar";
import { cn } from "@/lib/utils";
import { ExternalLink, Loader2, Settings2, Shield, User } from "lucide-react";
import client from "@/lib/api/client";
import { getMe } from "@/lib/api/auth";
import type { HealthResponse } from "@/types/api";

export default function SettingsPage() {
  return (
    <div className="flex flex-col h-full">
      <Topbar title="Settings" />
      <div className="flex-1 overflow-y-auto px-6 py-6 max-w-2xl space-y-8">
        <AccountSection />
        <ConnectionStatus />
      </div>
    </div>
  );
}

// ─── Account / user info ───────────────────────────────────────────────────

function AccountSection() {
  const { data: user, isLoading } = useQuery({
    queryKey: ["me"],
    queryFn: getMe,
    retry: false,
  });

  return (
    <section>
      <h2 className="text-sm font-semibold text-[var(--color-foreground)] mb-3 flex items-center gap-1.5">
        <User className="w-4 h-4" /> Account
      </h2>

      {isLoading ? (
        <div className="flex items-center gap-2 text-[var(--color-muted-foreground)] text-sm">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading…
        </div>
      ) : user ? (
        <div className="rounded-xl bg-[var(--color-card)] border border-[var(--color-border)] divide-y divide-[var(--color-border)]">
          <Row label="Email" value={user.email} />
          <Row label="Username" value={user.username} />
          <Row
            label="Role"
            value={
              <span
                className={cn(
                  "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium",
                  user.role === "admin"
                    ? "bg-amber-500/15 text-amber-400"
                    : "bg-blue-500/15 text-blue-400"
                )}
              >
                {user.role === "admin" && <Shield className="w-3 h-3" />}
                {user.role}
              </span>
            }
          />
        </div>
      ) : (
        <p className="text-sm text-[var(--color-muted-foreground)]">
          Not signed in.{" "}
          <Link href="/login" className="text-blue-400 hover:underline">
            Sign in
          </Link>
        </p>
      )}

      {user?.role === "admin" && (
        <div className="mt-3">
          <Link
            href="/admin/analytics"
            className="inline-flex items-center gap-1.5 text-sm text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] transition-colors"
          >
            <Settings2 className="w-4 h-4" />
            Open Admin Dashboard
            <ExternalLink className="w-3 h-3" />
          </Link>
        </div>
      )}
    </section>
  );
}

function Row({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between px-4 py-3">
      <span className="text-xs text-[var(--color-muted-foreground)] uppercase tracking-wide">
        {label}
      </span>
      <span className="text-sm text-[var(--color-foreground)]">{value}</span>
    </div>
  );
}

// ─── Connection status ─────────────────────────────────────────────────────

function ConnectionStatus() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const { data } = await client.get<HealthResponse>("/health");
      return data;
    },
    refetchInterval: 30_000,
  });

  return (
    <section>
      <h2 className="text-sm font-semibold text-[var(--color-foreground)] mb-1">
        Backend connection
      </h2>
      <p className="text-xs text-[var(--color-muted-foreground)] mb-3">
        Checks connectivity to the FastAPI backend at{" "}
        <code className="font-mono bg-[var(--color-muted)] px-1 rounded">
          /api/v1/health
        </code>
        .
      </p>
      <div className="flex items-center gap-3 p-3 rounded-xl bg-[var(--color-card)] border border-[var(--color-border)]">
        {isLoading ? (
          <Loader2 className="w-4 h-4 animate-spin text-[var(--color-muted-foreground)]" />
        ) : isError ? (
          <span className="w-2.5 h-2.5 rounded-full bg-red-500 shrink-0" />
        ) : (
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 shrink-0 animate-pulse" />
        )}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-[var(--color-foreground)]">
            {isLoading
              ? "Checking…"
              : isError
              ? "Unreachable"
              : `Connected — indexxxer v${data?.version}`}
          </p>
          {isError && (
            <p className="text-xs text-[var(--color-muted-foreground)] mt-0.5">
              Cannot reach the backend. Make sure it is running.
            </p>
          )}
        </div>
        <button
          onClick={() => refetch()}
          className="text-xs text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] transition-colors"
        >
          Retry
        </button>
      </div>
    </section>
  );
}
