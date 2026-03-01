import type { PaginatedResponse, Tag, TagCreate } from "@/types/api";
import client from "./client";

export async function listTags(params?: { category?: string; q?: string; page?: number; limit?: number }) {
  const { data } = await client.get<PaginatedResponse<Tag>>("/tags", { params });
  return data;
}

export async function createTag(payload: TagCreate) {
  const { data } = await client.post<Tag>("/tags", payload);
  return data;
}

export async function deleteTag(id: string) {
  await client.delete(`/tags/${id}`);
}
