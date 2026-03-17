import client from "./client";

export interface TagItem {
  id: string;
  name: string;
  slug: string;
  category: string | null;
  color: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaginatedTags {
  items: TagItem[];
  total: number;
  page: number;
  pages: number;
  limit: number;
}

export async function listTags(params?: {
  page?: number;
  limit?: number;
  category?: string;
  q?: string;
}): Promise<PaginatedTags> {
  const { data } = await client.get("/tags", { params });
  return data;
}

export interface BackfillParams {
  media_type?: "image" | "video";
  performer_id?: string;
  category?: string;
  retag?: boolean;
}

export async function backfillAiTags(params?: BackfillParams): Promise<{ task_id: string; status: string }> {
  const { data } = await client.post("/tags/ai/backfill", null, { params });
  return data;
}

export async function pauseTagging(): Promise<{ status: string }> {
  const { data } = await client.post("/tags/ai/pause");
  return data;
}

export async function resumeTagging(): Promise<{ status: string }> {
  const { data } = await client.post("/tags/ai/resume");
  return data;
}

export async function stopTagging(): Promise<{ status: string; flushed: number }> {
  const { data } = await client.post("/tags/ai/stop");
  return data;
}

export async function deleteTag(id: string): Promise<void> {
  await client.delete(`/tags/${id}`);
}

export interface TagLogEntry {
  media_id: string;
  filename: string;
  status: string;
  tags_applied: number;
  detail: string;
  ts: string;
}

export interface TagProgress {
  total: number;
  tagged: number;
  pending: number;
  queue_depth: number;
  progress_pct: number;
  paused: boolean;
  log: TagLogEntry[];
}

export async function getTagProgress(): Promise<TagProgress> {
  const { data } = await client.get<TagProgress>("/tags/ai/progress");
  return data;
}
