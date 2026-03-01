import type {
  BulkActionRequest,
  MediaItem,
  MediaItemPatch,
  PaginatedResponse,
  SearchParams,
} from "@/types/api";
import client from "./client";

export async function listMedia(params: SearchParams & { page?: number; limit?: number }) {
  const { data } = await client.get<PaginatedResponse<MediaItem>>("/media", { params });
  return data;
}

export async function getMedia(id: string) {
  const { data } = await client.get<MediaItem>(`/media/${id}`);
  return data;
}

export async function patchMedia(id: string, payload: MediaItemPatch) {
  const { data } = await client.patch<MediaItem>(`/media/${id}`, payload);
  return data;
}

export async function deleteMedia(id: string) {
  await client.delete(`/media/${id}`);
}

export async function bulkMedia(payload: BulkActionRequest) {
  const { data } = await client.post("/media/bulk", payload);
  return data;
}

export function thumbnailUrl(id: string) {
  return `/api/v1/media/${id}/thumbnail`;
}

export function streamUrl(id: string) {
  return `/api/v1/media/${id}/stream`;
}
