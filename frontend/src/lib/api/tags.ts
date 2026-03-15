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

export async function backfillAiTags(): Promise<{ task_id: string; status: string }> {
  const { data } = await client.post("/tags/ai/backfill");
  return data;
}

export async function deleteTag(id: string): Promise<void> {
  await client.delete(`/tags/${id}`);
}
