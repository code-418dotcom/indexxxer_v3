import type { Webhook, WebhookCreate, WebhookDelivery } from "@/types/api";
import client from "./client";

export async function listWebhooks(): Promise<Webhook[]> {
  const { data } = await client.get<Webhook[]>("/webhooks");
  return data;
}

export async function createWebhook(payload: WebhookCreate): Promise<Webhook> {
  const { data } = await client.post<Webhook>("/webhooks", payload);
  return data;
}

export async function updateWebhook(id: string, payload: Partial<WebhookCreate>): Promise<Webhook> {
  const { data } = await client.put<Webhook>(`/webhooks/${id}`, payload);
  return data;
}

export async function deleteWebhook(id: string): Promise<void> {
  await client.delete(`/webhooks/${id}`);
}

export async function listDeliveries(webhookId: string): Promise<WebhookDelivery[]> {
  const { data } = await client.get<WebhookDelivery[]>(`/webhooks/${webhookId}/deliveries`);
  return data;
}

export async function testWebhook(webhookId: string): Promise<void> {
  await client.post(`/webhooks/${webhookId}/test`);
}
