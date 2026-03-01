"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getToken } from "@/lib/api/client";
import type { JobEvent } from "@/types/api";

export interface UseJobStreamOptions {
  jobId: string | null;
  enabled?: boolean;
  onEvent?: (event: JobEvent) => void;
}

export function useJobStream({ jobId, enabled = true, onEvent }: UseJobStreamOptions) {
  const [events, setEvents] = useState<JobEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [done, setDone] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  const clear = useCallback(() => {
    setEvents([]);
    setConnected(false);
    setDone(false);
  }, []);

  useEffect(() => {
    if (!jobId || !enabled) return;

    const token = getToken();
    const url = `/api/v1/jobs/${jobId}/stream?token=${encodeURIComponent(token)}`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => setConnected(true);

    es.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data) as JobEvent;
        setEvents((prev) => [...prev, event]);
        onEvent?.(event);

        if (event.type === "stream.end" || event.type === "scan.complete") {
          setDone(true);
          es.close();
        }
      } catch {
        // ignore malformed events
      }
    };

    es.onerror = () => {
      setConnected(false);
      es.close();
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, enabled]);

  return { events, connected, done, clear };
}
