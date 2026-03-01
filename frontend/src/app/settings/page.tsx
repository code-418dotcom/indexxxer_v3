"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getToken, setToken } from "@/lib/api/client";
import { Topbar } from "@/components/layout/Topbar";
import { cn } from "@/lib/utils";
import { CheckCircle2, Eye, EyeOff, Loader2, Save } from "lucide-react";
import client from "@/lib/api/client";
import type { HealthResponse } from "@/types/api";

export default function SettingsPage() {
  return (
    <div className="flex flex-col h-full">
      <Topbar title="Settings" />
      <div className="flex-1 overflow-y-auto px-6 py-6 max-w-2xl space-y-8">
        <ApiTokenSection />
        <ConnectionStatus />
      </div>
    </div>
  );
}

// ─── API token ────────────────────────────────────────────────────────────

function ApiTokenSection() {
  const [token, setLocalToken] = useState("");
  const [show, setShow] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setLocalToken(getToken());
  }, []);

  const save = () => {
    setToken(token.trim());
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <section>
      <h2 className="text-sm font-semibold text-[var(--color-foreground)] mb-1">
        API token
      </h2>
      <p className="text-xs text-[var(--color-muted-foreground)] mb-3">
        The static bearer token set as <code className="font-mono bg-[var(--color-muted)] px-1 rounded">API_TOKEN</code> in your backend <code className="font-mono bg-[var(--color-muted)] px-1 rounded">.env</code>.
        Stored in your browser&apos;s localStorage.
      </p>
      <div className="flex gap-2">
        <div className="relative flex-1">
          <input
            type={show ? "text" : "password"}
            value={token}
            onChange={(e) => setLocalToken(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && save()}
            placeholder="Paste your API token…"
            className={cn(
              "w-full h-9 px-3 pr-9 text-sm rounded-lg font-mono",
              "bg-[var(--color-muted)] border border-[var(--color-border)]",
              "text-[var(--color-foreground)] placeholder:text-[var(--color-muted-foreground)]",
              "focus:outline-none focus:border-[hsl(217_91%_60%)] focus:ring-1 focus:ring-[hsl(217_91%_60%/0.3)]",
              "transition-colors"
            )}
          />
          <button
            type="button"
            onClick={() => setShow(!show)}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] transition-colors"
          >
            {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
        <button
          onClick={save}
          className={cn(
            "flex items-center gap-1.5 px-3 h-9 text-sm rounded-lg font-medium transition-colors",
            saved
              ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
              : "bg-[hsl(217_91%_60%)] hover:bg-[hsl(217_91%_55%)] text-white"
          )}
        >
          {saved ? (
            <>
              <CheckCircle2 className="w-4 h-4" /> Saved
            </>
          ) : (
            <>
              <Save className="w-4 h-4" /> Save
            </>
          )}
        </button>
      </div>
    </section>
  );
}

// ─── Connection status ─────────────────────────────────────────────────────

function ConnectionStatus() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const { data } = await client.get<HealthResponse>("/health", {
        // health endpoint is unauthenticated — strip interceptor token for this call
        headers: { "X-API-Token": undefined },
      });
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
        Checks connectivity to the FastAPI backend at <code className="font-mono bg-[var(--color-muted)] px-1 rounded">/api/v1/health</code>.
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
