import type { MediaItem, PaginatedResponse, Tag, TagCreate, TagUpdate } from "@/types/api";
import client from "./client";

export async function listTags(params?: { category?: string; q?: string; page?: number; limit?: number }) {
  const { data } = await client.get<PaginatedResponse<Tag>>("/tags", { params });
  return data;
}

export async function createTag(payload: TagCreate) {
  const { data } = await client.post<Tag>("/tags", payload);
  return data;
}

export async function getTag(id: string) {
  const { data } = await client.get<Tag>(`/tags/${id}`);
  return data;
}

export async function updateTag(id: string, payload: TagUpdate) {
  const { data } = await client.put<Tag>(`/tags/${id}`, payload);
  return data;
}

export async function deleteTag(id: string) {
  await client.delete(`/tags/${id}`);
}

export async function getTagMedia(id: string, params?: { page?: number; limit?: number }) {
  const { data } = await client.get<PaginatedResponse<MediaItem>>(`/tags/${id}/media`, { params });
  return data;
}
