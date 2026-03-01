import type { MediaItem, PaginatedResponse, SearchParams } from "@/types/api";
import client from "./client";

export async function search(params: SearchParams) {
  const { data } = await client.get<PaginatedResponse<MediaItem>>("/search", { params });
  return data;
}

export async function suggestions(q: string, limit = 8) {
  const { data } = await client.get<string[]>("/search/suggestions", {
    params: { q, limit },
  });
  return data;
}
