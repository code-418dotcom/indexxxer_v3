"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listWebhooks,
  createWebhook,
  deleteWebhook,
  testWebhook,
  listDeliveries,
} from "@/lib/api/webhooks";
import type { Webhook, WebhookDelivery } from "@/types/api";

const AVAILABLE_EVENTS = [
  "scan.started",
  "scan.completed",
  "scan.failed",
  "media.indexed",
  "media.deleted",
  "tag.created",
];

export default function WebhooksPage() {
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", url: "", events: [] as string[], secret: "" });

  const { data: webhooks = [], isLoading } = useQuery({
    queryKey: ["webhooks"],
    queryFn: listWebhooks,
  });

  const { data: deliveries = [] } = useQuery({
    queryKey: ["deliveries", expandedId],
    queryFn: () => listDeliveries(expandedId!),
    enabled: !!expandedId,
  });

  const create = useMutation({
    mutationFn: () =>
      createWebhook({
        name: form.name,
        url: form.url,
        events: form.events,
        secret: form.secret || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["webhooks"] });
      setShowCreate(false);
      setForm({ name: "", url: "", events: [], secret: "" });
    },
  });

  const remove = useMutation({
    mutationFn: deleteWebhook,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["webhooks"] }),
  });

  const test = useMutation({
    mutationFn: testWebhook,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["deliveries", expandedId] }),
  });

  const toggleEvent = (event: string) => {
    setForm((f) => ({
      ...f,
      events: f.events.includes(event)
        ? f.events.filter((e) => e !== event)
        : [...f.events, event],
    }));
  };

  if (isLoading) return <div className="p-8 text-neutral-400">Loading…</div>;

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Webhooks</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="bg-blue-600 hover:bg-blue-500 text-white text-sm px-4 py-2 rounded-lg"
        >
          Add Webhook
        </button>
      </div>

      {showCreate && (
        <div className="bg-neutral-800 rounded-xl p-6 mb-6 space-y-4">
          <h2 className="text-white font-semibold">New Webhook</h2>
          <input
            placeholder="Name"
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            className="w-full bg-neutral-700 text-white rounded-lg px-3 py-2 text-sm"
          />
          <input
            placeholder="URL"
            value={form.url}
            onChange={(e) => setForm((f) => ({ ...f, url: e.target.value }))}
            className="w-full bg-neutral-700 text-white rounded-lg px-3 py-2 text-sm"
          />
          <input
            placeholder="Secret (optional)"
            value={form.secret}
            onChange={(e) => setForm((f) => ({ ...f, secret: e.target.value }))}
            className="w-full bg-neutral-700 text-white rounded-lg px-3 py-2 text-sm"
          />
          <div>
            <p className="text-neutral-400 text-sm mb-2">Events</p>
            <div className="flex flex-wrap gap-2">
              {AVAILABLE_EVENTS.map((ev) => (
                <button
                  key={ev}
                  onClick={() => toggleEvent(ev)}
                  className={`text-xs px-2 py-1 rounded ${
                    form.events.includes(ev)
                      ? "bg-blue-600 text-white"
                      : "bg-neutral-700 text-neutral-300"
                  }`}
                >
                  {ev}
                </button>
              ))}
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => create.mutate()}
              disabled={!form.name || !form.url}
              className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg"
            >
              Create
            </button>
            <button
              onClick={() => setShowCreate(false)}
              className="text-neutral-400 hover:text-white text-sm px-4 py-2"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="space-y-4">
        {webhooks.map((wh: Webhook) => (
          <div key={wh.id} className="bg-neutral-800 rounded-xl p-4">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-white font-medium">{wh.name}</p>
                <p className="text-neutral-400 text-sm">{wh.url}</p>
                <div className="flex gap-1 mt-2">
                  {wh.events.map((ev) => (
                    <span key={ev} className="text-xs bg-neutral-700 text-neutral-300 px-2 py-0.5 rounded">
                      {ev}
                    </span>
                  ))}
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    test.mutate(wh.id);
                    setExpandedId(wh.id);
                  }}
                  className="text-xs text-blue-400 hover:text-blue-300"
                >
                  Test
                </button>
                <button
                  onClick={() => setExpandedId(expandedId === wh.id ? null : wh.id)}
                  className="text-xs text-neutral-400 hover:text-white"
                >
                  {expandedId === wh.id ? "Hide" : "Deliveries"}
                </button>
                <button
                  onClick={() => {
                    if (confirm(`Delete webhook ${wh.name}?`)) remove.mutate(wh.id);
                  }}
                  className="text-xs text-red-400 hover:text-red-300"
                >
                  Delete
                </button>
              </div>
            </div>

            {expandedId === wh.id && (
              <div className="mt-4 border-t border-neutral-700 pt-4">
                <p className="text-neutral-400 text-xs mb-2">Recent deliveries</p>
                {deliveries.length === 0 ? (
                  <p className="text-neutral-500 text-sm">No deliveries yet</p>
                ) : (
                  <div className="space-y-2">
                    {deliveries.map((d: WebhookDelivery) => (
                      <div key={d.id} className="flex items-center gap-3 text-sm">
                        <span
                          className={`w-2 h-2 rounded-full flex-shrink-0 ${
                            d.status === "delivered"
                              ? "bg-green-400"
                              : d.status === "failed"
                              ? "bg-red-400"
                              : "bg-yellow-400"
                          }`}
                        />
                        <span className="text-neutral-400">{d.event_type}</span>
                        <span className="text-neutral-500">{d.http_status ?? "—"}</span>
                        <span className="text-neutral-500 text-xs">
                          {new Date(d.created_at).toLocaleString()}
                        </span>
                        {d.error && (
                          <span className="text-red-400 text-xs truncate max-w-xs">{d.error}</span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
        {webhooks.length === 0 && (
          <p className="text-neutral-500 text-sm">No webhooks configured.</p>
        )}
      </div>
    </div>
  );
}
