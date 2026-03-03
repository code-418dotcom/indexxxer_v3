import client from "./client";

export interface QueueStatus {
  depths: Record<string, number>;
  workers: { name: string; queues: string[] }[];
}

export async function getQueueStatus(): Promise<QueueStatus> {
  const { data } = await client.get<QueueStatus>("/workers/queues");
  return data;
}

export async function pauseQueue(queue: string): Promise<void> {
  await client.post(`/workers/queues/${queue}/pause`);
}

export async function resumeQueue(queue: string): Promise<void> {
  await client.post(`/workers/queues/${queue}/resume`);
}

export async function flushQueue(queue: string): Promise<{ count: number }> {
  const { data } = await client.delete<{ count: number }>(`/workers/queues/${queue}`);
  return data;
}
